import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, current_app
from config import Config
from extensions import db, login_manager, csrf
from models import User, Product, Category, Order, OrderItem, OrderAddress, WishlistItem, Coupon
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from decimal import Decimal

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Send unauthenticated visitors to the correct sign-in screen. The admin
    # login is intentionally not linked from the public storefront.
    @login_manager.unauthorized_handler
    def _unauthorized():
        if request.path.startswith("/admin"):
            return redirect(url_for("admin.login", next=request.full_path))
        return redirect(url_for("auth.login", next=request.full_path))

    # Safe, idempotent compatibility migration. Older BANS databases may not
    # have the new commerce tables/columns; initialize them before template
    # context processors query StoreSetting (the previous cause of HTTP 500).
    @app.before_request
    def _ensure_bans_schema():
        if app.extensions.get("bans_schema_ready"):
            return None
        from sqlalchemy import inspect, text
        from commerce import DEFAULTS, StoreSetting
        db.create_all()
        additions = {
            "product": {"sku": "VARCHAR(80)", "category_name": "VARCHAR(100) DEFAULT 'Signature'", "fragrance_family": "VARCHAR(100) DEFAULT ''", "available_sizes": "VARCHAR(120) DEFAULT '50ml, 100ml'", "video_url": "VARCHAR(500) DEFAULT ''"},
            "coupon": {"minimum_order": "NUMERIC(10,2) DEFAULT 0", "maximum_discount": "NUMERIC(10,2)", "usage_limit": "INTEGER", "used_count": "INTEGER DEFAULT 0", "expires_at": "DATETIME"},
            "order": {"courier_name": "VARCHAR(120) DEFAULT ''", "tracking_number": "VARCHAR(120) DEFAULT ''", "tracking_url": "VARCHAR(500) DEFAULT ''"}
        }
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        for table, columns in additions.items():
            if table not in tables:
                continue
            present = {col["name"] for col in inspect(db.engine).get_columns(table)}
            for column, definition in columns.items():
                if column not in present:
                    db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'))
        for key, value in DEFAULTS.items():
            if not StoreSetting.query.filter_by(key=key).first():
                db.session.add(StoreSetting(key=key, value=value))
        db.session.commit()
        app.extensions["bans_schema_ready"] = True
        return None

    from auth import auth_bp
    from admin import admin_bp
    from orders import orders_bp
    from payment import payment_bp
    from commerce import StoreSetting, PaymentTransaction, setting
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(orders_bp, url_prefix="/orders")
    app.register_blueprint(payment_bp)

    @app.context_processor
    def shared():
        cart = session.get("cart", {})
        count = sum(int(v) for v in cart.values())
        return {"cart_count": count, "store_announcement": setting("announcement", "B BANS · THE ART OF YOUR SIGNATURE SCENT"), "store_contact_email": setting("contact_email", ""), "store_contact_phone": setting("contact_phone", ""), "cart_coupon_code": session.get('coupon_code','')}

    @app.route("/")
    def index():
        # Always show active catalogue products on the homepage. Product flags
        # are merchandising labels, not prerequisites for products to appear.
        all_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
        featured = Product.query.filter_by(is_active=True, is_featured=True).order_by(Product.created_at.desc()).limit(8).all()
        bestsellers = Product.query.filter_by(is_active=True, is_bestseller=True).order_by(Product.created_at.desc()).limit(8).all()
        new_arrivals = Product.query.filter_by(is_active=True, is_new=True).order_by(Product.created_at.desc()).limit(8).all()

        # Graceful fallbacks ensure a newly-added product is visible without
        # requiring the admin to tick Featured/Bestseller/New Arrival.
        if not featured:
            featured = all_products[:8]
        if not bestsellers:
            bestsellers = [p for p in all_products if p not in featured][:8] or all_products[:8]
        if not new_arrivals:
            new_arrivals = all_products[:8]

        from commerce import setting, StoreOffer, HomeBanner
        active_offers = StoreOffer.query.filter_by(active=True).order_by(StoreOffer.id.desc()).all()
        banners = HomeBanner.query.filter_by(active=True).order_by(HomeBanner.sort_order, HomeBanner.id.desc()).all()
        return render_template("index.html", featured=featured, bestsellers=bestsellers, new_arrivals=new_arrivals,
                               hero_title=setting('hero_title'), hero_subtitle=setting('hero_subtitle'),
                               active_offers=active_offers, banners=banners, catalogue_count=len(all_products))

    @app.route("/shop")
    def shop():
        q = request.args.get("q", "").strip()
        gender = request.args.get("gender", "")
        query = Product.query.filter_by(is_active=True)
        if q: query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.description.ilike(f"%{q}%")))
        if gender: query = query.filter_by(gender=gender)
        sort = request.args.get("sort")
        if sort == "price_low": query = query.order_by(Product.price.asc())
        elif sort == "price_high": query = query.order_by(Product.price.desc())
        else: query = query.order_by(Product.created_at.desc())
        return render_template("shop.html", products=query.all(), q=q, gender=gender)

    @app.route("/product/<slug>")
    def product(slug):
        item = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
        related = Product.query.filter(Product.id != item.id, Product.is_active.is_(True)).limit(4).all()
        return render_template("product.html", product=item, related=related)

    @app.route("/collections")
    def collections(): return render_template("collections.html")
    @app.route("/men")
    def men(): return render_template("shop.html", products=Product.query.filter_by(gender="Men", is_active=True).all(), q="", gender="Men")
    @app.route("/women")
    def women(): return render_template("shop.html", products=Product.query.filter_by(gender="Women", is_active=True).all(), q="", gender="Women")
    @app.route("/unisex")
    def unisex(): return render_template("shop.html", products=Product.query.filter_by(gender="Unisex", is_active=True).all(), q="", gender="Unisex")
    @app.route("/about")
    def about(): return render_template("about.html")
    @app.route("/contact")
    def contact(): return render_template("contact.html")
    @app.route("/faq")
    def faq(): return render_template("faq.html")
    @app.route("/privacy")
    def privacy(): return render_template("policy.html", title="Privacy Policy")
    @app.route("/terms")
    def terms(): return render_template("policy.html", title="Terms & Conditions")
    @app.route("/shipping-policy")
    def shipping_policy(): return render_template("policy.html", title="Shipping Policy")
    @app.route("/refund")
    def refund(): return render_template("policy.html", title="Returns & Refunds")

    @app.route("/cart")
    def cart():
        cart_data = session.get("cart", {})
        items, total = [], Decimal("0.00")
        for pid, qty in cart_data.items():
            p = db.session.get(Product, int(pid))
            if p and p.is_active:
                line = p.price * int(qty); total += line
                items.append({"product": p, "qty": int(qty), "line": line})
        return render_template("cart.html", items=items, total=total)

    @app.post("/cart/coupon")
    def apply_coupon():
        code = request.form.get('coupon_code','').strip().upper()
        coupon = Coupon.query.filter(Coupon.code == code, Coupon.active.is_(True), or_(Coupon.expires_at.is_(None), Coupon.expires_at > datetime.utcnow())).first() if code else None
        if coupon:
            session['coupon_code'] = code; flash(f'Coupon {code} applied.', 'success')
        else:
            session.pop('coupon_code', None); flash('Coupon code is invalid or inactive.', 'error')
        return redirect(url_for('cart'))

    @app.post("/cart/add/<int:product_id>")
    def add_to_cart(product_id):
        p = db.session.get(Product, product_id)
        if not p or not p.is_active: flash("Product unavailable.", "error")
        elif p.stock < 1: flash("This fragrance is currently out of stock.", "error")
        else:
            cart = session.get("cart", {})
            cart[str(product_id)] = min(int(cart.get(str(product_id), 0)) + 1, p.stock)
            session["cart"] = cart
            flash("Added to your bag.", "success")
        return redirect(request.referrer or url_for("shop"))

    @app.post("/cart/update")
    def update_cart():
        cart = session.get("cart", {})
        for pid, qty in request.form.items():
            try:
                p = db.session.get(Product, int(pid)); n = max(0, int(qty))
                if p: 
                    if n: cart[pid] = min(n, p.stock)
                    else: cart.pop(pid, None)
            except (ValueError, TypeError): continue
        session["cart"] = cart
        return redirect(url_for("cart"))

    @app.route("/wishlist")
    @login_required
    def wishlist():
        rows = WishlistItem.query.filter_by(user_id=current_user.id).all()
        return render_template("wishlist.html", products=[r.product for r in rows])

    @app.post("/wishlist/toggle/<int:product_id>")
    @login_required
    def wishlist_toggle(product_id):
        p = db.session.get(Product, product_id)
        if p:
            row = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if row: db.session.delete(row)
            else: db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
            db.session.commit()
        return redirect(request.referrer or url_for("shop"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        cart = session.get("cart", {})
        if not cart:
            flash("Your bag is empty.", "info")
            return redirect(url_for("cart"))
        items, total = [], Decimal("0.00")
        for pid, qty in cart.items():
            try:
                p = db.session.get(Product, int(pid))
                quantity = int(qty)
            except (ValueError, TypeError):
                continue
            if p and p.is_active and quantity > 0:
                if quantity > p.stock:
                    flash(f"Only {p.stock} unit(s) of {p.name} are currently available.", "error")
                    return redirect(url_for("cart"))
                total += p.price * quantity
                items.append((p, quantity))
        if not items:
            session["cart"] = {}
            flash("Your bag has no available products.", "error")
            return redirect(url_for("cart"))
        coupon_code = session.get('coupon_code','')
        coupon = Coupon.query.filter(Coupon.code == coupon_code, Coupon.active.is_(True), or_(Coupon.expires_at.is_(None), Coupon.expires_at > datetime.utcnow())).first() if coupon_code else None
        discount = Decimal('0.00')
        if coupon and total >= (coupon.minimum_order or Decimal('0')) and (not coupon.usage_limit or coupon.used_count < coupon.usage_limit):
            discount = (total * coupon.amount / Decimal('100')).quantize(Decimal('0.01')) if coupon.discount_type == 'percentage' else min(total, coupon.amount)
            if coupon.maximum_discount: discount = min(discount, coupon.maximum_discount)
        elif coupon:
            flash('Coupon minimum cart value or usage limit has not been met.', 'error')
            coupon = None; session.pop('coupon_code', None); coupon_code = ''
        if request.method == "POST":
            fields = {key: request.form.get(key, "").strip() for key in ["full_name", "phone", "email", "address_line", "landmark", "city", "state", "pincode"]}
            required = ["full_name", "phone", "email", "address_line", "city", "state", "pincode"]
            if any(not fields[k] for k in required):
                flash("Please complete all required delivery details.", "error")
            elif not fields["phone"].replace("+", "").replace(" ", "").isdigit() or len(fields["phone"].replace("+", "").replace(" ", "")) < 10:
                flash("Enter a valid mobile number.", "error")
            elif not fields["pincode"].isdigit() or len(fields["pincode"]) != 6:
                flash("Enter a valid 6-digit PIN code.", "error")
            elif "@" not in fields["email"]:
                flash("Enter a valid email address.", "error")
            else:
                method = request.form.get("payment_method", "online")
                if method not in {"online", "cod"}:
                    method = "online"
                from commerce import setting, PaymentTransaction
                online_enabled = setting("online_enabled", "1") == "1"
                cod_enabled = setting("cod_enabled", "1") == "1"
                if method == "online" and not online_enabled:
                    flash("Online payment is currently unavailable.", "error")
                elif method == "cod" and not cod_enabled:
                    flash("Cash on Delivery is currently unavailable.", "error")
                else:
                    shipping = Decimal(setting("shipping_charge", "79"))
                    free_limit = Decimal(setting("free_shipping_threshold", "1499"))
                    shipping = Decimal("0") if (total - discount) >= free_limit else shipping
                    final_total = max(Decimal('0.00'), total - discount) + shipping
                    advance = min(Decimal(setting("cod_advance", "50")), final_total) if method == "cod" else final_total
                    order = Order(
                        user_id=current_user.id,
                        total=final_total,
                        status="Payment Pending" if method == "online" else "Awaiting COD Advance",
                        payment_method="Online" if method == "online" else f"COD - ₹{advance:.2f} Advance"
                    )
                    try:
                        db.session.add(order)
                        db.session.flush()  # Allocate the order ID before related rows.
                        for product, quantity in items:
                            db.session.add(OrderItem(
                                order_id=order.id,
                                product_id=product.id,
                                product_name=product.name,
                                quantity=quantity,
                                unit_price=product.price
                            ))
                        db.session.add(OrderAddress(order_id=order.id, **fields))
                        db.session.add(PaymentTransaction(
                            order_id=order.id,
                            kind="prepaid" if method == "online" else "cod_advance",
                            amount_paise=int(advance * 100),
                            status="created"
                        ))
                        if coupon and discount > 0:
                            coupon.used_count = (coupon.used_count or 0) + 1
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception("Checkout order creation failed")
                        flash("We could not place your order due to a temporary issue. Your cart is safe—please try again. If it continues, contact support.", "error")
                        return redirect(url_for("checkout"))
                    session["cart"] = {}
                    session.pop("coupon_code", None)
                    return redirect(url_for("payment.start", order_id=order.id))
        from commerce import setting
        return render_template("checkout.html", items=items, total=total, discount=discount, shipping_charge=setting("shipping_charge", "79"), free_shipping_threshold=setting("free_shipping_threshold", "1499"), cod_enabled=setting("cod_enabled", "1") == "1", online_enabled=setting("online_enabled", "1") == "1", cod_advance=setting("cod_advance", "50"), coupon_code=coupon_code)

    @app.route("/order-confirmation/<int:order_id>")
    @login_required
    def order_confirmation(order_id):
        order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
        return render_template("order-confirmation.html", order=order)

    @app.route("/account")
    @login_required
    def account():
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        customer_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        recent_address = customer_orders[0].delivery_address if customer_orders else None
        total_spent = sum((o.total for o in customer_orders if o.status not in {"Cancelled", "Payment Pending", "Awaiting COD Advance"}), Decimal("0.00"))
        return render_template("account.html", orders=customer_orders[:5], order_count=len(customer_orders),
                               total_spent=total_spent, recent_address=recent_address)

    @app.post("/account/profile")
    @login_required
    def update_customer_profile():
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        duplicate = User.query.filter(User.email == email, User.id != current_user.id).first() if email else None
        if not name or not email or "@" not in email or duplicate:
            flash("Enter a valid name and email. That email may already be in use.", "error")
        elif phone and (not phone.replace("+", "").replace(" ", "").isdigit() or len(phone.replace("+", "").replace(" ", "")) < 10):
            flash("Enter a valid mobile number.", "error")
        else:
            current_user.name, current_user.email, current_user.phone = name, email, phone
            db.session.commit()
            flash("Your account information has been updated.", "success")
        return redirect(url_for("account"))

    @app.route("/orders")
    @login_required
    def my_orders():
        return render_template("orders.html", orders=Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all())

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        from commerce import DEFAULTS, StoreSetting
        for key, value in DEFAULTS.items():
            if not StoreSetting.query.filter_by(key=key).first(): db.session.add(StoreSetting(key=key, value=value))
        if not Category.query.first():
            db.session.add_all([Category(name=n, slug=n.lower()) for n in ["Signature", "Men", "Women", "Unisex"]])
        if not Product.query.first():
            samples = [
                Product(name="Éclat No. 01", slug="eclat-no-01", description="A luminous blend of citrus, jasmine and warm woods.", gender="Unisex", price=Decimal("1299"), mrp=Decimal("1699"), stock=30, is_featured=True, is_bestseller=True, notes_top="Bergamot, Mandarin", notes_heart="Jasmine, Neroli", notes_base="Cedarwood, Musk"),
                Product(name="Velvet Oud", slug="velvet-oud", description="Deep woods softened with amber and a velvety finish.", gender="Men", price=Decimal("1599"), mrp=Decimal("1999"), stock=24, is_featured=True, notes_top="Saffron", notes_heart="Rose, Oud", notes_base="Amber, Sandalwood"),
                Product(name="Rose Lumière", slug="rose-lumiere", description="A graceful floral signature with a soft musky trail.", gender="Women", price=Decimal("1199"), mrp=Decimal("1499"), stock=35, is_new=True, notes_top="Pear", notes_heart="Rose, Peony", notes_base="White Musk"),
                Product(name="Santal Veil", slug="santal-veil", description="Creamy sandalwood, spice and skin-like warmth.", gender="Unisex", price=Decimal("1399"), mrp=Decimal("1799"), stock=18, is_bestseller=True, notes_top="Cardamom", notes_heart="Iris", notes_base="Sandalwood, Vanilla"),
            ]
            db.session.add_all(samples)
        db.session.commit()
        print("BANS database initialized with sample products.")

    @app.cli.command("upgrade-db")
    def upgrade_db():
        """Create new tables and add compatible columns to an existing SQLite database."""
        from sqlalchemy import inspect, text
        db.create_all()
        inspector = inspect(db.engine)
        additions = {
            'product': {
                'sku': 'VARCHAR(80)', 'category_name': "VARCHAR(100) DEFAULT 'Signature'",
                'fragrance_family': "VARCHAR(100) DEFAULT ''", 'available_sizes': "VARCHAR(120) DEFAULT '50ml, 100ml'",
                'video_url': "VARCHAR(500) DEFAULT ''"
            },
            'coupon': {
                'minimum_order': 'NUMERIC(10,2) DEFAULT 0', 'maximum_discount': 'NUMERIC(10,2)',
                'usage_limit': 'INTEGER', 'used_count': 'INTEGER DEFAULT 0', 'expires_at': 'DATETIME'
            },
            'order': {
                'courier_name': "VARCHAR(120) DEFAULT ''", 'tracking_number': "VARCHAR(120) DEFAULT ''",
                'tracking_url': "VARCHAR(500) DEFAULT ''"
            }
        }
        for table, columns in additions.items():
            if table not in inspector.get_table_names(): continue
            present = {col['name'] for col in inspect(db.engine).get_columns(table)}
            for column, definition in columns.items():
                if column not in present:
                    db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'))
        from commerce import DEFAULTS, StoreSetting
        for key, value in DEFAULTS.items():
            if not StoreSetting.query.filter_by(key=key).first(): db.session.add(StoreSetting(key=key, value=value))
        db.session.commit()
        print('BANS database upgraded. Existing products, customers and orders were preserved.')

    @app.cli.command("create-admin")
    def create_admin():
        import getpass
        email = input("Admin email: ").strip().lower()
        password = getpass.getpass("Admin password (12+ characters): ")
        if len(password) < 12: raise SystemExit("Password must be at least 12 characters.")
        if User.query.filter_by(email=email).first(): raise SystemExit("User already exists.")
        db.session.add(User(name="B BANS Administrator", email=email, password_hash=generate_password_hash(password), is_admin=True))
        db.session.commit()
        print("Admin created. Sign in at /auth/login.")

    return app

app = create_app()
if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
