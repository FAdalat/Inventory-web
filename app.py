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
import json 
import os 
import re 
from datetime import datetime ,date ,timedelta ,timezone 
from functools import wraps 
from zoneinfo import ZoneInfo ,ZoneInfoNotFoundError 

from dotenv import load_dotenv 
from flask import Flask ,render_template ,request ,redirect ,url_for ,flash ,session ,jsonify ,send_file 
from flask_login import (
LoginManager ,login_user ,logout_user ,login_required ,current_user 
)
from flask_wtf import CSRFProtect 
from sqlalchemy import inspect ,text 

import ai_insights 
import exports 
from models import db ,Product ,Sale ,SaleItem ,User ,AIInsight 





load_dotenv ()

CSV_PATH ="data.csv"
login_manager =LoginManager ()
csrf =CSRFProtect ()


class Config :
    SQLALCHEMY_DATABASE_URI ="sqlite:///inventory.db"
    SQLALCHEMY_TRACK_MODIFICATIONS =False 





    SECRET_KEY =os .environ .get ("SECRET_KEY")





    SESSION_COOKIE_HTTPONLY =True 
    SESSION_COOKIE_SAMESITE ="Lax"





    SESSION_COOKIE_SECURE =os .environ .get ("SESSION_COOKIE_SECURE")=="1"





    LOCAL_TIMEZONE =os .environ .get ("SHOP_TIMEZONE","Asia/Baku")


try :
    LOCAL_TZ =ZoneInfo (Config .LOCAL_TIMEZONE )
except ZoneInfoNotFoundError as exc :





    raise RuntimeError (
    f"Could not find timezone '{Config .LOCAL_TIMEZONE }'. This usually "
    "means the 'tzdata' package isn't installed (common on Windows, "
    "which has no built-in IANA timezone database). Fix it with:\n\n"
    "    pip install tzdata\n\n"
    "or simply:\n\n"
    "    pip install -r requirements.txt\n"
    )from exc 


def utc_to_local (dt :datetime |None )->datetime |None :
    """
    Every datetime coming out of the database (Sale.created_at, etc.) is
    naive and represents UTC — that's what datetime.utcnow() in models.py
    stores. To display it correctly, we have to explicitly say "this is
    UTC" (.replace(tzinfo=timezone.utc)) before converting it to the
    shop's local time. Skipping that first step is exactly the bug this
    fixes: without it, Python has no idea the naive datetime was UTC in
    the first place, so nothing gets shifted at all.
    """
    if dt is None :
        return None 
    return dt .replace (tzinfo =timezone .utc ).astimezone (LOCAL_TZ )


def local_today ()->date :
    """Today's date as understood in the shop's local timezone — not the
    server's timezone, which may well be UTC on a hosting platform."""
    return datetime .now (LOCAL_TZ ).date ()


def local_day_to_utc_range (local_calendar_date :date )->tuple [datetime ,datetime ]:
    """
    Given a calendar date the way a person in the shop's timezone means
    it (e.g. "July 3rd"), return the UTC start/end instants that actually
    correspond to that local day. Sale.created_at is stored as naive UTC,
    so this is what has to be compared against it — comparing raw UTC
    midnight-to-midnight against a local calendar date is the second bug:
    a sale made at, say, 1 AM Baku time is still the *previous* day in
    UTC, so it would silently land in the wrong day's dashboard numbers.
    """
    local_start =datetime .combine (local_calendar_date ,datetime .min .time (),tzinfo =LOCAL_TZ )
    local_end =local_start +timedelta (days =1 )
    return (
    local_start .astimezone (timezone .utc ).replace (tzinfo =None ),
    local_end .astimezone (timezone .utc ).replace (tzinfo =None ),
    )


def local_month_to_utc_range (year :int ,month :int )->tuple [datetime ,datetime ]:
    """The monthly sibling of local_day_to_utc_range: given a calendar
    month in the shop's local timezone, return the UTC start/end instants
    that correspond to it, for the same reason — Sale.created_at is
    stored as naive UTC, so this is what has to be compared against it."""
    local_start =datetime (year ,month ,1 ,tzinfo =LOCAL_TZ )
    if month ==12 :
        local_end =datetime (year +1 ,1 ,1 ,tzinfo =LOCAL_TZ )
    else :
        local_end =datetime (year ,month +1 ,1 ,tzinfo =LOCAL_TZ )
    return (
    local_start .astimezone (timezone .utc ).replace (tzinfo =None ),
    local_end .astimezone (timezone .utc ).replace (tzinfo =None ),
    )


