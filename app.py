"""
Inventory & POS System — Flask + SQLAlchemy version
=====================================================
This is your original CLI tool (buy / sell / report over a CSV file)
rebuilt as a web app with two account roles:

  - owner   : full access — report, buy/restock, sell, all sales history,
              and an Employees tab to manage sales manager accounts
  - manager : report (read-only) and sell only; sales history is limited
              to sales they personally made

There's no public sign-up. The very first run shows a one-time setup
screen to create the first owner account; after that, only /login is
reachable, and new accounts can only be created by an owner from the
Employees tab.

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
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from models import db, Product, Sale, SaleItem, User

CSV_PATH = "data.csv"
login_manager = LoginManager()


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///inventory.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "dev-secret-key-change-me"  # needed for flash messages + cart session


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # Flask-Login needs to know: where to send anonymous visitors,
    # and how to turn a user id (stored in the session cookie) back
    # into a User object on every request.
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to continue."

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        # If the account was fired since the session cookie was issued,
        # returning None here makes Flask-Login treat them as logged
        # out on their very next request — no lingering access.
        if user is None or not user.active:
            return None
        return user

    with app.app_context():
        db.create_all()
        _import_csv_if_present()

    register_routes(app)
    return app


def owner_required(f):
    """
    Stack this under @login_required:

        @app.route(...)
        @login_required
        @owner_required
        def some_view(): ...

    login_required runs first and handles "not logged in at all".
    This decorator only needs to worry about "logged in, but not an
    owner" — it redirects sales managers back to the report page
    instead of letting them hit owner-only routes directly by URL.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_owner:
            flash("That page is only available to shop owners.", "info")
            return redirect(url_for("products"))
        return f(*args, **kwargs)
    return wrapper


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

    # ================= AUTH =================
    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        """
        One-time first-run screen. Only reachable while the database has
        zero users. Creates the first owner account and logs them in.
        Once any account exists, this route just bounces to /login.
        """
        if User.query.count() > 0:
            return redirect(url_for("login"))

        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]
            confirm = request.form["confirm_password"]

            if not username or not password:
                flash("Username and password are required.", "info")
            elif password != confirm:
                flash("Passwords don't match.", "info")
            else:
                owner = User(username=username, role=User.ROLE_OWNER)
                owner.set_password(password)
                db.session.add(owner)
                db.session.commit()
                login_user(owner)
                flash(f"Welcome, {owner.username} — your shop owner account is ready.", "success")
                return redirect(url_for("products"))

        return render_template("setup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        # No accounts yet -> send everyone to first-run setup instead.
        if User.query.count() == 0:
            return redirect(url_for("setup"))

        if current_user.is_authenticated:
            return redirect(url_for("products"))

        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]
            user = User.query.filter_by(username=username).first()

            if user and not user.active:
                flash("This account has been deactivated.", "info")
            elif user and user.check_password(password):
                login_user(user)
                flash(f"Welcome back, {user.username}.", "success")
                next_page = request.args.get("next")
                return redirect(next_page or url_for("products"))
            else:
                flash("Invalid username or password.", "info")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("login"))

    # ================= EMPLOYEES (owner-only) =================
    @app.route("/employees")
    @login_required
    @owner_required
    def employees():
        rows = User.query.order_by(User.role.desc(), User.username).all()
        return render_template("employees.html", employees=rows)

    @app.route("/employees/add", methods=["POST"])
    @login_required
    @owner_required
    def add_employee():
        # This is the *only* way new accounts get created after first
        # run — always as a sales manager. Promoting to owner is a
        # separate, explicit action below.
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if not username or not password:
            flash("Username and password are required.", "info")
        elif password != confirm:
            flash("Passwords don't match.", "info")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "info")
        else:
            manager = User(username=username, role=User.ROLE_MANAGER)
            manager.set_password(password)
            db.session.add(manager)
            db.session.commit()
            flash(f'Added sales manager "{username}".', "success")

        return redirect(url_for("employees"))

    @app.route("/employees/<int:user_id>/promote", methods=["POST"])
    @login_required
    @owner_required
    def promote_employee(user_id):
        employee = User.query.get_or_404(user_id)
        if employee.role == User.ROLE_MANAGER:
            employee.role = User.ROLE_OWNER
            db.session.commit()
            flash(f"{employee.username} is now a shop owner.", "success")
        return redirect(url_for("employees"))

    @app.route("/employees/<int:user_id>/fire", methods=["POST"])
    @login_required
    @owner_required
    def fire_employee(user_id):
        employee = User.query.get_or_404(user_id)
        if employee.id == current_user.id:
            flash("You can't fire your own account.", "info")
        elif employee.role == User.ROLE_OWNER:
            flash("Owners can't be fired from this screen.", "info")
        else:
            employee.active = False
            db.session.commit()
            flash(f"{employee.username} has been removed.", "info")
        return redirect(url_for("employees"))

    @app.route("/employees/<int:user_id>/reinstate", methods=["POST"])
    @login_required
    @owner_required
    def reinstate_employee(user_id):
        employee = User.query.get_or_404(user_id)
        employee.active = True
        db.session.commit()
        flash(f"{employee.username} reinstated.", "success")
        return redirect(url_for("employees"))

    # ================= REPORT (list / "read") =================
    # Both roles can view this; only the template hides Edit/Delete
    # buttons from managers (route-level enforcement is still below
    # on add/edit/delete, so hiding the buttons is just UX polish).
    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("products"))

    @app.route("/products")
    @login_required
    def products():
        rows = Product.query.order_by(Product.name).all()
        return render_template("products.html", products=rows)

    # ================= BUY (create / restock) — owner only =================
    @app.route("/products/add", methods=["GET", "POST"])
    @login_required
    @owner_required
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
    @login_required
    @owner_required
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
    @login_required
    @owner_required
    def delete_product(product_id):
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        flash(f'Deleted "{product.name}".', "info")
        return redirect(url_for("products"))

    # ================= SELL (POS mode with a cart) — both roles =================
    # The cart lives in the session as a list of dicts until checkout,
    # mirroring how your CLI accumulated receipt_prices before printing
    # the final total.

    @app.route("/sell")
    @login_required
    def sell():
        cart = session.get("cart", [])
        total = round(sum(item["quantity"] * item["unit_price"] for item in cart), 2)
        available_products = Product.query.filter(Product.quantity > 0).order_by(Product.name).all()
        return render_template("sell.html", cart=cart, total=total,
                                products=available_products)

    @app.route("/sell/add", methods=["POST"])
    @login_required
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
    @login_required
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
    @login_required
    def checkout():
        cart = session.pop("cart", [])
        if not cart:
            flash("Cart is empty — nothing to check out.", "info")
            return redirect(url_for("sell"))

        total = round(sum(item["quantity"] * item["unit_price"] for item in cart), 2)
        sale = Sale(total=total, user_id=current_user.id)
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
    # Owners see every sale with who made it; managers see only their own.
    @app.route("/sales")
    @login_required
    def sales():
        query = Sale.query.order_by(Sale.created_at.desc())
        if not current_user.is_owner:
            query = query.filter_by(user_id=current_user.id)
        return render_template("sales.html", sales=query.all())

    @app.route("/sales/<int:sale_id>")
    @login_required
    def receipt(sale_id):
        sale = Sale.query.get_or_404(sale_id)
        if not current_user.is_owner and sale.user_id != current_user.id:
            flash("You can only view your own sales.", "info")
            return redirect(url_for("sales"))
        return render_template("receipt.html", sale=sale)


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
