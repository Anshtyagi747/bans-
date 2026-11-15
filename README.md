# B BANS® — Premium Perfume Store

Flask + SQLite e-commerce project with a soft-luxury storefront and an admin control room.

## What the admin can control

- Products: create, edit, archive/restore, price, MRP, stock, SKU, category label, fragrance family, sizes, notes, video URL, product image and merchandising flags.
- Categories and inventory.
- Orders: view delivery details, update fulfilment status, courier and tracking information.
- Coupons: flat/percentage discounts, minimum cart value, maximum discount and usage limit; coupon is recalculated on the server at checkout.
- Offers/campaign messages and homepage banners.
- Store settings: announcement bar, homepage hero copy, contact information, shipping fee, free-shipping threshold, COD/online availability and COD advance amount.
- Razorpay: enter Key ID, Key Secret and Webhook Secret in Admin → Payment Settings. No Razorpay credentials need to be typed into Python source files.
- Reports and payment transaction status.

## First-time local setup (Windows PowerShell)

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a long random `FLASK_SECRET_KEY`. For local testing, keep `COOKIE_SECURE=0`.

For a brand-new database:

```powershell
flask --app app init-db
flask --app app create-admin
flask --app app run
```

Open `http://127.0.0.1:5000`. Admin login: `http://127.0.0.1:5000/admin/login`; dashboard: `http://127.0.0.1:5000/admin/`.

## Updating an existing BANS project (IMPORTANT)

1. Stop the Flask server with `Ctrl+C`.
2. Back up `instance/bans.db` and the whole `static/uploads` folder.
3. Copy the new project files over the existing project and choose **Replace the files in the destination**.
4. Do **not** delete or replace `instance/bans.db`, `instance/settings.key`, `.env`, or existing uploaded product images.
5. Activate the same virtual environment and run:

```powershell
pip install -r requirements.txt
flask --app app upgrade-db
flask --app app run
```

`upgrade-db` creates new tables and adds the new columns to the existing SQLite tables. It does not intentionally delete customer, product or order records. Always keep the backup before upgrading.

## Configure Razorpay from the Admin Panel

1. Sign in as the admin and open Admin → Payment Settings.
2. In the Razorpay Dashboard, create API keys. Start with **Test Mode** credentials.
3. Paste Key ID, Key Secret and Webhook Secret into the admin form and save. The app encrypts these values at rest; the secret values are not sent back to the browser after saving.
4. Enable Razorpay and save again if needed.
5. For webhooks, set the public HTTPS URL to `https://YOUR-DOMAIN/payment/webhook` and subscribe to `payment.captured` (and optionally `payment.failed`). The webhook secret entered in Admin must match the Razorpay webhook secret.
6. Test successful, failed, cancelled and duplicate payment cases in Razorpay Test Mode before switching to Live Mode.

The encryption key is generated locally at `instance/settings.key` when first saving gateway credentials, unless `SETTINGS_ENCRYPTION_KEY` is provided in the server environment. **Back up `instance/settings.key` securely**; without it, encrypted credentials cannot be decrypted after restore. On hosting with ephemeral disks, set a stable `SETTINGS_ENCRYPTION_KEY` in the hosting environment and persist the SQLite database/uploads or use managed storage.

## Payment behaviour and important limitations

- The server creates Razorpay payment orders. Browser callbacks are not trusted as proof of payment; the backend verifies the Razorpay signature and fetches the payment status before confirming the order.
- Inventory is deducted only after a captured payment is verified. COD orders take the configured advance online; the remaining COD balance is the order total minus the captured advance.
- Do not dispatch orders with `Payment Pending`, `Awaiting COD Advance`, or any payment transaction that is not `captured`.
- The current build does not implement automated Razorpay refunds, courier API integrations, OTP/email password-reset delivery, multi-role permissions, or complete tax/GST invoicing. Order status can be managed in the admin panel, but mark refunds only after you actually process them in Razorpay.
- Before live commerce, configure HTTPS, a production WSGI server, a strong `FLASK_SECRET_KEY`, backups, email delivery, rate limiting, privacy/returns/shipping policies, tax compliance and payment/webhook end-to-end tests. Test Mode working does not by itself certify production readiness.

## Brand assets

Place the approved original logo at `static/images/brand/bans-logo-original.png`. Do not replace it with a generated logo. Add genuine product photography using Admin → Products.

## Customer and administrator sign-in (updated)

- Customer registration: `/auth/register`
- Customer sign-in: `/auth/login`
- Private administrator sign-in: `/admin/login`
- Admin dashboard: `/admin/`

The public storefront does not display an administrator link. Hiding the URL is not an access-control mechanism: every `/admin` route still checks the authenticated user's `is_admin` flag. Customer registration explicitly creates `is_admin=False`. If an administrator is signed in and opens customer registration in the same browser, the admin session is signed out first so a separate customer account can be created.

## Existing database upgrade

Back up `instance/bans.db` before replacing application files. Keep the existing `instance/bans.db`, `.env`, `instance/settings.key`, uploaded product images, and official logo. The app performs a safe first-request schema compatibility check for the known added columns and new tables. You can also run:

```powershell
flask --app app upgrade-db
```

Then start:

```powershell
flask --app app run
```

If the admin page still returns HTTP 500, copy the full red traceback from the VS Code terminal. The browser's generic 500 page does not show the actual exception.

## Razorpay credentials

Enter the Razorpay Key ID, Key Secret, and Webhook Secret in Admin → Payment settings. Use Test Mode first. The secret values are encrypted in the database using `instance/settings.key`; back up that key securely and do not commit it to Git. The saved secrets are not sent back to the browser. Use HTTPS and configure the public webhook URL `/payment/webhook` in Razorpay before live mode.

## Important release note

This is a local development build, not a production certification. Before accepting real payments, test the full flow in Razorpay Test Mode, verify webhook delivery, test stock and duplicate-order handling, configure HTTPS and backups, and complete the remaining operational checks. Do not use real customer payment credentials on an unverified local build.
