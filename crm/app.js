const STATUS_LABELS = {
  pending: "⏳ ожидает подтверждения",
  confirmed: "✅ подтверждена",
  declined: "❌ отклонена",
};

const TYPE_LABELS = { A: "Сканер", B: "Катастрофист", C: "Замиратель", D: "Контролёр" };

let STAGES = [];
let currentSearch = "";
let panelUserId = null;

// Диалог открытого клиента: копим порциями от новых к старым, oldestId —
// курсор для догрузки ("показать раньше").
let dialogMessages = [];
let dialogHasMore = false;
let dialogOldestId = null;

// Всё, что пришло из базы, вставляется через innerHTML — а текст сообщений
// пишут сами клиенты в Telegram, так что любой <тег> из переписки иначе
// исполнился бы прямо в панели Евы.
function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

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
    (s) => `<option value="${esc(s.key)}" ${s.key === selected ? "selected" : ""}>${esc(s.label)}</option>`
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
        <div class="card-name">${esc(clientDisplayName(c))}</div>
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

// ── Диалог (консоль переписки в карточке) ───────────────────────────────

function formatUnixTime(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function sameDay(a, b) {
  return new Date(a * 1000).toDateString() === new Date(b * 1000).toDateString();
}

// Разделитель дня внутри переписки: «Сегодня»/«Вчера» вместо даты, а год —
// только если переписка не этого года. Полный формат formatUnixDate («29 июля
// 2026 г.») для лога слишком шумный: он повторяется через каждые пару экранов.
function formatDialogDay(ts) {
  const d = new Date(ts * 1000);
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const daysAgo = Math.floor((midnight - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);

  if (daysAgo === 0) return "Сегодня";
  if (daysAgo === 1) return "Вчера";

  return d.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    ...(d.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  });
}

// Ссылки в переписке (клиенты присылают их, и на них надо уметь перейти).
// Линкуем уже экранированный текст, а не исходный: иначе пришлось бы
// собирать <a> из неэкранированных кусков и вся защита esc() рассыпается.
// Схемы только http/https — javascript: через этот шаблон не пройдёт.
function linkifyEscaped(escaped) {
  return escaped.replace(/https?:\/\/[^\s]+/g, (raw) => {
    // Точка, запятая, закрывающая скобка или кавычка в конце — почти всегда
    // пунктуация предложения, а не часть адреса.
    let url = raw;
    let tail = "";
    let m;
    while ((m = url.match(/(&(?:quot|amp|lt|gt|#39);|[.,;:!?)\]])$/))) {
      tail = m[0] + tail;
      url = url.slice(0, -m[0].length);
    }
    if (!url) return raw;
    return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>${tail}`;
  });
}

function dialogMessageHtml(m, prev) {
  // ai_user/ai_bot — переписка с AI-помощником, user/bot — обычные шаги бота
  // и нажатия кнопок. Слева клиент, справа бот, как в мессенджере.
  const fromClient = m.role === "user" || m.role === "ai_user";
  const fromAi = m.role === "ai_user" || m.role === "ai_bot";

  const daySep = !prev || !sameDay(prev.created_at, m.created_at)
    ? `<div class="dialog-day">${esc(formatDialogDay(m.created_at))}</div>`
    : "";

  return `${daySep}
    <div class="dialog-msg ${fromClient ? "from-client" : "from-bot"}">
      <div class="dialog-bubble">${linkifyEscaped(esc(m.text))}</div>
      <div class="dialog-time">${esc(formatUnixTime(m.created_at))}${fromAi ? " · AI" : ""}</div>
    </div>`;
}

function renderDialogLog(userId) {
  const log = document.getElementById("dialog-log");
  if (!log) return;

  if (!dialogMessages.length) {
    log.innerHTML = `<p class="hint">Переписки пока нет.</p>`;
    return;
  }

  let html = dialogHasMore
    ? `<button type="button" class="dialog-more" id="dialog-more">Показать раньше</button>`
    : `<div class="dialog-start">начало переписки</div>`;

  let prev = null;
  dialogMessages.forEach((m) => {
    html += dialogMessageHtml(m, prev);
    prev = m;
  });
  log.innerHTML = html;

  const moreBtn = document.getElementById("dialog-more");
  if (moreBtn) {
    moreBtn.addEventListener("click", () => {
      moreBtn.disabled = true;
      moreBtn.textContent = "Загружаю…";
      loadDialog(userId, { more: true });
    });
  }
}

async function loadDialog(userId, { more = false } = {}) {
  const log = document.getElementById("dialog-log");
  if (!log) return;

  if (!more) {
    log.innerHTML = `<div class="center-note"><div class="spinner"></div></div>`;
  }

  let data;
  try {
    const query = more && dialogOldestId ? `?before_id=${dialogOldestId}` : "";
    const res = await api(`/api/crm/client/${userId}/dialog${query}`);
    data = await res.json();
  } catch (e) {
    if (panelUserId === userId) {
      log.innerHTML = `<p class="hint">Не удалось загрузить переписку.</p>`;
    }
    return;
  }

  // Пока грузилось, панель могли закрыть или открыть другого клиента —
  // тогда дописывать этот ответ в лог уже нельзя.
  if (panelUserId !== userId) return;

  dialogMessages = more ? [...data.messages, ...dialogMessages] : data.messages;
  dialogHasMore = data.has_more;
  if (dialogMessages.length) dialogOldestId = dialogMessages[0].id;

  // Лог перерисовывается целиком, поэтому при догрузке старых сообщений
  // возвращаем прокрутку на прежнее место (иначе взгляд улетает наверх).
  const heightBefore = more ? log.scrollHeight : 0;
  renderDialogLog(userId);
  log.scrollTop = more ? log.scrollHeight - heightBefore : log.scrollHeight;
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
          <div>${formatUnixDate(d.created_at)} — тревога ${esc(d.score)}/10</div>
          ${d.note ? `<div class="hint">${esc(d.note)}</div>` : ""}
        </div>`).join("")
    : `<p class="hint">Дневник пуст.</p>`;

  const notesHtml = detail.notes.length
    ? detail.notes.map((n) => {
        const due = n.reminder_at && !n.reminder_done && n.reminder_at <= now;
        return `
        <div class="list-item note-item ${due ? "reminder-due" : ""}">
          <div>${esc(n.text)}</div>
          <div class="hint">${formatUnixDate(n.created_at)}${n.reminder_at ? ` · напоминание ${formatUnixDate(n.reminder_at)}` : ""}</div>
          ${n.reminder_at && !n.reminder_done ? `<button class="note-done-btn" data-note-id="${n.id}">Готово</button>` : ""}
        </div>`;
      }).join("")
    : `<p class="hint">Заметок пока нет.</p>`;

  el.innerHTML = `
    <div class="panel-name">${esc(clientDisplayName(detail))}</div>
    <div class="panel-sub">${detail.username ? `@${esc(detail.username)} · ` : ""}${TYPE_LABELS[detail.anxiety_type] || "тип не определён"}${detail.phone ? ` · ${esc(detail.phone)}` : ""}</div>

    <div class="panel-stage-row">
      <label class="hint">Этап</label>
      <select id="panel-stage-select">${stageOptionsHtml(detail.stage)}</select>
    </div>

    <div class="panel-section">
      <div class="panel-section-title">Диалог</div>
      <div id="dialog-log" class="dialog-log"><div class="center-note"><div class="spinner"></div></div></div>
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

  // Переписка грузится отдельным запросом — карточка не ждёт её, чтобы
  // открыться, а история может быть в тысячи сообщений.
  loadDialog(detail.user_id);
}

async function openClientPanel(userId) {
  panelUserId = userId;
  dialogMessages = [];
  dialogHasMore = false;
  dialogOldestId = null;
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
