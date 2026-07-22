const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

function haptic(kind, style) {
  try {
    const h = tg.HapticFeedback;
    if (!h) return;
    if (kind === "selection") h.selectionChanged();
    else if (kind === "impact") h.impactOccurred(style || "light");
    else if (kind === "notification") h.notificationOccurred(style || "success");
  } catch (e) {}
}

const TYPE_ICONS = {
  A: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  B: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 18a4.5 4.5 0 0 1-.5-8.97A5.5 5.5 0 0 1 16.5 9a4 4 0 0 1 .5 7.98"/><path d="M13 17l-2 3M9.5 17l-2 3"/></svg>',
  C: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M4.9 6.5l14.2 11M4.9 17.5l14.2-11"/></svg>',
  D: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>',
};

function cleanTypeName(name) {
  return (name || "").replace(/^\S+\s*/u, "");
}

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((el) => {
    el.classList.toggle("hidden", el.id !== id);
  });
}

document.querySelectorAll(".back").forEach((btn) => {
  btn.addEventListener("click", () => {
    showScreen(btn.dataset.back);
  });
});

// ── Бронирование ─────────────────────────────────────────────────────────

function initBooking() {
  const state = { dateStr: "", dateLabel: "", time: "" };

  const DAY_NAMES_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

  function monthLabel(d) {
    const m = d.toLocaleDateString("ru-RU", { month: "long" });
    return `${m[0].toUpperCase()}${m.slice(1)} ${d.getFullYear()}`;
  }

  function toIsoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function buildDayPicker() {
    const picker = document.getElementById("day-picker");
    const today = new Date();
    let monthKey = "";
    let grid = null;

    for (let i = 1; i <= 60; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      if (d.getDay() === 0) continue;

      const key = `${d.getFullYear()}-${d.getMonth()}`;
      if (key !== monthKey) {
        monthKey = key;
        const label = document.createElement("div");
        label.className = "month-label";
        label.textContent = monthLabel(d);
        picker.appendChild(label);
        grid = document.createElement("div");
        grid.className = "day-grid";
        picker.appendChild(grid);
      }

      const chip = document.createElement("button");
      chip.className = "day-chip";
      chip.innerHTML = `<span class="wd">${DAY_NAMES_SHORT[d.getDay()]}</span><span class="dn">${d.getDate()}</span>`;
      chip.addEventListener("click", () => {
        document.querySelectorAll(".day-chip.selected").forEach((el) => el.classList.remove("selected"));
        chip.classList.add("selected");
        haptic("selection");

        state.dateStr = toIsoLocal(d).replaceAll("-", "");
        state.dateLabel = d.toLocaleDateString("ru-RU", {
          weekday: "long", day: "numeric", month: "long",
        });

        loadSlots();
      });
      grid.appendChild(chip);
    }
  }

  buildDayPicker();

  const slotsBox = document.getElementById("slots");
  const timeEmpty = document.getElementById("time-empty");
  const timeTitle = document.getElementById("time-title");

  async function loadSlots() {
    timeTitle.textContent = `${state.dateLabel} — выбери время`;
    slotsBox.innerHTML = "";
    timeEmpty.classList.add("hidden");

    let data;
    try {
      const res = await fetch(
        `/api/booking/slots?date=${state.dateStr}&initData=${encodeURIComponent(tg.initData)}`
      );
      data = await res.json();
      if (!res.ok) throw new Error(data.error || "request_failed");
    } catch (e) {
      tg.showAlert("Не удалось загрузить свободное время. Попробуй ещё раз.");
      return;
    }

    showScreen("screen-time");

    if (!data.free || data.free.length === 0) {
      timeEmpty.classList.remove("hidden");
      return;
    }

    data.free.forEach((slot) => {
      const btn = document.createElement("button");
      btn.className = "slot-btn";
      btn.textContent = slot;
      btn.addEventListener("click", () => {
        haptic("selection");
        state.time = slot;
        showScreen("screen-concern");
      });
      slotsBox.appendChild(btn);
    });
  }

  const concernInput = document.getElementById("concern-input");
  const concernError = document.getElementById("concern-error");
  const concernBtn = document.getElementById("concern-submit-btn");

  concernBtn.addEventListener("click", submitBooking);

  async function submitBooking() {
    concernError.textContent = "";
    const concern = concernInput.value.trim();
    if (!concern) {
      concernError.textContent = "Напиши в двух словах, что тебя беспокоит";
      haptic("notification", "error");
      return;
    }

    concernBtn.disabled = true;
    concernBtn.textContent = "Отправляю…";

    let res, data;
    try {
      res = await fetch("/api/booking/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initData: tg.initData,
          date: state.dateStr,
          time: state.time,
          concern,
        }),
      });
      data = await res.json();
    } catch (e) {
      concernBtn.disabled = false;
      concernBtn.textContent = "Отправить запрос";
      tg.showAlert("Не удалось отправить запрос. Проверь связь и попробуй снова.");
      return;
    }

    if (!res.ok) {
      concernBtn.disabled = false;
      concernBtn.textContent = "Отправить запрос";
      if (data.error === "slot_unavailable") {
        tg.showAlert("Это время только что заняли — выбери другое.");
        await loadSlots();
        return;
      }
      tg.showAlert("Не удалось отправить запрос. Попробуй ещё раз.");
      return;
    }

    document.getElementById("done-text").textContent =
      `${state.dateLabel}, в ${state.time}`;
    haptic("notification", "success");
    showScreen("screen-done");
  }
}

