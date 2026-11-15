"""Razorpay server-side order creation, signature and webhook verification."""
import hashlib, hmac, json
import razorpay
from flask import Blueprint, render_template, abort, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from extensions import db, csrf
from models import Order, Product
from commerce import PaymentTransaction, setting, get_secret
from decimal import Decimal

payment_bp = Blueprint('payment', __name__, url_prefix='/payment')

def client():
    key_id = get_secret('razorpay_key_id') or current_app.config.get('RAZORPAY_KEY_ID', '')
    secret = get_secret('razorpay_key_secret') or current_app.config.get('RAZORPAY_KEY_SECRET', '')
    if not key_id or not secret or setting('razorpay_enabled', '0') != '1': return None, None
    return razorpay.Client(auth=(key_id, secret)), key_id

@payment_bp.route('/start/<int:order_id>')
@login_required
def start(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    txn = PaymentTransaction.query.filter_by(order_id=order.id).order_by(PaymentTransaction.id.desc()).first()
    if not txn: abort(404)
    api, key_id = client()
    if not api:
        flash('Online payment is not configured yet. Ask the store administrator to complete Razorpay settings.', 'error')
        return redirect(url_for('order_confirmation', order_id=order.id))
    if not txn.gateway_order_id:
        try:
            result = api.order.create({'amount': txn.amount_paise, 'currency': 'INR', 'receipt': f'BANS-{order.id}-{txn.id}', 'notes': {'order_id': str(order.id), 'payment_type': txn.kind}})
            txn.gateway_order_id = result['id']; db.session.commit()
        except Exception:
            current_app.logger.exception('Razorpay order creation failed')
            flash('Razorpay could not create a payment order. Check the credentials and mode in Admin → Payment Settings.', 'error')
            return redirect(url_for('order_confirmation', order_id=order.id))
    return render_template('payment-checkout.html', order=order, txn=txn, key_id=key_id)

@payment_bp.post('/verify')
@login_required
def verify():
    order_id = request.form.get('order_id', type=int)
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    txn = PaymentTransaction.query.filter_by(order_id=order.id).order_by(PaymentTransaction.id.desc()).first_or_404()
    payment_id = request.form.get('razorpay_payment_id', '')
    gateway_order_id = request.form.get('razorpay_order_id', '')
    signature = request.form.get('razorpay_signature', '')
    if not txn.gateway_order_id or gateway_order_id != txn.gateway_order_id or not payment_id or not signature:
        abort(400)
    api, _ = client()
    if not api: abort(503)
    try:
        api.utility.verify_payment_signature({'razorpay_order_id': gateway_order_id, 'razorpay_payment_id': payment_id, 'razorpay_signature': signature})
        # Fetch from Razorpay to ensure the transaction is captured, not merely authorized.
        payment = api.payment.fetch(payment_id)
        if payment.get('order_id') != gateway_order_id or payment.get('status') != 'captured':
            txn.status = payment.get('status', 'pending'); db.session.commit()
            flash('Payment is not captured yet. Order remains unconfirmed.', 'error')
            return redirect(url_for('order_confirmation', order_id=order.id))
        if txn.status != 'captured':
            txn.status = 'captured'; txn.gateway_payment_id = payment_id
            order.status = 'Confirmed'
            # Deduct inventory exactly once after verified capture.
            for line in order.items:
                product = db.session.get(Product, line.product_id) if line.product_id else None
                if product:
                    if product.stock < line.quantity:
                        db.session.rollback(); abort(409)
                    product.stock -= line.quantity
            db.session.commit()
        flash('Payment verified successfully. Your order is confirmed.', 'success')
    except razorpay.errors.SignatureVerificationError:
        txn.status = 'failed'; db.session.commit()
        flash('Payment signature could not be verified. Contact support before retrying.', 'error')
    except Exception:
        current_app.logger.exception('Payment verification error')
        flash('Payment verification is pending. Please check your order status before trying again.', 'error')
    return redirect(url_for('order_confirmation', order_id=order.id))

@payment_bp.post('/webhook')
@csrf.exempt
def webhook():
    secret = get_secret('razorpay_webhook_secret') or current_app.config.get('RAZORPAY_WEBHOOK_SECRET', '')
    signature = request.headers.get('X-Razorpay-Signature', '')
    body = request.get_data()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest() if secret else ''
    if not secret or not hmac.compare_digest(expected, signature): abort(400)
    payload = json.loads(body or b'{}')
    event = payload.get('event')
    entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
    if event == 'payment.captured' and entity:
        txn = PaymentTransaction.query.filter_by(gateway_order_id=entity.get('order_id')).first()
        if txn and txn.status != 'captured':
            txn.status = 'captured'; txn.gateway_payment_id = entity.get('id')
            txn.order.status = 'Confirmed'
            for line in txn.order.items:
                product = db.session.get(Product, line.product_id) if line.product_id else None
                if product: product.stock = max(0, product.stock - line.quantity)
            db.session.commit()
    return {'ok': True}
