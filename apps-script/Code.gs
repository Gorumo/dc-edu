// Запись на консультации: Google Таблица + Apps Script Web App.
// Фронтенд — zapis.html (GitHub Pages), он ходит сюда через fetch.
//
// Развёртывание (один раз):
//   1. Создать Google Таблицу → Расширения → Apps Script → вставить этот файл целиком.
//   2. Выбрать функцию setup → Выполнить (создаст листы «Слоты» и «Записи», выдать доступ).
//   3. Начать развёртывание → Новое развёртывание → тип «Веб-приложение»:
//        Запуск от имени: «Я»;  У кого есть доступ: «Все».
//      Скопировать URL вида https://script.google.com/macros/s/.../exec
//      и вставить его в SCRIPT_URL в zapis.html.
//   4. После правок этого кода: Начать развёртывание → Управление → ✏️ → Версия «Новая».
//      URL при этом не меняется.
//
// Лист «Слоты» заполняется вручную, по строке на консультацию:
//   id (проставится сам) | Курс | Преподаватель | Дата | Время (текстом «18:50–20:20») |
//   Ссылка | Мест | Активен (галочка)
// Студентам видны активные слоты, которые ещё не начались. Ссылка отдаётся только
// после успешной записи.

const SHEET_SLOTS = 'Слоты';
const SHEET_BOOK = 'Записи';
const SLOT_HEAD = ['id', 'Курс', 'Преподаватель', 'Дата', 'Время', 'Ссылка', 'Мест', 'Активен'];
const BOOK_HEAD = ['Дата записи', 'id слота', 'Курс', 'ЛР №', 'ИСУ', 'ФИО', 'Почта',
                   'Преподаватель', 'Дата консультации', 'Время', 'Ссылка', 'Оценка'];
const LABS = 6;                 // номера лабораторных: 1..LABS
const ISU_RE = /^\d{6}$/;       // номер ИСУ — 6 цифр
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CLOSE_BEFORE_MIN = 0;     // за сколько минут до начала закрывать запись
const DOW = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

// ---------- настройка таблицы ----------

function setup() {
  const ss = SpreadsheetApp.getActive();
  // таблица, созданная из slots.csv, — единственный лист с id в A1: переименовываем его
  const first = ss.getSheets()[0];
  if (!ss.getSheetByName(SHEET_SLOTS) && first.getRange('A1').getValue() === 'id') first.setName(SHEET_SLOTS);
  const slots = ss.getSheetByName(SHEET_SLOTS) || ss.insertSheet(SHEET_SLOTS);
  if (slots.getLastRow() === 0) slots.appendRow(SLOT_HEAD);
  // форматы применяются и после импорта slots.csv — галочки сохраняют значения TRUE/FALSE
  slots.setFrozenRows(1);
  slots.getRange('A1:H1').setFontWeight('bold');
  slots.getRange('D2:D').setNumberFormat('dd.mm.yyyy');
  slots.getRange('E2:E').setNumberFormat('@');              // время — текстом
  const act = slots.getRange(2, 8, Math.max(slots.getLastRow(), 500) - 1, 1);
  act.setValues(act.getValues().map(r => [isTrue(r[0])]));
  act.insertCheckboxes();
  const book = ss.getSheetByName(SHEET_BOOK) || ss.insertSheet(SHEET_BOOK);
  if (book.getLastRow() === 0) {
    book.appendRow(BOOK_HEAD);
    book.setFrozenRows(1);
    book.getRange(1, 1, 1, BOOK_HEAD.length).setFontWeight('bold');
    book.getRange('A2:A').setNumberFormat('dd.mm.yyyy HH:mm');
    book.getRange('I2:I').setNumberFormat('dd.mm.yyyy');
    book.getRange('L1').setBackground('#fff2cc');           // колонка для преподавателя
  }
  fillIds();
}

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Консультации')
    .addItem('Проставить id слотам', 'fillIds')
    .addToUi();
}

// id проставляется автоматически при вводе строки в «Слоты»
function onEdit(e) {
  if (e && e.range.getSheet().getName() === SHEET_SLOTS) fillIds();
}

function fillIds() {
  const sh = SpreadsheetApp.getActive().getSheetByName(SHEET_SLOTS);
  if (!sh || sh.getLastRow() < 2) return;
  const rng = sh.getRange(2, 1, sh.getLastRow() - 1, 2);
  const vals = rng.getValues();
  let changed = false;
  vals.forEach(r => {
    if (!r[0] && r[1]) { r[0] = 's' + Utilities.getUuid().slice(0, 7); changed = true; }
  });
  if (changed) rng.setValues(vals);
}

// ---------- API ----------

