"""Debug: test the expansion regex with actual task text."""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

TASK = """REQUIRED SECTIONS (all 30 must be present):
1. Input Validation — describe techniques, give 2 code examples in Python
2. Authentication — multi-factor auth, OAuth2 flows, session management
3. Authorization — RBAC, ABAC, principle of least privilege with examples
4. Cryptography — symmetric vs asymmetric, hashing algorithms, key management
5. Error Handling — secure logging, never expose stack traces, structured errors
6. Data Protection — encryption at rest, in transit, data classification levels
7. API Security — rate limiting, input sanitization, CORS configuration
8. Dependency Management — supply chain attacks, SCA tools, SBOM generation
9. Security Testing — SAST, DAST, penetration testing, fuzzing strategies
10. Incident Response — detection, containment, eradication, recovery phases"""

# Test current regex
items = []
for m in re.finditer(
    r"(?:^|\n)\s*(\d{1,3})[.)]\s+(.+?)(?=\n\s*\d{1,3}[.)]\s|\n\n|\Z)",
    TASK,
    re.DOTALL,
):
    num = int(m.group(1))
    title = m.group(2).split("\n")[0].strip()
    items.append((num, title))
    
print(f"Found {len(items)} items:")
for num, title in items:
    section_name = title.split(" — ")[0].split(" - ")[0].strip()
    print(f"  {num}. {section_name}")

# Test enumerated_items regex (current - fails on "30 numbered sections")
text1 = "EXACTLY 30 numbered sections"
text2 = "EXACTLY 30 sections"
text3 = "all 30 must be present"

r1 = r"\b(\d+)\s*(?:items?|points?|steps?|sections?|parts?)\b"
r2 = r"\b(\d+)\s+(?:\w+\s+){0,2}(?:items?|points?|steps?|sections?|parts?)\b"

print(f"\nCurrent regex '{r1}':")
print(f"  '30 numbered sections' match: {bool(re.search(r1, text1, re.I))}")
print(f"  '30 sections' match: {bool(re.search(r1, text2, re.I))}")
print(f"  'all 30 must' match: {bool(re.search(r1, text3, re.I))}")

print(f"\nFixed regex '{r2}':")
print(f"  '30 numbered sections' match: {bool(re.search(r2, text1, re.I))}")
print(f"  '30 sections' match: {bool(re.search(r2, text2, re.I))}")
print(f"  'all 30 must' match: {bool(re.search(r2, text3, re.I))}")

# Verify fixed regex captures the right number
m = re.search(r2, text1, re.I)
if m:
    print(f"  Captured number: {m.group(1)}")
