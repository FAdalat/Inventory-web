"""
Models
======
Four tables now — the three from before, plus User for login:

    Product (1) ----< (many) SaleItem
    Sale    (1) ----< (many) SaleItem
    User    (1) ----< (many) Sale      (who rang up each sale)

Every User has a role: "owner" (shop owner) or "manager" (sales manager).
Owners can do everything; managers can view inventory and make sales but
can't buy/restock, edit products, or see other managers' sales. Applying
a discount at checkout, however, is open to both roles equally — see
Sale.discount_percent below.

A SaleItem is a line on a receipt: "2x Wool Trench Coat @ $89.50".
A Sale is the receipt itself (one checkout = one Sale = many SaleItems).
"""

from datetime import datetime 
import json 
from flask_sqlalchemy import SQLAlchemy 
from flask_login import UserMixin 
from werkzeug .security import generate_password_hash ,check_password_hash 

db =SQLAlchemy ()


class User (db .Model ,UserMixin ):
    """
    UserMixin (from Flask-Login) bolts on the properties Flask-Login
    expects every user object to have: is_authenticated, is_active,
    is_anonymous, and get_id(). We override is_active ourselves below
    so that a "fired" account is instantly locked out.

    role is either "owner" (shop owner) or "manager" (sales manager).
    """
    __tablename__ ="users"

    ROLE_OWNER ="owner"
    ROLE_MANAGER ="manager"

    id =db .Column (db .Integer ,primary_key =True )
    username =db .Column (db .String (80 ),unique =True ,nullable =False )
    password_hash =db .Column (db .String (255 ),nullable =False )
    role =db .Column (db .String (20 ),nullable =False ,default =ROLE_MANAGER )
    active =db .Column (db .Boolean ,nullable =False ,default =True )
    fixed_wage =db .Column (db .Float ,nullable =False ,default =0.0 )
    commission_percent =db .Column (db .Float ,nullable =False ,default =0.0 )
    created_at =db .Column (db .DateTime ,default =datetime .utcnow )

    sales =db .relationship ("Sale",back_populates ="user")

    def set_password (self ,raw_password :str )->None :

        self .password_hash =generate_password_hash (raw_password )

    def check_password (self ,raw_password :str )->bool :
        return check_password_hash (self .password_hash ,raw_password )

    @property 
    def is_owner (self )->bool :
        return self .role ==self .ROLE_OWNER 





    @property 
    def is_active (self )->bool :
        return self .active 

    def __repr__ (self ):
        return f"<User {self .username } ({self .role })>"


class Product (db .Model ):
    __tablename__ ="products"

    id =db .Column (db .Integer ,primary_key =True )
    sku =db .Column (db .String (40 ),unique =True ,nullable =False )
    name =db .Column (db .String (120 ),nullable =False )
    cost_price =db .Column (db .Float ,nullable =False ,default =0.0 )
    shipping_cost =db .Column (db .Float ,nullable =False ,default =0.0 )
    sell_price =db .Column (db .Float ,nullable =False ,default =0.0 )
    quantity =db .Column (db .Integer ,nullable =False ,default =0 )

    sale_items =db .relationship ("SaleItem",back_populates ="product")

    def in_stock (self ,qty :int )->bool :
        return self .quantity >=qty 

    def __repr__ (self ):
        return f"<Product {self .sku } {self .name }>"


class Sale (db .Model ):
    """One completed checkout — the equivalent of a printed receipt.

    Discounting happens here, at the whole-checkout level, not per
    product — this app is for wholesale, where a discount is normally a
    deal on the whole order, not a markdown on one item sitting on a
    shelf. `subtotal` is what the cart added up to before any discount;
    `total` is what was actually charged after applying discount_percent.
    """
    __tablename__ ="sales"

    id =db .Column (db .Integer ,primary_key =True )
    created_at =db .Column (db .DateTime ,default =datetime .utcnow )
    subtotal =db .Column (db .Float ,nullable =False ,default =0.0 )
    discount_percent =db .Column (db .Float ,nullable =False ,default =0.0 )
    total =db .Column (db .Float ,nullable =False ,default =0.0 )
    user_id =db .Column (db .Integer ,db .ForeignKey ("users.id"),nullable =True )

    items =db .relationship ("SaleItem",back_populates ="sale",
    cascade ="all, delete-orphan")
    user =db .relationship ("User",back_populates ="sales")

    @property 
    def discount_amount (self )->float :
        return round (self .subtotal -self .total ,2 )

    @property 
    def commission_earned (self )->float :
        """What the salesperson earns on this one sale, based on their
        commission_percent at the time this is calculated (not snapshotted —
        if you change someone's rate, it applies to their historical sales
        too when viewed). Deliberately uses `total` (what was actually
        collected after any checkout discount), not `subtotal` — a
        discounted sale shouldn't pay commission as if it were full-price."""
        if not self .user :
            return 0.0 
        return round (self .total *self .user .commission_percent /100 ,2 )

    def __repr__ (self ):
        return f"<Sale #{self .id } ${self .total :.2f}>"


class SaleItem (db .Model ):
    """One line on a receipt. Snapshots name/price/cost so old receipts
    (and historical profit figures) stay accurate even if the product is
    later renamed, repriced, or its cost changes. unit_price here is
    always the plain catalog price — any whole-checkout discount lives on
    the parent Sale, not distributed across individual lines."""
    __tablename__ ="sale_items"

    id =db .Column (db .Integer ,primary_key =True )
    sale_id =db .Column (db .Integer ,db .ForeignKey ("sales.id"),nullable =False )
    product_id =db .Column (db .Integer ,db .ForeignKey ("products.id"),nullable =False )

    product_name =db .Column (db .String (120 ),nullable =False )
    quantity =db .Column (db .Integer ,nullable =False )
    unit_price =db .Column (db .Float ,nullable =False )




    unit_cost =db .Column (db .Float ,nullable =False ,default =0.0 )

    sale =db .relationship ("Sale",back_populates ="items")
    product =db .relationship ("Product",back_populates ="sale_items")

    @property 
    def line_total (self )->float :
        return round (self .quantity *self .unit_price ,2 )

    @property 
    def line_profit (self )->float :
        """Gross margin on this line at full catalog price. Note this
        does NOT reflect any whole-checkout discount — that's tracked on
        the parent Sale (see Sale.discount_amount), since a checkout-wide
        discount isn't attributable to any one line item."""
        return round (self .quantity *(self .unit_price -self .unit_cost ),2 )


class AIInsight (db .Model ):
    """
    A cached AI-generated monthly business report — see ai_insights.py
    for the actual Anthropic API call. Generation is explicit (an owner
    clicks a button), never automatic on page load, for two reasons:
    it avoids surprise API costs from a request firing on every visit,
    and it avoids making every page load wait on a multi-second LLM
    call. This table just stores whatever the AI returned, keyed by
    month, so it can be served instantly until someone regenerates it.
    """
    __tablename__ ="ai_insights"

    id =db .Column (db .Integer ,primary_key =True )
    month =db .Column (db .String (7 ),nullable =False ,index =True )
    generated_at =db .Column (db .DateTime ,default =datetime .utcnow )



    content_json =db .Column (db .Text ,nullable =False )

    def content (self )->dict :
        try :
            return json .loads (self .content_json )
        except (TypeError ,ValueError ):
            return {}