// ── Оплата ───────────────────────────────────────────────────────────────

const PAYMENT_TITLES = {
  session: "Консультация с Евой Левиной",
  product: "Полный разбор твоего типа тревоги",
};

function initPayment(paymentType) {
  showScreen("screen-payment");

  const loadingEl = document.getElementById("payment-loading");
  const errEl = document.getElementById("payment-error");
  const btn = document.getElementById("payment-btn");
  const waitEl = document.getElementById("payment-waiting");
  const titleEl = document.getElementById("payment-title");
  const amountEl = document.getElementById("payment-amount");

  if (paymentType !== "session" && paymentType !== "product") {
    loadingEl.classList.add("hidden");
    errEl.textContent = "Некорректный тип оплаты — вернись в чат и попробуй снова";
    return;
  }

  titleEl.textContent = PAYMENT_TITLES[paymentType];

  let paymentId = null;
  let paymentUrl = null;
  let pollTimer = null;

  async function create() {
    loadingEl.classList.remove("hidden");

    let res, data;
    try {
      res = await fetch("/api/payment/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData: tg.initData, payment_type: paymentType }),
      });
      data = await res.json();
      if (!res.ok) throw new Error(data.error || "request_failed");
    } catch (e) {
      loadingEl.classList.add("hidden");
      errEl.textContent = "Не удалось создать оплату. Попробуй ещё раз через минуту.";
      return;
    }

    paymentId = data.payment_id;
    paymentUrl = data.url;
    loadingEl.classList.add("hidden");
    amountEl.textContent = `К оплате: ${data.amount}₽`;
    btn.textContent = `💳 Оплатить ${data.amount}₽`;
    btn.classList.remove("hidden");
  }

  btn.addEventListener("click", () => {
    if (!paymentUrl) return;
    haptic("impact", "light");
    tg.openLink(paymentUrl);
    btn.classList.add("hidden");
    waitEl.classList.remove("hidden");
    startPolling();
  });

  function startPolling() {
    pollTimer = setInterval(async () => {
      let res, data;
      try {
        res = await fetch(
          `/api/payment/status?payment_id=${encodeURIComponent(paymentId)}&initData=${encodeURIComponent(tg.initData)}`
        );
        data = await res.json();
        if (!res.ok) return;
      } catch (e) {
        return;
      }

      if (data.status === "succeeded") {
        clearInterval(pollTimer);
        haptic("notification", "success");
        showScreen("screen-payment-done");
      } else if (data.status === "canceled") {
        clearInterval(pollTimer);
        waitEl.classList.add("hidden");
        errEl.textContent = "Платёж отменён. Можно попробовать ещё раз.";
        btn.classList.remove("hidden");
      }
    }, 2500);
  }

  create();
}