def validate_password_strength (password :str )->str |None :
    """
    Returns None if the password meets the minimum bar, otherwise a
    human-readable reason it was rejected. This is enforced here, in
    Python, not just via the form's `minlength`/pattern attributes in
    the templates — an HTML attribute only stops a browser's own submit
    button; it does nothing to stop a request sent directly (curl,
    a script, a modified form), so the real check has to live server-side.
    """
    if len (password )<10 :
        return "Password must be at least 10 characters long."
    if not re .search (r"[a-z]",password ):
        return "Password must include at least one lowercase letter."
    if not re .search (r"[A-Z]",password ):
        return "Password must include at least one uppercase letter."
    return None 


def create_app ():
    app =Flask (__name__ )
    app .config .from_object (Config )

    if not app .config ["SECRET_KEY"]:
        raise RuntimeError (
        "SECRET_KEY is not set. Add it to your .env file — generate one with:\n"
        '    python -c "import secrets; print(secrets.token_hex(32))"\n'
        "See .env.example."
        )

    db .init_app (app )
    csrf .init_app (app )




    login_manager .init_app (app )
    login_manager .login_view ="login"
    login_manager .login_message ="Please log in to continue."

    @app .template_filter ("localtime")
    def localtime_filter (dt ,fmt ="%Y-%m-%d %H:%M"):
        """Used in templates as {{ some_datetime | localtime }} instead of
        the old {{ some_datetime.strftime(...) }}, which displayed the raw
        UTC value with no conversion at all."""
        local_dt =utc_to_local (dt )
        return local_dt .strftime (fmt )if local_dt else ""

    @app .context_processor 
    def inject_ai_widget ():
        """
        Makes the AI insights widget's data available in every template
        without every single route having to fetch and pass it manually —
        base.html renders the floating panel using these variables. Only
        does the (cheap, indexed-by-month) lookup for owners, since the
        widget itself is owner-only, same as Buy and the Dashboard.
        """
        if not current_user .is_authenticated or not current_user .is_owner :
            return {}
        month_key =local_today ().strftime ("%Y-%m")
        latest =(
        AIInsight .query .filter_by (month =month_key )
        .order_by (AIInsight .generated_at .desc ())
        .first ()
        )
        return {
        "ai_current_month":month_key ,
        "ai_latest_insight":latest ,
        "ai_configured":ai_insights .is_configured (),
        }

    @login_manager .user_loader 
    def load_user (user_id ):
        user =db .session .get (User ,int (user_id ))



        if user is None or not user .active :
            return None 
        return user 

    with app .app_context ():
        db .create_all ()
        _ensure_schema_upgrades ()
        _import_csv_if_present ()

    register_routes (app )
    return app 


def _ensure_schema_upgrades ():
    """
    db.create_all() only creates tables that don't exist yet — it never
    alters an existing table when a model gains a new column. Without
    this, anyone who already has an inventory.db from before a feature
    like wages/commission or cost snapshotting would hit "no such column"
    errors. This adds any missing columns by hand, and is safe to run on
    every startup (it checks before altering anything).

    For a project this size, this is a reasonable stand-in for a real
    migration tool. If the schema keeps growing, switch to Flask-Migrate.
    """
    inspector =inspect (db .engine )
    if "users"not in inspector .get_table_names ():
        return 

    with db .engine .begin ()as conn :
        user_columns ={c ["name"]for c in inspector .get_columns ("users")}
        if "fixed_wage"not in user_columns :
            conn .execute (text ("ALTER TABLE users ADD COLUMN fixed_wage FLOAT NOT NULL DEFAULT 0.0"))
        if "commission_percent"not in user_columns :
            conn .execute (text ("ALTER TABLE users ADD COLUMN commission_percent FLOAT NOT NULL DEFAULT 0.0"))

        sale_item_columns ={c ["name"]for c in inspector .get_columns ("sale_items")}
        if "unit_cost"not in sale_item_columns :
            conn .execute (text ("ALTER TABLE sale_items ADD COLUMN unit_cost FLOAT NOT NULL DEFAULT 0.0"))







            conn .execute (text ("""
                UPDATE sale_items
                SET unit_cost = (
                    SELECT COALESCE(p.cost_price, 0) + COALESCE(p.shipping_cost, 0)
                    FROM products p
                    WHERE p.id = sale_items.product_id
                )
                WHERE unit_cost = 0.0
            """))








        sale_columns ={c ["name"]for c in inspector .get_columns ("sales")}
        if "subtotal"not in sale_columns :
            conn .execute (text ("ALTER TABLE sales ADD COLUMN subtotal FLOAT NOT NULL DEFAULT 0.0"))





            conn .execute (text ("UPDATE sales SET subtotal = total WHERE subtotal = 0.0"))
        if "discount_percent"not in sale_columns :
            conn .execute (text ("ALTER TABLE sales ADD COLUMN discount_percent FLOAT NOT NULL DEFAULT 0.0"))


