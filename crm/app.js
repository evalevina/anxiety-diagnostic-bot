const STATUS_LABELS = {
  pending: "⏳ ожидает подтверждения",
  confirmed: "✅ подтверждена",
  declined: "❌ отклонена",
};

const TYPE_LABELS = { A: "Сканер", B: "Катастрофист", C: "Замиратель", D: "Контролёр" };

let STAGES = [];
let currentSearch = "";
let panelUserId = null;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    credentials: "same-origin",
  });
  if (res.status === 401) {
    showLogin();
    throw new Error("unauthorized");
  }
  return res;
}

function showLogin() {
  document.getElementById("screen-login").classList.remove("hidden");
  document.getElementById("screen-app").classList.add("hidden");
}

function showApp() {
  document.getElementById("screen-login").classList.add("hidden");
  document.getElementById("screen-app").classList.remove("hidden");
}

// ── Логин ────────────────────────────────────────────────────────────────

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("login-error");
  const password = document.getElementById("login-password").value;
  errEl.textContent = "";

  let res;
  try {
    res = await fetch("/api/crm/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ password }),
    });
  } catch (e2) {
    errEl.textContent = "Не удалось подключиться. Попробуй ещё раз.";
    return;
  }

  if (res.status === 429) {
    errEl.textContent = "Слишком много попыток — подожди немного.";
    return;
  }
  if (!res.ok) {
    errEl.textContent = "Неверный пароль.";
    return;
  }

  await bootApp();
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/crm/logout", { method: "POST", credentials: "same-origin" });
  showLogin();
});

// ── Доска ────────────────────────────────────────────────────────────────

function clientDisplayName(c) {
  const name = [c.first_name, c.last_name].filter(Boolean).join(" ").trim();
  if (name) return name;
  return c.username ? `@${c.username}` : `id${c.user_id}`;
}

function relativeActivity(ts) {
  if (!ts) return "нет активности";
  const days = Math.floor((Date.now() / 1000 - ts) / 86400);
  if (days <= 0) return "сегодня";
  if (days === 1) return "вчера";
  if (days < 7) return `${days} дн. назад`;
  if (days < 30) return `${Math.floor(days / 7)} нед. назад`;
  return `${Math.floor(days / 30)} мес. назад`;
}

function stageOptionsHtml(selected) {
  return STAGES.map(
    (s) => `<option value="${s.key}" ${s.key === selected ? "selected" : ""}>${s.label}</option>`
  ).join("");
}

