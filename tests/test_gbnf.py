# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Known-answer tests for the JSON Schema → GBNF compiler (CRP-SPEC-054 §4)."""

from __future__ import annotations

import pytest

from crp.gateway.gbnf import GBNFSchemaError, compile_gbnf

WS = "ws ::= [ \\t\\n]*"
STRING = 'string ::= "\\"" ([^"\\\\] | "\\\\" .)* "\\""'
INTEGER = 'integer ::= "-"? [0-9]+'
NUMBER = 'number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?'
BOOLEAN = 'boolean ::= "true" | "false"'


class TestKnownAnswers:
    def test_flat_object(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            f"{STRING}\n"
            f"{INTEGER}\n"
            'root ::= "{" ws "\\"name\\"" ws ":" ws string "," ws '
            '"\\"age\\"" ws ":" ws integer "}" ws\n'
        )

    def test_optional_fields_wrapped(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            f"{STRING}\n"
            f"{INTEGER}\n"
            'root ::= "{" ws "\\"name\\"" ws ":" ws string '
            '("," ws "\\"age\\"" ws ":" ws integer)? "}" ws\n'
        )

    def test_all_optional_nested_chain(self) -> None:
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "boolean"}},
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            f"{STRING}\n"
            f"{BOOLEAN}\n"
            'root ::= "{" ws ("\\"a\\"" ws ":" ws string '
            '("," ws "\\"b\\"" ws ":" ws boolean)?)? "}" ws\n'
        )

    def test_enum_parenthesised_alternation(self) -> None:
        schema = {
            "type": "object",
            "properties": {"level": {"enum": ["low", "high"]}},
            "required": ["level"],
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            'root ::= "{" ws "\\"level\\"" ws ":" ws '
            '("\\"low\\"" | "\\"high\\"") "}" ws\n'
        )

    def test_nested_object(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                }
            },
            "required": ["address"],
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            f"{STRING}\n"
            'root-address ::= "{" ws "\\"city\\"" ws ":" ws string "}" ws\n'
            'root ::= "{" ws "\\"address\\"" ws ":" ws root-address "}" ws\n'
        )

    def test_array_of_strings(self) -> None:
        schema = {
            "type": "object",
            "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
            "required": ["tags"],
        }
        assert compile_gbnf(schema) == (
            f"{WS}\n"
            f"{STRING}\n"
            'root-tags ::= "[" ws (string ("," ws string)*)? "]" ws\n'
            'root ::= "{" ws "\\"tags\\"" ws ":" ws root-tags "}" ws\n'
        )

    def test_number_and_boolean_primitives(self) -> None:
        schema = {
            "type": "object",
            "properties": {"score": {"type": "number"}, "ok": {"type": "boolean"}},
            "required": ["score", "ok"],
        }
        grammar = compile_gbnf(schema)
        assert NUMBER in grammar
        assert BOOLEAN in grammar
        assert '"\\"score\\"" ws ":" ws number' in grammar
        assert '"\\"ok\\"" ws ":" ws boolean' in grammar


class TestSchemaErrors:
    def test_root_must_be_object(self) -> None:
        with pytest.raises(GBNFSchemaError, match="root: expected type 'object'"):
            compile_gbnf({"type": "array", "items": {"type": "string"}})

    def test_non_dict_schema(self) -> None:
        with pytest.raises(GBNFSchemaError, match="schema must be an object"):
            compile_gbnf(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_unsupported_keyword_anyof(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
        }
        with pytest.raises(GBNFSchemaError, match="unsupported keyword 'anyOf'"):
            compile_gbnf(schema)

    def test_unsupported_ref(self) -> None:
        schema = {"type": "object", "properties": {"x": {"$ref": "#/definitions/y"}}}
        with pytest.raises(GBNFSchemaError, match="unsupported keyword '\\$ref'"):
            compile_gbnf(schema)

    def test_array_of_objects_rejected(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"y": {"type": "string"}}},
                }
            },
        }
        with pytest.raises(GBNFSchemaError, match="only arrays of scalars"):
            compile_gbnf(schema)

    def test_missing_type_rejected(self) -> None:
        schema = {"type": "object", "properties": {"x": {}}}
        with pytest.raises(GBNFSchemaError, match="unsupported or missing type"):
            compile_gbnf(schema)

    def test_required_key_not_in_properties(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["nope"],
        }
        with pytest.raises(GBNFSchemaError, match="required keys not in properties"):
            compile_gbnf(schema)

    def test_empty_properties_rejected(self) -> None:
        with pytest.raises(GBNFSchemaError, match="non-empty 'properties'"):
            compile_gbnf({"type": "object", "properties": {}})
