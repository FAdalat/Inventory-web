"""
Models
======
Four tables now — the three from before, plus User for login:

    Product (1) ----< (many) SaleItem
    Sale    (1) ----< (many) SaleItem
    User    (1) ----< (many) Sale      (who rang up each sale)

Every User has a role: "owner" (shop owner) or "manager" (sales manager).
Owners can do everything; managers can view inventory and make sales but
can't buy/restock, edit products, or see other managers' sales.

A SaleItem is a line on a receipt: "2x Wool Trench Coat @ $89.50".
A Sale is the receipt itself (one checkout = one Sale = many SaleItems).
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """
    UserMixin (from Flask-Login) bolts on the properties Flask-Login
    expects every user object to have: is_authenticated, is_active,
    is_anonymous, and get_id(). We override is_active ourselves below
    so that a "fired" account is instantly locked out.

    role is either "owner" (shop owner) or "manager" (sales manager).
    """
    __tablename__ = "users"

    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_MANAGER)
    active = db.Column(db.Boolean, nullable=False, default=True)  # False = "fired"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship("Sale", back_populates="user")

    def set_password(self, raw_password: str) -> None:
        # Never store the plain password — only a salted hash of it.
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_owner(self) -> bool:
        return self.role == self.ROLE_OWNER

    # Flask-Login checks current_user.is_active on every request via the
    # user_loader below. Returning False here (instead of the UserMixin
    # default of True) is what makes a fired account stop working
    # immediately, even if they're still "logged in" in their browser.
    @property
    def is_active(self) -> bool:
        return self.active

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False)   # was "id" in data.csv
    name = db.Column(db.String(120), nullable=False)              # was "kind"
    cost_price = db.Column(db.Float, nullable=False, default=0.0)     # was "cost"
    shipping_cost = db.Column(db.Float, nullable=False, default=0.0)  # was "shp"
    sell_price = db.Column(db.Float, nullable=False, default=0.0)     # was "price"
    quantity = db.Column(db.Integer, nullable=False, default=0)       # was "q"

    sale_items = db.relationship("SaleItem", back_populates="product")

    def in_stock(self, qty: int) -> bool:
        return self.quantity >= qty

    def __repr__(self):
        return f"<Product {self.sku} {self.name}>"


class Sale(db.Model):
    """One completed checkout — the equivalent of a printed receipt."""
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    items = db.relationship("SaleItem", back_populates="sale",
                             cascade="all, delete-orphan")
    user = db.relationship("User", back_populates="sales")

    def __repr__(self):
        return f"<Sale #{self.id} ${self.total:.2f}>"


class SaleItem(db.Model):
    """One line on a receipt. Snapshots name/price so old receipts stay
    accurate even if the product is later renamed or repriced."""
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    product_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product", back_populates="sale_items")

    @property
    def line_total(self) -> float:
        return round(self.quantity * self.unit_price, 2)