// ── Результат квиза ──────────────────────────────────────────────────────

function formatDate(unixSeconds) {
  const d = new Date(unixSeconds * 1000);
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

function initResult() {
  showScreen("screen-result");

  const loadingEl = document.getElementById("result-loading");
  const badgeEl = document.getElementById("result-badge");
  const nameEl = document.getElementById("result-name");
  const dateEl = document.getElementById("result-date");
  const textEl = document.getElementById("result-text");
  const exerciseEl = document.getElementById("result-exercise");
  const imageEl = document.getElementById("result-image");
  const bodyEl = document.getElementById("result-body");
  const emptyEl = document.getElementById("result-empty");

  fetch(`/api/results/latest?initData=${encodeURIComponent(tg.initData)}`)
    .then((res) => res.json())
    .then((data) => {
      loadingEl.classList.add("hidden");
      if (!data.result) {
        emptyEl.textContent = "Ты ещё не проходил(а) тест — пройди его в чате с ботом 🤍";
        emptyEl.classList.remove("hidden");
        return;
      }
      const r = data.result;
      badgeEl.innerHTML = TYPE_ICONS[r.type] || "";
      badgeEl.classList.remove("hidden");
      nameEl.textContent = cleanTypeName(r.name);
      dateEl.textContent = formatDate(r.created_at);
      textEl.textContent = r.text;
      exerciseEl.textContent = r.exercise;
      imageEl.src = r.image;
      imageEl.classList.remove("hidden");
      bodyEl.classList.remove("hidden");
    })
    .catch(() => {
      loadingEl.classList.add("hidden");
      emptyEl.textContent = "Не удалось загрузить результат. Попробуй ещё раз.";
      emptyEl.classList.remove("hidden");
    });
}

// ── Личный кабинет ───────────────────────────────────────────────────────

const BOOKING_STATUS_LABELS = {
  pending: "⏳ ожидает подтверждения",
  confirmed: "✅ подтверждена",
  declined: "❌ отклонена",
};

function drawDiaryChart(entries) {
  const canvas = document.getElementById("diary-chart");
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || canvas.width;
  const height = canvas.clientHeight || canvas.height;
  canvas.width = width;
  canvas.height = height;

  const points = entries.slice().reverse();
  ctx.clearRect(0, 0, width, height);

  if (points.length < 2) return;

  const pad = 10;
  const stepX = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;
  const accent = getComputedStyle(document.body).getPropertyValue("--accent").trim() || "#9C8469";

  const coords = points.map((p, i) => ({
    x: pad + i * stepX,
    y: height - pad - (p.score / 10) * (height - pad * 2),
  }));

  // Заливка под линией — мягкий градиент в тон акцента
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, `color-mix(in srgb, ${accent} 35%, transparent)`);
  gradient.addColorStop(1, `color-mix(in srgb, ${accent} 0%, transparent)`);

  ctx.beginPath();
  ctx.moveTo(coords[0].x, height - pad);
  coords.forEach((c) => ctx.lineTo(c.x, c.y));
  ctx.lineTo(coords[coords.length - 1].x, height - pad);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.beginPath();
  coords.forEach((c, i) => {
    if (i === 0) ctx.moveTo(c.x, c.y);
    else ctx.lineTo(c.x, c.y);
  });
  ctx.strokeStyle = accent;
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke();

  coords.forEach((c) => {
    ctx.beginPath();
    ctx.arc(c.x, c.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = accent;
    ctx.fill();
  });
}

const ICON_CALENDAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="16" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/></svg>';
const ICON_BOOK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z"/><path d="M4 19a2.5 2.5 0 0 1 2.5-2.5H20"/></svg>';

function initCabinet() {
  showScreen("screen-cabinet");

  const tabButtons = document.querySelectorAll(".bottom-tab");
  const panels = {
    profile: document.getElementById("tab-profile"),
    bookings: document.getElementById("tab-bookings"),
    diary: document.getElementById("tab-diary"),
  };

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      haptic("selection");
      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      for (const key in panels) {
        panels[key].classList.toggle("hidden", key !== btn.dataset.tab);
      }
    });
  });

  fetch(`/api/cabinet?initData=${encodeURIComponent(tg.initData)}`)
    .then((res) => res.json())
    .then((data) => {
      const heroHtml = data.result
        ? `<div class="hero-card with-photo" style="background-image:url('${data.result.image}')">
             <div class="hero-badge">Твой тип тревоги</div>
             <div class="hero-name">${cleanTypeName(data.result.name)}</div>
             <div class="hero-date">Пройден ${formatDate(data.result.created_at)}</div>
           </div>`
        : `<div class="hero-card">
             <div class="hero-badge">Тип тревоги</div>
             <div class="hero-name">Пройди тест, чтобы узнать свой тип</div>
           </div>`;

      const today = new Date();
      const todayStr = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}`;
      const upcoming = (data.bookings || [])
        .filter((b) => b.status !== "declined" && b.date >= todayStr)
        .sort((a, b) => a.date.localeCompare(b.date))[0];

      const promoHtml = upcoming
        ? `<div class="promo-card">
             <div class="promo-title">Ближайшая запись</div>
             <div class="promo-sub">${upcoming.date_label} в ${upcoming.time} — ${BOOKING_STATUS_LABELS[upcoming.status] || upcoming.status}</div>
           </div>`
        : `<div class="promo-card promo-clickable" id="promo-book">
             <div class="promo-title">Готовы сделать шаг?</div>
             <div class="promo-sub">Запишись на консультацию с Евой — разберём твою тревогу вместе</div>
           </div>`;

      panels.profile.innerHTML = `
        ${heroHtml}
        <div class="quick-actions">
          <button class="quick-action" id="qa-booking"><span class="qa-icon">${ICON_CALENDAR}</span>Записаться</button>
          <button class="quick-action" id="qa-diary"><span class="qa-icon">${ICON_BOOK}</span>Дневник</button>
        </div>
        ${promoHtml}
      `;

      document.getElementById("qa-booking").addEventListener("click", () => {
        haptic("impact", "light");
        location.href = "index.html?screen=booking";
      });
      document.getElementById("qa-diary").addEventListener("click", () => {
        haptic("selection");
        document.querySelector('.bottom-tab[data-tab="diary"]').click();
      });
      const promoBookEl = document.getElementById("promo-book");
      if (promoBookEl) {
        promoBookEl.addEventListener("click", () => {
          haptic("impact", "light");
          location.href = "index.html?screen=booking";
        });
      }

      if (!data.bookings || data.bookings.length === 0) {
        panels.bookings.innerHTML = '<p class="hint">Пока нет записей на сессию.</p>';
      } else {
        panels.bookings.innerHTML = data.bookings.map((b) => `
          <div class="list-item">
            <div>${b.date_label} в ${b.time}</div>
            <div class="hint">${BOOKING_STATUS_LABELS[b.status] || b.status}</div>
          </div>
        `).join("");
      }

      if (!data.diary || data.diary.length === 0) {
        panels.diary.innerHTML = '<canvas id="diary-chart"></canvas><p class="hint">Пока нет записей в дневнике.</p>';
      } else {
        drawDiaryChart(data.diary);
        document.getElementById("diary-list").innerHTML = data.diary.slice(0, 20).map((d) => `
          <div class="list-item">
            <div>${formatDate(d.created_at)} — тревога ${d.score}/10</div>
            ${d.note ? `<div class="hint">${d.note}</div>` : ""}
          </div>
        `).join("");
      }
    })
    .catch(() => {
      panels.profile.innerHTML = '<p class="hint">Не удалось загрузить данные кабинета.</p>';
    });
}

// ── Вход ─────────────────────────────────────────────────────────────────

const params = new URLSearchParams(location.search);
const screen = params.get("screen") || "booking";

if (screen === "payment") {
  initPayment(params.get("type") || "");
} else if (screen === "result") {
  initResult();
} else if (screen === "cabinet") {
  initCabinet();
} else {
  initBooking();
}
