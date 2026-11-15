# B BANS customer account and checkout update

## Changes
- Checkout now creates the order, line items, address and payment transaction in one rollback-safe database transaction.
- The cart is only cleared after the database commit succeeds.
- A failed order save logs the actual exception in the Flask terminal and shows a customer-safe message.
- Customer account now shows profile information, order count, completed order value, recent delivery address and recent orders.
- Customers can update their own name, email and phone.
- Admin → Customers supports search and customer detail/edit.
- Admin can update customer name, email, phone and optionally set a new password, and review order history.

## Install
1. Stop Flask with Ctrl+C.
2. Back up `instance/bans.db`, `.env`, `instance/settings.key`, `static/uploads/`, and the official logo.
3. Extract ZIP and copy the `bans` folder contents over the existing project; choose Replace.
4. Preserve the database, environment file, encryption key, uploads and logo.
5. Run `flask --app app upgrade-db` (no new database columns are required by this update, but this safely checks existing schema).
6. Run `flask --app app run`.
7. Hard refresh the browser with Ctrl+F5.

## Important payment note
Online orders and COD advance orders require a working Razorpay configuration to complete payment. If Razorpay is not configured, the order record is retained as Payment Pending / Awaiting COD Advance and the customer can see it in their account; do not dispatch until payment is verified and the order is confirmed.

## Verification
Python syntax compilation and the existing unit tests are run on the packaged source. A live checkout still needs to be tested on the user's machine with the actual SQLite database, product stock and Razorpay test credentials.
