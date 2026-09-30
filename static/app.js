// Renders the simulation response. Projections are calculated on the server.

const tooltip = document.querySelector("#tooltip");
const chart = document.querySelector("#chart");
const euroWhole = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const fields = {
  car: document.querySelector("#car-fields"),
  apartment: document.querySelector("#apartment-fields"),
  leave: document.querySelector("#leave-fields"),
  spending: document.querySelector("#spending-fields"),
};

let latest = null;
let requestId = 0;
let pinnedMonth = 36;
let profileId = "alex";

function formatEuro(value) {
  const whole = Math.abs(value - Math.round(value)) < 0.001;
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(value);
}

function months(value) {
  return `${Number(value).toFixed(1)} months`;
}

function syncOutputs() {
  const price = Number(document.querySelector("#car-price").value);
  const down = document.querySelector("#down-payment");
  down.max = String(price);
  if (Number(down.value) > price) down.value = String(price);
  text("#price-out", euroWhole.format(price));
  text("#down-out", euroWhole.format(Number(down.value)));
  const years = Number(document.querySelector("#loan-years").value);
  text("#years-out", `${years} ${years === 1 ? "year" : "years"}`);
  text("#running-out", euroWhole.format(Number(document.querySelector("#running-cost").value)));
  text("#rent-out", `${euroWhole.format(Number(document.querySelector("#extra-rent").value))} / month`);
  text("#deposit-out", euroWhole.format(Number(document.querySelector("#deposit").value)));
  const away = Number(document.querySelector("#leave-months").value);
  text("#leave-out", `${away} ${away === 1 ? "month" : "months"}`);
  text("#kept-out", `${document.querySelector("#income-kept").value}%`);
  text("#spend-out", `${euroWhole.format(Number(document.querySelector("#variable-spend").value))} / month`);
  setEnabled("car", document.querySelector("#car-enabled").checked);
  setEnabled("apartment", document.querySelector("#apartment-enabled").checked);
  setEnabled("leave", document.querySelector("#leave-enabled").checked);
  setEnabled("spending", document.querySelector("#spending-enabled").checked);
}

function setEnabled(name, enabled) {
  fields[name].disabled = !enabled;
}

function readInputs() {
  syncOutputs();
  return {
    profile: profileId,
    car: {
      enabled: document.querySelector("#car-enabled").checked,
      price: Number(document.querySelector("#car-price").value),
      down_payment: Number(document.querySelector("#down-payment").value),
      loan_years: Number(document.querySelector("#loan-years").value),
      running_cost: Number(document.querySelector("#running-cost").value),
    },
    apartment: {
      enabled: document.querySelector("#apartment-enabled").checked,
      extra_rent: Number(document.querySelector("#extra-rent").value),
      deposit: Number(document.querySelector("#deposit").value),
    },
    leave: {
      enabled: document.querySelector("#leave-enabled").checked,
      months: Number(document.querySelector("#leave-months").value),
      income_kept_percent: Number(document.querySelector("#income-kept").value),
    },
    spending: {
      enabled: document.querySelector("#spending-enabled").checked,
      variable: Number(document.querySelector("#variable-spend").value),
    },
  };
}

async function refresh() {
  const inputs = readInputs();
  const id = ++requestId;
  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputs),
    });
    const payload = await response.json();
    if (id !== requestId) return;
    if (!response.ok) {
      showError(payload.error || "The simulation could not be updated.");
      return;
    }
    showError("");
    latest = payload;
    render(payload);
  } catch (error) {
    if (id !== requestId) return;
    showError("The simulation could not be reached.");
  }
}

function showError(message) {
  const node = document.querySelector("#error");
  node.hidden = !message;
  node.textContent = message;
}

