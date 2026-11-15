"""Database-backed store settings and encrypted gateway credential helpers."""
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from extensions import db

class StoreSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default='')

class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)  # prepaid / cod_advance
    amount_paise = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default='created', nullable=False)
    gateway_order_id = db.Column(db.String(100), unique=True)
    gateway_payment_id = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    order = db.relationship('Order', backref=db.backref('payment_transactions', lazy=True))

class StoreOffer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    subtitle = db.Column(db.String(255), default='')
    code = db.Column(db.String(40), default='')
    active = db.Column(db.Boolean, default=True, nullable=False)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class HomeBanner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    subtitle = db.Column(db.String(255), default='')
    image = db.Column(db.String(255), default='')
    link = db.Column(db.String(255), default='/shop')
    active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

DEFAULTS = {
    'announcement': 'A QUIETER KIND OF LUXURY · COMPLIMENTARY SHIPPING ON SELECT ORDERS',
    'hero_title': 'The art of your signature scent.',
    'hero_subtitle': 'Discover fragrances that leave an impression without saying a word.',
    'contact_email': '', 'contact_phone': '', 'instagram_url': '',
    'shipping_charge': '79', 'free_shipping_threshold': '1499',
    'cod_enabled': '1', 'online_enabled': '1', 'cod_advance': '50',
    'razorpay_enabled': '0', 'razorpay_mode': 'test'
}

def setting(key, default=None):
    row = StoreSetting.query.filter_by(key=key).first()
    if row: return row.value
    return DEFAULTS.get(key, default if default is not None else '')

def set_setting(key, value):
    row = StoreSetting.query.filter_by(key=key).first()
    if row is None:
        row = StoreSetting(key=key, value=str(value)); db.session.add(row)
    else: row.value = str(value)

def _fernet():
    configured = current_app.config.get('SETTINGS_ENCRYPTION_KEY')
    if configured: key = configured.encode()
    else:
        path = Path(current_app.instance_path) / 'settings.key'
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(Fernet.generate_key())
            try: path.chmod(0o600)
            except OSError: pass
        key = path.read_bytes().strip()
    return Fernet(key)

def save_secret(name, value):
    if value and value.strip(): set_setting('secret:' + name, _fernet().encrypt(value.strip().encode()).decode())

def get_secret(name):
    encrypted = setting('secret:' + name, '')
    if not encrypted: return ''
    try: return _fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError): return ''
