---
seo_title: Setting Up CRP MCP Checkpoint Connectors
description: Step-by-step setup for Slack, Gmail, Firebase Cloud Messaging, PagerDuty, email, and SMS checkpoint connectors in the CRP MCP server.
---

# Setting Up CRP MCP Checkpoint Connectors

This guide walks through enabling each checkpoint review channel for the CRP MCP server. You only need to configure the connectors your team actually uses.

## What connectors do

When a checkpoint fires, the MCP server can notify one or more review channels. Each connector is a small adapter that turns the checkpoint record into a message the channel understands (Slack webhook, Gmail email, FCM push, PagerDuty incident, etc.).

The first human resolution wins — if someone approves via Slack, the email and Comply UI updates are ignored.

---

## Quick start checklist

1. Decide which channels you need.
2. Enable them by setting `CRP_MCP_CHECKPOINT_CONNECTORS`.
3. Set the environment variables for each chosen connector.
4. Trigger a test checkpoint.
5. Verify the message arrived and that approval/rejection updates the checkpoint status.

---

## Enable connectors

Set the list of active connectors in your env:

```bash
CRP_MCP_CHECKPOINT_CONNECTORS=console,slack,gmail
```

Order does not matter. Available names:

- `console` — local log output (always available, useful for dev)
- `comply` — forwards to the CRP Comply backend when hosted
- `slack` — Slack Incoming Webhook
- `gmail` — Gmail App-Password SMTP
- `email` — generic SMTP
- `fcm` — Firebase Cloud Messaging push notifications
- `pagerduty` — PagerDuty Events API v2 incident
- `sms` — Twilio SMS
- `webhook` — generic HTTP POST webhook

---

## Slack

### What you get

A message card in a Slack channel with checkpoint details and a link to the review page.

### What you need

- A Slack workspace where you can add integrations.
- Incoming Webhook URL.

### Steps

1. Go to `https://api.slack.com/messaging/webhooks`.
2. Click **Create your Slack app** → **From scratch**.
3. Choose **Incoming Webhooks** and toggle it **On**.
4. Click **Add New Webhook to Workspace** and pick the channel.
5. Copy the Webhook URL (looks like `https://hooks.slack.com/services/T.../B.../...`).

### Env vars

```bash
SLACK_WEBHOOK_URL=<YOUR_SLACK_WEBHOOK_URL>
```

### Test

Run the server with the Slack env set and call:

```text
Use crp_safety_checkpoint with trigger="SLACK_TEST", message="Test Slack checkpoint", confirm=true.
```

Check the channel for the message.

---

## Gmail

### What you get

Transactional emails to one or more recipients when a checkpoint fires.

### What you need

- A Gmail or Google Workspace account.
- 2-Step Verification enabled.
- An App Password (not your regular password).

### Steps

1. Enable 2-Step Verification at `https://myaccount.google.com/signinoptions/two-step-verification`.
2. Go to `https://myaccount.google.com/apppasswords`.
3. Select **Mail** → **Other (custom name)** → type `CRP MCP`.
4. Copy the 16-character App Password (e.g. `abcd efgh ijkl mnop`).

### Env vars

```bash
GMAIL_USER=alerts@crprotocol.io
GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
GMAIL_TO=team@crprotocol.io,ops@crprotocol.io
```

### Test

Call `crp_safety_checkpoint` with `confirm=true` and check the recipient inboxes.

---

## Firebase Cloud Messaging (FCM)

### What you get

Push notifications to registered Android / iOS / web devices.

### What you need

- A Firebase project.
- Service-account JSON.
- At least one device registration token.

### Steps

1. Create a Firebase project at `https://console.firebase.google.com`.
2. Go to Project Settings → Service Accounts.
3. Click **Generate new private key** and download the JSON.
4. Get device registration tokens from your client app (see Firebase docs for `getToken()`).

### Env vars

Paste the entire service-account JSON on one line:

```bash
FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"...","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}'
FIREBASE_PROJECT_ID=your-project-id
FCM_DEVICE_TOKENS=token1,token2,token3
```

Keep the JSON minified or use single quotes around the whole value.

### Test

Call `crp_safety_checkpoint` and watch for the push on the registered device.

---

## PagerDuty

### What you get

A PagerDuty incident for critical checkpoints, visible to on-call engineers.

### What you need

- PagerDuty account.
- Integration / routing key from a PagerDuty Events API v2 integration.

### Steps

1. In PagerDuty, go to **Services** → select or create a service.
2. Go to **Integrations** → **Add Integration**.
3. Choose **Events API v2**.
4. Copy the **Integration Key** (also called routing key).

### Env vars

```bash
PAGERDUTY_ROUTING_KEY=your-32-char-routing-key
```

Add `pagerduty` to `CRP_MCP_CHECKPOINT_CONNECTORS`.

### Test

Call `crp_safety_checkpoint` with a high-risk trigger and verify the incident in PagerDuty.

---

## Generic SMTP email

Use this if you do not want to use Gmail.

### Env vars

```bash
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=alerts@example.com
EMAIL_SMTP_PASSWORD=your-smtp-password
EMAIL_FROM=alerts@example.com
EMAIL_TO=team@example.com,ops@example.com
```

Add `email` to `CRP_MCP_CHECKPOINT_CONNECTORS`.

---

## Twilio SMS

### What you need

- Twilio account SID, auth token, and a Twilio phone number.
- Destination phone numbers.

### Env vars

```bash
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1234567890
SMS_TO=+61400000000,+61400000001
```

Add `sms` to `CRP_MCP_CHECKPOINT_CONNECTORS`.

---

## Generic webhook

Use this to POST checkpoint payloads to any custom endpoint.

### Env vars

```bash
CRP_MCP_CHECKPOINT_WEBHOOK_URL=https://your-service.com/crp-checkpoint
```

Add `webhook` to `CRP_MCP_CHECKPOINT_CONNECTORS`.

The POST body is a JSON checkpoint record.

---

## Recommended free stack

For most teams starting out, configure these three free channels:

```bash
CRP_MCP_CHECKPOINT_CONNECTORS=console,slack,gmail
SLACK_WEBHOOK_URL=<YOUR_SLACK_WEBHOOK_URL>
GMAIL_USER=alerts@crprotocol.io
GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
GMAIL_TO=team@crprotocol.io
```

This gives you:

- `console` for local dev visibility.
- `slack` for team chat alerts.
- `gmail` for user/operator email notifications.

---

## Escalation policy

After you have connectors working, add escalation rules:

```bash
CRP_MCP_CHECKPOINT_ESCALATION=[
  {"after_seconds":900,"channels":["slack"]},
  {"after_seconds":3600,"on_timeout":"reject"}
]
```

This re-notifies Slack after 15 minutes and auto-rejects after 1 hour.

---

## Routing rules

Route different risks to different channels:

```bash
CRP_MCP_CHECKPOINT_ROUTES=[
  {"condition":"risk >= HIGH","connector":"slack","route_to":"#safety"},
  {"condition":"tool_call == 'deploy_endpoint'","connector":"pagerduty"}
]
```

Conditions use the policy compiler in `crp_mcp/checkpoint_policy.py`.

---

## What to send me after setup

Do not paste secrets in chat. After you configure the connectors, tell me:

1. Which connectors you enabled.
2. Whether the test checkpoint reached each channel.
3. If any connector failed, share the error message (with secrets redacted).

I will then verify the configuration and update the production checklist.