function render(data) {
  const customer = data.customer;
  const current = data.scenarios.find((scenario) => scenario.id === "current");
  const future = data.scenarios.find((scenario) => scenario.id === "future");

  document.querySelectorAll(".profile").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.profile === customer.id));
  });
  text("#customer-line", `${customer.name} · fictional customer · synthetic banking data`);
  text("#metric-savings", formatEuro(customer.savings));
  text("#metric-income", formatEuro(customer.monthly_net_income));
  text("#metric-expenses", formatEuro(customer.monthly_expenses));
  text("#expense-breakdown", `${formatEuro(customer.monthly_housing)} housing · ${formatEuro(customer.monthly_fixed_other)} other fixed · ${formatEuro(customer.monthly_variable)} variable`);
  text("#metric-disposable", formatEuro(customer.monthly_disposable_income));
  text("#metric-runway", months(customer.emergency_runway_months));
  text("#runway-goal", `Goal: ${customer.emergency_months_goal} months of expenses`);
  text("#metric-deposit", formatEuro(customer.apartment_goal));
  text("#deposit-caption", `${formatEuro(customer.savings)} of ${formatEuro(customer.apartment_goal)}`);
  const meter = document.querySelector("#deposit-meter");
  meter.setAttribute("aria-valuemax", String(customer.apartment_goal));
  meter.setAttribute("aria-valuenow", String(Math.min(customer.savings, customer.apartment_goal)));
  document.querySelector("#deposit-bar").style.width = `${Math.min(customer.apartment_progress, 1) * 100}%`;
  text("#today-savings", formatEuro(customer.savings));
  text("#future-title", future.label);
  text("#future-swatch", future.label);
  text("#legend-future", future.label);
  text("#rate-note", data.assumptions.annual_interest_rate_label + " is a mock rate used only for a financed car.");
  text("#assumption-note", data.assumptions.note);
  text("#fork-caption", `Today splits into the current path and ${future.label.toLowerCase()}.`);

  const details = document.querySelector("#future-details");
  details.replaceChildren();
  const lines = future.decisions.length
    ? future.decisions.map((decision) => decision.detail)
    : ["Nothing is changed from the current path."];
  lines.forEach((line) => {
    const paragraph = document.createElement("p");
    paragraph.className = "detail";
    paragraph.textContent = line;
    details.append(paragraph);
  });

  fillFacts("#current-facts", current);
  fillFacts("#future-facts", future);
  renderStatements("#statements", data.comparison.statements, true);
  renderStatements("#peer-statements", data.peers.statements, false);
  text("#peer-disclaimer", data.peers.disclaimer);
  const traits = document.querySelector("#traits");
  traits.replaceChildren();
  data.peers.traits.forEach((trait) => {
    const item = document.createElement("li");
    item.textContent = trait;
    traits.append(item);
  });
  drawChart(current.series, future.series, customer.apartment_goal, future.label);
  showMonth(pinnedMonth);
}

function fillFacts(selector, scenario) {
  const rows = [
    ["Savings after 1 year", formatEuro(scenario.savings_after_1_year)],
    ["Savings after 3 years", formatEuro(scenario.savings_after_3_years)],
    ["Disposable income in month 1", formatEuro(scenario.monthly_disposable_income)],
    ["Savings rate in month 1", scenario.savings_rate_month_one_label],
    ["Emergency runway in month 1", months(scenario.emergency_runway_after_decision)],
    ["Lowest savings in 3 years", `${formatEuro(scenario.lowest_savings)} · month ${scenario.lowest_savings_month}`],
    ["Apartment deposit", scenario.apartment_goal_label],
  ];
  const list = document.querySelector(selector);
  list.replaceChildren();
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "fact";
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    const strong = document.createElement("strong");
    strong.textContent = value;
    detail.append(strong);
    row.append(term, detail);
    list.append(row);
  });
}

function renderStatements(selector, statements, asList) {
  const host = document.querySelector(selector);
  host.replaceChildren();
  statements.forEach((statement) => {
    const node = document.createElement(asList ? "li" : "p");
    if (!asList) node.className = "peer-line";
    node.textContent = statement;
    host.append(node);
  });
}

function text(selector, value) {
  document.querySelector(selector).textContent = value;
}

