const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

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

  const dateInput = document.getElementById("date-input");
  const dateError = document.getElementById("date-error");

  const today = new Date();
  const minDate = new Date(today);
  minDate.setDate(minDate.getDate() + 1);
  const maxDate = new Date(today);
  maxDate.setDate(maxDate.getDate() + 60);

  function toIso(d) {
    return d.toISOString().slice(0, 10);
  }

  dateInput.min = toIso(minDate);
  dateInput.max = toIso(maxDate);

  dateInput.addEventListener("change", async () => {
    dateError.textContent = "";
    if (!dateInput.value) return;

    const d = new Date(dateInput.value + "T00:00:00");
    if (d.getDay() === 0) {
      dateError.textContent = "По воскресеньям не работаем — выбери другой день";
      dateInput.value = "";
      return;
    }

    state.dateStr = dateInput.value.replaceAll("-", "");
    state.dateLabel = dateInput.value;

    await loadSlots();
  });

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
    showScreen("screen-done");
  }
}

// ── Оплата ───────────────────────────────────────────────────────────────

function initPayment(paymentType) {
  showScreen("screen-payment");

  const descEl = document.getElementById("payment-desc");
  const errEl = document.getElementById("payment-error");
  const btn = document.getElementById("payment-btn");
  const waitEl = document.getElementById("payment-waiting");

  if (paymentType !== "session" && paymentType !== "product") {
    errEl.textContent = "Некорректный тип оплаты — вернись в чат и попробуй снова";
    return;
  }

  let paymentId = null;
  let paymentUrl = null;
  let pollTimer = null;

  async function create() {
    descEl.textContent = "Готовим ссылку на оплату…";

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
      descEl.textContent = "";
      errEl.textContent = "Не удалось создать оплату. Попробуй ещё раз через минуту.";
      return;
    }

    paymentId = data.payment_id;
    paymentUrl = data.url;
    descEl.textContent = `К оплате: ${data.amount}₽`;
    btn.textContent = `💳 Оплатить ${data.amount}₽`;
    btn.classList.remove("hidden");
  }

  btn.addEventListener("click", () => {
    if (!paymentUrl) return;
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

  const nameEl = document.getElementById("result-name");
  const dateEl = document.getElementById("result-date");
  const textEl = document.getElementById("result-text");
  const exerciseEl = document.getElementById("result-exercise");
  const imageEl = document.getElementById("result-image");
  const emptyEl = document.getElementById("result-empty");

  fetch(`/api/results/latest?initData=${encodeURIComponent(tg.initData)}`)
    .then((res) => res.json())
    .then((data) => {
      if (!data.result) {
        emptyEl.textContent = "Ты ещё не проходил(а) тест — пройди его в чате с ботом 🤍";
        emptyEl.classList.remove("hidden");
        return;
      }
      const r = data.result;
      nameEl.textContent = r.name;
      dateEl.textContent = formatDate(r.created_at);
      textEl.textContent = r.text;
      exerciseEl.textContent = r.exercise;
      imageEl.src = r.image;
      imageEl.classList.remove("hidden");
    })
    .catch(() => {
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
  const stepX = (width - pad * 2) / (points.length - 1);
  const lineColor = getComputedStyle(document.body).getPropertyValue("--tg-theme-link-color") || "#2481cc";

  ctx.strokeStyle = lineColor.trim() || "#2481cc";
  ctx.lineWidth = 2;
  ctx.beginPath();

  points.forEach((p, i) => {
    const x = pad + i * stepX;
    const y = height - pad - (p.score / 10) * (height - pad * 2);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();
}

function initCabinet() {
  showScreen("screen-cabinet");

  const tabButtons = document.querySelectorAll(".tab-btn");
  const panels = {
    results: document.getElementById("tab-results"),
    bookings: document.getElementById("tab-bookings"),
    diary: document.getElementById("tab-diary"),
  };

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      for (const key in panels) {
        panels[key].classList.toggle("hidden", key !== btn.dataset.tab);
      }
    });
  });

  fetch(`/api/cabinet?initData=${encodeURIComponent(tg.initData)}`)
    .then((res) => res.json())
    .then((data) => {
      if (data.result) {
        panels.results.innerHTML =
          `<div class="list-item"><div>${data.result.name}</div>` +
          `<div class="hint">${formatDate(data.result.created_at)}</div></div>`;
      } else {
        panels.results.innerHTML = '<p class="hint">Ты ещё не проходил(а) тест.</p>';
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
      panels.results.innerHTML = '<p class="hint">Не удалось загрузить данные кабинета.</p>';
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