function renderBoard(clients) {
  const board = document.getElementById("board");
  board.innerHTML = "";

  STAGES.forEach((stage) => {
    const inStage = clients.filter((c) => c.stage === stage.key);

    const col = document.createElement("div");
    col.className = "column";
    col.innerHTML = `<div class="column-title"><span>${stage.label}</span><span class="column-count">${inStage.length}</span></div>`;

    inStage.forEach((c) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-name">${clientDisplayName(c)}</div>
        <div class="card-meta">${TYPE_LABELS[c.anxiety_type] || "тип не определён"} · ${relativeActivity(c.last_activity_at)}</div>
        <select class="card-select">${stageOptionsHtml(c.stage)}</select>
      `;
      card.querySelector(".card-name").addEventListener("click", () => openClientPanel(c.user_id));
      card.querySelector(".card-meta").addEventListener("click", () => openClientPanel(c.user_id));
      card.querySelector(".card-select").addEventListener("click", (e) => e.stopPropagation());
      card.querySelector(".card-select").addEventListener("change", async (e) => {
        await api(`/api/crm/client/${c.user_id}/stage`, {
          method: "POST",
          body: JSON.stringify({ stage: e.target.value }),
        });
        loadBoard();
      });
      col.appendChild(card);
    });

    board.appendChild(col);
  });
}

async function loadBoard() {
  const [stagesRes, clientsRes] = await Promise.all([
    api("/api/crm/stages"),
    api(`/api/crm/clients${currentSearch ? `?search=${encodeURIComponent(currentSearch)}` : ""}`),
  ]);
  const stagesData = await stagesRes.json();
  const clientsData = await clientsRes.json();
  STAGES = stagesData.stages;
  renderBoard(clientsData.clients);
}

let searchTimer = null;
document.getElementById("search-input").addEventListener("input", (e) => {
  currentSearch = e.target.value.trim();
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadBoard, 300);
});

// ── Карточка клиента ────────────────────────────────────────────────────

function formatUnixDate(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

function formatBookingDate(dateStr) {
  if (!dateStr || dateStr.length !== 8) return dateStr || "";
  const d = new Date(`${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}T00:00:00`);
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long", weekday: "short" });
}

function renderClientPanel(detail) {
  const el = document.getElementById("panel-content");
  const now = Date.now() / 1000;

  const bookingsHtml = detail.bookings.length
    ? detail.bookings.map((b) => `
        <div class="list-item">
          <div>${formatBookingDate(b.date_str)} в ${b.time_str}</div>
          <div class="hint">${STATUS_LABELS[b.status] || b.status}</div>
        </div>`).join("")
    : `<p class="hint">Записей нет.</p>`;

  const paymentsHtml = detail.payments.length
    ? detail.payments.map((p) => `
        <div class="list-item">
          <div>${p.payment_type === "session" ? "Сессия" : "Разбор"}</div>
          <div class="hint">${formatUnixDate(p.created_at)}</div>
        </div>`).join("")
    : `<p class="hint">Платежей нет.</p>`;

  const diaryLast = detail.diary.slice(-5).reverse();
  const diaryHtml = diaryLast.length
    ? diaryLast.map((d) => `
        <div class="list-item">
          <div>${formatUnixDate(d.created_at)} — тревога ${d.score}/10</div>
          ${d.note ? `<div class="hint">${d.note}</div>` : ""}
        </div>`).join("")
    : `<p class="hint">Дневник пуст.</p>`;

  const notesHtml = detail.notes.length
    ? detail.notes.map((n) => {
        const due = n.reminder_at && !n.reminder_done && n.reminder_at <= now;
        return `
        <div class="list-item note-item ${due ? "reminder-due" : ""}">
          <div>${n.text}</div>
          <div class="hint">${formatUnixDate(n.created_at)}${n.reminder_at ? ` · напоминание ${formatUnixDate(n.reminder_at)}` : ""}</div>
          ${n.reminder_at && !n.reminder_done ? `<button class="note-done-btn" data-note-id="${n.id}">Готово</button>` : ""}
        </div>`;
      }).join("")
    : `<p class="hint">Заметок пока нет.</p>`;

  el.innerHTML = `
    <div class="panel-name">${clientDisplayName(detail)}</div>
    <div class="panel-sub">${detail.username ? `@${detail.username} · ` : ""}${TYPE_LABELS[detail.anxiety_type] || "тип не определён"}${detail.phone ? ` · ${detail.phone}` : ""}</div>

    <div class="panel-stage-row">
      <label class="hint">Этап</label>
      <select id="panel-stage-select">${stageOptionsHtml(detail.stage)}</select>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Записи на сессию</div>
      ${bookingsHtml}
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Платежи</div>
      ${paymentsHtml}
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Дневник (последние записи)</div>
      ${diaryHtml}
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Заметки</div>
      ${notesHtml}
      <form id="note-form" style="margin-top:12px">
        <textarea id="note-text" rows="3" placeholder="Новая заметка…"></textarea>
        <input type="datetime-local" id="note-reminder">
        <button type="submit" class="btn-primary">Добавить</button>
      </form>
    </div>
  `;

  document.getElementById("panel-stage-select").addEventListener("change", async (e) => {
    await api(`/api/crm/client/${detail.user_id}/stage`, {
      method: "POST",
      body: JSON.stringify({ stage: e.target.value }),
    });
    loadBoard();
  });

  el.querySelectorAll(".note-done-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/crm/note/${btn.dataset.noteId}/done`, { method: "POST" });
      openClientPanel(detail.user_id);
    });
  });

  document.getElementById("note-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = document.getElementById("note-text").value.trim();
    if (!text) return;
    const reminderInput = document.getElementById("note-reminder").value;
    const reminder_at = reminderInput ? Math.floor(new Date(reminderInput).getTime() / 1000) : null;

    await api(`/api/crm/client/${detail.user_id}/note`, {
      method: "POST",
      body: JSON.stringify({ text, reminder_at }),
    });
    openClientPanel(detail.user_id);
  });
}

async function openClientPanel(userId) {
  panelUserId = userId;
  document.getElementById("overlay").classList.remove("hidden");
  document.getElementById("client-panel").classList.remove("hidden");
  document.getElementById("panel-content").innerHTML = `<div class="center-note"><div class="spinner"></div></div>`;

  const res = await api(`/api/crm/client/${userId}`);
  const detail = await res.json();
  renderClientPanel(detail);
}

function closeClientPanel() {
  panelUserId = null;
  document.getElementById("overlay").classList.add("hidden");
  document.getElementById("client-panel").classList.add("hidden");
}

document.getElementById("panel-close").addEventListener("click", closeClientPanel);
document.getElementById("overlay").addEventListener("click", closeClientPanel);

// ── Старт ────────────────────────────────────────────────────────────────

async function bootApp() {
  showApp();
  await loadBoard();
}

(async () => {
  try {
    await bootApp();
  } catch (e) {
    // 401 уже показал экран логина внутри api()
  }
})();
