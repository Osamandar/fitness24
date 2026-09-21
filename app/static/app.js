"use strict";
/* Клиентская часть ИС «Фитнес-центр 24». Все данные экранируются перед выводом (защита от XSS). */

const S = { token: sessionStorage.getItem("token"), user: null, qrTimer: null };
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (d) => d ? new Date(d).toLocaleDateString("ru-RU") : "—";
const fmtTime = (d) => new Date(d).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
const fmtDT = (d) => `${fmtDate(d)} ${fmtTime(d)}`;
const rub = (n) => `${Number(n).toLocaleString("ru-RU")} ₽`;
const ROLE = { admin: "Администратор", trainer: "Тренер", client: "Клиент" };

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers.Authorization = `Bearer ${S.token}`;
  const res = await fetch(`/api${path}`, { ...opts, headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined });
  if (res.status === 401 && S.user) { logout(); throw new Error("Сессия истекла, войдите заново"); }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = "Проверьте поля: " + msg.map((e) => e.loc.at(-1)).join(", ");
    throw new Error(msg || `Ошибка ${res.status}`);
  }
  return data;
}

function toast(text, err = false) {
  const t = $("#toast");
  t.textContent = text; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 3500);
}

const formData = (form) => Object.fromEntries(new FormData(form).entries());
const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== ""));

/* ---------- Вход и регистрация ---------- */
function showAuth() {
  $("#shell").hidden = true; $("#auth").hidden = false;
}
document.addEventListener("click", (e) => {
  const sw = e.target.closest("[data-switch]");
  if (!sw) return;
  $("#login-form").hidden = sw.dataset.switch !== "login";
  $("#register-form").hidden = sw.dataset.switch !== "register";
});
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try { start(await api("/auth/login", { method: "POST", body: formData(e.target) })); }
  catch (err) { $("#login-error").textContent = err.message; }
});
$("#register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(e.target); d.pd_consent = e.target.pd_consent.checked;
  $("#register-error").textContent = "";
  try { start(await api("/auth/register", { method: "POST", body: d })); }
  catch (err) { $("#register-error").textContent = err.message; }
});
$("#logout").addEventListener("click", logout);

function start(res) {
  S.token = res.access_token; S.user = res.user;
  sessionStorage.setItem("token", S.token);
  enter();
}
function logout() {
  S.token = null; S.user = null; sessionStorage.removeItem("token");
  clearInterval(S.qrTimer); showAuth();
}

/* ---------- Навигация по ролям ---------- */
const MENUS = {
  admin: [["summary", "Сводка"], ["clients", "Клиенты"], ["memberships", "Абонементы"],
          ["schedule", "Расписание"], ["gate", "Турникет"], ["audit", "Журнал аудита"]],
  trainer: [["schedule", "Мои занятия"]],
  client: [["pass", "Мой абонемент"], ["schedule", "Расписание"]],
};

function enter() {
  $("#auth").hidden = true; $("#shell").hidden = false;
  $("#who-name").textContent = S.user.full_name;
  $("#who-role").textContent = ROLE[S.user.role];
  $("#menu").innerHTML = MENUS[S.user.role]
    .map(([id, name]) => `<li><a href="#${id}">${esc(name)}</a></li>`).join("");
  if (!MENUS[S.user.role].some(([id]) => `#${id}` === location.hash)) location.hash = MENUS[S.user.role][0][0];
  else route();
}
window.addEventListener("hashchange", () => S.user && route());

