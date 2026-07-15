<div align="center">

# 🛒 Inventory & POS System

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://sqlalchemy.org)
[![Anthropic](https://img.shields.io/badge/Claude_AI-Haiku-CC785C?style=for-the-badge&logo=anthropic&logoColor=white)](https://anthropic.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<br/>

**A production-ready, role-based Inventory & Point-of-Sale web app for wholesale and retail businesses.**  
Built with Flask, SQLAlchemy, and the Anthropic API — evolved from a CS50P CLI project into a full multi-user platform.

<br/>

🎥 **[Watch the Demo →](https://youtu.be/WJFrkC3xlQw)**

</div>

---

## 📸 Screenshots

<div align="center">
<img width="700" alt="Dashboard" src="https://github.com/user-attachments/assets/cbd19547-a1fc-4f48-821b-8e9ec4e38e10" />
<br/><br/>
<img width="700" alt="POS Sell Screen" src="https://github.com/user-attachments/assets/312a5903-739a-4611-9f35-a620ae382818" />
<br/><br/>
<img width="700" alt="Inventory Report" src="https://github.com/user-attachments/assets/89e65262-c194-42e1-b25b-bef3bfea1123" />
</div>

---

## ✨ Features at a Glance

<table>
<tr>
<td width="50%" valign="top">

### 🔐 Auth & Roles
- No public sign-up — owners create all accounts
- Two roles: **Owner** (full access) and **Sales Manager** (scoped access)
- Session-based auth with Werkzeug password hashing
- CSRF protection on every state-changing form

### 🛍️ POS & Inventory
- Session-based cart with real-time stock decrement
- Itemized receipts with permanent history
- Whole-order checkout discounts (great for wholesale)
- **40% markup auto-suggestion** when adding products

</td>
<td width="50%" valign="top">

### 📊 Dashboard & Analytics
- Daily view: sales count, revenue, discounts, and profit
- Per-employee sales, commission, and wages breakdown
- Excel export (`.xlsx` via `openpyxl`) scoped by role
- Historical profit never retroactively changes (cost snapshotting)

### 🤖 AI Insights (Owner only)
- Monthly sales report powered by **Claude Haiku**
- Structured output via **tool use** (`tool_choice`) — not fragile prompted JSON
- Result cached in DB — no surprise API charges on every page load
- Fails gracefully: no key → hint shown; error → message, not crash

</td>
</tr>
</table>

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF |
| **Database** | SQLite (URI-swappable for Postgres / MySQL) |
| **Auth & Security** | Werkzeug password hashing · CSRF tokens · HttpOnly + SameSite cookies |
| **AI** | Anthropic API (Claude Haiku) · `anthropic` Python SDK · tool use |
| **Exports** | `openpyxl` — real `.xlsx` files, role-scoped |
| **Frontend** | Jinja2 templates · Vanilla JS · No framework |

---

## 🚀 Getting Started

```bash
git clone https://github.com/FAdalat/Inventory-web
cd inventory-web
pip install -r requirements.txt
cp .env.example .env

# Generate a secure SECRET_KEY and paste it into .env
python -c "import secrets; print(secrets.token_hex(32))"

python app.py
```

Open **http://127.0.0.1:5000** — on first launch you'll be guided through creating the owner account.

> **`SECRET_KEY` is required.** The app raises `RuntimeError` on startup if it's missing — a hardcoded secret in source is not a secret, and anyone who reads the git history could forge session cookies with it.  
> **`ANTHROPIC_API_KEY` is optional** — the app runs fully without it; the AI widget just shows a setup hint. Get a key at [console.anthropic.com](https://console.anthropic.com).

### First steps after setup

| Step | What to do |
|------|-----------|
| 1 | Log in as owner |
| 2 | **Buy** → add your first products |
| 3 | **Employees** → create sales manager accounts with wages & commission % |
| 4 | **Sell** → open the POS cart and ring up sales |
| 5 | **Dashboard** → review daily turnover, profit, and commissions |
| 6 | **AI Insights** (bottom-right) → generate a monthly summary once sales are in |

---

## 🔒 Security

| Concern | Approach |
|---------|----------|
| Password policy | Min 10 chars, upper + lowercase — enforced **server-side** |
| CSRF | `Flask-WTF CSRFProtect` globally; AI widget uses `X-CSRFToken` header |
| Session cookies | `HttpOnly` + `SameSite=Lax`; set `SESSION_COOKIE_SECURE=1` behind HTTPS |
| Secret key | No default — app refuses to start without one |
| Debug mode | Off by default; interactive debugger allows arbitrary code execution if exposed |
| XSS | AI API output inserted via `textContent`, never `innerHTML` |

**Known gaps** (not yet built): login rate-limiting, HTTPS (use nginx/Caddy as a reverse proxy), password-reset flow.

---

## 🏗️ Project Structure

```
inventory-web/
├── app.py                        # App factory, routes, access control
├── models.py                     # SQLAlchemy models: User, Product, Sale, SaleItem, AIInsight
├── ai_insights.py                # Anthropic API integration — pure in/out, no Flask dependency
├── exports.py                    # Excel (.xlsx) export helpers
├── requirements.txt
├── .env.example                  # Template: ANTHROPIC_API_KEY, SHOP_TIMEZONE
├── .gitignore
├── data.csv                      # Optional: seed from original CLI tool
├── templates/
│   ├── base.html                 # Shared layout, role-aware nav, AI widget markup
│   ├── _ai_insight_content.html  # Partial: renders one AI report (reused on load)
│   ├── setup.html                # First-run owner account creation
│   ├── login.html
│   ├── employees.html            # Owner-only: staff, wages, commission
│   ├── dashboard.html            # Owner-only: daily sales/profit/turnover
│   ├── products.html             # Inventory report
│   ├── product_form.html         # Buy / restock / edit product
│   ├── sell.html                 # POS cart
│   ├── sales.html                # Sales history (role-scoped)
│   └── receipt.html              # Single receipt view
└── static/
    ├── style.css
    └── ai_widget.js              # Collapse/expand + fetch()-based report generation
```

---

## 🗄️ Data Model

```
User    (1) ──< (many) Sale
Product (1) ──< (many) SaleItem
Sale    (1) ──< (many) SaleItem
```

| Model | Key Fields |
|-------|-----------|
| **User** | `username`, hashed password, `role` (owner/manager), `active`, `fixed_wage`, `commission_percent` |
| **Product** | `sku`, `name`, `cost_price`, `shipping_cost`, `sell_price`, `quantity` |
| **Sale** | `subtotal`, `discount_percent`, `total` (net), `created_at`, `user_id` |
| **SaleItem** | Snapshots `unit_price` and `unit_cost` at time of sale — profit never drifts retroactively |
| **AIInsight** | `month` (YYYY-MM), `generated_at`, `content_json` |

---

## 👥 Access Control

| Action | 👑 Owner | 🧑‍💼 Sales Manager |
|--------|:-------:|:---------------:|
| View inventory | ✅ | ✅ |
| Buy / restock / edit / delete products | ✅ | ❌ |
| Make a sale | ✅ | ✅ |
| Apply a checkout discount | ✅ | ✅ |
| View all sales history | ✅ | Own sales only |
| Manage employees, wages, commission | ✅ | ❌ |
| View daily dashboard (profit / turnover) | ✅ | ❌ |
| AI Insights | ✅ | ❌ |

> Access control is enforced **at the route level** via an `@owner_required` decorator — navigating directly to an owner URL redirects, never shows a broken page.

Checkout discounts are open to both roles by design: in wholesale, a discount is a deal negotiated on the whole order at point-of-sale, not a permanent price change that needs owner approval.

---

## 🧠 AI Insights — How It Works

The floating bottom-right widget generates a monthly sales summary via the Anthropic API.

**Data flow:**

```
1. build_monthly_stats()    →  Aggregates Sale/SaleItem rows in Python (no AI yet)
2. Aggregated dict          →  Sent to Claude Haiku with a strict JSON Schema tool
3. Structured response      →  Validated by tool_choice, parsed, stored in AIInsight table
4. context_processor        →  Injects cached report into every template (no per-view API calls)
```

**Design decisions:**

- 🗃️ **Cached, not live** — generating costs one API call; loading a page should never trigger a charge
- ⚡ **Claude Haiku, not a larger model** — structured summarization over pre-aggregated data doesn't need deep reasoning; matching model to task is a deliberate cost/latency call
- 🔧 **Tool use, not prompted JSON** — `tool_choice` makes the API validate the shape before the response reaches this code; asking a model to "respond with only JSON" is fragile
- 💱 **Currency stated explicitly** — keys like `turnover_usd` and a top-level `"currency": "USD"` stop the model from guessing and printing the wrong symbol
- 🛡️ **Output treated as untrusted** — every AI string is inserted via `textContent`, never `innerHTML`
- 📦 **Isolated module** — `ai_insights.py` has no Flask imports; takes a dict in, returns a dict out — independently testable

---

## ⚙️ Notable Engineering Details

<details>
<summary><strong>🕐 Timezone handling</strong></summary>

Every timestamp is stored as **UTC** (`datetime.utcnow()`) — the correct, unambiguous way to store time. Display and day-boundary logic convert back to local time:

- Templates use a custom Jinja filter `{{ sale.created_at | localtime }}` instead of raw `.strftime()`
- The Dashboard's "today" uses `local_today()` and SQL boundaries use `local_day_to_utc_range()` — a sale just after local midnight won't fall on the wrong day
- Defaults to `Asia/Baku`; override with `SHOP_TIMEZONE=America/New_York` (any IANA name) in `.env`

</details>

<details>
<summary><strong>🔄 Schema migrations (no Alembic needed — yet)</strong></summary>

`db.create_all()` never alters existing tables. A small `_ensure_schema_upgrades()` runs on every startup, uses `SQLAlchemy inspect()` to find missing columns, and `ALTER TABLE`s them in. Backfill logic handles historical data safely (e.g. `subtotal` on old sales is set to `total` → shows $0 discount rather than "fully discounted"). If the schema keeps growing, the natural next step is `Flask-Migrate`.

</details>

---

## 🗺️ Roadmap

- [ ] Phase 2 AI: follow-up chat interface ("why did profit drop in week 3?") grounded in the same monthly data
- [ ] Login rate-limiting / account lockout
- [ ] Password-reset flow
- [ ] Multi-tenant / SaaS mode — serve multiple shop customers from one deployment

---

<div align="center">

**Built by [FAdalat](https://github.com/FAdalat)**  
*Started as a CS50P problem set. Grew into something real.*

</div>
