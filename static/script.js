/**
 * APEX FINTECH DASHBOARD ENGINE
 * Handles charts, real-time filtering, modals, budget progress, and UI interactions.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Current formatted date in topbar
  const dateElement = document.getElementById("current-date-display");
  if (dateElement) {
    const now = new Date();
    const options = { weekday: "short", month: "short", day: "numeric", year: "numeric" };
    dateElement.textContent = now.toLocaleDateString("en-US", options);
  }

  // -------------------------------------------------------------------------
  // 1. SIDEBAR & MOBILE DRAWER LOGIC
  // -------------------------------------------------------------------------
  const sidebar = document.getElementById("main-sidebar");
  const collapseBtn = document.getElementById("sidebar-collapse-btn");
  const mobileToggle = document.getElementById("mobile-menu-toggle");

  if (collapseBtn && sidebar) {
    // Restore sidebar state from localStorage
    const isCollapsed = localStorage.getItem("apex_sidebar_collapsed") === "true";
    if (isCollapsed) {
      sidebar.classList.add("collapsed");
    }

    collapseBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem("apex_sidebar_collapsed", sidebar.classList.contains("collapsed"));
    });
  }

  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", () => {
      sidebar.classList.toggle("mobile-open");
    });

    // Close on outside click on mobile
    document.addEventListener("click", (e) => {
      if (window.innerWidth <= 992 && sidebar.classList.contains("mobile-open")) {
        if (!sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
          sidebar.classList.remove("mobile-open");
        }
      }
    });
  }

  // -------------------------------------------------------------------------
  // 2. USER PROFILE DROPDOWN
  // -------------------------------------------------------------------------
  const profileTrigger = document.getElementById("profile-dropdown-trigger");
  const profileMenu = document.getElementById("profile-dropdown-menu");

  if (profileTrigger && profileMenu) {
    profileTrigger.addEventListener("click", (e) => {
      e.stopPropagation();
      profileMenu.classList.toggle("show");
    });

    document.addEventListener("click", () => {
      profileMenu.classList.remove("show");
    });
  }

  // -------------------------------------------------------------------------
  // 3. MONTHLY BUDGET / LIMIT WIDGET
  // -------------------------------------------------------------------------
  initBudgetWidget();

  // -------------------------------------------------------------------------
  // 4. CHART.JS ANALYTICS INITIALIZATION
  // -------------------------------------------------------------------------
  initAnalyticsCharts();

  // -------------------------------------------------------------------------
  // 5. TRANSACTION TABLE SEARCH & FILTERS
  // -------------------------------------------------------------------------
  initTransactionFilters();

  // -------------------------------------------------------------------------
  // 6. MODALS: ADD TRANSACTION & EDIT TRANSACTION
  // -------------------------------------------------------------------------
  initModals();
});

// =========================================================================
// BUDGET WIDGET FUNCTIONALITY
// =========================================================================
function initBudgetWidget() {
  const defaultLimit = 30000;
  const storedLimit = parseFloat(localStorage.getItem("apex_monthly_limit")) || defaultLimit;

  // Retrieve total expenses from hidden data element or DOM
  const totalExpenseElem = document.getElementById("raw-total-expense");
  const totalExpense = totalExpenseElem ? parseFloat(totalExpenseElem.value) || 0 : 0;

  updateBudgetDisplay(storedLimit, totalExpense);

  const editLimitBtn = document.getElementById("edit-limit-btn");
  if (editLimitBtn) {
    editLimitBtn.addEventListener("click", () => {
      const current = parseFloat(localStorage.getItem("apex_monthly_limit")) || defaultLimit;
      const input = prompt("Enter your monthly expense limit (₹):", current);
      if (input !== null) {
        const newLimit = parseFloat(input);
        if (!isNaN(newLimit) && newLimit > 0) {
          localStorage.setItem("apex_monthly_limit", newLimit);
          updateBudgetDisplay(newLimit, totalExpense);
        } else {
          alert("Please enter a valid positive number.");
        }
      }
    });
  }
}

function updateBudgetDisplay(limit, expense) {
  const limitValueElem = document.getElementById("budget-limit-val");
  const spentValueElem = document.getElementById("budget-spent-val");
  const remainingValueElem = document.getElementById("budget-remaining-val");
  const progressBar = document.getElementById("budget-progress-fill");
  const statusPill = document.getElementById("budget-status-pill");

  if (!progressBar) return;

  const percentage = Math.min(Math.round((expense / limit) * 100), 100);
  const remaining = Math.max(0, limit - expense);

  if (limitValueElem) limitValueElem.textContent = "₹" + limit.toLocaleString("en-IN");
  if (spentValueElem) spentValueElem.textContent = "₹" + expense.toLocaleString("en-IN");
  if (remainingValueElem) remainingValueElem.textContent = "₹" + remaining.toLocaleString("en-IN");

  progressBar.style.width = `${percentage}%`;

  // Color and pill status depending on ratio
  progressBar.classList.remove("warning", "danger");
  if (statusPill) {
    statusPill.classList.remove("good", "warning", "danger");

    if (expense > limit) {
      progressBar.classList.add("danger");
      statusPill.classList.add("danger");
      statusPill.textContent = "Limit Exceeded";
    } else if (percentage >= 80) {
      progressBar.classList.add("warning");
      statusPill.classList.add("warning");
      statusPill.textContent = `${percentage}% Consumed`;
    } else {
      statusPill.classList.add("good");
      statusPill.textContent = "On Track";
    }
  }
}

// =========================================================================
// REAL DATA CHARTS VIA CHART.JS
// =========================================================================
function initAnalyticsCharts() {
  const cashflowCtx = document.getElementById("cashflowTrendChart");
  const categoryCtx = document.getElementById("categoryDonutChart");

  // Read backend JSON data embedded in script tags
  let monthlyData = [];
  let categoryData = [];

  const monthlyScript = document.getElementById("monthly-data-json");
  const categoryScript = document.getElementById("category-data-json");

  if (monthlyScript && monthlyScript.textContent) {
    try {
      monthlyData = JSON.parse(monthlyScript.textContent);
    } catch (e) {
      console.error("Error parsing monthly data", e);
    }
  }

  if (categoryScript && categoryScript.textContent) {
    try {
      categoryData = JSON.parse(categoryScript.textContent);
    } catch (e) {
      console.error("Error parsing category data", e);
    }
  }

  // --- 1. Cashflow Trend Chart (Monthly Income vs Expense) ---
  if (cashflowCtx && typeof Chart !== "undefined") {
    // If no monthly aggregated data exists yet, create fallback labels
    let labels = [];
    let incomePoints = [];
    let expensePoints = [];

    if (monthlyData && monthlyData.length > 0) {
      labels = monthlyData.map((d) => {
        // d.month is 'YYYY-MM'
        if (d.month) {
          const parts = d.month.split("-");
          const date = new Date(parts[0], parts[1] - 1, 1);
          return date.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
        }
        return "Recent";
      });
      incomePoints = monthlyData.map((d) => d.income || 0);
      expensePoints = monthlyData.map((d) => d.expense || 0);
    } else {
      // Graceful fallback for single or initial session
      labels = ["This Month"];
      const totalIncomeElem = document.getElementById("raw-total-income");
      const totalExpenseElem = document.getElementById("raw-total-expense");
      incomePoints = [totalIncomeElem ? parseFloat(totalIncomeElem.value) || 0 : 0];
      expensePoints = [totalExpenseElem ? parseFloat(totalExpenseElem.value) || 0 : 0];
    }

    new Chart(cashflowCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Income",
            data: incomePoints,
            backgroundColor: "rgba(16, 185, 129, 0.8)",
            borderColor: "#10B981",
            borderWidth: 1,
            borderRadius: 6,
            maxBarThickness: 32,
          },
          {
            label: "Expenses",
            data: expensePoints,
            backgroundColor: "rgba(244, 63, 94, 0.8)",
            borderColor: "#F43F5E",
            borderWidth: 1,
            borderRadius: 6,
            maxBarThickness: 32,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: {
              color: "#94A3B8",
              font: { family: "Inter", size: 12 },
              usePointStyle: true,
              boxWidth: 8,
              padding: 16,
            },
          },
          tooltip: {
            backgroundColor: "#151F32",
            borderColor: "rgba(255, 255, 255, 0.15)",
            borderWidth: 1,
            titleColor: "#F9FAFB",
            bodyColor: "#94A3B8",
            padding: 12,
            boxPadding: 6,
            cornerRadius: 8,
            callbacks: {
              label: function (context) {
                return `${context.dataset.label}: ₹${context.raw.toLocaleString("en-IN")}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#64748B", font: { family: "Inter", size: 11 } },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#64748B",
              font: { family: "Inter", size: 11 },
              callback: function (value) {
                return "₹" + value.toLocaleString("en-IN");
              },
            },
          },
        },
      },
    });
  }

  // --- 2. Category Distribution Donut Chart ---
  if (categoryCtx && typeof Chart !== "undefined") {
    let catLabels = [];
    let catTotals = [];

    if (categoryData && categoryData.length > 0) {
      catLabels = categoryData.map((c) => c.category || "Uncategorized");
      catTotals = categoryData.map((c) => c.total || 0);
    }

    const palette = ["#10B981", "#06B6D4", "#6366F1", "#F59E0B", "#EC4899", "#8B5CF6", "#14B8A6"];

    if (catTotals.length === 0) {
      // Empty state display
      const parent = categoryCtx.parentElement;
      if (parent) {
        categoryCtx.style.display = "none";
        const emptyMsg = document.createElement("div");
        emptyMsg.className = "chart-empty";
        emptyMsg.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></svg>
          <p>No expense data recorded yet.</p>
        `;
        parent.appendChild(emptyMsg);
      }
    } else {
      new Chart(categoryCtx, {
        type: "doughnut",
        data: {
          labels: catLabels,
          datasets: [
            {
              data: catTotals,
              backgroundColor: palette.slice(0, catLabels.length),
              borderWidth: 2,
              borderColor: "#151F32",
              hoverOffset: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "72%",
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                color: "#94A3B8",
                font: { family: "Inter", size: 11 },
                usePointStyle: true,
                padding: 12,
              },
            },
            tooltip: {
              backgroundColor: "#151F32",
              borderColor: "rgba(255, 255, 255, 0.15)",
              borderWidth: 1,
              titleColor: "#F9FAFB",
              bodyColor: "#94A3B8",
              padding: 12,
              cornerRadius: 8,
              callbacks: {
                label: function (context) {
                  const totalSum = context.dataset.data.reduce((a, b) => a + b, 0);
                  const percentage = totalSum > 0 ? Math.round((context.raw / totalSum) * 100) : 0;
                  return `${context.label}: ₹${context.raw.toLocaleString("en-IN")} (${percentage}%)`;
                },
              },
            },
          },
        },
      });
    }
  }
}

// =========================================================================
// REAL-TIME TRANSACTION TABLE SEARCH & FILTERS
// =========================================================================
function initTransactionFilters() {
  const searchInput = document.getElementById("table-search-input") || document.getElementById("global-search-input");
  const categoryFilter = document.getElementById("table-category-filter");
  const typeButtons = document.querySelectorAll(".type-toggle-btn");
  const tableRows = document.querySelectorAll(".tx-row");
  const visibleCountElem = document.getElementById("visible-tx-count");
  const emptyFilterState = document.getElementById("empty-filter-state");

  let activeType = "all";

  function applyFilters() {
    const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    const category = categoryFilter ? categoryFilter.value.toLowerCase() : "all";

    let visibleCount = 0;

    tableRows.forEach((row) => {
      const rowType = (row.getAttribute("data-type") || "expense").toLowerCase();
      const rowCategory = (row.getAttribute("data-category") || "").toLowerCase();
      const rowDesc = (row.getAttribute("data-desc") || "").toLowerCase();
      const rowDate = (row.getAttribute("data-date") || "").toLowerCase();
      const rowAmount = (row.getAttribute("data-amount") || "").toLowerCase();

      // Check Type
      const matchesType = activeType === "all" || rowType === activeType;

      // Check Category
      const matchesCategory = category === "all" || rowCategory === category;

      // Check Search Query
      const matchesSearch =
        query === "" ||
        rowCategory.includes(query) ||
        rowDesc.includes(query) ||
        rowDate.includes(query) ||
        rowAmount.includes(query);

      if (matchesType && matchesCategory && matchesSearch) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    if (visibleCountElem) {
      visibleCountElem.textContent = visibleCount;
    }

    if (emptyFilterState) {
      emptyFilterState.style.display = visibleCount === 0 && tableRows.length > 0 ? "flex" : "none";
    }
  }

  // Type Toggle Buttons (All, Expense, Income)
  typeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      typeButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeType = btn.getAttribute("data-filter") || "all";
      applyFilters();
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
  }

  if (categoryFilter) {
    categoryFilter.addEventListener("change", applyFilters);
  }
}

// =========================================================================
// MODALS LOGIC (ADD & EDIT TRANSACTIONS)
// =========================================================================
function initModals() {
  const addModal = document.getElementById("add-transaction-modal");
  const editModal = document.getElementById("edit-transaction-modal");

  const openAddBtns = document.querySelectorAll(".open-add-modal-btn");
  const closeBtns = document.querySelectorAll(".modal-close-trigger");

  // Pre-fill today's date in add modal
  const addDateInput = document.getElementById("modal-add-date");
  if (addDateInput && !addDateInput.value) {
    const today = new Date().toISOString().split("T")[0];
    addDateInput.value = today;
  }

  // Open Add Modal
  openAddBtns.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (addModal) {
        // If button specifies an initial type (e.g. data-type="income")
        const requestedType = btn.getAttribute("data-type");
        if (requestedType) {
          selectModalType(addModal, requestedType);
        }
        addModal.classList.add("show");
      }
    });
  });

  // Close Modals on click outside or close button
  closeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (addModal) addModal.classList.remove("show");
      if (editModal) editModal.classList.remove("show");
    });
  });

  [addModal, editModal].forEach((modal) => {
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) {
          modal.classList.remove("show");
        }
      });
    }
  });

  // Segmented Type Selector inside Add Modal
  if (addModal) {
    setupSegmentedControl(addModal);
    setupCategoryQuickPills(addModal);
  }

  // Edit Modal Setup
  if (editModal) {
    setupSegmentedControl(editModal);
    setupCategoryQuickPills(editModal);

    // Attach click events to all edit action buttons on rows
    const editBtns = document.querySelectorAll(".tx-edit-btn");
    editBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const date = btn.getAttribute("data-date");
        const category = btn.getAttribute("data-category");
        const amount = btn.getAttribute("data-amount");
        const desc = btn.getAttribute("data-desc");
        const type = btn.getAttribute("data-type") || "expense";

        // Set action of edit form to /edit/<id>
        const editForm = document.getElementById("edit-tx-form");
        if (editForm) {
          editForm.action = `/edit/${id}`;
        }

        // Fill fields
        const dateInput = document.getElementById("modal-edit-date");
        const catInput = document.getElementById("modal-edit-category");
        const amtInput = document.getElementById("modal-edit-amount");
        const descInput = document.getElementById("modal-edit-desc");

        if (dateInput) dateInput.value = date;
        if (catInput) catInput.value = category;
        if (amtInput) amtInput.value = amount;
        if (descInput) descInput.value = desc;

        selectModalType(editModal, type);

        editModal.classList.add("show");
      });
    });
  }

  // Delete Confirmation Interceptor
  const deleteBtns = document.querySelectorAll(".tx-delete-btn");
  deleteBtns.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const confirmDelete = confirm("Are you sure you want to delete this transaction? This action cannot be undone.");
      if (!confirmDelete) {
        e.preventDefault();
      }
    });
  });
}

function selectModalType(modal, type) {
  const segmentBtns = modal.querySelectorAll(".segment-btn");
  const hiddenTypeInput = modal.querySelector(".hidden-type-input");

  if (hiddenTypeInput) {
    hiddenTypeInput.value = type;
  }

  segmentBtns.forEach((btn) => {
    btn.classList.remove("active");
    if (btn.getAttribute("data-type") === type) {
      btn.classList.add("active");
    }
  });
}

function setupSegmentedControl(modal) {
  const segmentBtns = modal.querySelectorAll(".segment-btn");
  const hiddenTypeInput = modal.querySelector(".hidden-type-input");

  segmentBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      segmentBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const selectedType = btn.getAttribute("data-type");
      if (hiddenTypeInput) {
        hiddenTypeInput.value = selectedType;
      }
    });
  });
}

function setupCategoryQuickPills(modal) {
  const quickPills = modal.querySelectorAll(".quick-pill");
  const categoryInput = modal.querySelector(".category-target-input");

  quickPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      quickPills.forEach((p) => p.classList.remove("selected"));
      pill.classList.add("selected");
      if (categoryInput) {
        categoryInput.value = pill.getAttribute("data-category");
      }
    });
  });
}