async function route() {
  clearInterval(S.qrTimer);
  const id = location.hash.slice(1);
  document.querySelectorAll("#menu a").forEach((a) => {
    if (a.getAttribute("href") === `#${id}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const view = $("#view");
  try { await (VIEWS[id] || VIEWS[MENUS[S.user.role][0][0]])(view); }
  catch (err) { view.innerHTML = `<p class="form-error">${esc(err.message)}</p>`; }
  view.focus();
}

function table(cols, rows, emptyText) {
  if (!rows.length) return `<div class="table-wrap"><p class="empty">${esc(emptyText)}</p></div>`;
  return `<div class="table-wrap"><table><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const stateTag = (m) => `<span class="tag ${m.state === "active" ? "ok" : m.state === "frozen" ? "warn" : "no"}">${esc(m.state_name)}</span>`;

/* ---------- Экраны ---------- */
const VIEWS = {
  async summary(v) {
    const [s, ev] = await Promise.all([api("/reports/summary"), api("/access/events?limit=8")]);
    const hour = new Date().getHours();
    v.innerHTML = `<h1>Сводка на ${esc(new Date().toLocaleDateString("ru-RU", { day: "numeric", month: "long" }))}</h1>
      <div class="stats">
        <div class="stat"><b>${s.in_gym_now}</b><span class="muted">сейчас в клубе</span></div>
        <div class="stat"><b>${s.visits_today}</b><span class="muted">посещений за сутки</span></div>
        <div class="stat"><b>${s.active_memberships}</b><span class="muted">действующих абонементов</span></div>
        <div class="stat"><b>${esc(rub(s.revenue_month))}</b><span class="muted">выручка за месяц</span></div>
        <div class="stat"><b>${s.denied_today}</b><span class="muted">отказов на турникете</span></div>
      </div>
      <section class="day" aria-label="Посещения по часам">
        <div class="day-head"><strong>Посещения по часам</strong><span class="muted">клуб открыт 24 часа</span></div>
        <div class="bars" id="bars"></div>
        <div class="hours">${Array.from({ length: 24 }, (_, i) => `<span>${i}</span>`).join("")}</div>
      </section>
      <h2>Последние проходы</h2>
      ${table(["Время", "Клиент", "Направление", "Результат"], ev.map((e) => [
        esc(fmtDT(e.at)), esc(e.client_name || "неизвестный"), e.direction === "in" ? "Вход" : "Выход",
        `<span class="tag ${e.granted ? "ok" : "no"}">${esc(e.reason)}</span>`]), "Сегодня проходов ещё не было")}`;
    const max = Math.max(1, ...s.visits_by_hour);
    const bars = $("#bars", v);
    s.visits_by_hour.forEach((n, i) => {
      const b = document.createElement("div");
      b.className = "bar" + (n ? " has" : "") + (i === hour ? " now" : "");
      b.style.height = `${Math.max(3, (n / max) * 100)}%`;
      b.title = `${i}:00 — ${n} чел.`;
      bars.append(b);
    });
  },

  async clients(v) {
    const plans = await api("/plans");
    v.innerHTML = `<h1>Клиенты</h1>
      <details class="panel"><summary><strong>Новый клиент</strong></summary>
        <form id="new-client" class="grid-form">
          <label>ФИО<input name="full_name" required></label>
          <label>Телефон<input name="phone" placeholder="+79991234567" required></label>
          <label>Email<input name="email" type="email"></label>
          <label>Дата рождения<input name="birth_date" type="date"></label>
          <label>Пароль личного кабинета<input name="password" type="password" autocomplete="new-password">
            <small>Необязательно</small></label>
          <label class="check"><input name="pd_consent" type="checkbox">Клиент подписал согласие на обработку ПДн</label>
          <div class="actions"><button class="btn-primary">Добавить клиента</button></div>
        </form></details>
      <div class="toolbar"><input id="q" type="search" placeholder="Поиск по ФИО, телефону, email" aria-label="Поиск клиентов"></div>
      <div id="list"></div>`;
    const load = async () => {
      const rows = await api(`/clients?q=${encodeURIComponent($("#q", v).value)}`);
      $("#list", v).innerHTML = table(["ФИО", "Телефон", "Абонемент", "Продать абонемент"], rows.map((c) => [
        esc(c.full_name), esc(c.phone), c.membership ? esc(c.membership) : '<span class="muted">нет</span>',
        `<form class="sell toolbar" data-id="${c.id}"><select name="plan_id" aria-label="Тариф">${plans.map((p) =>
          `<option value="${p.id}">${esc(p.name)} — ${esc(rub(p.price))}</option>`).join("")}</select>
          <button class="btn">Продать</button></form>`]), "Клиенты не найдены");
    };
    $("#q", v).addEventListener("input", () => { clearTimeout(load.t); load.t = setTimeout(load, 250); });
    $("#new-client", v).addEventListener("submit", async (e) => {
      e.preventDefault();
      const d = clean(formData(e.target)); d.pd_consent = e.target.pd_consent.checked;
      try { await api("/clients", { method: "POST", body: d }); e.target.reset(); toast("Клиент добавлен"); load(); }
      catch (err) { toast(err.message, true); }
    });
    $("#list", v).addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target.closest(".sell");
      try {
        const m = await api("/memberships", { method: "POST",
          body: { client_id: +f.dataset.id, plan_id: +f.plan_id.value } });
        toast(`Абонемент «${m.plan_name}» оформлен до ${fmtDate(m.end_date)}`); load();
      } catch (err) { toast(err.message, true); }
    });
    load();
  },

  async memberships(v) {
    const [ms, plans] = await Promise.all([api("/memberships"), api("/plans")]);
    v.innerHTML = `<h1>Абонементы</h1>
      ${table(["№", "Клиент", "Тариф", "Период", "Осталось посещений", "Статус"], ms.map((m) => [
        m.id, esc(m.client_name), esc(m.plan_name), esc(`${fmtDate(m.start_date)} – ${fmtDate(m.end_date)}`),
        m.visits_left ?? "без ограничений", stateTag(m)]), "Абонементов пока нет")}
      <h2>Тарифы</h2>
      ${table(["Название", "Срок", "Доступ", "Посещений", "Цена"], plans.map((p) => [
        esc(p.name), `${p.duration_days} дн.`, p.access_mode === "day" ? "07:00–23:00" : "Круглосуточно",
        p.visits_limit ?? "без ограничений", esc(rub(p.price))]), "Тарифов нет")}
      <form id="new-plan" class="panel grid-form">
        <label>Название тарифа<input name="name" required></label>
        <label>Срок, дней<input name="duration_days" type="number" min="1" required></label>
        <label>Цена, ₽<input name="price" type="number" min="0" required></label>
        <label>Доступ<select name="access_mode"><option value="24/7">Круглосуточно</option>
          <option value="day">Дневной, 07:00–23:00</option></select></label>
        <label>Лимит посещений<input name="visits_limit" type="number" min="1"><small>Пусто — без ограничений</small></label>
        <div class="actions"><button class="btn-primary">Добавить тариф</button></div>
      </form>`;
    $("#new-plan", v).addEventListener("submit", async (e) => {
      e.preventDefault();
      const d = clean(formData(e.target));
      ["duration_days", "price", "visits_limit"].forEach((k) => d[k] && (d[k] = +d[k]));
      try { await api("/plans", { method: "POST", body: d }); toast("Тариф добавлен"); route(); }
      catch (err) { toast(err.message, true); }
    });
  },

  async schedule(v) {
    const role = S.user.role;
    const classes = await api("/classes?days=7");
    const trainers = role === "admin" ? await api("/trainers") : [];
    const byDay = {};
    classes.forEach((c) => (byDay[fmtDate(c.starts_at)] ??= []).push(c));
    const now = new Date();
    const action = (c) => {
      if (role === "client") {
        if (new Date(c.starts_at) <= now) return '<span class="muted">прошло</span>';
        if (c.is_booked_by_me) return `<button class="btn btn-danger" data-cancel="${c.id}">Отменить запись</button>`;
        return c.booked >= c.capacity ? '<span class="muted">мест нет</span>'
          : `<button class="btn" data-book="${c.id}">Записаться</button>`;
      }
      return `<button class="btn" data-att="${c.id}">Кто записан</button>`;
    };
    v.innerHTML = `<h1>${role === "trainer" ? "Мои занятия" : "Расписание на неделю"}</h1>
      ${role === "admin" ? `<details class="panel"><summary><strong>Новое занятие</strong></summary>
        <form id="new-class" class="grid-form">
          <label>Название<input name="title" required></label>
          <label>Тренер<select name="trainer_id">${trainers.map((t) =>
            `<option value="${t.id}">${esc(t.full_name)}</option>`).join("")}</select></label>
          <label>Начало<input name="starts_at" type="datetime-local" required></label>
          <label>Длительность, мин<input name="duration_min" type="number" value="60" min="15"></label>
          <label>Мест<input name="capacity" type="number" value="15" min="1"></label>
          <label>Зал<input name="room" value="Зал 1"></label>
          <div class="actions"><button class="btn-primary">Добавить в расписание</button></div>
        </form></details>` : ""}
      ${Object.keys(byDay).length ? Object.entries(byDay).map(([day, list]) => `
        <p class="day-label">${esc(day)}</p><div class="day-list">${list.map((c) => `
          <div class="cls"><time>${esc(fmtTime(c.starts_at))}</time>
            <div><strong>${esc(c.title)}</strong><br><span class="muted">${esc(c.trainer_name)}, ${esc(c.room)},
              ${c.duration_min} мин, записано ${c.booked} из ${c.capacity}</span>
              <div class="muted att" id="att-${c.id}"></div></div>
            ${action(c)}</div>`).join("")}</div>`).join("")
        : '<div class="table-wrap"><p class="empty">На ближайшую неделю занятий нет</p></div>'}
      ${role === "admin" ? `<h2>Тренеры</h2>${table(["ФИО", "Специализация", "Телефон"], trainers.map((t) =>
        [esc(t.full_name), esc(t.specialization), esc(t.phone)]), "Тренеров нет")}
        <form id="new-trainer" class="panel grid-form">
          <label>ФИО тренера<input name="full_name" required></label>
          <label>Специализация<input name="specialization" required></label>
          <label>Телефон<input name="phone"></label>
          <label>Email для входа<input name="email" type="email"></label>
          <label>Пароль<input name="password" type="password" autocomplete="new-password"></label>
          <div class="actions"><button class="btn-primary">Добавить тренера</button></div>
        </form>` : ""}`;

    v.onclick = async (e) => {
      const b = e.target.closest("button[data-book],button[data-cancel],button[data-att]");
      if (!b) return;
      try {
        if (b.dataset.book) { await api(`/classes/${b.dataset.book}/book`, { method: "POST" }); toast("Вы записаны"); route(); }
        if (b.dataset.cancel) { await api(`/classes/${b.dataset.cancel}/book`, { method: "DELETE" }); toast("Запись отменена"); route(); }
        if (b.dataset.att) {
          const names = await api(`/classes/${b.dataset.att}/attendees`);
          $(`#att-${b.dataset.att}`, v).textContent = names.length ? "Записаны: " + names.join(", ") : "Пока никто не записался";
        }
      } catch (err) { toast(err.message, true); }
    };
    const nc = $("#new-class", v);
    if (nc) nc.addEventListener("submit", async (e) => {
      e.preventDefault();
      const d = formData(e.target);
      ["trainer_id", "duration_min", "capacity"].forEach((k) => (d[k] = +d[k]));
      try { await api("/classes", { method: "POST", body: d }); toast("Занятие добавлено"); route(); }
      catch (err) { toast(err.message, true); }
    });
    const nt = $("#new-trainer", v);
    if (nt) nt.addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await api("/trainers", { method: "POST", body: clean(formData(e.target)) }); toast("Тренер добавлен"); route(); }
      catch (err) { toast(err.message, true); }
    });
  },

  async gate(v) {
    v.innerHTML = `<h1>Турникет</h1>
      <p class="muted">Эмулятор считывателя: вставьте код из личного кабинета клиента. Код действует 60 секунд.</p>
      <div class="gate">
        <form id="scan" class="panel">
          <label>Код с QR<input name="token" required autocomplete="off"></label>
          <label>Направление<select name="direction"><option value="in">Вход</option><option value="out">Выход</option></select></label>
          <button class="btn-primary">Проверить</button>
        </form>
        <div id="light" class="gate-light" aria-live="polite"><div><strong>Ожидание</strong>Поднесите QR-код</div></div>
      </div>
      <h2>Журнал проходов</h2><div id="events"></div>`;
    const loadEvents = async () => {
      const ev = await api("/access/events?limit=20");
      $("#events", v).innerHTML = table(["Время", "Клиент", "Направление", "Результат"], ev.map((e) => [
        esc(fmtDT(e.at)), esc(e.client_name || "неизвестный"), e.direction === "in" ? "Вход" : "Выход",
        `<span class="tag ${e.granted ? "ok" : "no"}">${esc(e.reason)}</span>`]), "Проходов ещё не было");
    };
    $("#scan", v).addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const r = await api("/access/check", { method: "POST", body: formData(e.target) });
        const light = $("#light", v);
        light.className = "gate-light " + (r.granted ? "ok" : "no");
        light.innerHTML = `<div><strong>${r.granted ? "Проходите" : "Доступ закрыт"}</strong>
          ${esc(r.client_name || "")}<br>${esc(r.reason)}</div>`;
        loadEvents();
      } catch (err) { toast(err.message, true); }
    });
    loadEvents();
  },

  async audit(v) {
    const rows = await api("/audit?limit=100");
    v.innerHTML = `<h1>Журнал аудита</h1>
      <p class="muted">Все значимые действия пользователей: входы, неудачные попытки, продажи, изменения.</p>
      ${table(["Время", "Пользователь", "Действие", "Подробности"], rows.map((a) => [
        esc(fmtDT(a.at)), esc(a.user || "—"), `<span class="tag ${a.action === "login_failed" ? "no" : ""}">${esc(a.action)}</span>`,
        esc(a.details)]), "Записей нет")}`;
  },

  async pass(v) {
    const ms = await api("/me/memberships");
    const active = ms.find((m) => m.state === "active");
    v.innerHTML = `<h1>Мой абонемент</h1>
      ${active ? `<div class="pass">
        <div><div class="qr" id="qr" aria-label="QR-код для прохода"></div><div class="ttl"><i id="ttl"></i></div></div>
        <div><h2>${esc(active.plan_name)}</h2>
          <p>Действует до <strong>${esc(fmtDate(active.end_date))}</strong><br>
          Доступ: ${active.access_mode === "day" ? "с 07:00 до 23:00" : "круглосуточно"}<br>
          Посещений осталось: ${active.visits_left ?? "без ограничений"}</p>
          <p class="muted">Покажите код на турникете. Он обновляется автоматически, скриншот не сработает.</p>
          <p class="token" id="token"></p>
          <form id="freeze" class="toolbar"><input name="days" type="number" min="1" max="30" value="7" aria-label="Дней заморозки">
            <button class="btn">Заморозить абонемент</button></form></div>
      </div>` : `<div class="panel"><strong>Действующего абонемента нет.</strong>
        <p class="muted">Оформите абонемент на ресепшене, после этого здесь появится QR-код для прохода.</p></div>`}
      <h2>История</h2>
      ${table(["Тариф", "Период", "Статус"], ms.map((m) => [esc(m.plan_name),
        esc(`${fmtDate(m.start_date)} – ${fmtDate(m.end_date)}`), stateTag(m)]), "Абонементов пока нет")}`;
    if (!active) return;
    const refresh = async () => {
      const q = await api("/me/qr");
      $("#qr", v).innerHTML = q.svg;  // SVG сгенерирован сервером из подписанного токена
      $("#token", v).textContent = q.token;
      let left = q.ttl - 5;
      const bar = $("#ttl", v);
      bar.style.width = "100%";
      clearInterval(S.qrTimer);
      S.qrTimer = setInterval(() => {
        left -= 1;
        bar.style.width = `${Math.max(0, (left / (q.ttl - 5)) * 100)}%`;
        if (left <= 0) refresh();
      }, 1000);
    };
    refresh();
    $("#freeze", v).addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!confirm("Заморозить абонемент? Заморозка доступна один раз.")) return;
      try {
        const m = await api(`/memberships/${active.id}/freeze`, { method: "POST", body: { days: +e.target.days.value } });
        toast(`Абонемент заморожен, теперь действует до ${fmtDate(m.end_date)}`); route();
      } catch (err) { toast(err.message, true); }
    });
  },
};

/* ---------- Старт ---------- */
(async () => {
  if (!S.token) return showAuth();
  try { S.user = await api("/auth/me"); enter(); } catch { logout(); }
})();
