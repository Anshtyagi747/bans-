from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user, login_user
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse
from extensions import db
from models import Product, Order, User, Category, Coupon
from decimal import Decimal, InvalidOperation
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path
from PIL import Image
from io import BytesIO
import uuid

admin_bp = Blueprint("admin", __name__)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

def admin_required():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)

def save_product_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Upload JPG, PNG or WebP images only.")
    data = file.read()
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Image must be smaller than 5 MB.")
    try:
        image = Image.open(BytesIO(data))
        image.verify()
    except Exception:
        raise ValueError("The uploaded file is not a valid image.")
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((1800, 1800))
    filename = f"{uuid.uuid4().hex}.webp"
    folder = Path(current_app.root_path) / "static" / "uploads" / "products"
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / filename, "WEBP", quality=88, optimize=True)
    return f"uploads/products/{filename}"


@admin_bp.route("/login", methods=["GET", "POST"])

def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Temporary demo login
        # Temporary demo admin login
if email == "demo@bans.com" and password == "BANSdemo123":

    user = User.query.filter_by(email="demo@bans.com").first()

    if not user:
        existing_admin = User.query.filter_by(is_admin=True).first()

        if existing_admin:
            flash("An admin account already exists. Demo account creation disabled.", "error")
            return redirect(url_for("admin.login"))

        user = User(
            name="BANS Demo Admin",
            email="demo@bans.com",
            password_hash=generate_password_hash("BANSdemo123"),
            is_admin=True
        )

        db.session.add(user)
        db.session.commit()

    if not user.is_admin:
        flash("This account is not an administrator.", "error")
        return redirect(url_for("admin.login"))

    login_user(user)
    return redirect(url_for("admin.dashboard"))

        user = User.query.filter_by(email=email, is_admin=True).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            target = request.args.get("next", "")
            parsed = urlparse(target)

            if target.startswith("/admin/") and not parsed.netloc:
                return redirect(target)

            return redirect(url_for("admin.dashboard"))

        flash("Administrator email or password is incorrect.", "error")

    return render_template("admin/login.html")

@admin_bp.route("/")
@login_required
def dashboard():
    admin_required()
    orders = Order.query.all()
    return render_template(
        "admin/dashboard.html",
        products=Product.query.count(),
        orders=len(orders),
        customers=User.query.filter_by(is_admin=False).count(),
        revenue=sum((o.total for o in orders if o.status != "Cancelled"), Decimal("0.00")),
        pending=sum(1 for o in orders if o.status == "Pending"),
        low_stock=Product.query.filter(Product.is_active.is_(True), Product.stock <= 5).count()
    )

@admin_bp.route("/products")
@login_required
def products():
    admin_required()
    return render_template("admin/products.html", products=Product.query.order_by(Product.created_at.desc()).all())

@admin_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def add_product():
    admin_required()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower()
        try:
            price = Decimal(request.form.get("price", "0"))
            mrp = Decimal(request.form.get("mrp", "0"))
            stock = int(request.form.get("stock", "0"))
        except (InvalidOperation, ValueError):
            flash("Check price and stock values.", "error")
            return redirect(url_for("admin.add_product"))
        if not name or not slug or price <= 0 or mrp < price or stock < 0:
            flash("Please enter valid product details. MRP must be at least the selling price.", "error")
            return redirect(url_for("admin.add_product"))
        if Product.query.filter_by(slug=slug).first():
            flash("That product URL already exists.", "error")
            return redirect(url_for("admin.add_product"))
        try:
            image_path = save_product_image(request.files.get("image"))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.add_product"))
        p = Product(
            name=name, slug=slug, description=request.form.get("description", ""),
            gender=request.form.get("gender", "Unisex"), price=price, mrp=mrp,
            stock=stock, image=image_path or "", notes_top=request.form.get("top", ""),
            notes_heart=request.form.get("heart", ""), notes_base=request.form.get("base", ""),
            sku=request.form.get("sku", "").strip() or None, category_name=request.form.get("category_name", "Signature").strip(),
            fragrance_family=request.form.get("fragrance_family", "").strip(), available_sizes=request.form.get("available_sizes", "50ml, 100ml").strip(),
            video_url=request.form.get("video_url", "").strip(),
            is_featured=bool(request.form.get("featured")),
            is_bestseller=bool(request.form.get("bestseller")),
            is_new=bool(request.form.get("new"))
        )
        db.session.add(p)
        db.session.commit()
        flash("Product created successfully.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product-form.html", product=None)

