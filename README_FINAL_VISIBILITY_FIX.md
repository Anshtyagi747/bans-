# BANS final storefront visibility fix

## What changed
- Removed the scroll-reveal IntersectionObserver that hid sections at opacity 0.
- Storefront sections and product cards now render visibly without waiting for JavaScript.
- Homepage product queries now fall back to all active products when Featured/Bestseller/New Arrival flags are not set.
- Product image rendering is more robust and missing images show a BANS fallback label.
- Added cache-busting query strings for CSS and JS.

## Apply to an existing BANS installation
1. Stop Flask with Ctrl+C.
2. Back up `instance/bans.db`, `.env`, `instance/settings.key`, `static/uploads/`, and your official logo.
3. Extract this ZIP and copy the contents of its `bans` folder over your existing project, choosing Replace.
4. Do NOT replace/delete your existing database, `.env`, encryption key, uploaded product images, or logo.
5. Restart: `flask --app app run`
6. In Chrome press Ctrl+F5 to force-refresh cached CSS/JS.

## Product visibility checklist
- In Admin → Products, product status must be Active.
- Upload an image in JPG/PNG/WebP format.
- Save the product.
- It should appear in the homepage product sections even if Featured/Bestseller/New Arrival are unchecked (fallback behaviour).
- The homepage will display products only when active products exist in the database.

## Launch readiness
This patch addresses the reported blank-on-scroll behaviour and homepage product visibility fallback. It is not a substitute for testing the full checkout/payment/shipping/tax/legal flows on the actual hosting environment before accepting live orders.
