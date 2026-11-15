from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Order
orders_bp=Blueprint("orders",__name__)
@orders_bp.route("/")
@login_required
def list_orders():
    return render_template("orders.html",orders=Order.query.filter_by(user_id=current_user.id).all())
