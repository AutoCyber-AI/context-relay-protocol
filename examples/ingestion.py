#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Ingestion — feed external data without using an LLM call.

ingest() extracts facts from raw text using the graduated extraction
pipeline (stages 1-5, no LLM). Ingested facts appear in subsequent
dispatch() envelopes automatically.
"""

import crp

client = crp.Client()

# Ingest a knowledge base article (no LLM call — pure extraction)
article = """
Transport Layer Security (TLS) 1.3 reduces handshake latency from two
round trips (TLS 1.2) to one, using ephemeral Diffie-Hellman key exchange.
The cipher suite is simplified: only AEAD ciphers (AES-256-GCM,
ChaCha20-Poly1305) are supported. RSA key transport is removed entirely.
Zero-RTT resumption is supported but carries replay risk. The handshake
is encrypted after the ServerHello, protecting certificate exchange from
passive eavesdroppers. Session tickets replace session IDs for resumption.
"""

facts_count = client.ingest(article, label="tls13-overview")
print(f"Ingested {facts_count} facts from article")

# Now dispatch — CRP automatically packs the ingested TLS facts
# into the envelope when they're relevant to the task
output, report = client.dispatch(
    system_prompt="You are a security expert.",
    task_input="What are the key security improvements in TLS 1.3 over 1.2?",
)

print(f"\nQuality: {report.quality_tier}")
print(f"Envelope saturation: {report.envelope_saturation:.0%}")
print(f"\n{output}")

client.close()
