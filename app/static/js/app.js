"use strict";

const $ = (sel) => document.querySelector(sel);
const fmt = (n, d = 2) =>
  n === null || n === undefined || Number.isNaN(n)
    ? "—"
    : Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const money = (n) => (n === null || n === undefined ? "—" : "$" + fmt(n));
const pct = (n) => (n === null || n === undefined ? "—" : (n >= 0 ? "+" : "") + fmt(n) + "%");
const cls = (n) => (n >= 0 ? "up" : "down");

function bigMoney(n) {
  if (n === null || n === undefined) return "—";
  const a = Math.abs(n);
  if (a >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  return money(n);
}

// ---------------- Tabs ----------------
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $("#tab-" + t.dataset.tab).classList.add("active");
    if (t.dataset.tab === "portfolio") loadPortfolio();
  });
});

// ---------------- Week / picks ----------------
async function loadWeek() {
  const res = await fetch("/api/week");
  const data = await res.json();
  renderWeek(data);
}

function renderWeek(data) {
  $("#week-label").textContent = data.label || "—";
  const badge = $("#engine-badge");
  badge.textContent = data.engine === "claude" ? "Claude AI" : "Heuristic";
  badge.className = "badge " + (data.engine === "claude" ? "" : "heuristic");
  $("#footer-engine").textContent = data.engine;
  if (data.disclaimer) $("#disclaimer").innerHTML = "&#9888; " + data.disclaimer;

  const grid = $("#picks-grid");
  if (!data.picks || !data.picks.length) {
    grid.innerHTML = '<div class="loading">No picks available right now.</div>';
    return;
  }
  grid.innerHTML = data.picks.map(cardHTML).join("");
  data.picks.forEach((p) => {
    $("#card-" + p.symbol).addEventListener("click", () => openDetail(p.symbol));
  });
}

function cardHTML(p) {
  const chg = p.signals ? p.signals.ret_5d : null;
  return `
  <div class="card" id="card-${p.symbol}">
    <div class="card-head">
      <div>
        <div class="sym">${p.symbol}</div>
        <div class="chg ${cls(chg ?? 0)}">${pct(chg)} <span style="color:var(--muted)">5d</span></div>
      </div>
      <div style="text-align:right">
        <div class="price">${money(p.price_at_pick)}</div>
        <span class="risk ${p.risk}">${p.risk}</span>
      </div>
    </div>
    <div class="window">
      <div class="daychip buy"><div class="lbl">Buy</div><div class="day">${p.buy_day}</div></div>
      <div class="daychip sell"><div class="lbl">Sell</div><div class="day">${p.sell_day}</div></div>
    </div>
    <div class="rationale">${p.rationale || ""}</div>
    <div class="card-foot">
      <span>Budget <b>${money(p.budget)}</b> · ${fmt(p.shares, 3)} sh</span>
      <span>Target <b>${money(p.target)}</b></span>
    </div>
  </div>`;
}

// ---------------- Portfolio ----------------
async function loadPortfolio() {
  const res = await fetch("/api/portfolio");
  const data = await res.json();
  const s = data.summary;
  $("#summary-cards").innerHTML = `
    <div class="scard"><div class="k">Invested</div><div class="v">${money(s.invested)}</div></div>
    <div class="scard"><div class="k">Current Value</div><div class="v">${money(s.value)}</div></div>
    <div class="scard"><div class="k">Total P&L</div><div class="v ${cls(s.pnl)}">${money(s.pnl)}</div></div>
    <div class="scard"><div class="k">Return</div><div class="v ${cls(s.pnl_pct)}">${pct(s.pnl_pct)}</div></div>
    <div class="scard"><div class="k">Positions</div><div class="v">${s.num_positions}</div></div>`;

  const tbody = $("#portfolio-table tbody");
  tbody.innerHTML = data.positions
    .map(
      (r) => `
    <tr data-sym="${r.symbol}">
      <td><span class="tsym">${r.symbol}</span></td>
      <td>${money(r.entry_price)}</td>
      <td>${fmt(r.shares, 3)}</td>
      <td>${money(r.current_price)}</td>
      <td>${money(r.current_value)}</td>
      <td class="${cls(r.pnl)}">${money(r.pnl)}</td>
      <td class="${cls(r.pnl_pct)}">${pct(r.pnl_pct)}</td>
      <td style="color:var(--muted)">${r.buy_day}→${r.sell_day}</td>
    </tr>`
    )
    .join("");
  tbody.querySelectorAll("tr").forEach((tr) =>
    tr.addEventListener("click", () => openDetail(tr.dataset.sym))
  );
}

// ---------------- Detail drawer ----------------
let chart = null;
let currentSym = null;

function closeDetail() {
  $("#detail").classList.add("hidden");
  $("#overlay").classList.add("hidden");
  if (chart) { chart.destroy(); chart = null; }
}
$("#detail-close").addEventListener("click", closeDetail);
$("#overlay").addEventListener("click", closeDetail);

