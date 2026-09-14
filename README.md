# MindType — Telegram Bot, Mini App & CRM

A psychology practice product connecting a five-question self-reflection quiz, a Claude-powered companion, a personal journal, paid guides and consultation booking. A private CRM gives the practitioner a workspace for client follow-up.

Built by **Eva Levina** with Python, aiogram, aiohttp and vanilla JavaScript.

[Open the bot](https://t.me/chto_so_mnoy_test_bot) · [Landing page](https://levinaeva.com) · [Project case study](https://evalevina.dev/work-anxiety-bot.html)

## Features

- Five-question quiz with four profiles, individual results and a suggested exercise.
- Claude AI companion, emotion journal and thought records.
- Follow-up sequences, reminders, referrals and review collection.
- YooKassa payment creation, status checks and material delivery.
- Telegram Mini App: results, personal account, journal history and booking.
- Practitioner CRM: client stages, cards, conversation history, notes and reminders.
- SQLite storage for application data and persistent conversation state.

The quiz is a self-reflection tool, not a clinical diagnosis. The companion is not a substitute for professional or emergency support.

## Architecture

```text
Telegram chat ── aiogram handlers ────────┐
                                        ├── SQLite
Telegram Mini App ──┐                   │
                    ├── HTTPS / Nginx ── aiohttp API
Practitioner CRM ───┘                   │
                                       ├── Claude API
                                       └── YooKassa
```

The bot, API and background reminder workers run in one Python process. The API binds to `127.0.0.1:8080`; an HTTPS reverse proxy serves public requests. Mini App requests use Telegram `initData` verification, while CRM uses password authentication and a signed session cookie.

## Repository layout

| Path | Purpose |
| --- | --- |
| `bot.py` | Polling, routers and background workers |
| `handlers/` | Quiz, AI, journal, booking and administration |
| `database.py`, `fsm_storage.py` | SQLite data and conversation state |
| `web_server.py` | Mini App / CRM API and payment notifications |
| `miniapp/`, `crm/` | Browser interfaces, without a build step |
| `images/`, `fonts/` | Interface assets and chart fonts |
| `materials/` | Private-content setup instructions |
| `docs/DEPLOYMENT.md` | Deployment requirements and verification checklist |

The marketing website and portfolio website are separate projects. Their source is not included here.

## Development setup

Use **Python 3.11** and a separate Telegram test bot. Run commands from the repository root:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell alternative: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` (`cp .env.example .env` on Linux/macOS, `Copy-Item .env.example .env` in PowerShell) and supply your own settings. At minimum, set a valid `BOT_TOKEN` and numeric `ADMIN_ID`. AI, payments and CRM each require their corresponding credentials. Some features initialize provider clients at startup, so configure the integrations before a full run.

```bash
python bot.py
```

The application creates its local SQLite data as needed. Never run a second polling process with the production token or replace a live database with a development copy.

Mini App and CRM require HTTPS and the proxy routes described in [deployment notes](docs/DEPLOYMENT.md). `/miniapp/images/` is served from the root `images/` folder, so a second copy inside `miniapp/` is unnecessary.

Branding, contact links, offer/privacy URLs and some commercial prices are specific to this practice. Review them before adapting the project. In particular, the 72-hour guide pricing is implemented in `yookassa_payment.py`, not solely in `.env`.

## Publication scope and current limitations

This repository is a clean source snapshot. Production secrets, client databases, logs, server diagnostics, internal deployment archives and paid PDF/audio/video content are intentionally excluded, including from this repository's initial history.

- Supply private content following [materials/README.md](materials/README.md). Empty audio/video files are skipped by the current delivery function.
- Payment confirmation and successful material delivery are not tracked as separate durable states; delivery recovery and webhook idempotency need further work.
- Review slot reservation under simultaneous requests before expanding booking traffic.
- End-to-end payments, AI responses and Telegram user journeys must be verified in a separate test environment. A source publication does not certify production readiness.
- Several dependencies are unpinned. Create and validate a locked environment before a reproducible production deployment.

## Rights and third-party assets

This is a portfolio source publication. No open-source license has been granted for the application or its original content. Contact the author about reuse. DejaVu font notices are provided in `fonts/LICENSE-DejaVu.txt`; third-party dependencies retain their own licenses.

## Кратко по-русски

Бот для практики психолога: тест, AI-компаньон, дневник, оплата материалов, запись на консультацию, Mini App и личная CRM. Репозиторий показывает устройство проекта. База клиентов, ключи, платные материалы и внутренние серверные документы не публикуются. Для запуска нужны собственные настройки и отдельный тестовый бот.