function drawChart(currentSeries, futureSeries, goal, futureLabel) {
  const width = 860;
  const height = 390;
  const pad = { left: 78, right: 18, top: 26, bottom: 36 };
  const savings = currentSeries.concat(futureSeries).map((point) => point.savings);
  let min = Math.min(0, ...savings);
  let max = Math.max(goal, ...savings);
  const span = max - min || 1;
  min -= span * 0.06;
  max += span * 0.08;
  const lastMonth = currentSeries[currentSeries.length - 1].month;
  const x = (month) => pad.left + (month / lastMonth) * (width - pad.left - pad.right);
  const y = (value) => pad.top + ((max - value) / (max - min)) * (height - pad.top - pad.bottom);
  const step = span > 80000 ? 20000 : span > 40000 ? 10000 : 5000;
  const ticks = [];
  for (let value = Math.ceil(min / step) * step; value <= max; value += step) ticks.push(value);

  const parts = [];
  ticks.forEach((value) => {
    parts.push(`<line class="chart-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y(value)}" y2="${y(value)}"></line>`);
    parts.push(`<text class="axis-label" x="${pad.left - 8}" y="${y(value) + 4}" text-anchor="end">${euroWhole.format(value)}</text>`);
  });
  [0, 12, 24, 36].forEach((month) => {
    if (month > lastMonth) return;
    parts.push(`<text class="axis-label" x="${x(month)}" y="${height - 12}" text-anchor="middle">${month === 0 ? "Today" : `${month}m`}</text>`);
  });
  parts.push(`<line class="chart-goal" x1="${pad.left}" x2="${width - pad.right}" y1="${y(goal)}" y2="${y(goal)}"></line>`);
  parts.push(`<text class="goal-label" x="${pad.left + 8}" y="${Math.max(16, y(goal) - 8)}">Apartment ${euroWhole.format(goal)}</text>`);
  parts.push(`<path class="series-current" d="${linePath(currentSeries, x, y)}"></path>`);
  parts.push(`<path class="series-future" d="${linePath(futureSeries, x, y)}"></path>`);
  parts.push(`<circle cx="${x(0)}" cy="${y(currentSeries[0].savings)}" r="4" fill="#14283f"></circle>`);
  const cursorMonth = Math.min(pinnedMonth, lastMonth);
  parts.push(`<line id="cursor" class="chart-cursor" x1="${x(cursorMonth)}" x2="${x(cursorMonth)}" y1="${pad.top}" y2="${height - pad.bottom}"></line>`);
  chart.innerHTML = parts.join("");
  chart.dataset.min = String(min);
  chart.dataset.max = String(max);
  chart.dataset.last = String(lastMonth);
  chart.dataset.padLeft = String(pad.left);
  chart.dataset.padRight = String(pad.right);
  chart.setAttribute("aria-label", `Savings on the current path and ${futureLabel} over ${lastMonth} months`);
}