@admin_bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit_product(pid):
    admin_required()
    p = db.session.get(Product, pid) or abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower()
        try:
            price = Decimal(request.form.get("price", "0"))
            mrp = Decimal(request.form.get("mrp", "0"))
            stock = int(request.form.get("stock", "0"))
        except (InvalidOperation, ValueError):
            flash("Check price and stock values.", "error")
            return redirect(url_for("admin.edit_product", pid=pid))
        duplicate = Product.query.filter(Product.slug == slug, Product.id != pid).first()
        if not name or not slug or price <= 0 or mrp < price or stock < 0 or duplicate:
            flash("Please check required fields, price/MRP, stock and unique slug.", "error")
            return redirect(url_for("admin.edit_product", pid=pid))
        try:
            new_image = save_product_image(request.files.get("image"))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.edit_product", pid=pid))
        p.name, p.slug, p.price, p.mrp, p.stock = name, slug, price, mrp, stock
        p.description = request.form.get("description", "")
        p.gender = request.form.get("gender", "Unisex")
        p.notes_top, p.notes_heart, p.notes_base = request.form.get("top", ""), request.form.get("heart", ""), request.form.get("base", "")
        p.sku = request.form.get("sku", "").strip() or None
        p.category_name = request.form.get("category_name", "Signature").strip()
        p.fragrance_family = request.form.get("fragrance_family", "").strip()
        p.available_sizes = request.form.get("available_sizes", "50ml, 100ml").strip()
        p.video_url = request.form.get("video_url", "").strip()
        p.is_featured, p.is_bestseller, p.is_new = bool(request.form.get("featured")), bool(request.form.get("bestseller")), bool(request.form.get("new"))
        if new_image:
            p.image = new_image
        db.session.commit()
        flash("Product updated successfully.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product-form.html", product=p)

@admin_bp.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def delete_product(pid):
    admin_required()
    p = db.session.get(Product, pid)
    if p:
        p.is_active = False
        db.session.commit()
        flash("Product archived. Existing order history remains intact.", "success")
    return redirect(url_for("admin.products"))

@admin_bp.route("/products/<int:pid>/restore", methods=["POST"])
@login_required
def restore_product(pid):
    admin_required()
    p = db.session.get(Product, pid)
    if p:
        p.is_active = True
        db.session.commit()
        flash("Product restored.", "success")
    return redirect(url_for("admin.products"))

@admin_bp.route("/orders")
@login_required
def orders():
    admin_required()
    return render_template("admin/orders.html", orders=Order.query.order_by(Order.created_at.desc()).all())

@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    admin_required()
    order = db.session.get(Order, order_id) or abort(404)
    allowed = {"Pending", "Confirmed", "Processing", "Shipped", "Out for Delivery", "Delivered", "Cancelled", "Refunded"}
    new_status = request.form.get("status", "")
    if new_status not in allowed:
        flash("Invalid order status.", "error")
    else:
        order.status = new_status
        if hasattr(order, 'courier_name'):
            order.courier_name = request.form.get('courier_name','').strip() or order.courier_name
            order.tracking_number = request.form.get('tracking_number','').strip() or order.tracking_number
            order.tracking_url = request.form.get('tracking_url','').strip() or order.tracking_url
        db.session.commit()
        flash(f"Order #{order.id} updated to {new_status}.", "success")
    return redirect(url_for("admin.orders"))

