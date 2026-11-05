/**
 * SHOPLEDGER POS BILLING ENGINE
 * High-speed POS terminal operations, barcode scanner support, decimal arithmetic, and checkout.
 */

(function () {
  let cart = [];
  let selectedPaymentMethod = "cash";
  let activeCategoryId = "";

  const searchInput = document.getElementById("pos-search-input");
  const productGrid = document.getElementById("pos-product-grid");
  const cartList = document.getElementById("pos-cart-list");
  const cartEmptyMsg = document.getElementById("pos-cart-empty");
  const subtotalElem = document.getElementById("pos-subtotal");
  const discountInput = document.getElementById("pos-discount-input");
  const taxValElem = document.getElementById("pos-tax-val");
  const grandTotalElem = document.getElementById("pos-grand-total");
  const submitBtn = document.getElementById("pos-submit-btn");
  const clearCartBtn = document.getElementById("pos-clear-cart");
  const tenderedInput = document.getElementById("pos-tendered-input");
  const changeDisplay = document.getElementById("pos-change-display");
  const cashCalcBox = document.getElementById("pos-cash-calc");
  const custNameInput = document.getElementById("pos-cust-name");
  const custPhoneInput = document.getElementById("pos-cust-phone");

  const currency = window.SHOP_CURRENCY || "₹";
  const taxEnabled = window.TAX_ENABLED !== false;

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    bindProductTiles();
    bindSearch();
    bindCategoryFilters();
    bindPaymentMethods();
    bindCartActions();
    bindShortcuts();
  }

  // 1. CLICK TO ADD FROM TILE
  function bindProductTiles() {
    document.querySelectorAll(".product-tile").forEach((tile) => {
      tile.addEventListener("click", () => {
        const id = parseInt(tile.getAttribute("data-id"));
        const name = tile.getAttribute("data-name");
        const price = parseFloat(tile.getAttribute("data-price")) || 0;
        const cost = parseFloat(tile.getAttribute("data-cost")) || 0;
        const tax = parseFloat(tile.getAttribute("data-tax")) || 0;
        const sku = tile.getAttribute("data-sku") || "";

        addToCart({
          product_id: id,
          name: name,
          unit_price: price,
          purchase_price: cost,
          tax_rate: tax,
          sku: sku,
        });
      });
    });
  }

  // 2. SEARCH & BARCODE SCANNER
  function bindSearch() {
    if (!searchInput) return;

    let debounceTimer = null;

    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetchProducts(searchInput.value.trim(), activeCategoryId);
      }, 250);
    });

    // Barcode Scanner: hitting enter in search input
    searchInput.addEventListener("keydown", async (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const code = searchInput.value.trim();
        if (!code) return;

        try {
          const res = await fetch(`${window.BARCODE_API_URL}?code=${encodeURIComponent(code)}`);
          const data = await res.json();
          if (data.found && data.product) {
            const p = data.product;
            addToCart({
              product_id: p.id,
              name: p.name,
              unit_price: p.selling_price,
              purchase_price: p.purchase_price,
              tax_rate: p.tax_rate,
              sku: p.sku,
            });
            searchInput.value = "";
          }
        } catch (err) {
          console.error("Barcode lookup error", err);
        }
      }
    });
  }

  // Fetch products by query and category
  async function fetchProducts(query, categoryId) {
    if (!productGrid) return;
    try {
      let url = `${window.PRODUCTS_API_URL}?q=${encodeURIComponent(query)}`;
      if (categoryId) url += `&category_id=${categoryId}`;

      const res = await fetch(url);
      const items = await res.json();

      productGrid.innerHTML = "";
      if (items.length === 0) {
        productGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 30px; color: var(--text-muted); font-size: 0.82rem;">No matching products found.</div>`;
        return;
      }

      items.forEach((p) => {
        const div = document.createElement("div");
        div.className = "product-tile";
        div.setAttribute("data-id", p.id);
        div.setAttribute("data-name", p.name);
        div.setAttribute("data-price", p.selling_price);
        div.setAttribute("data-cost", p.purchase_price);
        div.setAttribute("data-tax", p.tax_rate);
        div.setAttribute("data-sku", p.sku || "");

        div.innerHTML = `
          <div>
            <div style="font-size: 0.82rem; font-weight: 600; color: var(--text-main); line-height: 1.3;">${p.name}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">${p.sku || "No SKU"}</div>
          </div>
          <div style="margin-top: 8px; display: flex; align-items: center; justify-content: space-between;">
            <span style="font-weight: 700; font-size: 0.95rem; color: var(--accent-green-text);">
              ${currency}${p.selling_price.toFixed(2)}
            </span>
            <span style="font-size: 0.68rem; padding: 1px 5px; border-radius: 4px; background: var(--bg-surface); color: ${p.stock_quantity <= p.min_stock_level ? "var(--accent-red-text)" : "var(--text-faint)"};">
              Stock: ${p.stock_quantity}
            </span>
          </div>
        `;

        div.addEventListener("click", () => {
          addToCart({
            product_id: p.id,
            name: p.name,
            unit_price: p.selling_price,
            purchase_price: p.purchase_price,
            tax_rate: p.tax_rate,
            sku: p.sku,
          });
        });

        productGrid.appendChild(div);
      });
    } catch (err) {
      console.error(err);
    }
  }

  // 3. CATEGORY FILTER TABS
  function bindCategoryFilters() {
    document.querySelectorAll(".pos-cat-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".pos-cat-btn").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        activeCategoryId = btn.getAttribute("data-cat-id") || "";
        fetchProducts(searchInput ? searchInput.value.trim() : "", activeCategoryId);
      });
    });
  }

  // 4. CART OPERATIONS
  function addToCart(product) {
    const existing = cart.find((item) => item.product_id === product.product_id);
    if (existing) {
      existing.quantity += 1;
    } else {
      cart.push({
        product_id: product.product_id,
        name: product.name,
        unit_price: parseFloat(product.unit_price) || 0,
        purchase_price: parseFloat(product.purchase_price) || 0,
        tax_rate: parseFloat(product.tax_rate) || 0,
        sku: product.sku || "",
        quantity: 1,
        discount: 0,
      });
    }
    renderCart();
  }

  function renderCart() {
    if (!cartList) return;

    if (cart.length === 0) {
      cartList.innerHTML = `
        <div id="pos-cart-empty" style="text-align: center; padding: 40px 16px; color: var(--text-muted); font-size: 0.82rem;">
          <i data-lucide="shopping-cart" style="width: 32px; height: 32px; color: var(--text-faint); margin-bottom: 8px;"></i>
          <p>Cart is empty. Tap or scan items on the left.</p>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
      updateTotals();
      return;
    }

    cartList.innerHTML = "";

    cart.forEach((item, index) => {
      const rowTotal = item.unit_price * item.quantity;
      const row = document.createElement("div");
      row.className = "cart-item-row";
      row.innerHTML = `
        <div>
          <div style="font-size: 0.82rem; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ${item.name}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">
            ${currency}${item.unit_price.toFixed(2)} ${item.tax_rate > 0 ? `(+${item.tax_rate}% GST)` : ""}
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: center; gap: 4px;">
          <button class="qty-btn" data-action="dec" data-index="${index}">-</button>
          <span style="font-weight: 600; font-size: 0.85rem; min-width: 20px; text-align: center;">${item.quantity}</span>
          <button class="qty-btn" data-action="inc" data-index="${index}">+</button>
        </div>
        <div style="text-align: right; font-weight: 700; font-size: 0.85rem; color: var(--text-main);">
          ${currency}${rowTotal.toFixed(2)}
        </div>
        <div style="text-align: right;">
          <button data-action="del" data-index="${index}" style="background: transparent; border: none; color: var(--text-faint); cursor: pointer; padding: 4px;" title="Remove">
            <i data-lucide="x" style="width: 14px; height: 14px;"></i>
          </button>
        </div>
      `;
      cartList.appendChild(row);
    });

    if (window.lucide) window.lucide.createIcons();
    updateTotals();
  }

  function bindCartActions() {
    if (cartList) {
      cartList.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (!btn) return;
        const action = btn.getAttribute("data-action");
        const idx = parseInt(btn.getAttribute("data-index"));

        if (action === "inc") {
          cart[idx].quantity += 1;
        } else if (action === "dec") {
          cart[idx].quantity -= 1;
          if (cart[idx].quantity <= 0) {
            cart.splice(idx, 1);
          }
        } else if (action === "del") {
          cart.splice(idx, 1);
        }
        renderCart();
      });
    }

    if (clearCartBtn) {
      clearCartBtn.addEventListener("click", () => {
        if (cart.length > 0 && confirm("Clear entire cart?")) {
          cart = [];
          renderCart();
        }
      });
    }

    if (discountInput) {
      discountInput.addEventListener("input", updateTotals);
    }

    if (tenderedInput) {
      tenderedInput.addEventListener("input", updateCashChange);
    }

    if (submitBtn) {
      submitBtn.addEventListener("click", executeCheckout);
    }
  }

  function updateTotals() {
    let subtotal = 0;
    let taxTotal = 0;

    cart.forEach((itm) => {
      const line = itm.unit_price * itm.quantity;
      subtotal += line;
      if (taxEnabled && itm.tax_rate > 0) {
        taxTotal += line * (itm.tax_rate / 100);
      }
    });

    const discount = parseFloat(discountInput ? discountInput.value : 0) || 0;
    const grandTotal = Math.max(0, subtotal - discount + taxTotal);

    if (subtotalElem) subtotalElem.textContent = `${currency}${subtotal.toFixed(2)}`;
    if (taxValElem) taxValElem.textContent = `${currency}${taxTotal.toFixed(2)}`;
    if (grandTotalElem) grandTotalElem.textContent = `${currency}${grandTotal.toFixed(2)}`;

    updateCashChange();
  }

  function updateCashChange() {
    if (!tenderedInput || !changeDisplay) return;
    const grandTotalStr = grandTotalElem ? grandTotalElem.textContent.replace(currency, "") : "0";
    const grandTotal = parseFloat(grandTotalStr) || 0;
    const tendered = parseFloat(tenderedInput.value) || 0;

    if (tendered > grandTotal) {
      const change = tendered - grandTotal;
      changeDisplay.textContent = `Change Due: ${currency}${change.toFixed(2)}`;
      changeDisplay.style.color = "var(--accent-green-text)";
    } else {
      changeDisplay.textContent = `Change Due: ${currency}0.00`;
      changeDisplay.style.color = "var(--text-muted)";
    }
  }

  // 5. PAYMENT METHODS
  function bindPaymentMethods() {
    document.querySelectorAll(".payment-method-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".payment-method-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        selectedPaymentMethod = btn.getAttribute("data-method");

        if (cashCalcBox) {
          cashCalcBox.style.display = selectedPaymentMethod === "cash" ? "flex" : "none";
        }
      });
    });
  }

  // 6. CHECKOUT EXECUTION
  async function executeCheckout() {
    if (cart.length === 0) {
      alert("Cart is empty. Please add items before checking out.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Processing Bill...</span>`;

    const grandTotalStr = grandTotalElem ? grandTotalElem.textContent.replace(currency, "") : "0";
    const grandTotal = parseFloat(grandTotalStr) || 0;
    const discount = parseFloat(discountInput ? discountInput.value : 0) || 0;

    let paidAmount = grandTotal;
    if (selectedPaymentMethod === "credit") {
      paidAmount = 0.0;
    } else if (selectedPaymentMethod === "cash" && tenderedInput && parseFloat(tenderedInput.value) > 0) {
      paidAmount = Math.min(grandTotal, parseFloat(tenderedInput.value));
    }

    const payload = {
      items: cart,
      customer_name: custNameInput ? custNameInput.value.trim() : "",
      customer_phone: custPhoneInput ? custPhoneInput.value.trim() : "",
      discount_amount: discount,
      payment_method: selectedPaymentMethod,
      paid_amount: paidAmount,
    };

    try {
      const res = await fetch(window.CHECKOUT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.success) {
        // Open print view in new window or redirect
        window.open(data.print_url, "_blank");
        // Clear cart and reset inputs
        cart = [];
        renderCart();
        if (discountInput) discountInput.value = "0";
        if (tenderedInput) tenderedInput.value = "";
        if (custNameInput) custNameInput.value = "";
        if (custPhoneInput) custPhoneInput.value = "";
        alert(`Bill generated successfully!\nInvoice Number: ${data.invoice_number}`);
        if (searchInput) searchInput.focus();
      } else {
        alert(`Checkout failed: ${data.error || "Unknown error"}`);
      }
    } catch (err) {
      alert(`Network error during checkout: ${err.message}`);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<i data-lucide="check-circle-2" style="width: 20px; height: 20px;"></i><span>Complete & Print Bill (F9)</span>`;
      if (window.lucide) window.lucide.createIcons();
    }
  }

  // 7. KEYBOARD SHORTCUTS
  function bindShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "F2") {
        e.preventDefault();
        if (searchInput) searchInput.focus();
      } else if (e.key === "F9") {
        e.preventDefault();
        if (cart.length > 0) executeCheckout();
      }
    });
  }
})();
