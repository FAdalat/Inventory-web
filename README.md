# Inventory & POS System
Video Link: https://youtu.be/WJFrkC3xlQw

A role-based inventory and point-of-sale web app for small retail or wholesale
businesses, built with **Flask** and **SQLAlchemy**. Started life as a CS50P
CLI tool (buy / sell / report over a CSV file) and has grown into a proper
multi-user web app with authentication, role-based access control, and
persistent sale history.

> the feature set (buy/restock, sell with a cart, sales-manager accounts)
> reflects real day-to-day shop operations rather than a generic CRUD demo.

## Features

- **Two account roles**
  - **Shop owner** — full access: inventory report, buy/restock, sell,
    complete sales history across all staff, and an Employees panel
  - **Sales manager** — can view inventory (read-only) and make sales;
    sales history is limited to sales they personally made
- **No public sign-up.** First launch walks you through creating the one
  owner account; every account after that is created by an owner from the
  Employees tab
- **POS-style checkout** — a session-based cart, stock is decremented as
  items are added, and checkout writes a permanent, itemized receipt
- **Employee management** — owners can add sales managers, promote a
  manager to owner, or fire (deactivate) an account. Fired accounts lose
  access immediately, even mid-session
- **Wages & commission** — every sales manager has a fixed wage and a
  commission percentage set when they're added (editable anytime from the
  Employees tab); the Employees page shows each manager's all-time sales
  count, revenue generated, and commission actually earned — not just
  their rate — and the dashboard breaks the same figures down per day
- **Owner dashboard** — a daily view of sales count, items sold, turnover
  (revenue), discounts given, and profit, plus a per-employee breakdown
  of sales and commission earned for any selected day
- **Whole-checkout discounts** — built for wholesale, where a discount is
  normally a deal on the whole order rather than a markdown on one item.
  Anyone logged in — owner or sales manager — can apply a discount
  percentage to the current cart at checkout; individual product prices
  are never touched, and the discount is snapshotted onto the receipt
  (subtotal, discount %, and final total) so it stays accurate forever
- **Automatic 40% price suggestion** — entering a cost and shipping price
  while adding/editing a product suggests a selling price at a 40% markup;
  the owner can always override it, and a manual entry is never silently
  replaced
- **Excel export** — a "⬇ Export to Excel" button on the Report, Sales
  History, and Employees pages downloads a real `.xlsx` file (via
  `openpyxl`) of exactly what that page shows — respecting the same
  role-based scoping as the page itself (a sales manager's export
  contains only their own sales, no "Sold by" column, and no access to
  the Employees export at all)
