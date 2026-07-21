const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const state = { dateStr: "", dateLabel: "", time: "" };

const screens = {
  date: document.getElementById("screen-date"),
  time: document.getElementById("screen-time"),
  concern: document.getElementById("screen-concern"),
  done: document.getElementById("screen-done"),
};

function showScreen(name) {
  for (const key in screens) {
    screens[key].classList.toggle("hidden", key !== name);
  }
}

document.querySelectorAll(".back").forEach((btn) => {
  btn.addEventListener("click", () => {
    tg.MainButton.hide();
    const target = btn.dataset.back.replace("screen-", "");
    showScreen(target);
  });
});

// ── Шаг 1: дата ──────────────────────────────────────────────────────────

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

// ── Шаг 2: время ─────────────────────────────────────────────────────────

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

  showScreen("time");

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
      showScreen("concern");
      setupConcernMainButton();
    });
    slotsBox.appendChild(btn);
  });
}

// ── Шаг 3: что беспокоит ─────────────────────────────────────────────────

const concernInput = document.getElementById("concern-input");
const concernError = document.getElementById("concern-error");

function setupConcernMainButton() {
  tg.MainButton.setText("Отправить запрос");
  tg.MainButton.show();
  tg.MainButton.offClick(submitBooking);
  tg.MainButton.onClick(submitBooking);
}

async function submitBooking() {
  concernError.textContent = "";
  const concern = concernInput.value.trim();
  if (!concern) {
    concernError.textContent = "Напиши в двух словах, что тебя беспокоит";
    return;
  }

  tg.MainButton.showProgress();

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
    tg.MainButton.hideProgress();
    tg.showAlert("Не удалось отправить запрос. Проверь связь и попробуй снова.");
    return;
  }

  tg.MainButton.hideProgress();

  if (!res.ok) {
    if (data.error === "slot_unavailable") {
      tg.showAlert("Это время только что заняли — выбери другое.");
      tg.MainButton.hide();
      await loadSlots();
      return;
    }
    tg.showAlert("Не удалось отправить запрос. Попробуй ещё раз.");
    return;
  }

  tg.MainButton.hide();
  document.getElementById("done-text").textContent =
    `${state.dateLabel}, в ${state.time}`;
  showScreen("done");
}
