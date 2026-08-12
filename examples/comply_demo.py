#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Comply — AI Governance compliance example.

Demonstrates:
  1. Risk assessment (EU AI Act Art. 6)
  2. Compliance status report (Art. 9-17 + ISO 42001)
  3. DPIA generation (GDPR Art. 35)
  4. Transparency declaration (Art. 13)
  5. Full conformity evidence pack (for regulators)

No LLM required — all governance features work offline.

Run:
  python examples/comply_demo.py
  python examples/comply_demo.py --category healthcare
  python examples/comply_demo.py --output-dir ./compliance-reports/
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure CRP is importable from the repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isfile(os.path.join(_REPO_ROOT, "pyproject.toml")):
    sys.path.insert(0, _REPO_ROOT)

from crp.products.comply import CRPComply  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="CRP Comply — AI Governance Demo")
    parser.add_argument("--category", default="context_management",
                        help="AI system category (healthcare, financial, employment, etc.)")
    parser.add_argument("--system-name", default="CRP-powered AI System",
                        help="Name of your AI system")
    parser.add_argument("--output-dir", default=None,
                        help="Save reports to this directory")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of Markdown")
    args = parser.parse_args()

    comply = CRPComply()

    print()
    print("=" * 60)
    print("  CRP Comply — AI Governance & EU AI Act Compliance")
    print("=" * 60)

    # ── 1. Risk Assessment ──────────────────────────────────────
    print("\n━━━ 1. Risk Assessment (EU AI Act Art. 6) ━━━\n")
    assessment = comply.assess_risk(
        category=args.category,
        processes_personal_data=True,
        makes_automated_decisions=args.category in ("healthcare", "financial", "employment"),
        affects_fundamental_rights=args.category in ("healthcare", "employment", "law_enforcement"),
        safety_critical=args.category == "critical_infrastructure",
    )
    risk_icons = {"minimal": "🟢", "limited": "🟡", "high": "🔴", "unacceptable": "⛔"}
    print(f"  Category: {assessment.system_category.value}")
    print(f"  Risk Level: {risk_icons.get(assessment.risk_level.value, '❓')} {assessment.risk_level.value.upper()}")
    print(f"  Mitigations: {len(assessment.mitigations)} CRP-native controls")
    print(f"  Residual Risks: {len(assessment.residual_risks)}")

    # ── 2. Compliance Report ────────────────────────────────────
    print("\n━━━ 2. Compliance Report (Art. 9-17 + ISO 42001) ━━━\n")
    report = comply.compliance_report(risk_assessment=assessment)
    summary = report["summary"]
    print(f"  Total Controls: {summary['total_controls']}")
    print(f"  Implemented: {summary['implemented']}")
    print(f"  Compliance Score: {summary['compliance_score']}%")
    for fw_name, fw in report["frameworks"].items():
        nice = {"eu_ai_act": "EU AI Act", "iso_42001": "ISO 42001"}.get(fw_name, fw_name)
        print(f"    {nice}: {fw['implemented']}/{fw['total_controls']} ({fw['compliance_pct']}%)")

    # ── 3. DPIA ─────────────────────────────────────────────────
    print("\n━━━ 3. DPIA (GDPR Art. 35) ━━━\n")
    dpia = comply.generate_dpia(
        system_name=args.system_name,
        data_subjects="end users and data subjects",
        category=args.category,
    )
    print(f"  DPIA ID: {dpia.dpia_id}")
    print(f"  Consultation Required: {'Yes' if dpia.consultation_required else 'No'}")
    print(f"  Risk Categories: {len(dpia.risk_assessment)}")
    print(f"  Mitigation Measures: {len(dpia.mitigation_measures)}")

    # ── 4. Transparency Declaration ─────────────────────────────
    print("\n━━━ 4. Transparency Declaration (Art. 13) ━━━\n")
    td = comply.transparency_declaration()
    print(f"  System: {td['system_name']}")
    print(f"  Provider: {td['provider']}")
    print(f"  Risk Level: {td['risk_level']}")

    # ── 5. Conformity Evidence Pack ─────────────────────────────
    print("\n━━━ 5. Conformity Evidence Pack ━━━\n")
    pack = comply.conformity_evidence_pack(
        system_name=args.system_name,
        category=args.category,
    )
    print(f"  Artifacts included: {len(pack['artifacts'])}")
    for name in pack["artifacts"]:
        print(f"    ✅ {name}")

    # ── Save to files if requested ──────────────────────────────
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        files = {
            "compliance_report.md": comply.compliance_report_markdown(risk_assessment=assessment),
            "dpia.md": dpia.to_markdown(),
            "risk_assessment.json": json.dumps(assessment.to_dict(), indent=2),
            "transparency_declaration.json": json.dumps(td, indent=2, default=str),
            "technical_documentation.json": json.dumps(
                comply.technical_documentation(risk_assessment=assessment), indent=2, default=str
            ),
            "evidence_pack.json": json.dumps(pack, indent=2, default=str),
        }
        for filename, content in files.items():
            path = os.path.join(args.output_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"    📄 {path}")
        print(f"\n  All reports saved to {args.output_dir}/")

    print()
    print("=" * 60)
    print("  EU AI Act enforcement: August 2, 2026")
    print("  Your CRP deployment is governance-ready.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