def owner_required (f ):
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
    @wraps (f )
    def wrapper (*args ,**kwargs ):
        if not current_user .is_owner :
            flash ("That page is only available to shop owners.","info")
            return redirect (url_for ("products"))
        return f (*args ,**kwargs )
    return wrapper 


def build_monthly_stats (year :int ,month :int )->dict :
    """
    Aggregates one calendar month of sales into a compact summary — this
    is what gets sent to the AI (see ai_insights.py), not raw database
    rows. Keeping the aggregation in plain Python here, separate from the
    prompt-building logic, means the AI module never touches SQLAlchemy
    at all and can be tested with a plain dict.
    """
    start ,end =local_month_to_utc_range (year ,month )
    sales =Sale .query .filter (Sale .created_at >=start ,Sale .created_at <end ).all ()

    turnover =round (sum (s .total for s in sales ),2 )
    discount_given =round (sum (s .discount_amount for s in sales ),2 )
    cost_of_goods =sum (item .quantity *item .unit_cost for s in sales for item in s .items )
    profit =round (turnover -cost_of_goods ,2 )





    product_stats :dict [str ,dict ]={}
    for s in sales :
        for item in s .items :
            entry =product_stats .setdefault (
            item .product_name ,{"quantity":0 ,"revenue":0.0 ,"cost":0.0 }
            )
            entry ["quantity"]+=item .quantity 
            entry ["revenue"]+=item .line_total 
            entry ["cost"]+=item .quantity *item .unit_cost 

    products =[
    {
    "name":name ,
    "quantity_sold":v ["quantity"],
    "revenue_usd":round (v ["revenue"],2 ),
    "profit_usd":round (v ["revenue"]-v ["cost"],2 ),
    }
    for name ,v in product_stats .items ()
    ]
    top_by_quantity =sorted (products ,key =lambda p :p ["quantity_sold"],reverse =True )[:5 ]
    slow_by_quantity =sorted (products ,key =lambda p :p ["quantity_sold"])[:5 ]

    employee_stats =[]
    for manager in User .query .filter_by (role =User .ROLE_MANAGER ).all ():
        manager_sales =[s for s in sales if s .user_id ==manager .id ]
        if not manager_sales :
            continue 
        employee_stats .append ({
        "username":manager .username ,
        "sales_count":len (manager_sales ),
        "revenue_usd":round (sum (s .total for s in manager_sales ),2 ),
        "commission_earned_usd":round (sum (s .commission_earned for s in manager_sales ),2 ),
        })

    return {
    "month":f"{year :04d}-{month :02d}",
    "currency":"USD",
    "sales_count":len (sales ),
    "turnover_usd":turnover ,
    "discount_given_usd":discount_given ,
    "profit_usd":profit ,
    "top_products_by_quantity":top_by_quantity ,
    "slow_products_by_quantity":slow_by_quantity ,
    "employees":employee_stats ,
    }


def _import_csv_if_present ():
    """
    One-time migration: if the database has no products yet and a
    data.csv from the old CLI tool exists next to this file, load it in.
    Old columns -> new columns:  id->sku, kind->name, cost->cost_price,
    shp->shipping_cost, price->sell_price, q->quantity
    """
    if Product .query .count ()>0 or not os .path .exists (CSV_PATH ):
        return 

    with open (CSV_PATH ,newline ="")as f :
        reader =csv .DictReader (f )
        imported =0 
        for row in reader :
            if row .get ("id")in (None ,"","id"):
                continue 
            try :
                db .session .add (Product (
                sku =row ["id"],
                name =row ["kind"],
                cost_price =float (row ["cost"]),
                shipping_cost =float (row ["shp"]),
                sell_price =float (row ["price"]),
                quantity =int (row ["q"]),
                ))
                imported +=1 
            except (KeyError ,ValueError ):
                continue 
        db .session .commit ()
        if imported :
            print (f"Imported {imported } products from {CSV_PATH }")


