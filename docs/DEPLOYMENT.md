# Deployment notes

This document describes the application's routing requirements, not a copy of private server configuration.

## Runtime

1. Create a dedicated unprivileged service user and a Python 3.11 virtual environment.
2. Install `requirements.txt`, configure a private `.env` and supply the paid materials separately.
3. Run `bot.py` from the project directory. Relative database paths require a stable working directory.
4. Use a process manager with restart-on-failure and exactly one polling process per Telegram token.
5. Back up the live SQLite database with SQLite's backup mechanism. Keep copies outside the public repository and test restoration into a separate environment.

## HTTPS reverse proxy

The aiohttp server listens on `127.0.0.1:8080`. Forward these paths to it, preserving their original URI:

- `/miniapp/` (including `/miniapp/images/`)
- `/crm/`
- `/api/`
- `/webhook`

For example, inside an HTTPS Nginx server block:

```nginx
location ~ ^/(miniapp/|crm/|api/|webhook$) {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The backend trusts `X-Real-IP` for webhook IP checks and CRM throttling. Overwrite that header at the trusted proxy; do not expose port 8080 publicly. If another proxy/CDN is present, configure trusted real-IP handling deliberately before using this example.

Set `MINIAPP_URL` to your HTTPS origin plus `/miniapp`. Configure Telegram's web-app entry for your test bot. CRM session cookies are `Secure`, so login requires HTTPS.

Configure YooKassa notifications for your HTTPS `/webhook` endpoint and the matching `WEBHOOK_SECRET` query parameter. Review the provider's current notification IP ranges before enabling live payments. Keep URLs containing the secret out of logs shared publicly. Verify payment ownership, duplicate notifications and recovery after interrupted delivery in a test shop before production use.

## Verification before launch

- A new test account can complete the quiz, open results, use the diary and access AI with the intended consent flow.
- Mini App API calls without valid Telegram data and CRM data calls without login return 401.
- CRM login, logout, notes and reminders work over HTTPS.
- Booking confirmation, conflicting reservations and cancellation are checked with test accounts.
- Test-shop payment status matches access; retries do not duplicate fulfilment and interrupted delivery can be recovered.
- Every promised PDF, audio and video is delivered and opens correctly.
- Branding, prices, contact details, policy and offer links match the deployed service.
- Backups, restoration, service restart and monitoring are verified.

The current source has known fulfilment limitations listed in the root README. Resolve them before treating this checklist as passed.