- **AI Insights** — a floating widget (bottom-right, owner accounts only)
  that turns the current month's sales into a short, structured report
  via the Anthropic API: a plain-language summary, top and slow-moving
  products, concrete recommendations, and margin warnings. See
  [AI Insights](#ai-insights) below for how it's built and why.
- **CSV migration** — imports an existing `data.csv` from the original CLI
  tool into the database automatically on first run

## Screenshots

<img width="700" alt="p1" src="https://github.com/user-attachments/assets/cbd19547-a1fc-4f48-821b-8e9ec4e38e10" />
<img width="700" alt="p3" src="https://github.com/user-attachments/assets/312a5903-739a-4611-9f35-a620ae382818" />
<img width="700" alt="p2" src="https://github.com/user-attachments/assets/89e65262-c194-42e1-b25b-bef3bfea1123" />

## Tech stack

| | |
|---|---|
| Backend | Flask, Flask-SQLAlchemy, Flask-Login |
| Database | SQLite (swap the URI for Postgres/MySQL in production) |
| Auth | Werkzeug password hashing (salted, one-way) |
| AI | Anthropic API (Claude Haiku), via the official `anthropic` Python SDK |
| Frontend | Server-rendered Jinja templates + vanilla JS, no framework |

## Getting started

```bash
git clone <your-repo-url>
cd inventory-web
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output into .env as SECRET_KEY
python app.py
```

`SECRET_KEY` is **required** — the app refuses to start without it (see
[Security](#security) below for why). `ANTHROPIC_API_KEY` is optional —
the app runs fine without it, just with the AI Insights widget showing a
"set your API key" hint instead of a report. Get a key at
[console.anthropic.com](https://console.anthropic.com/). `.env` is
gitignored; never commit your real secrets.

Open **http://127.0.0.1:5000**. Since this is a fresh install, you'll land
on a one-time setup screen to create the first shop owner account. From
there:

1. Log in as the owner
2. **Buy** → add your first products
3. **Employees** → add sales manager accounts with a fixed wage and
   commission percentage
4. **Sell** → start ringing up sales
5. **Dashboard** → check daily turnover, profit, and commission earned
6. **AI Insights** (bottom-right widget) → generate a monthly report once
   you have a few sales recorded

## Security

Passwords require at least 10 characters with one uppercase and one
lowercase letter, enforced server-side (`validate_password_strength()`
in `app.py`) — the HTML form's `pattern`/`minlength` attributes are only
a same-page hint, since anyone can bypass a client-side check by
submitting the form directly.

Every state-changing form includes a CSRF token (`Flask-WTF`'s
`CSRFProtect`, applied globally in `create_app()`), and the AI widget's
JavaScript `fetch()` call sends its token via an `X-CSRFToken` header
instead, read from a `<meta>` tag in `base.html`. Session cookies are
`HttpOnly` and `SameSite=Lax` by default; set `SESSION_COOKIE_SECURE=1`
in `.env` once you're actually running behind HTTPS.

`SECRET_KEY` has no default and the app raises `RuntimeError` on startup
if it's missing — a secret that ships as a literal string in source code
isn't a secret at all, since anyone who reads the code (or the git
history) could forge a valid session cookie with it.

`FLASK_DEBUG` defaults to off. Debug mode's interactive in-browser
debugger allows arbitrary code execution to anyone who can trigger an
unhandled error and reach it — only ever set `FLASK_DEBUG=1` for local
development, never on anything another person can reach over a network.

**What this project deliberately doesn't cover**, if you take it further
than local/trusted-network use: login rate limiting (no lockout after
repeated failed attempts), HTTPS itself (the Flask dev server has no
TLS — put a reverse proxy like nginx or Caddy in front of it), and a
password-reset flow (currently none — a forgotten password has to be
reset directly in the database). Worth knowing about, not yet built.

## Project structure

```
inventory-web/
├── app.py                 # App factory, routes, access control
├── models.py               # SQLAlchemy models (User, Product, Sale, SaleItem, AIInsight)
├── ai_insights.py           # Anthropic API integration — separate from Flask routes
├── exports.py                # Excel (.xlsx) export helpers, separate from Flask routes
├── requirements.txt
├── .env.example              # Template for ANTHROPIC_API_KEY / SHOP_TIMEZONE (copy to .env)
├── .gitignore                 # Excludes .env, the database, __pycache__, etc.
├── data.csv                 # Optional: seed data from the original CLI tool
├── templates/
│   ├── base.html             # Shared layout, role-aware nav, AI widget markup
│   ├── _ai_insight_content.html  # Partial: renders one AI report (reused on load)
│   ├── setup.html            # First-run owner account creation
│   ├── login.html
│   ├── employees.html        # Owner-only: manage staff, wages, commission
│   ├── dashboard.html        # Owner-only: daily sales/profit/turnover
│   ├── products.html         # Inventory report
│   ├── product_form.html     # Buy / restock / edit product
│   ├── sell.html             # POS cart
│   ├── sales.html            # Sales history (scoped by role)
│   └── receipt.html          # Single receipt view
└── static/
    ├── style.css
    └── ai_widget.js           # Widget collapse/expand + fetch()-based report generation
```

## Data model

```
User    (1) ----< (many) Sale
Product (1) ----< (many) SaleItem
Sale    (1) ----< (many) SaleItem
```

- **User** — `username`, hashed password, `role` (`owner`/`manager`),
  `active` (used to fire/reinstate accounts), `fixed_wage` and
  `commission_percent` (sales managers only — used on the Employees tab
  and the dashboard's commission breakdown)
- **Product** — `sku`, `name`, `cost_price`, `shipping_cost`, `sell_price`,
  `quantity`. No discount field here — discounting is a checkout-time
  decision, not a property of the product (see Sale below)
- **Sale** — one row per checkout: `subtotal` (what the cart added up to
  before any discount), `discount_percent` (applied at checkout, to the
  whole order), `total` (what was actually charged), `created_at`,
  `user_id`
- **SaleItem** — one row per line item on a receipt; snapshots the product
  name, its catalog price, and its cost (`unit_price`, `unit_cost`) at
  time of sale. `unit_price` here is always the plain catalog price — any
  whole-checkout discount lives on the parent `Sale`, not distributed
  across individual lines, since a discount on the whole order isn't
  attributable to any one item
- **AIInsight** — one row per generated monthly report: `month`
  (`"YYYY-MM"`), `generated_at`, and `content_json` (the AI's structured
  response, stored as JSON text rather than one column per field — see
  [AI Insights](#ai-insights) below)

## Access control

| Action | Owner | Sales manager |
|---|:---:|:---:|
| View inventory report | ✅ | ✅ |
| Buy / restock / edit / delete products | ✅ | ❌ |
| Make a sale | ✅ | ✅ |
| Apply a checkout discount | ✅ | ✅ |
| View all sales history | ✅ | Own sales only |
| Manage employee accounts, wages, commission | ✅ | ❌ |
| View daily dashboard (profit/turnover) | ✅ | ❌ |

Applying a checkout discount is deliberately open to both roles — there's
no `@owner_required` (or equivalent) on `/sell/discount`. This is a
wholesale app: a discount is normally a deal negotiated on the whole
order at the point of sale, something either an owner or a sales manager
might do, not a pricing decision that needs owner sign-off the way
permanently changing `sell_price` does.

Access control is enforced at the route level (an `@owner_required`
decorator in `app.py`), not just hidden in the UI — a sales manager who
navigates directly to an owner-only URL is redirected, not shown a broken
page.

The dashboard is owner-only for the same reason Buy is: profit is derived
from cost data, which sales managers never see anywhere else in the app
either. Profit is calculated from each `SaleItem`'s snapshotted
`unit_cost` against the `Sale.total` actually collected (already net of
any checkout discount) — so restocking a product at a new cost won't
retroactively change what a past day's profit was. Profit is allowed to
land at zero or negative on a heavily discounted day; it's shown as-is
rather than clamped, since hiding a real loss would defeat the point of
the dashboard.

### Schema upgrades on existing databases

`db.create_all()` only creates tables that don't exist yet — it never
alters an existing table when a model gains a new column. `app.py` has a
small `_ensure_schema_upgrades()` step that runs on every startup, checks
for columns the current models expect but an older database might be
missing (e.g. `fixed_wage`, `unit_cost`, `subtotal`), and adds them with
`ALTER TABLE`. For `unit_cost` on old sale_items, it backfills using each
product's *current* cost as a one-time best-effort estimate. For
`subtotal` on old sales (which predate checkout-wide discounts entirely),
it backfills with the row's own `total`, so historical sales correctly
show a $0 discount rather than looking fully discounted. Sales made from
this point onward are exact for both, since the app now snapshots the
real cost and checkout discount at the moment of sale. An earlier design
briefly stored a per-product discount column on `products` — that
approach was replaced with the whole-checkout discount described above,
and the old column (if a database happens to have it from that version)
is simply ignored; SQLAlchemy doesn't mind unused columns.

This is a lightweight stand-in for a real migration tool; if the schema
keeps growing, switch to `Flask-Migrate`.

### Timezones

Every timestamp is stored in the database as **UTC** (`datetime.utcnow()`
in `models.py`) — this is deliberate and is the normal way to store
timestamps, since it avoids ambiguity regardless of where the server or
its visitors are. What matters is converting *back* to local time
correctly whenever a timestamp is shown or used to group things by day:

- **Display** — templates never call `.strftime()` on a raw database
  timestamp directly. They use a custom Jinja filter, `{{ sale.created_at
  | localtime }}`, which converts UTC to the shop's local timezone first
  (`app.py`, `localtime_filter`).
- **The Dashboard's day boundaries** — "today" and the date picker use
  `local_today()`, not the server's own clock, and the SQL query
  boundaries use `local_day_to_utc_range()`, which converts the shop's
  local midnight into the correct UTC instants. Without this, a sale made
  shortly after local midnight can fall on the wrong side of a naive UTC
  day boundary and show up under the wrong day.

The timezone defaults to `Asia/Baku` and can be overridden with the
`SHOP_TIMEZONE` environment variable (any IANA name, e.g.
`America/New_York`) without touching code.

## AI Insights

A floating widget, bottom-right, visible only to shop owner accounts —
same reasoning as the Dashboard and Buy being owner-only: this surfaces
cost and margin data sales managers don't see anywhere else. Clicking
"Generate report" sends one month of aggregated sales data to the
Anthropic API and gets back a structured summary: overview, top and
slow-moving products, concrete recommendations, and margin warnings.

**Data flow:**

1. `build_monthly_stats()` in `app.py` aggregates the month's `Sale`/
   `SaleItem` rows in Python — turnover, profit, discounts given, top/
   slow products by quantity, and per-manager sales/commission. This is
   plain aggregation, no AI involved yet.
2. That summary (not raw database rows) is sent to Claude, with a system
   prompt that asks for a strict JSON shape back — see `ai_insights.py`.
3. The response is parsed, defensively coerced to the expected shape
   (capped list lengths, string casts), and stored in the `AIInsight`
   table, keyed by month.
4. The widget reads the *cached* row on every page load via a Flask
   `context_processor` (so every template gets the data without each
   route fetching it manually) — it does **not** call the AI API on
   every page view. Regenerating is an explicit, separate action.

**Design choices worth knowing about:**

- **Caching, not live calls.** Generating a report costs one API call and
  a few seconds; loading a page should never wait on that or trigger a
  charge you didn't ask for. The widget shows whatever was last
  generated until you click "Regenerate."
- **Model choice: Claude Haiku, not the biggest available model.** This
  is a short, structured summarization task over data that's already
  aggregated — it doesn't need deep reasoning, just to turn numbers into
  clear bullets. Matching model size to task complexity is a deliberate
  cost/latency decision, not a default left unconsidered.
- **Structured output via tool use, not prompted JSON.** The model is
  given a JSON Schema (`INSIGHT_TOOL` in `ai_insights.py`) and forced to
  call it via `tool_choice`, rather than being asked in plain English to
  "respond with only JSON." Asking nicely is fragile — a model can still
  wrap its answer in markdown fences or add a stray sentence even when
  told not to; tool use makes the API itself validate the shape before
  the response ever reaches this code.
- **Currency is stated explicitly, not left implicit.** Early on, the
  generated report used the wrong currency symbol because the raw
  numbers sent to the model (e.g. `"turnover": 130.0`) never said what
  currency they were in — the model had to guess. The fix has two
  layers: `build_monthly_stats()` sends self-documenting keys
  (`turnover_usd`, `profit_usd`, plus a top-level `"currency": "USD"`),
  and the system prompt states outright that all figures are USD and
  must be written with `$`. Any place a model has to infer units,
  currency, or format from context alone is worth making explicit
  instead — assuming works most of the time, until it doesn't.
- **The AI's output is treated as untrusted text, not markup.** In
  `static/ai_widget.js`, every string from the API response is inserted
  with `textContent`, never `innerHTML` — the same rule you'd apply to
  any third-party API response. This is what stops a stray HTML-looking
  string in a model's output from ever being interpreted as real markup
  and rendered as an active element on the page.
- **Fails loudly but gracefully.** No `ANTHROPIC_API_KEY` → the widget
  shows a setup hint instead of a button. A failed API call → the panel
  shows the actual error message instead of crashing the page. Nothing
  about this feature can take down the rest of the app.
- **Kept in its own module.** `ai_insights.py` never imports Flask or
  touches the database — it takes a plain dict in and returns a plain
  dict out. That separation makes the "call an LLM" logic independently
  testable and keeps `app.py` focused on request handling.

**Possible Phase 2 (not built yet):** a follow-up chat interface where
the owner can ask a specific question ("why did profit drop in week 3?")
and get an answer grounded in the same monthly data. The report version
here is deliberately the simpler, ship-first version; a real conversation
UI with state management is a meaningfully bigger scope, so it's being
treated as a separate, later iteration rather than bolted on early.

