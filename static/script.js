/**
 * EXPENSE TRACKER SCRIPT
 * Theme switching, Chart.js instances, live filters, modals, and budget tracking.
 */

let cashflowChartInstance = null;
let categoryChartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Initialize Theme Switcher (Dark & Light)
  initThemeSwitcher();

  // Current formatted date in topbar
  const dateElement = document.getElementById("current-date-display");
  if (dateElement) {
    const now = new Date();
    const options = { weekday: "short", month: "short", day: "numeric", year: "numeric" };
    dateElement.textContent = now.toLocaleDateString("en-US", options);
  }

  // Sidebar & Mobile Navigation
  initSidebar();

  // User Profile Dropdown
  initProfileDropdown();

  // Monthly Budget Tracker
  initBudgetWidget();

  // Chart.js Analytics
  initAnalyticsCharts();

  // Table Search & Filters
  initTransactionFilters();

  // Add & Edit Modals
  initModals();
});

// =========================================================================
// ENFORCE COMMERCIAL LIGHT THEME
// =========================================================================
function initThemeSwitcher() {
  document.documentElement.setAttribute("data-theme", "light");
  localStorage.setItem("theme", "light");
}

function updateThemeIcons(theme) {
  // Pure light theme - no dark toggle needed
}

function updateChartThemes(theme) {
  const textColor = "#64748B";
  const gridColor = "#E2E8F0";

  if (cashflowChartInstance) {
    if (cashflowChartInstance.options.scales.x) {
      cashflowChartInstance.options.scales.x.ticks.color = textColor;
    }
    if (cashflowChartInstance.options.scales.y) {
      cashflowChartInstance.options.scales.y.ticks.color = textColor;
      cashflowChartInstance.options.scales.y.grid.color = gridColor;
    }
    if (cashflowChartInstance.options.plugins.legend) {
      cashflowChartInstance.options.plugins.legend.labels.color = textColor;
    }
    cashflowChartInstance.update();
  }
}

  if (cashflowChartInstance) {
    if (cashflowChartInstance.options.scales.x) {
      cashflowChartInstance.options.scales.x.ticks.color = textColor;
    }
    if (cashflowChartInstance.options.scales.y) {
      cashflowChartInstance.options.scales.y.ticks.color = textColor;
      cashflowChartInstance.options.scales.y.grid.color = gridColor;
    }
    if (cashflowChartInstance.options.plugins.legend) {
      cashflowChartInstance.options.plugins.legend.labels.color = textColor;
    }
    cashflowChartInstance.update();
  }

  if (categoryChartInstance) {
    if (categoryChartInstance.options.plugins.legend) {
      categoryChartInstance.options.plugins.legend.labels.color = textColor;
    }
    categoryChartInstance.update();
  }
}

// =========================================================================
// SIDEBAR & MOBILE DRAWER
// =========================================================================
function initSidebar() {
  const sidebar = document.getElementById("main-sidebar");
  const collapseBtn = document.getElementById("sidebar-collapse-btn");
  const mobileToggle = document.getElementById("mobile-menu-toggle");
  const closeBtn = document.getElementById("sidebar-close-btn-mobile");
  const backdrop = document.getElementById("sidebar-backdrop");

  if (collapseBtn && sidebar) {
    const isCollapsed = localStorage.getItem("sidebar_collapsed") === "true";
    if (isCollapsed) {
      sidebar.classList.add("collapsed");
    }

    collapseBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem("sidebar_collapsed", sidebar.classList.contains("collapsed"));
    });
  }

  function closeMobileSidebar() {
    if (sidebar) sidebar.classList.remove("mobile-open");
    if (backdrop) backdrop.classList.remove("show");
  }

  function openMobileSidebar() {
    if (sidebar) sidebar.classList.add("mobile-open");
    if (backdrop) backdrop.classList.add("show");
  }

  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      if (sidebar.classList.contains("mobile-open")) {
        closeMobileSidebar();
      } else {
        openMobileSidebar();
      }
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", closeMobileSidebar);
  }

  if (backdrop) {
    backdrop.addEventListener("click", closeMobileSidebar);
  }

  // Close sidebar on link click on mobile
  const navLinks = document.querySelectorAll(".sidebar-nav .nav-link");
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 992) {
        closeMobileSidebar();
      }
    });
  });
}