function linePath(series, x, y) {
  return series.map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.month).toFixed(1)} ${y(point.savings).toFixed(1)}`).join(" ");
}

function monthFromEvent(event) {
  if (!latest) return 0;
  const bounds = chart.getBoundingClientRect();
  const last = Number(chart.dataset.last || 36);
  const ratio = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
  const viewX = ratio * 860;
  const padLeft = Number(chart.dataset.padLeft || 78);
  const padRight = Number(chart.dataset.padRight || 18);
  const monthRatio = (viewX - padLeft) / (860 - padLeft - padRight);
  return Math.min(last, Math.max(0, Math.round(monthRatio * last)));
}

function showMonth(month) {
  if (!latest) return;
  const current = latest.scenarios[0].series[month];
  const future = latest.scenarios[1].series[month];
  if (!current || !future) return;
  const when = month === 0 ? "Today" : `Month ${month}`;
  const futureLabel = latest.scenarios[1].label;
  document.querySelector("#chart-readout").textContent =
    `${when}: Current Path ${formatEuro(current.savings)} · ${futureLabel} ${formatEuro(future.savings)} · disposable ${formatEuro(current.monthly_disposable_income)} vs ${formatEuro(future.monthly_disposable_income)}`;
  const cursor = chart.querySelector("#cursor");
  if (cursor && chart.dataset.last) {
    const last = Number(chart.dataset.last);
    const padLeft = Number(chart.dataset.padLeft || 78);
    const padRight = Number(chart.dataset.padRight || 18);
    const x = padLeft + (month / last) * (860 - padLeft - padRight);
    cursor.setAttribute("x1", String(x));
    cursor.setAttribute("x2", String(x));
  }
}

chart.addEventListener("pointermove", (event) => {
  if (!latest) return;
  const month = monthFromEvent(event);
  const current = latest.scenarios[0].series[month];
  const future = latest.scenarios[1].series[month];
  const frame = chart.getBoundingClientRect();
  tooltip.hidden = false;
  tooltip.style.left = `${event.clientX - frame.left}px`;
  tooltip.style.top = `${event.clientY - frame.top}px`;
  const when = month === 0 ? "Today" : `Month ${month}`;
  tooltip.textContent = `${when}. Current Path ${formatEuro(current.savings)}. ${latest.scenarios[1].label} ${formatEuro(future.savings)}.`;
  showMonth(month);
});

chart.addEventListener("pointerleave", () => {
  tooltip.hidden = true;
  showMonth(pinnedMonth);
});

chart.addEventListener("click", (event) => {
  pinnedMonth = monthFromEvent(event);
  showMonth(pinnedMonth);
});

document.querySelectorAll("input").forEach((input) => {
  input.addEventListener("input", () => {
    clearPreset();
    refresh();
  });
});

document.querySelectorAll(".profile").forEach((button) => {
  button.addEventListener("click", () => {
    profileId = button.dataset.profile;
    if (!document.querySelector("#spending-enabled").checked && latest) {
      const variable = button.dataset.profile === "sam" ? 1400 : 850;
      document.querySelector("#variable-spend").value = String(Math.max(200, variable - 200));
    }
    clearPreset();
    refresh();
  });
});

document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    applyPreset(button.dataset.preset);
    document.querySelectorAll("[data-preset]").forEach((other) => {
      other.setAttribute("aria-pressed", String(other === button));
    });
    refresh();
  });
});

function clearPreset() {
  document.querySelectorAll("[data-preset]").forEach((button) => button.setAttribute("aria-pressed", "false"));
}

function applyPreset(name) {
  const variable = latest?.customer.monthly_variable ?? 850;
  const presets = {
    city: { car: [true, 18000, 3000, 4, 180], apartment: false, leave: false, spending: false },
    family: { car: [true, 32000, 4000, 6, 280], apartment: false, leave: false, spending: false },
    flat: { car: false, apartment: [true, 350, 1800], leave: false, spending: false },
    leave: { car: false, apartment: false, leave: [true, 6, 0], spending: false },
    spend: { car: false, apartment: false, leave: false, spending: [true, Math.max(200, variable - 200)] },
    stack: { car: [true, 24000, 4000, 5, 220], apartment: [true, 250, 1500], leave: false, spending: false },
    clear: { car: false, apartment: false, leave: false, spending: false },
  };
  const preset = presets[name];
  setCar(preset.car);
  setApartment(preset.apartment);
  setLeave(preset.leave);
  setSpending(preset.spending, variable);
}

function setCar(value) {
  const on = Array.isArray(value);
  document.querySelector("#car-enabled").checked = on;
  if (!on) return;
  document.querySelector("#car-price").value = String(value[1]);
  document.querySelector("#down-payment").value = String(value[2]);
  document.querySelector("#loan-years").value = String(value[3]);
  document.querySelector("#running-cost").value = String(value[4]);
}

function setApartment(value) {
  const on = Array.isArray(value);
  document.querySelector("#apartment-enabled").checked = on;
  if (!on) return;
  document.querySelector("#extra-rent").value = String(value[1]);
  document.querySelector("#deposit").value = String(value[2]);
}

function setLeave(value) {
  const on = Array.isArray(value);
  document.querySelector("#leave-enabled").checked = on;
  if (!on) return;
  document.querySelector("#leave-months").value = String(value[1]);
  document.querySelector("#income-kept").value = String(value[2]);
}

function setSpending(value, fallback) {
  const on = Array.isArray(value);
  document.querySelector("#spending-enabled").checked = on;
  document.querySelector("#variable-spend").value = String(on ? value[1] : Math.max(200, fallback - 200));
}

refresh();
