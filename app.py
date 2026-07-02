"""
Inventory & POS System — Flask + SQLAlchemy version
=====================================================
This is your original CLI tool (buy / sell / report over a CSV file)
rebuilt as a web app, following the same structure as the earlier
Flask-SQLAlchemy basics example:

  - App factory pattern
  - Config class
  - SQLAlchemy models with relationships (see models.py)
  - Full CRUD for products, plus a POS-style sell flow with a cart

Run it:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000

Your existing data.csv (if present in this folder) is imported
automatically the first time the database is created — see
`_import_csv_if_present()` below.
"""

import csv
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, Product, Sale, SaleItem

CSV_PATH = "data.csv"


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///inventory.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "dev-secret-key-change-me"  # needed for flash messages + cart session


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _import_csv_if_present()

    register_routes(app)
    return app


def _import_csv_if_present():
    """
    One-time migration: if the database has no products yet and a
    data.csv from the old CLI tool exists next to this file, load it in.
    Old columns -> new columns:  id->sku, kind->name, cost->cost_price,
    shp->shipping_cost, price->sell_price, q->quantity
    """
    if Product.query.count() > 0 or not os.path.exists(CSV_PATH):
        return

    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        imported = 0
        for row in reader:
            if row.get("id") in (None, "", "id"):  # skip stray/duplicate header rows
                continue
            try:
                db.session.add(Product(
                    sku=row["id"],
                    name=row["kind"],
                    cost_price=float(row["cost"]),
                    shipping_cost=float(row["shp"]),
                    sell_price=float(row["price"]),
                    quantity=int(row["q"]),
                ))
                imported += 1
            except (KeyError, ValueError):
                continue  # skip malformed rows rather than crash the import
        db.session.commit()
        if imported:
            print(f"Imported {imported} products from {CSV_PATH}")


def register_routes(app: Flask):

    # ================= REPORT (list / "read") =================
    @app.route("/")
    def index():
        return redirect(url_for("products"))

    @app.route("/products")
    def products():
        rows = Product.query.order_by(Product.name).all()
        return render_template("products.html", products=rows)

    # ================= BUY (create / restock) =================
    @app.route("/products/add", methods=["GET", "POST"])
    def add_product():
        if request.method == "POST":
            sku = request.form["sku"].strip()
            existing = Product.query.filter_by(sku=sku).first()

            if existing:
                # Buying more of a product you already stock -> restock it
                existing.quantity += int(request.form["quantity"])
                existing.cost_price = float(request.form["cost_price"])
                existing.shipping_cost = float(request.form["shipping_cost"])
                existing.sell_price = float(request.form["sell_price"])
                db.session.commit()
                flash(f'Restocked "{existing.name}" (SKU {sku}).', "success")
            else:
                product = Product(
                    sku=sku,
                    name=request.form["name"].strip(),
                    cost_price=float(request.form["cost_price"]),
                    shipping_cost=float(request.form["shipping_cost"]),
                    sell_price=float(request.form["sell_price"]),
                    quantity=int(request.form["quantity"]),
                )
                db.session.add(product)
                db.session.commit()
                flash(f'Added "{product.name}" to inventory.', "success")

            return redirect(url_for("products"))

        return render_template("product_form.html", product=None)

    @app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
    def edit_product(product_id):
        product = Product.query.get_or_404(product_id)

        if request.method == "POST":
            product.sku = request.form["sku"].strip()
            product.name = request.form["name"].strip()
            product.cost_price = float(request.form["cost_price"])
            product.shipping_cost = float(request.form["shipping_cost"])
            product.sell_price = float(request.form["sell_price"])
            product.quantity = int(request.form["quantity"])
            db.session.commit()
            flash(f'Updated "{product.name}".', "success")
            return redirect(url_for("products"))

        return render_template("product_form.html", product=product)

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def delete_product(product_id):
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        flash(f'Deleted "{product.name}".', "info")
        return redirect(url_for("products"))

    # ================= SELL (POS mode with a cart) =================
    # The cart lives in the session as a list of dicts until checkout,
    # mirroring how your CLI accumulated receipt_prices before printing
    # the final total.

    @app.route("/sell")
    def sell():
        cart = session.get("cart", [])
        total = round(sum(item["quantity"] * item["unit_price"] for item in cart), 2)
        available_products = Product.query.filter(Product.quantity > 0).order_by(Product.name).all()
        return render_template("sell.html", cart=cart, total=total,
                                products=available_products)

    @app.route("/sell/add", methods=["POST"])
    def sell_add():
        product = Product.query.get_or_404(int(request.form["product_id"]))
        quantity = int(request.form["quantity"])

        # Same guard as the original process_sale(): not found is handled by
        # get_or_404 above; here we just check stock.
        if quantity <= 0 or not product.in_stock(quantity):
            flash(f"Not enough stock for {product.name} "
                  f"(have {product.quantity}, asked for {quantity}).", "info")
            return redirect(url_for("sell"))

        product.quantity -= quantity
        db.session.commit()

        cart = session.get("cart", [])
        cart.append({
            "product_id": product.id,
            "name": product.name,
            "quantity": quantity,
            "unit_price": product.sell_price,
        })
        session["cart"] = cart
        flash(f"Added {quantity} × {product.name} to the sale.", "success")
        return redirect(url_for("sell"))

    @app.route("/sell/cancel", methods=["POST"])
    def sell_cancel():
        """Abandon the current sale and restock everything in the cart."""
        cart = session.pop("cart", [])
        for item in cart:
            product = Product.query.get(item["product_id"])
            if product:
                product.quantity += item["quantity"]
        db.session.commit()
        flash("Sale cancelled — items restocked.", "info")
        return redirect(url_for("sell"))

    @app.route("/sell/checkout", methods=["POST"])
    def checkout():
        cart = session.pop("cart", [])
        if not cart:
            flash("Cart is empty — nothing to check out.", "info")
            return redirect(url_for("sell"))

        total = round(sum(item["quantity"] * item["unit_price"] for item in cart), 2)
        sale = Sale(total=total)
        for item in cart:
            sale.items.append(SaleItem(
                product_id=item["product_id"],
                product_name=item["name"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            ))
        db.session.add(sale)
        db.session.commit()

        return redirect(url_for("receipt", sale_id=sale.id))

    # ================= Receipts (sale history) =================
    @app.route("/sales")
    def sales():
        rows = Sale.query.order_by(Sale.created_at.desc()).all()
        return render_template("sales.html", sales=rows)

    @app.route("/sales/<int:sale_id>")
    def receipt(sale_id):
        sale = Sale.query.get_or_404(sale_id)
        return render_template("receipt.html", sale=sale)


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
