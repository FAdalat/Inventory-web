# Inventory & POS System
#### Video Demo: `https://youtu.be/_2LluyesaJY`
A role-based inventory and point-of-sale web app for small retail or wholesale
businesses, built with **Flask** and **SQLAlchemy**. Started life as a CS50P
CLI tool (buy / sell / report over a CSV file) and has grown into a proper
multi-user web app with authentication, role-based access control, and
persistent sale history.

> Built for and by someone running a wholesale women's fashion business —
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
| Frontend | Server-rendered Jinja templates, no JS framework |

## Getting started

```bash
cd inventory-web
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. Since this is a fresh install, you'll land
on a one-time setup screen to create the first shop owner account. From
there:

1. Log in as the owner
2. **Buy** → add your first products
3. **Employees** → add sales manager accounts for your staff
4. **Sell** → start ringing up sales

## Project structure

```
inventory-web/
├── app.py                 # App factory, routes, access control
├── models.py               # SQLAlchemy models (User, Product, Sale, SaleItem)
├── requirements.txt
├── data.csv                 # Optional: seed data from the original CLI tool
├── templates/
│   ├── base.html             # Shared layout, role-aware nav
│   ├── setup.html            # First-run owner account creation
│   ├── login.html
│   ├── employees.html        # Owner-only: manage staff accounts
│   ├── products.html         # Inventory report
│   ├── product_form.html     # Buy / restock / edit product
│   ├── sell.html             # POS cart
│   ├── sales.html            # Sales history (scoped by role)
│   └── receipt.html          # Single receipt view
└── static/
    └── style.css
```

## Data model

```
User    (1) ----< (many) Sale
Product (1) ----< (many) SaleItem
Sale    (1) ----< (many) SaleItem
```

- **User** — `username`, hashed password, `role` (`owner`/`manager`),
  `active` (used to fire/reinstate accounts)
- **Product** — `sku`, `name`, `cost_price`, `shipping_cost`, `sell_price`,
  `quantity`
- **Sale** — one row per checkout: `total`, `created_at`, `user_id`
- **SaleItem** — one row per line item on a receipt; snapshots the product
  name and price at time of sale, so a receipt stays accurate even if the
  product is later renamed or repriced

## Access control

| Action | Owner | Sales manager |
|---|:---:|:---:|
| View inventory report | ✅ | ✅ |
| Buy / restock / edit / delete products | ✅ | ❌ |
| Make a sale | ✅ | ✅ |
| View all sales history | ✅ | Own sales only |
| Manage employee accounts | ✅ | ❌ |

Access control is enforced at the route level (an `@owner_required`
decorator in `app.py`), not just hidden in the UI — a sales manager who
navigates directly to an owner-only URL is redirected, not shown a broken
page.

## Roadmap / natural next steps

- [ ] `Flask-Migrate` for schema changes without dropping the database
- [ ] `Flask-WTF` for form validation and CSRF protection
- [ ] Postgres for a production deployment
- [ ] Low-stock email/Telegram alerts
- [ ] Export sales history to CSV/Excel