// =========================================================================
// PROFILE DROPDOWN
// =========================================================================
function initProfileDropdown() {
  const trigger = document.getElementById("profile-dropdown-trigger");
  const menu = document.getElementById("profile-dropdown-menu");

  if (trigger && menu) {
    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("show");
    });

    document.addEventListener("click", () => {
      menu.classList.remove("show");
    });
  }
}

// =========================================================================
// MONTHLY BUDGET TRACKER
// =========================================================================
function initBudgetWidget() {
  const defaultLimit = 25000;
  const storedLimit = parseFloat(localStorage.getItem("user_monthly_limit")) || defaultLimit;

  const totalExpenseElem = document.getElementById("raw-total-expense");
  const totalExpense = totalExpenseElem ? parseFloat(totalExpenseElem.value) || 0 : 0;

  updateBudgetDisplay(storedLimit, totalExpense);

  const editLimitBtn = document.getElementById("edit-limit-btn");
  if (editLimitBtn) {
    editLimitBtn.addEventListener("click", () => {
      const current = parseFloat(localStorage.getItem("user_monthly_limit")) || defaultLimit;
      const input = prompt("Set your monthly spending budget (₹):", current);
      if (input !== null) {
        const newLimit = parseFloat(input);
        if (!isNaN(newLimit) && newLimit > 0) {
          localStorage.setItem("user_monthly_limit", newLimit);
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

  progressBar.classList.remove("warning", "danger");
  if (statusPill) {
    statusPill.classList.remove("good", "warning", "danger");

    if (expense > limit) {
      progressBar.classList.add("danger");
      statusPill.classList.add("danger");
      statusPill.textContent = "Over Budget";
    } else if (percentage >= 80) {
      progressBar.classList.add("warning");
      statusPill.classList.add("warning");
      statusPill.textContent = `${percentage}% Used`;
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

  let monthlyData = [];
  let categoryData = [];

  const monthlyScript = document.getElementById("monthly-data-json");
  const categoryScript = document.getElementById("category-data-json");

  if (monthlyScript && monthlyScript.textContent) {
    try {
      monthlyData = JSON.parse(monthlyScript.textContent);
    } catch (e) {
      console.error(e);
    }
  }

  if (categoryScript && categoryScript.textContent) {
    try {
      categoryData = JSON.parse(categoryScript.textContent);
    } catch (e) {
      console.error(e);
    }
  }

  const textColor = "#64748B";
  const gridColor = "#E2E8F0";

  // --- Cashflow Trend Chart ---
  if (cashflowCtx && typeof Chart !== "undefined") {
    let labels = [];
    let incomePoints = [];
    let expensePoints = [];

    if (monthlyData && monthlyData.length > 0) {
      labels = monthlyData.map((d) => {
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
      labels = ["Current"];
      const totalIncomeElem = document.getElementById("raw-total-income");
      const totalExpenseElem = document.getElementById("raw-total-expense");
      incomePoints = [totalIncomeElem ? parseFloat(totalIncomeElem.value) || 0 : 0];
      expensePoints = [totalExpenseElem ? parseFloat(totalExpenseElem.value) || 0 : 0];
    }

    cashflowChartInstance = new Chart(cashflowCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Income",
            data: incomePoints,
            backgroundColor: "#10B981",
            borderRadius: 4,
            maxBarThickness: 28,
          },
          {
            label: "Expenses",
            data: expensePoints,
            backgroundColor: "#EF4444",
            borderRadius: 4,
            maxBarThickness: 28,
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
              color: textColor,
              font: { family: "Inter", size: 12 },
              usePointStyle: true,
              boxWidth: 7,
              padding: 14,
            },
          },
          tooltip: {
            padding: 10,
            cornerRadius: 6,
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
            ticks: { color: textColor, font: { family: "Inter", size: 11 } },
          },
          y: {
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              font: { family: "Inter", size: 11 },
              callback: function (val) {
                return "₹" + val.toLocaleString("en-IN");
              },
            },
          },
        },
      },
    });
  }

  // --- Category Donut Chart ---
  if (categoryCtx && typeof Chart !== "undefined") {
    let catLabels = [];
    let catTotals = [];

    if (categoryData && categoryData.length > 0) {
      catLabels = categoryData.map((c) => c.category || "Uncategorized");
      catTotals = categoryData.map((c) => c.total || 0);
    }

    const palette = ["#10B981", "#3B82F6", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#64748B"];

    if (catTotals.length === 0) {
      const parent = categoryCtx.parentElement;
      if (parent) {
        categoryCtx.style.display = "none";
        const emptyMsg = document.createElement("div");
        emptyMsg.className = "chart-empty";
        emptyMsg.innerHTML = `
          <p style="font-size: 0.85rem; color: var(--text-muted);">No expenses recorded yet.</p>
        `;
        parent.appendChild(emptyMsg);
      }
    } else {
      categoryChartInstance = new Chart(categoryCtx, {
        type: "doughnut",
        data: {
          labels: catLabels,
          datasets: [
            {
              data: catTotals,
              backgroundColor: palette.slice(0, catLabels.length),
              borderWidth: 2,
              borderColor: "transparent",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "70%",
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                color: textColor,
                font: { family: "Inter", size: 11 },
                usePointStyle: true,
                padding: 12,
              },
            },
            tooltip: {
              padding: 10,
              cornerRadius: 6,
              callbacks: {
                label: function (context) {
                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? Math.round((context.raw / total) * 100) : 0;
                  return `${context.label}: ₹${context.raw.toLocaleString("en-IN")} (${pct}%)`;
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
// TABLE SEARCH & FILTERS
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

      const matchesType = activeType === "all" || rowType === activeType;
      const matchesCategory = category === "all" || rowCategory === category;
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
// MODALS (ADD & EDIT)
// =========================================================================
function initModals() {
  const addModal = document.getElementById("add-transaction-modal");
  const editModal = document.getElementById("edit-transaction-modal");

  const openAddBtns = document.querySelectorAll(".open-add-modal-btn");
  const closeBtns = document.querySelectorAll(".modal-close-trigger");

  const addDateInput = document.getElementById("modal-add-date");
  if (addDateInput && !addDateInput.value) {
    addDateInput.value = new Date().toISOString().split("T")[0];
  }

  openAddBtns.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (addModal) {
        const reqType = btn.getAttribute("data-type");
        if (reqType) {
          selectModalType(addModal, reqType);
        }
        addModal.classList.add("show");
      }
    });
  });

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

  if (addModal) {
    setupSegmentedControl(addModal);
    setupCategoryQuickPills(addModal);
  }

  if (editModal) {
    setupSegmentedControl(editModal);
    setupCategoryQuickPills(editModal);

    const editBtns = document.querySelectorAll(".tx-edit-btn");
    editBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const date = btn.getAttribute("data-date");
        const category = btn.getAttribute("data-category");
        const amount = btn.getAttribute("data-amount");
        const desc = btn.getAttribute("data-desc");
        const type = btn.getAttribute("data-type") || "expense";

        const editForm = document.getElementById("edit-tx-form");
        if (editForm) {
          editForm.action = `/edit/${id}`;
        }

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

  const deleteBtns = document.querySelectorAll(".tx-delete-btn");
  deleteBtns.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (!confirm("Delete this transaction?")) {
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