async function openDetail(symbol) {
  currentSym = symbol;
  $("#overlay").classList.remove("hidden");
  $("#detail").classList.remove("hidden");
  $("#detail-body").innerHTML = '<div class="loading">Loading ' + symbol + "…</div>";

  const res = await fetch("/api/stock/" + symbol);
  const d = await res.json();
  const q = d.quote || {};
  const f = d.fundamentals || {};
  const name = f.longName || f.shortName || symbol;

  $("#detail-body").innerHTML = `
    <div class="d-head"><span class="d-sym">${symbol}</span><span class="d-name">${name}</span></div>
    <div class="d-price">${money(q.price)}</div>
    <div class="d-meta ${cls(q.change_pct ?? 0)}">${money(q.change)} (${pct(q.change_pct)}) today
      <span style="color:var(--muted)">· ${f.sector || ""}</span></div>

    <div class="range-btns" id="range-btns">
      ${["1mo", "6mo", "1y", "5y"].map((r) =>
        `<button data-range="${r}" class="${r === "6mo" ? "active" : ""}">${r}</button>`).join("")}
    </div>
    <div class="chart-box"><canvas id="price-chart" height="190"></canvas></div>

    <div class="stats">
      ${stat("Market Cap", bigMoney(q.market_cap))}
      ${stat("P/E (TTM)", fmt(f.trailingPE))}
      ${stat("52w High", money(q.year_high))}
      ${stat("52w Low", money(q.year_low))}
      ${stat("Beta", fmt(f.beta))}
      ${stat("Div Yield", f.dividendYield ? fmt(f.dividendYield) + "%" : "—")}
      ${stat("EPS (TTM)", fmt(f.trailingEps))}
      ${stat("Avg Volume", q.volume ? bigMoney(f.averageVolume).replace("$", "") : "—")}
    </div>

    ${f.longBusinessSummary ? `<div class="d-section-title">About</div>
      <div class="summary-text">${f.longBusinessSummary.slice(0, 420)}…</div>` : ""}

    <div class="d-section-title">Recent News</div>
    <div id="news-list">${(d.news && d.news.length)
      ? d.news.map(newsHTML).join("")
      : '<div style="color:var(--muted);font-size:13px">No recent headlines.</div>'}</div>
  `;

  $("#range-btns").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      $("#range-btns .active")?.classList.remove("active");
      b.classList.add("active");
      loadChart(symbol, b.dataset.range);
    })
  );
  loadChart(symbol, "6mo");
}

const stat = (k, v) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;
function newsHTML(n) {
  return `<a class="news-item" href="${n.link || "#"}" target="_blank" rel="noopener">
    ${n.title}<div class="src">${n.publisher || ""}</div></a>`;
}

async function loadChart(symbol, range) {
  const res = await fetch(`/api/stock/${symbol}/history?range=${range}`);
  const hist = await res.json();
  if (chart) chart.destroy();
  const labels = hist.map((h) => h.t.slice(0, 10));
  const data = hist.map((h) => h.close);
  const up = data.length && data[data.length - 1] >= data[0];
  const color = up ? "#1ecb81" : "#ff5c5c";
  const ctx = $("#price-chart").getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, 190);
  grad.addColorStop(0, up ? "rgba(30,203,129,0.32)" : "rgba(255,92,92,0.32)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ data, borderColor: color, backgroundColor: grad,
      fill: true, borderWidth: 2, pointRadius: 0, tension: 0.25 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
      scales: {
        x: { ticks: { color: "#8b97a7", maxTicksLimit: 6 }, grid: { display: false } },
        y: { ticks: { color: "#8b97a7", callback: (v) => "$" + v }, grid: { color: "#1c232c" } },
      },
    },
  });
}

// ---------------- Refresh / countdown ----------------
$("#refresh-btn").addEventListener("click", async () => {
  const btn = $("#refresh-btn");
  btn.disabled = true;
  btn.textContent = "Re-evaluating…";
  try {
    const res = await fetch("/api/week/refresh", { method: "POST" });
    renderWeek(await res.json());
    loadPortfolio();
  } finally {
    btn.disabled = false;
    btn.innerHTML = "&#8635; Re-evaluate";
  }
});

function updateCountdown() {
  const now = new Date();
  const day = now.getDay(); // 0 Sun .. 6 Sat
  const daysToSat = (6 - day + 7) % 7 || 7;
  const next = new Date(now);
  next.setDate(now.getDate() + daysToSat);
  next.setHours(0, 0, 0, 0);
  const h = Math.floor((next - now) / 3.6e6);
  $("#countdown").textContent = `· new picks in ${Math.floor(h / 24)}d ${h % 24}h`;
}

// ---------------- Boot ----------------
loadWeek();
updateCountdown();
setInterval(updateCountdown, 60000);
