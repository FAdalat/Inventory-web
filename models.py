"""
Models
======
Three tables, two relationships — this is the same one-to-many pattern as
the earlier Category/Product example, applied to your actual buy/sell data:

    Product (1) ----< (many) SaleItem
    Sale    (1) ----< (many) SaleItem

A SaleItem is a line on a receipt: "2x Wool Trench Coat @ $89.50".
A Sale is the receipt itself (one checkout = one Sale = many SaleItems).
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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

    items = db.relationship("SaleItem", back_populates="sale",
                             cascade="all, delete-orphan")

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
