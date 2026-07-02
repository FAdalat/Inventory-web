# Inventory & POS System — Flask + SQLAlchemy

Your original CS50P CLI tool (`buy` / `sell` / `report` over a CSV file),
rebuilt as a web app using the same structure as the Flask-SQLAlchemy
basics example: app factory, `Config` class, models with real
relationships, and full CRUD — now with a proper database instead of a
hand-parsed CSV.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. On first run, if `data.csv` (your old file)
is sitting in this folder, it's imported automatically into a new
`inventory.db` SQLite database. Delete `inventory.db` any time to
re-import from scratch.

## What changed vs. the CLI version

| CLI version | Web version |
|---|---|
| `data.csv` + manual header repair | SQLite via SQLAlchemy — no more parsing bugs |
| `buy_mode()` prompts | `/products/add` form (also restocks existing SKUs) |
| `sell_mode()` loop + `process_sale()` | `/sell` page with a cart, backed by the same stock-check logic |
| `print_report()` | `/products` table |
| Printed receipt at end of `sell_mode()` | Persistent `Sale` + `SaleItem` rows, viewable anytime at `/sales` |

Your core business rule — reject a sale if `quantity > stock` — is still
enforced the same way, just as `product.in_stock(quantity)` in
`models.py` instead of an `if` inside `process_sale()`.

## Data model (`models.py`)

```
Product (1) ----< (many) SaleItem
Sale    (1) ----< (many) SaleItem
```

- **Product** — your old CSV columns, renamed for clarity:
  `sku` (was `id`), `name` (was `kind`), `cost_price` (was `cost`),
  `shipping_cost` (was `shp`), `sell_price` (was `price`), `quantity` (was `q`)
- **Sale** — one row per checkout, with a `total`
- **SaleItem** — one row per line on a receipt; snapshots the product
  name and price at time of sale so old receipts don't change if you
  later rename or reprice a product

## Routes

| Route | Purpose |
|---|---|
| `GET /products` | Report — full inventory table |
| `GET/POST /products/add` | Buy — add new stock or restock an existing SKU |
| `GET/POST /products/<id>/edit` | Edit a product's details |
| `POST /products/<id>/delete` | Remove a product |
| `GET /sell`, `POST /sell/add`, `/sell/checkout`, `/sell/cancel` | POS-style sale with a session-based cart |
| `GET /sales`, `GET /sales/<id>` | Sale history and individual receipts |

## Natural next steps

- Add **Flask-Migrate** before changing the schema again, so you don't
  need to delete `inventory.db` each time
- Move validation into **Flask-WTF** forms for better error messages
- Add a `User`/login layer if this ever needs multiple staff accounts
- Swap SQLite for Postgres when you're ready to deploy somewhere real
