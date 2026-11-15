from datetime import datetime
from decimal import Decimal
from flask_login import UserMixin
from extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    gender = db.Column(db.String(20), default="Unisex")
    price = db.Column(db.Numeric(10,2), nullable=False)
    mrp = db.Column(db.Numeric(10,2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255), default="")
    notes_top = db.Column(db.String(255), default="")
    notes_heart = db.Column(db.String(255), default="")
    notes_base = db.Column(db.String(255), default="")
    sku = db.Column(db.String(80), unique=True)
    category_name = db.Column(db.String(100), default="Signature")
    fragrance_family = db.Column(db.String(100), default="")
    available_sizes = db.Column(db.String(120), default="50ml, 100ml")
    video_url = db.Column(db.String(500), default="")
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_bestseller = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def discount(self):
        if self.mrp and self.mrp > 0: return max(0, round((1 - float(self.price / self.mrp)) * 100))
        return 0

class WishlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("user_id", "product_id"),)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total = db.Column(db.Numeric(10,2), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    payment_method = db.Column(db.String(30), default="Pending")
    courier_name = db.Column(db.String(120), default="")
    tracking_number = db.Column(db.String(120), default="")
    tracking_url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

class OrderAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    address_line = db.Column(db.String(255), nullable=False)
    landmark = db.Column(db.String(160), default="")
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    order = db.relationship("Order", backref=db.backref("delivery_address", uselist=False, cascade="all, delete-orphan"))

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_name = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10,2), nullable=False)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    active = db.Column(db.Boolean, default=True)
    minimum_order = db.Column(db.Numeric(10,2), default=0)
    maximum_discount = db.Column(db.Numeric(10,2))
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime)
