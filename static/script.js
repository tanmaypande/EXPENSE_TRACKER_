
// Line Chart
new Chart(document.getElementById("lineChart"), {
  type: "line",
  data: {
    labels: ["Jan", "Feb", "Mar", "Apr"],
    datasets: [{
      label: "Expenses",
      data: [4000, 3500, 5000, 4500],
      fill: false
    }]
  }
});