function doGet() {
  try {
    const ss = SpreadsheetApp.getActive();
    const taken = countBookings(ss);
    const now = Date.now();
    const slots = readSlots(ss)
      .filter(s => s.active && isOpen(s, now))
      .sort((a, b) => a.start - b.start)
      .map(s => ({
        id: s.id, course: s.course, teacher: s.teacher,
        date: fmtDate(ss, s.date), dow: DOW[s.start.getDay()], time: s.time,
        cap: s.cap, left: Math.max(0, s.cap - (taken[s.id] || 0))
      }));
    const courses = [...new Set(slots.map(s => s.course))];
    return json({ ok: true, courses, labs: LABS, slots });
  } catch (err) {
    return json({ ok: false, error: 'Ошибка сервера: ' + err.message });
  }
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (_) { return json({ ok: false, error: 'Некорректный запрос' }); }

  const isu = String(d.isu || '').trim();
  const name = clean(d.name, 120);
  const email = String(d.email || '').trim().toLowerCase();
  const lab = Number(d.lab);
  if (!ISU_RE.test(isu)) return json({ ok: false, error: 'Номер ИСУ — 6 цифр' });
  if (name.length < 5) return json({ ok: false, error: 'Укажите ФИО полностью' });
  if (!EMAIL_RE.test(email) || email.length > 120) return json({ ok: false, error: 'Некорректная почта' });
  if (!(lab >= 1 && lab <= LABS && Math.floor(lab) === lab)) return json({ ok: false, error: 'Выберите номер лабораторной' });

  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000);                       // записи обрабатываются строго по очереди
  } catch (_) {
    return json({ ok: false, error: 'Сервер занят, попробуйте ещё раз через несколько секунд' });
  }
  try {
    const ss = SpreadsheetApp.getActive();
    const slot = readSlots(ss).find(s => s.id === String(d.slotId || ''));
    if (!slot || !slot.active || !isOpen(slot, Date.now()))
      return json({ ok: false, error: 'Этот слот больше недоступен', refresh: true });

    const book = ss.getSheetByName(SHEET_BOOK);
    const rows = book.getLastRow() > 1 ? book.getRange(2, 2, book.getLastRow() - 1, 4).getValues() : [];
    const inSlot = rows.filter(r => r[0] === slot.id);
    if (inSlot.some(r => String(r[3]) === isu))
      return json({ ok: false, error: 'Вы уже записаны на этот слот' });
    if (inSlot.length >= slot.cap)
      return json({ ok: false, error: 'Свободных мест не осталось — выберите другой слот', refresh: true });

    book.appendRow([new Date(), slot.id, slot.course, lab, Number(isu), name, email,
                    slot.teacher, slot.date, slot.time, slot.link, '']);
    SpreadsheetApp.flush();

    return json({
      ok: true,
      booking: {
        course: slot.course, lab, teacher: slot.teacher,
        date: fmtDate(ss, slot.date), dow: DOW[slot.start.getDay()], time: slot.time,
        link: slot.link
      }
    });
  } finally {
    lock.releaseLock();
  }
}

// ---------- helpers ----------

function readSlots(ss) {
  const sh = ss.getSheetByName(SHEET_SLOTS);
  if (!sh || sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, SLOT_HEAD.length).getValues()
    .map(r => {
      const date = toDate(r[3]);
      const time = String(r[4] || '').trim();
      return {
        id: String(r[0] || '').trim(), course: String(r[1] || '').trim(),
        teacher: String(r[2] || '').trim(), date, time,
        link: String(r[5] || '').trim(), cap: Number(r[6]) || 0,
        active: isTrue(r[7]), start: startOf(date, time)
      };
    })
    .filter(s => s.id && s.course && s.start && s.cap > 0);
}

// число записей по id слота
function countBookings(ss) {
  const sh = ss.getSheetByName(SHEET_BOOK);
  const out = {};
  if (!sh || sh.getLastRow() < 2) return out;
  sh.getRange(2, 2, sh.getLastRow() - 1, 1).getValues()
    .forEach(r => { out[r[0]] = (out[r[0]] || 0) + 1; });
  return out;
}

function isTrue(v) {
  return v === true || String(v).trim().toUpperCase() === 'TRUE';
}

function isOpen(s, now) {
  return s.start.getTime() - CLOSE_BEFORE_MIN * 60000 > now;
}

// дата из ячейки: Date или строка «дд.мм.гггг» / «гггг-мм-дд»
function toDate(v) {
  if (v instanceof Date && !isNaN(v)) return v;
  const s = String(v || '').trim();
  let m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

// начало слота: дата + время начала из «18:50–20:20»
function startOf(date, time) {
  if (!date) return null;
  const m = String(time).match(/(\d{1,2}):(\d{2})/);
  const d = new Date(date.getTime());
  if (m) d.setHours(+m[1], +m[2], 0, 0);
  return d;
}

function fmtDate(ss, d) {
  return Utilities.formatDate(d, ss.getSpreadsheetTimeZone(), 'dd.MM.yyyy');
}

// обрезка и защита от формул в ячейках
function clean(v, max) {
  const s = String(v || '').replace(/\s+/g, ' ').trim().slice(0, max);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