@admin_bp.route("/customers")
@login_required
def customers():
    admin_required()
    q = request.args.get("q", "").strip()
    query = User.query.filter_by(is_admin=False)
    if q:
        query = query.filter((User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")) | (User.phone.ilike(f"%{q}%")))
    customers = query.order_by(User.created_at.desc()).all()
    order_counts = {customer.id: Order.query.filter_by(user_id=customer.id).count() for customer in customers}
    return render_template("admin/customers.html", customers=customers, search=q, order_counts=order_counts)

@admin_bp.route("/customers/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(user_id):
    admin_required()
    customer = User.query.filter_by(id=user_id, is_admin=False).first_or_404()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        duplicate = User.query.filter(User.email == email, User.id != customer.id).first() if email else None
        if not name or not email or "@" not in email or duplicate:
            flash("Enter a valid name and unique email address.", "error")
        elif phone and (not phone.replace("+", "").replace(" ", "").isdigit() or len(phone.replace("+", "").replace(" ", "")) < 10):
            flash("Enter a valid mobile number.", "error")
        else:
            customer.name, customer.email, customer.phone = name, email, phone
            new_password = request.form.get("new_password", "")
            if new_password:
                if len(new_password) < 10:
                    flash("New password must be at least 10 characters.", "error")
                    return redirect(url_for("admin.edit_customer", user_id=user_id))
                customer.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Customer information updated.", "success")
            return redirect(url_for("admin.customers"))
    customer_orders = Order.query.filter_by(user_id=customer.id).order_by(Order.created_at.desc()).all()
    return render_template("admin/customer-edit.html", customer=customer, orders=customer_orders)


@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    admin_required()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip().lower()
        if not name or not slug or Category.query.filter((Category.name == name) | (Category.slug == slug)).first():
            flash("Enter a unique category name and URL slug.", "error")
        else:
            db.session.add(Category(name=name, slug=slug))
            db.session.commit()
            flash("Category added.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())

@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    admin_required()
    category = db.session.get(Category, category_id) or abort(404)
    db.session.delete(category)
    db.session.commit()
    flash("Category removed.", "success")
    return redirect(url_for("admin.categories"))

@admin_bp.route("/inventory", methods=["GET", "POST"])
@login_required
def inventory():
    admin_required()
    if request.method == "POST":
        product = db.session.get(Product, int(request.form.get("product_id", "0")))
        try:
            stock = int(request.form.get("stock", "-1"))
        except ValueError:
            stock = -1
        if not product or stock < 0:
            flash("Invalid inventory update.", "error")
        else:
            product.stock = stock
            db.session.commit()
            flash(f"Stock updated for {product.name}.", "success")
        return redirect(url_for("admin.inventory"))
    products = Product.query.order_by(Product.stock.asc(), Product.name.asc()).all()
    return render_template("admin/inventory.html", products=products)

@admin_bp.route("/coupons", methods=["GET", "POST"])
@login_required
def coupons():
    admin_required()
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        discount_type = request.form.get("discount_type", "percentage")
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except InvalidOperation:
            amount = Decimal("0")
        if not code or amount <= 0 or discount_type not in {"percentage", "flat"} or Coupon.query.filter_by(code=code).first():
            flash("Enter a unique coupon code and a valid discount.", "error")
        elif discount_type == "percentage" and amount > 100:
            flash("Percentage discount cannot exceed 100.", "error")
        else:
            try:
                minimum_order = Decimal(request.form.get('minimum_order') or '0')
                maximum_discount_raw = request.form.get('maximum_discount','').strip()
                maximum_discount = Decimal(maximum_discount_raw) if maximum_discount_raw else None
                usage_limit_raw = request.form.get('usage_limit','').strip()
                usage_limit = int(usage_limit_raw) if usage_limit_raw else None
                expiry_raw = request.form.get('expires_at','').strip()
                expires_at = datetime.strptime(expiry_raw, '%Y-%m-%d') if expiry_raw else None
            except (InvalidOperation, ValueError):
                flash('Check coupon limits.', 'error'); return redirect(url_for('admin.coupons'))
            db.session.add(Coupon(code=code, discount_type=discount_type, amount=amount, active=True, minimum_order=minimum_order, maximum_discount=maximum_discount, usage_limit=usage_limit, expires_at=expires_at))
            db.session.commit()
            flash("Coupon created.", "success")
        return redirect(url_for("admin.coupons"))
    return render_template("admin/coupons.html", coupons=Coupon.query.order_by(Coupon.id.desc()).all())

@admin_bp.route("/coupons/<int:coupon_id>/toggle", methods=["POST"])
@login_required
def toggle_coupon(coupon_id):
    admin_required()
    coupon = db.session.get(Coupon, coupon_id) or abort(404)
    coupon.active = not coupon.active
    db.session.commit()
    flash("Coupon status updated.", "success")
    return redirect(url_for("admin.coupons"))

@admin_bp.route("/payments")
@login_required
def payments():
    admin_required()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/payments.html", orders=orders)

@admin_bp.route("/reports")
@login_required
def reports():
    admin_required()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    paid_or_recorded = [o for o in orders if o.status not in {"Cancelled", "Payment Pending", "Awaiting COD Advance"}]
    revenue = sum((o.total for o in paid_or_recorded), Decimal("0.00"))
    return render_template("admin/reports.html", orders=orders, revenue=revenue, products=Product.query.count(), customers=User.query.filter_by(is_admin=False).count())

# Extended business controls: store, shipping, offers, banners and gateway credentials.
from commerce import StoreSetting, StoreOffer, HomeBanner, PaymentTransaction, set_setting, setting, save_secret, get_secret

@admin_bp.route('/store-settings', methods=['GET', 'POST'])
@login_required
def store_settings():
    admin_required()
    keys = ['announcement','hero_title','hero_subtitle','contact_email','contact_phone','instagram_url','shipping_charge','free_shipping_threshold','cod_advance']
    if request.method == 'POST':
        for key in keys: set_setting(key, request.form.get(key, '').strip())
        for key in ['cod_enabled','online_enabled']:
            set_setting(key, '1' if request.form.get(key) == 'on' else '0')
        db.session.commit(); flash('Store and shipping settings saved.', 'success')
        return redirect(url_for('admin.store_settings'))
    return render_template('admin/store-settings.html', values={k: setting(k) for k in keys}, cod_enabled=setting('cod_enabled','1')=='1', online_enabled=setting('online_enabled','1')=='1')

@admin_bp.route('/payment-settings', methods=['GET','POST'])
@login_required
def payment_settings():
    admin_required()
    if request.method == 'POST':
        key_id = request.form.get('razorpay_key_id','').strip()
        key_secret = request.form.get('razorpay_key_secret','').strip()
        webhook_secret = request.form.get('razorpay_webhook_secret','').strip()
        if key_id: save_secret('razorpay_key_id', key_id)
        if key_secret: save_secret('razorpay_key_secret', key_secret)
        if webhook_secret: save_secret('razorpay_webhook_secret', webhook_secret)
        set_setting('razorpay_mode', request.form.get('razorpay_mode','test'))
        set_setting('razorpay_enabled', '1' if request.form.get('razorpay_enabled') == 'on' else '0')
        db.session.commit()
        flash('Gateway settings saved securely. Secret fields are stored encrypted and never shown again.', 'success')
        return redirect(url_for('admin.payment_settings'))
    return render_template('admin/payment-settings.html', key_configured=bool(get_secret('razorpay_key_id') or current_app.config.get('RAZORPAY_KEY_ID')), secret_configured=bool(get_secret('razorpay_key_secret') or current_app.config.get('RAZORPAY_KEY_SECRET')), webhook_configured=bool(get_secret('razorpay_webhook_secret') or current_app.config.get('RAZORPAY_WEBHOOK_SECRET')), enabled=setting('razorpay_enabled','0')=='1', mode=setting('razorpay_mode','test'))

@admin_bp.route('/offers', methods=['GET','POST'])
@login_required
def offers():
    admin_required()
    if request.method == 'POST':
        title=request.form.get('title','').strip(); subtitle=request.form.get('subtitle','').strip(); code=request.form.get('code','').strip().upper()
        if not title: flash('Offer title is required.', 'error')
        else:
            db.session.add(StoreOffer(title=title, subtitle=subtitle, code=code, active=request.form.get('active')=='on'))
            db.session.commit(); flash('Offer created.', 'success')
        return redirect(url_for('admin.offers'))
    return render_template('admin/offers.html', offers=StoreOffer.query.order_by(StoreOffer.id.desc()).all())

@admin_bp.post('/offers/<int:offer_id>/toggle')
@login_required
def toggle_offer(offer_id):
    admin_required(); offer=db.session.get(StoreOffer,offer_id) or abort(404)
    offer.active=not offer.active; db.session.commit(); flash('Offer visibility updated.', 'success')
    return redirect(url_for('admin.offers'))

@admin_bp.post('/offers/<int:offer_id>/delete')
@login_required
def delete_offer(offer_id):
    admin_required(); offer=db.session.get(StoreOffer,offer_id) or abort(404)
    db.session.delete(offer); db.session.commit(); flash('Offer deleted.', 'success')
    return redirect(url_for('admin.offers'))

@admin_bp.route('/banners', methods=['GET','POST'])
@login_required
def banners():
    admin_required()
    if request.method == 'POST':
        title=request.form.get('title','').strip(); subtitle=request.form.get('subtitle','').strip(); link=request.form.get('link','/shop').strip()
        if not title: flash('Banner title is required.', 'error')
        else:
            try: image=save_product_image(request.files.get('image'))
            except ValueError as exc: flash(str(exc),'error'); return redirect(url_for('admin.banners'))
            db.session.add(HomeBanner(title=title, subtitle=subtitle, image=image or '', link=link, active=request.form.get('active')=='on', sort_order=int(request.form.get('sort_order') or 0)))
            db.session.commit(); flash('Homepage banner saved.', 'success')
        return redirect(url_for('admin.banners'))
    return render_template('admin/banners.html', banners=HomeBanner.query.order_by(HomeBanner.sort_order, HomeBanner.id.desc()).all())

@admin_bp.post('/banners/<int:banner_id>/toggle')
@login_required
def toggle_banner(banner_id):
    admin_required(); banner=db.session.get(HomeBanner,banner_id) or abort(404)
    banner.active=not banner.active; db.session.commit(); return redirect(url_for('admin.banners'))

@admin_bp.post('/banners/<int:banner_id>/delete')
@login_required
def delete_banner(banner_id):
    admin_required(); banner=db.session.get(HomeBanner,banner_id) or abort(404)
    db.session.delete(banner); db.session.commit(); return redirect(url_for('admin.banners'))
