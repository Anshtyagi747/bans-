/*
 * BANS storefront interactions.
 * Content is deliberately visible immediately: no scroll-reveal observer,
 * opacity hiding, or delayed entrance animation. This avoids blank sections
 * when users scroll quickly or when JavaScript is delayed/disabled.
 */
document.addEventListener("DOMContentLoaded", () => {
  // Keep image fallbacks graceful if an uploaded/deleted product image is missing.
  document.querySelectorAll("img.product-photo, img.detail-photo").forEach((img) => {
    img.addEventListener("error", () => {
      img.hidden = true;
      const visual = img.closest(".product-visual, .detail-art");
      if (visual) {
        visual.classList.add("image-unavailable");
        if (!visual.querySelector(".image-fallback-label")) {
          const fallback = document.createElement("span");
          fallback.className = "image-fallback-label";
          fallback.textContent = "B BANS · PARFUMS";
          visual.appendChild(fallback);
        }
      }
    }, { once: true });
  });
});