def register_routes (app :Flask ):


    @app .route ("/setup",methods =["GET","POST"])
    def setup ():
        """
        One-time first-run screen. Only reachable while the database has
        zero users. Creates the first owner account and logs them in.
        Once any account exists, this route just bounces to /login.
        """
        if User .query .count ()>0 :
            return redirect (url_for ("login"))

        if request .method =="POST":
            username =request .form ["username"].strip ()
            password =request .form ["password"]
            confirm =request .form ["confirm_password"]

            if not username or not password :
                flash ("Username and password are required.","info")
            elif password !=confirm :
                flash ("Passwords don't match.","info")
            elif (reason :=validate_password_strength (password )):
                flash (reason ,"info")
            else :
                owner =User (username =username ,role =User .ROLE_OWNER )
                owner .set_password (password )
                db .session .add (owner )
                db .session .commit ()
                login_user (owner )
                flash (f"Welcome, {owner .username } — your shop owner account is ready.","success")
                return redirect (url_for ("products"))

        return render_template ("setup.html")

    @app .route ("/login",methods =["GET","POST"])
    def login ():

        if User .query .count ()==0 :
            return redirect (url_for ("setup"))

        if current_user .is_authenticated :
            return redirect (url_for ("products"))

        if request .method =="POST":
            username =request .form ["username"].strip ()
            password =request .form ["password"]
            user =User .query .filter_by (username =username ).first ()

            if user and not user .active :
                flash ("This account has been deactivated.","info")
            elif user and user .check_password (password ):
                login_user (user )
                flash (f"Welcome back, {user .username }.","success")
                next_page =request .args .get ("next")
                return redirect (next_page or url_for ("products"))
            else :
                flash ("Invalid username or password.","info")

        return render_template ("login.html")

    @app .route ("/logout")
    @login_required 
    def logout ():
        logout_user ()
        flash ("Logged out.","info")
        return redirect (url_for ("login"))


    def _compute_employee_earnings (rows ):
        """
        Shared by the Employees page and its Excel export, so the two
        never have a chance to drift out of sync with each other. See
        the employees() route below for what this data means.
        """
        earnings ={}
        for emp in rows :
            if emp .role !=User .ROLE_MANAGER :
                continue 
            sales_count =len (emp .sales )
            revenue =round (sum (s .total for s in emp .sales ),2 )
            commission_earned =round (sum (s .commission_earned for s in emp .sales ),2 )
            earnings [emp .id ]={
            "sales_count":sales_count ,
            "revenue":revenue ,
            "commission_earned":commission_earned ,
            }
        return earnings 

    @app .route ("/employees")
    @login_required 
    @owner_required 
    def employees ():
        rows =User .query .order_by (User .role .desc (),User .username ).all ()






        earnings =_compute_employee_earnings (rows )

        return render_template ("employees.html",employees =rows ,earnings =earnings )

    @app .route ("/employees/export")
    @login_required 
    @owner_required 
    def export_employees ():
        rows =User .query .order_by (User .role .desc (),User .username ).all ()
        earnings =_compute_employee_earnings (rows )
        buffer =exports .build_employees_workbook (rows ,earnings )
        filename =f"employees_{local_today ().isoformat ()}.xlsx"
        return send_file (
        buffer ,
        as_attachment =True ,
        download_name =filename ,
        mimetype ="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app .route ("/employees/add",methods =["POST"])
    @login_required 
    @owner_required 
    def add_employee ():



        username =request .form ["username"].strip ()
        password =request .form ["password"]
        confirm =request .form ["confirm_password"]

        if not username or not password :
            flash ("Username and password are required.","info")
        elif password !=confirm :
            flash ("Passwords don't match.","info")
        elif (reason :=validate_password_strength (password )):
            flash (reason ,"info")
        elif User .query .filter_by (username =username ).first ():
            flash ("That username is already taken.","info")
        else :
            try :
                fixed_wage =float (request .form ["fixed_wage"])
                commission_percent =float (request .form ["commission_percent"])
            except ValueError :
                flash ("Wage and commission must be numbers.","info")
                return redirect (url_for ("employees"))

            if fixed_wage <0 or commission_percent <0 :
                flash ("Wage and commission can't be negative.","info")
                return redirect (url_for ("employees"))

            manager =User (username =username ,role =User .ROLE_MANAGER ,
            fixed_wage =fixed_wage ,commission_percent =commission_percent )
            manager .set_password (password )
            db .session .add (manager )
            db .session .commit ()
            flash (f'Added sales manager "{username }".',"success")

        return redirect (url_for ("employees"))

    @app .route ("/employees/<int:user_id>/promote",methods =["POST"])
    @login_required 
    @owner_required 
    def promote_employee (user_id ):
        employee =User .query .get_or_404 (user_id )
        if employee .role ==User .ROLE_MANAGER :
            employee .role =User .ROLE_OWNER 
            db .session .commit ()
            flash (f"{employee .username } is now a shop owner.","success")
        return redirect (url_for ("employees"))

    @app .route ("/employees/<int:user_id>/fire",methods =["POST"])
    @login_required 
    @owner_required 
    def fire_employee (user_id ):
        employee =User .query .get_or_404 (user_id )
        if employee .id ==current_user .id :
            flash ("You can't fire your own account.","info")
        elif employee .role ==User .ROLE_OWNER :
            flash ("Owners can't be fired from this screen.","info")
        else :
            employee .active =False 
            db .session .commit ()
            flash (f"{employee .username } has been removed.","info")
        return redirect (url_for ("employees"))

    @app .route ("/employees/<int:user_id>/reinstate",methods =["POST"])
    @login_required 
    @owner_required 
    def reinstate_employee (user_id ):
        employee =User .query .get_or_404 (user_id )
        employee .active =True 
        db .session .commit ()
        flash (f"{employee .username } reinstated.","success")
        return redirect (url_for ("employees"))

    @app .route ("/employees/<int:user_id>/pay",methods =["POST"])
    @login_required 
    @owner_required 
    def update_employee_pay (user_id ):
        employee =User .query .get_or_404 (user_id )
        try :
            fixed_wage =float (request .form ["fixed_wage"])
            commission_percent =float (request .form ["commission_percent"])
        except ValueError :
            flash ("Wage and commission must be numbers.","info")
            return redirect (url_for ("employees"))

        if fixed_wage <0 or commission_percent <0 :
            flash ("Wage and commission can't be negative.","info")
            return redirect (url_for ("employees"))

        employee .fixed_wage =fixed_wage 
        employee .commission_percent =commission_percent 
        db .session .commit ()
        flash (f"Updated pay for {employee .username }.","success")
        return redirect (url_for ("employees"))





    @app .route ("/dashboard")
    @login_required 
    @owner_required 
    def dashboard ():
        date_param =request .args .get ("date")
        try :
            selected_date =datetime .strptime (date_param ,"%Y-%m-%d").date ()if date_param else local_today ()
        except ValueError :
            selected_date =local_today ()

        day_start ,day_end =local_day_to_utc_range (selected_date )

        sales_today =Sale .query .filter (
        Sale .created_at >=day_start ,Sale .created_at <day_end 
        ).order_by (Sale .created_at ).all ()

        turnover =round (sum (s .total for s in sales_today ),2 )
        items_sold =sum (item .quantity for s in sales_today for item in s .items )










        cost_of_goods =sum (item .quantity *item .unit_cost 
        for s in sales_today for item in s .items )
        profit =round (turnover -cost_of_goods ,2 )

        discount_given =round (sum (s .discount_amount for s in sales_today ),2 )

        by_employee ={}
        for s in sales_today :
            if not s .user :
                continue 
            row =by_employee .setdefault (s .user .id ,{
            "username":s .user .username ,
            "sales_count":0 ,
            "revenue":0.0 ,
            "commission_percent":s .user .commission_percent ,
            })
            row ["sales_count"]+=1 
            row ["revenue"]+=s .total 

        for row in by_employee .values ():
            row ["revenue"]=round (row ["revenue"],2 )
            row ["commission_earned"]=round (row ["revenue"]*row ["commission_percent"]/100 ,2 )

        return render_template (
        "dashboard.html",
        selected_date =selected_date ,
        today =local_today ().isoformat (),
        sales_count =len (sales_today ),
        items_sold =items_sold ,
        turnover =turnover ,
        profit =profit ,
        discount_given =discount_given ,
        breakdown =sorted (by_employee .values (),key =lambda r :r ["username"]),
        )






    @app .route ("/api/ai-insights/generate",methods =["POST"])
    @login_required 
    @owner_required 
    def generate_ai_insight ():
        today =local_today ()
        stats =build_monthly_stats (today .year ,today .month )

        try :
            content =ai_insights .generate_monthly_insight (stats )
        except ai_insights .AIInsightsUnavailable as exc :



            return jsonify ({"error":str (exc )}),503 

        insight =AIInsight (month =stats ["month"],content_json =json .dumps (content ))
        db .session .add (insight )
        db .session .commit ()

        return jsonify ({
        "month":insight .month ,
        "generated_at":utc_to_local (insight .generated_at ).strftime ("%Y-%m-%d %H:%M"),
        **content ,
        })





    @app .route ("/")
    @login_required 
    def index ():
        return redirect (url_for ("products"))

    @app .route ("/products")
    @login_required 
    def products ():
        rows =Product .query .order_by (Product .name ).all ()
        return render_template ("products.html",products =rows )

    @app .route ("/products/export")
    @login_required 
    def export_products ():



        rows =Product .query .order_by (Product .name ).all ()
        buffer =exports .build_products_workbook (rows )
        filename =f"inventory_{local_today ().isoformat ()}.xlsx"
        return send_file (
        buffer ,
        as_attachment =True ,
        download_name =filename ,
        mimetype ="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


    @app .route ("/products/add",methods =["GET","POST"])
    @login_required 
    @owner_required 
    def add_product ():
        if request .method =="POST":
            sku =request .form ["sku"].strip ()
            existing =Product .query .filter_by (sku =sku ).first ()

            if existing :

                existing .quantity +=int (request .form ["quantity"])
                existing .cost_price =float (request .form ["cost_price"])
                existing .shipping_cost =float (request .form ["shipping_cost"])
                existing .sell_price =float (request .form ["sell_price"])
                db .session .commit ()
                flash (f'Restocked "{existing .name }" (SKU {sku }).',"success")
            else :
                product =Product (
                sku =sku ,
                name =request .form ["name"].strip (),
                cost_price =float (request .form ["cost_price"]),
                shipping_cost =float (request .form ["shipping_cost"]),
                sell_price =float (request .form ["sell_price"]),
                quantity =int (request .form ["quantity"]),
                )
                db .session .add (product )
                db .session .commit ()
                flash (f'Added "{product .name }" to inventory.',"success")

            return redirect (url_for ("products"))

        return render_template ("product_form.html",product =None )

    @app .route ("/products/<int:product_id>/edit",methods =["GET","POST"])
    @login_required 
    @owner_required 
    def edit_product (product_id ):
        product =Product .query .get_or_404 (product_id )

        if request .method =="POST":
            product .sku =request .form ["sku"].strip ()
            product .name =request .form ["name"].strip ()
            product .cost_price =float (request .form ["cost_price"])
            product .shipping_cost =float (request .form ["shipping_cost"])
            product .sell_price =float (request .form ["sell_price"])
            product .quantity =int (request .form ["quantity"])
            db .session .commit ()
            flash (f'Updated "{product .name }".',"success")
            return redirect (url_for ("products"))

        return render_template ("product_form.html",product =product )

    @app .route ("/products/<int:product_id>/delete",methods =["POST"])
    @login_required 
    @owner_required 
    def delete_product (product_id ):
        product =Product .query .get_or_404 (product_id )
        db .session .delete (product )
        db .session .commit ()
        flash (f'Deleted "{product .name }".',"info")
        return redirect (url_for ("products"))






    @app .route ("/sell")
    @login_required 
    def sell ():
        cart =session .get ("cart",[])
        subtotal =round (sum (item ["quantity"]*item ["unit_price"]for item in cart ),2 )
        discount_percent =session .get ("cart_discount_percent",0.0 )
        total =round (subtotal *(1 -discount_percent /100 ),2 )
        available_products =Product .query .filter (Product .quantity >0 ).order_by (Product .name ).all ()
        return render_template ("sell.html",cart =cart ,subtotal =subtotal ,
        discount_percent =discount_percent ,total =total ,
        products =available_products )

    @app .route ("/sell/add",methods =["POST"])
    @login_required 
    def sell_add ():
        product =Product .query .get_or_404 (int (request .form ["product_id"]))
        quantity =int (request .form ["quantity"])



        if quantity <=0 or not product .in_stock (quantity ):
            flash (f"Not enough stock for {product .name } "
            f"(have {product .quantity }, asked for {quantity }).","info")
            return redirect (url_for ("sell"))

        product .quantity -=quantity 
        db .session .commit ()

        cart =session .get ("cart",[])
        cart .append ({
        "product_id":product .id ,
        "name":product .name ,
        "quantity":quantity ,
        "unit_price":product .sell_price ,
        })
        session ["cart"]=cart 
        flash (f"Added {quantity } × {product .name } to the sale.","success")
        return redirect (url_for ("sell"))

    @app .route ("/sell/discount",methods =["POST"])
    @login_required 
    def set_cart_discount ():
        """
        Applies a discount to the whole checkout, not any single product —
        this is a wholesale app, so a discount is normally a deal on the
        entire order, not a markdown on one item. Open to both roles
        equally: unlike Buy/Edit/Delete, there's no @owner_required (or
        equivalent) here on purpose.
        """
        try :
            discount_percent =float (request .form ["discount_percent"])
        except (KeyError ,ValueError ):
            flash ("Discount must be a number.","info")
            return redirect (url_for ("sell"))

        if not (0 <=discount_percent <=100 ):
            flash ("Discount must be between 0 and 100.","info")
            return redirect (url_for ("sell"))

        session ["cart_discount_percent"]=discount_percent 
        if discount_percent :
            flash (f"{discount_percent :g}% discount applied to this checkout.","success")
        else :
            flash ("Discount removed from this checkout.","info")
        return redirect (url_for ("sell"))

    @app .route ("/sell/cancel",methods =["POST"])
    @login_required 
    def sell_cancel ():
        """Abandon the current sale and restock everything in the cart."""
        cart =session .pop ("cart",[])
        session .pop ("cart_discount_percent",None )
        for item in cart :
            product =Product .query .get (item ["product_id"])
            if product :
                product .quantity +=item ["quantity"]
        db .session .commit ()
        flash ("Sale cancelled — items restocked.","info")
        return redirect (url_for ("sell"))

    @app .route ("/sell/checkout",methods =["POST"])
    @login_required 
    def checkout ():
        cart =session .pop ("cart",[])
        discount_percent =session .pop ("cart_discount_percent",0.0 )
        if not cart :
            flash ("Cart is empty — nothing to check out.","info")
            return redirect (url_for ("sell"))

        subtotal =round (sum (item ["quantity"]*item ["unit_price"]for item in cart ),2 )
        total =round (subtotal *(1 -discount_percent /100 ),2 )

        sale =Sale (subtotal =subtotal ,discount_percent =discount_percent ,
        total =total ,user_id =current_user .id )
        for item in cart :
            product =Product .query .get (item ["product_id"])
            unit_cost =(product .cost_price +product .shipping_cost )if product else 0.0 
            sale .items .append (SaleItem (
            product_id =item ["product_id"],
            product_name =item ["name"],
            quantity =item ["quantity"],
            unit_price =item ["unit_price"],
            unit_cost =unit_cost ,
            ))
        db .session .add (sale )
        db .session .commit ()

        return redirect (url_for ("receipt",sale_id =sale .id ))



    @app .route ("/sales")
    @login_required 
    def sales ():
        query =Sale .query .order_by (Sale .created_at .desc ())
        if not current_user .is_owner :
            query =query .filter_by (user_id =current_user .id )
        return render_template ("sales.html",sales =query .all ())

    @app .route ("/sales/export")
    @login_required 
    def export_sales ():



        query =Sale .query .order_by (Sale .created_at .desc ())
        if not current_user .is_owner :
            query =query .filter_by (user_id =current_user .id )
        buffer =exports .build_sales_workbook (query .all (),show_sold_by =current_user .is_owner )
        filename =f"sales_{local_today ().isoformat ()}.xlsx"
        return send_file (
        buffer ,
        as_attachment =True ,
        download_name =filename ,
        mimetype ="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app .route ("/sales/<int:sale_id>")
    @login_required 
    def receipt (sale_id ):
        sale =Sale .query .get_or_404 (sale_id )
        if not current_user .is_owner and sale .user_id !=current_user .id :
            flash ("You can only view your own sales.","info")
            return redirect (url_for ("sales"))
        return render_template ("receipt.html",sale =sale )


if __name__ =="__main__":
    app =create_app ()




    app .run (debug =os .environ .get ("FLASK_DEBUG")=="1")
