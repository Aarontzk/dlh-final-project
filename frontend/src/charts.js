// Bar chart ringan pakai Chart.js. Render ulang menggantikan chart lama.
import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from "chart.js";

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip);

let _chart = null;

/**
 * @param {HTMLCanvasElement} canvas
 * @param {string[]} labels
 * @param {number[]} values
 * @param {string} title
 */
export function renderBar(canvas, labels, values, title) {
  if (_chart) _chart.destroy();
  const GOLD = "#ca8a04";
  const GOLD_BRIGHT = "#daa520";
  const PARCHMENT = "#bfa98a";
  const GRID = "rgba(92, 61, 46, 0.5)";
  _chart = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: title,
          data: values,
          backgroundColor: GOLD,
          hoverBackgroundColor: GOLD_BRIGHT,
          borderColor: GOLD_BRIGHT,
          borderWidth: 1,
          borderRadius: 3,
          maxBarThickness: 28,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#3d2517",
          titleColor: "#f5e6d3",
          bodyColor: "#f5e6d3",
          borderColor: "rgba(202,138,4,0.4)",
          borderWidth: 1,
          titleFont: { family: "Cinzel" },
        },
      },
      scales: {
        x: {
          ticks: { color: PARCHMENT, autoSkip: true, maxRotation: 60, minRotation: 0 },
          grid: { color: GRID },
        },
        y: {
          beginAtZero: true,
          ticks: { color: PARCHMENT },
          grid: { color: GRID },
        },
      },
    },
  });
}
