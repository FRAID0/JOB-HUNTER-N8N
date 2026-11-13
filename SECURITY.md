# Security workflow

Before using Git in this repository:

```powershell
git config core.hooksPath .githooks
```

The pre-commit hook blocks common credentials and local runtime files. It is a
guardrail, not a replacement for rotating a credential that was already pushed.

Required local-only values:

- `.env`
- `profil.json`
- `n8n_workflow_job_hunter.json`
- `client_secret_*.json`
- `browser_profile/`
- PDF and screenshot files under `documents/`

For the status webhook, create an n8n `Header Auth` credential with header name
`X-Webhook-Token`. Its value must match `N8N_WEBHOOK_TOKEN` in the local `.env`.
Keep the n8n UI and worker bound to localhost unless a private, authenticated
network is explicitly required.

Password autofill is opt-in. Add exact hostnames to `password_domains` in the
local `profil.json` before using its existing `personal_info.default_password`.
Alternatively, use a local-only top-level `site_passwords` mapping keyed by
exact hostname. An empty allowlist means that no password is ever filled.