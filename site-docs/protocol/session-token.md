# Session Token

<div class="cr-hero" markdown>

## Cryptographic anchor for every window, call, and audit record

The CRP Session Token binds a whole session together. It prevents replay,
pins the active safety policy, and lets Gateway, Comply, Visualise, and the
audit sink verify that they are all talking about the same governed session.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## What It Is

A signed, structured token (JWS / COSE-compatible) carried in
`CRP-Session-Token` that includes:

<div class="cr-stats" markdown>
<div class="cr-stat"><span class="num">sid</span><span class="label">Session identifier</span></div>
<div class="cr-stat"><span class="num">iat</span><span class="label">Issued-at time</span></div>
<div class="cr-stat"><span class="num">exp</span><span class="label">Expiry</span></div>
<div class="cr-stat"><span class="num">cap</span><span class="label">Allowed features</span></div>
<div class="cr-stat"><span class="num">pol</span><span class="label">Safety policy hash</span></div>
</div>

- `aud` - intended audience (gateway, comply, audit sink)
- `kid` - signing key identifier

## Why It Exists

- **Continuation integrity** - Window N+1 cannot be forged or replayed without
  the session token.
- **Cross-service audit binding** - Gateway, Comply, and Visualise all
  verify the same token.
- **Policy pinning** - the active Safety Policy is hashed into the token, so
  policy substitution mid-session is detected.

## From the SDK

```python
import crp

client = crp.SDKClient()
session = client.session()

print(session.id)           # the session token's sid
print(session.status())     # live session status
print(session.fact_count)   # facts in warm store
print(session.window_count) # windows dispatched so far
```

[:octicons-arrow-right-24: SPEC-007 normative text](../spec/CRP-SPEC-007-session-token.md)
