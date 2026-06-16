#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор HTML-расписания (ВШ ЦК ОУМ, маги 2026-2027).

Как пользоваться:
  1. Правишь данные в блоке DATA / PEOPLE / TEACHERS ниже.
  2. Запускаешь:  python generate_schedule.py
  3. Рядом появляется файл raspisanie.html — открываешь в браузере.

  Чтобы сразу выложить расписание на GitHub, добавь флаг:
     python generate_schedule.py --publish

Зависимостей нет — нужен только Python 3.
"""

import json
import subprocess
import sys
from pathlib import Path

OUTPUT = "raspisanie.html"

# ---------------------------------------------------------------------------
# 1. ПРЕПОДАВАТЕЛИ:  ключ -> полное ФИО + telegram (без @)
# ---------------------------------------------------------------------------
PEOPLE = {
    "Двойникова": {"full": "Двойникова Анастасия Александровна", "tg": "nastya_dvoynikova"},
    "Азимов":     {"full": "Азимов Рустам Шухратуллович",        "tg": "rustamazimov95"},
    "Колцун":     {"full": "Колцун Никита Валерьевич",           "tg": "KoltsNik"},
    "Акопян":     {"full": "Акопян Анжела Артаковна",            "tg": "nglicae"},
    "Носань":     {"full": "Носань Марк",                        "tg": "doyouseemegod"},
}

# ---------------------------------------------------------------------------
# 2. ПРИВЯЗКА ПАР К ПРЕПОДАВАТЕЛЯМ: точное название пары -> ключ из PEOPLE
#    (название должно совпадать с тем, что стоит в DATA -> grid -> p1/p2)
# ---------------------------------------------------------------------------
TEACHERS = {
    # Двойникова
    "КультИИ: КЗ (Мод 1) 1.1": "Двойникова",
    "КультИИ: МиК (Мод 1) 1.1": "Двойникова",
    "КультИИ: КЗ (Мод 6) 1.1": "Двойникова",
    "КультИИ: МиК (Мод 6) 1.1": "Двойникова",
    # Азимов
    "КультИИ: АД (Мод 3) 1.1": "Азимов",
    "КультИИ: АД (Мод 3) 1.2": "Азимов",
    "КультИИ: АД (Мод 3) 1.3": "Азимов",
    "AI Culture (Mod 3) 1.1": "Азимов",
    "КультИИ: АД (Мод 4) 1.1": "Азимов",
    "КультИИ: АД (Мод 4) 1.2": "Азимов",
    "КультИИ: АД (Мод 5) 1.1": "Азимов",
    "КультИИ: АД (Мод 5) 1.2": "Азимов",
    "КультИИ: АД (Мод 5) 1.3": "Азимов",
    "КультИИ: АД (Мод 5) ON 1.4": "Азимов",
    "AI Culture (Mod 2) ON 1.2": "Азимов",
    "AI Culture (Mod 2) 1.1": "Азимов",
    # Колцун (как в исходном файле)
    "AI Culture (Mod 1) 1.1": "Колцун",
    "КультИИ: АД (Мод 1) 1.1": "Колцун",
    "КультИИ: АД (Мод 1) 1.2": "Колцун",
    "КультИИ: АД (Мод 1) 1.3": "Колцун",
    "КультИИ: АД (Мод 6) 1.1": "Колцун",
    "КультИИ: АД (Мод 6) 1.2": "Колцун",
    "КультИИ: АД (Мод 6) 1.3": "Колцун",
    "КультИИ: АД (Мод 6) 1.4": "Колцун",
    # Акопян (как в исходном файле)
    "КультИИ: КЗ (Мод 2) ON 1.1": "Акопян",
    "КультИИ: АД (Мод 2) ON 1.1": "Акопян",
    "КультИИ: АД (Мод 2) ON 1.2": "Акопян",
    "КультИИ: АД (Мод 2) ON 1.3": "Акопян",
    "КультИИ: КЗ (Мод 4) ON 1.1": "Акопян",
    "КультИИ: КЗ (Мод 4) ON 1.2": "Акопян",
    "КультИИ: АД (Мод 4) ON 1.3": "Акопян",
    "КультИИ: МиК (Мод 4) ON 1.2": "Акопян",
}

# Правило-шаблон: всё, что подходит под подстроку (ключ), уходит к этому преподавателю,
# если пара явно не задана в TEACHERS выше. Удобно для «все НиТ -> Носань».
TEACHER_RULES = [
    ("ИИ-м: НиТ", "Носань"),
]

# ---------------------------------------------------------------------------
# 3. ДАННЫЕ РАСПИСАНИЯ: модули и их сетки
#    time — строка вида "5 · 15:30–17:00"; p1/p2 — названия пар (или "" если пусто)
# ---------------------------------------------------------------------------
DATA = [
    {"name": "Модуль 1", "day": "СРЕДА", "date": "09.09.2026", "venue": "КРОН", "fmt": "ОЧНЫЙ",
     "aud1": "1428 (70)", "aud2": "2403 (92)",
     "subs": ["ИЛТ", "МНЦ БТТ", "ФПИиКТ", "ЦМиБТ"],
     "grid": [
         {"time": "5 · 15:30–17:00", "p1": "КультИИ: КЗ (Мод 1) 1.1", "p2": "AI Culture (Mod 1) 1.1"},
         {"time": "6 · 17:10–18:40", "p1": "КультИИ: МиК (Мод 1) 1.1", "p2": "КультИИ: АД (Мод 1) 1.1"},
         {"time": "7 · 18:50–20:20", "p1": "ИИ-м: НиТ (Мод 1) 1.1", "p2": "КультИИ: АД (Мод 1) 1.2"},
         {"time": "8 · 20:30–22:00", "p1": "ИИ-м: НиТ (Мод 1) 1.2", "p2": "КультИИ: АД (Мод 1) 1.3"}]},
    {"name": "Модуль 2", "day": "ЧЕТВЕРГ", "date": "10.09.2026", "venue": "ЧАЙКА", "fmt": "ОЧНО-ДИСТ",
     "aud1": "206 (110)", "aud2": "ДИСТ",
     "subs": ["ИМРиП", "НОЦ Инфохимии", "ЦРИИС"],
     "grid": [
         {"time": "5 · 15:30–17:00", "p1": "AI Culture (Mod 2) ON 1.2", "p2": "КультИИ: КЗ (Мод 2) ON 1.1"},
         {"time": "6 · 17:10–18:40", "p1": "AI Culture (Mod 2) 1.1", "p2": "КультИИ: АД (Мод 2) ON 1.1"},
         {"time": "7 · 18:50–20:20", "p1": "КультИИ: МиК (Мод 2) 1.1", "p2": "КультИИ: АД (Мод 2) ON 1.2"},
         {"time": "8 · 20:30–22:00", "p1": "ИИ-м: НиТ (Мод 2) 1.1", "p2": "КультИИ: АД (Мод 2) ON 1.3"}]},
    {"name": "Модуль 3", "day": "СУББОТА", "date": "12.09.2026", "venue": "ГРИВА", "fmt": "ОЧНО-ДИСТ",
     "aud1": "428 (84)", "aud2": "118 (50) ФСУиР / ДИСТ",
     "subs": ["ИМ", "ИПСПД", "ФСУиР", "ЦХИ", "ШРВ"],
     "grid": [
         {"time": "2 · 09:50–11:20", "p1": "КультИИ: АД (Мод 3) 1.1", "p2": "КультИИ: КЗ (Мод 3) 1.1"},
         {"time": "3 · 11:30–13:00", "p1": "КультИИ: АД (Мод 3) 1.2", "p2": "КультИИ: МиК (Мод 3) 1.1"},
         {"time": "4 · 13:10–15:00", "p1": "КультИИ: АД (Мод 3) 1.3", "p2": "ИИ-м: НиТ (Мод 3) 1.1"},
         {"time": "5 · 15:30–17:00", "p1": "AI Culture (Mod 3) 1.1", "p2": "КультИИ: АД (Мод 3) ON 1.4"}]},
    {"name": "Модуль 4", "day": "ЧЕТВЕРГ", "date": "05.11.2026", "venue": "БИРЖА", "fmt": "ОЧНО-ДИСТ",
     "aud1": "550 (110)", "aud2": "ДИСТ",
     "subs": ["ФТМИ"],
     "grid": [
         {"time": "2 · 09:50–11:20", "p1": "ИИ-м: НиТ (Мод 4) 1.1", "p2": ""},
         {"time": "3 · 11:30–13:00", "p1": "КультИИ: АД (Мод 4) 1.1", "p2": ""},
         {"time": "4 · 13:10–15:00", "p1": "КультИИ: АД (Мод 4) 1.2", "p2": ""},
         {"time": "5 · 15:30–17:00", "p1": "КультИИ: МиК (Мод 4) 1.1", "p2": "КультИИ: КЗ (Мод 4) ON 1.1"},
         {"time": "6 · 17:10–18:40", "p1": "AI Culture (Mod 4) 1.1", "p2": "КультИИ: КЗ (Мод 4) ON 1.2"},
         {"time": "7 · 18:50–20:20", "p1": "", "p2": "КультИИ: АД (Мод 4) ON 1.3"},
         {"time": "8 · 20:30–22:00", "p1": "", "p2": "КультИИ: МиК (Мод 4) ON 1.2"}]},
    {"name": "Модуль 5", "day": "СУББОТА", "date": "07.11.2026", "venue": "ЛОМО", "fmt": "ОЧНО-ДИСТ",
     "aud1": "1222 (88) / ДИСТ", "aud2": "1223 (78)",
     "subs": ["ИВИТШ", "НОЦ ФиОИ", "ОЦ ЭИС", "ФБИТ", "ФизФ"],
     "grid": [
         {"time": "2 · 09:50–11:20", "p1": "КультИИ: АД (Мод 5) 1.1", "p2": "AI Culture (Mod 5) 1.1"},
         {"time": "3 · 11:30–13:00", "p1": "КультИИ: АД (Мод 5) 1.2", "p2": "КультИИ: КЗ (Мод 5) 1.1"},
         {"time": "4 · 13:10–15:00", "p1": "КультИИ: АД (Мод 5) 1.3", "p2": "КультИИ: МиК (Мод 5) 1.1"},
         {"time": "5 · 15:30–17:00", "p1": "КультИИ: АД (Мод 5) ON 1.4", "p2": "ИИ-м: НиТ (Мод 5) 1.1"}]},
    {"name": "Модуль 6", "day": "СРЕДА", "date": "11.11.2026", "venue": "ЛОМО", "fmt": "ОЧНО-ДИСТ",
     "aud1": "1222 (88)", "aud2": "1223 (78) / ДИСТ",
     "subs": ["ВШ ЦК → ИПКН", "ИДУ", "ИПКН", "ПИШ ИТМО", "ФПИн", "ФЭТ"],
     "grid": [
         {"time": "5 · 15:30–17:00", "p1": "КультИИ: АД (Мод 6) 1.1", "p2": "AI Culture (Mod 6) ON 1.1"},
         {"time": "6 · 17:10–18:40", "p1": "КультИИ: АД (Мод 6) 1.2", "p2": "КультИИ: КЗ (Мод 6) 1.1"},
         {"time": "7 · 18:50–20:20", "p1": "КультИИ: АД (Мод 6) 1.3", "p2": "КультИИ: МиК (Мод 6) 1.1"},
         {"time": "8 · 20:30–22:00", "p1": "КультИИ: АД (Мод 6) 1.4", "p2": "ИИ-м: НиТ (Мод 6) 1.1"}]},
]

# ---------------------------------------------------------------------------
# HTML-шаблон. {DATA}, {PEOPLE}, {TEACHERS}, {RULES} подставляются как JSON.
# ---------------------------------------------------------------------------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Расписание · ВШ ЦК ОУМ · маги 2026–2027</title>
<style>
  :root{
    --bg:#0f1115; --card:#181b22; --card2:#1f232c; --line:#2a2f3a;
    --txt:#e8eaf0; --muted:#9aa3b2; --accent:#6aa0ff;
    --kz:#e0723b; --ad:#3b9ae0; --mik:#9b6ae0; --nit:#3bcf8e; --eng:#e0c23b;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    font-size:14px;line-height:1.4}
  header{padding:20px 22px 14px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:10}
  h1{margin:0;font-size:19px;font-weight:650}
  .sub{color:var(--muted);font-size:12.5px;margin-top:3px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:center}
  .ctl{display:flex;flex-direction:column;gap:3px}
  .ctl label{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
  select{background:var(--card2);color:var(--txt);border:1px solid var(--line);
    border-radius:8px;padding:6px 9px;font-size:13px;min-width:140px}
  .legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:14px;font-size:12px;color:var(--muted)}
  .lg{display:inline-flex;align-items:center;gap:6px}
  .dot{width:11px;height:11px;border-radius:3px;display:inline-block}
  main{padding:18px 22px 60px;display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}
  .mod{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
  .mhead{padding:13px 15px;background:linear-gradient(135deg,#222733,#1a1e26);border-bottom:1px solid var(--line)}
  .mtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
  .mname{font-weight:650;font-size:15px}
  .mday{font-size:12px;color:var(--accent);font-weight:600;letter-spacing:.04em}
  .mmeta{margin-top:7px;display:flex;flex-wrap:wrap;gap:5px}
  .chip{font-size:11px;background:var(--card2);border:1px solid var(--line);
    padding:2px 8px;border-radius:20px;color:var(--muted)}
  .chip.venue{color:#ffd9a8;border-color:#5a4530}
  .chip.fmt{color:#a8d5ff;border-color:#2c4866}
  .subs{margin-top:8px;font-size:11.5px;color:var(--muted)}
  .subs b{color:var(--txt);font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th,td{padding:8px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
  th{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600;background:#15181f}
  td.time{white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums;font-size:11.5px}
  td.time b{display:block;color:var(--txt);font-size:13px}
  .cell{display:flex;align-items:flex-start;gap:7px}
  .disc{display:block}
  .ptea{display:block;font-size:10.5px;color:var(--muted);margin-top:2px}
  .ptea.has{color:var(--accent);cursor:pointer;border-bottom:1px dashed rgba(106,160,255,.5);
    display:inline-block;line-height:1.5;outline:none}
  .ptea.has:hover,.ptea.has:focus{color:#9dc0ff}
  #pop{position:fixed;z-index:50;background:var(--card2);border:1px solid var(--accent);
    border-radius:10px;padding:11px 13px;max-width:260px;box-shadow:0 8px 28px rgba(0,0,0,.55);
    font-size:13px;display:none;animation:pf .12s ease}
  @keyframes pf{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
  #pop .pf{font-weight:650;margin-bottom:5px;color:var(--txt)}
  #pop a{color:var(--accent);text-decoration:none;font-size:12.5px}
  #pop a:hover{text-decoration:underline}
  .bar{width:4px;align-self:stretch;border-radius:3px;flex:none;margin-top:1px}
  .empty{color:#4a505c}
  .count{font-size:12px;color:var(--muted);margin-left:auto}
  @media(max-width:560px){main{grid-template-columns:1fr;padding:14px}header{padding:16px}}
</style>
</head>
<body>
<header>
  <h1>Расписание занятий · ВШ ЦК ОУМ</h1>
  <div class="sub">Магистратура 2026–2027 · 6 модулей · дисциплины «Культура ИИ» и «ИИ-мышление»</div>
  <div class="controls">
    <div class="ctl"><label>День недели</label><select id="fDay"></select></div>
    <div class="ctl"><label>Площадка</label><select id="fVenue"></select></div>
    <div class="ctl"><label>Преподаватель</label><select id="fTeach"></select></div>
    <div class="ctl"><label>Дисциплина</label><select id="fDisc"></select></div>
    <span class="count" id="count"></span>
  </div>
  <div class="legend">
    <span class="lg"><span class="dot" style="background:var(--kz)"></span>КультИИ КЗ — Квалифицированный заказчик</span>
    <span class="lg"><span class="dot" style="background:var(--ad)"></span>КультИИ АД — Аналитика данных</span>
    <span class="lg"><span class="dot" style="background:var(--mik)"></span>КультИИ МиК — Медиа и креативность</span>
    <span class="lg"><span class="dot" style="background:var(--nit)"></span>ИИ Прод — Наука и технологии</span>
    <span class="lg"><span class="dot" style="background:var(--eng)"></span>AI Culture (англ.)</span>
  </div>
</header>
<main id="grid"></main>
<div id="pop"></div>

<script>
const DATA = __DATA__;
const PEOPLE = __PEOPLE__;
const TEACHERS = __TEACHERS__;
const TEACHER_RULES = __RULES__;

function teachKey(s){
  if(s && TEACHERS[s]) return TEACHERS[s];
  if(s){ for(const [sub,k] of TEACHER_RULES){ if(s.includes(sub)) return k; } }
  return null;
}
function shortName(full){
  const p=full.split(" ");
  return p[0]+" "+p.slice(1).map(w=>w[0]+".").join("");
}
function teach(s){const k=teachKey(s);return k?shortName(PEOPLE[k].full):"не указан";}
function audName(a){
  const m=a.match(/\((\d+)\)/);
  const cap=m?m[1]:"";
  const num=a.split(/[\s(]/)[0];
  return cap?`${num} · ${cap} мест`:a;
}
function discColor(s){
  if(!s) return "transparent";
  if(/КЗ/.test(s)) return "var(--kz)";
  if(/АД/.test(s)) return "var(--ad)";
  if(/МиК/.test(s)) return "var(--mik)";
  if(/НиТ/.test(s)) return "var(--nit)";
  if(/AI Culture/.test(s)) return "var(--eng)";
  return "var(--muted)";
}
function discKey(s){
  if(/КЗ/.test(s)) return "КЗ";
  if(/АД/.test(s)) return "АД";
  if(/МиК/.test(s)) return "МиК";
  if(/НиТ/.test(s)) return "НиТ";
  if(/AI Culture/.test(s)) return "AI";
  return "";
}
function prettyName(s){
  if(!s) return s;
  // ИИ-м: НиТ -> ИИ Прод; убираем двоеточие после КультИИ
  let out = s.replace("ИИ-м: НиТ","ИИ Прод").replace("КультИИ:","КультИИ");
  const mod = out.match(/\((?:Мод|Mod) (\d+)\)/);   // номер модуля
  const tail = out.match(/(\d+)\.(\d+)\s*$/);        // хвост вида 1.2
  if(mod && tail){
    const on = /\bON\b/.test(out) ? " Онлайн" : "";  // сохраняем пометку онлайна
    const head = out.slice(0, out.search(/\((?:Мод|Mod)/)).trim();
    out = `${head} ${mod[1]}.${tail[2]}${on}`;
  }
  return out;
}
function cell(s){
  if(!s) return '<span class="empty">—</span>';
  const k=teachKey(s);
  const tea = k
    ? `<span class="ptea has" tabindex="0" data-tk="${k}">👤 ${teach(s)}</span>`
    : `<span class="ptea">👤 не указан</span>`;
  return `<span class="cell"><span class="bar" style="background:${discColor(s)}"></span>`+
    `<span><span class="disc">${prettyName(s)}</span>${tea}</span></span>`;
}
function uniq(arr){return [...new Set(arr.filter(Boolean))];}
function fill(sel,vals,allLabel){
  sel.innerHTML = `<option value="">${allLabel}</option>` +
    vals.map(v=>`<option value="${v}">${v}</option>`).join("");
}

fill(fDay,uniq(DATA.map(m=>m.day)),"Все дни");
fill(fVenue,uniq(DATA.map(m=>m.venue)),"Все площадки");
fill(fTeach,Object.keys(PEOPLE).map(k=>PEOPLE[k].full),"Все преподаватели");
const DISCS=[["КЗ","КультИИ КЗ"],["АД","КультИИ АД"],["МиК","КультИИ МиК"],["НиТ","ИИ Прод"],["AI","AI Culture"]];
fDisc.innerHTML='<option value="">Все дисциплины</option>'+
  DISCS.map(([v,l])=>`<option value="${v}">${l}</option>`).join("");

function teaFull(s){const k=teachKey(s);return k?PEOPLE[k].full:null;}
function render(){
  const d=fDay.value,v=fVenue.value,t=fTeach.value,dc=fDisc.value;
  const grid=document.getElementById("grid");
  grid.innerHTML="";
  let shown=0;
  DATA.forEach(m=>{
    if(d && m.day!==d) return;
    if(v && m.venue!==v) return;
    if(t && !m.grid.some(g=>teaFull(g.p1)===t||teaFull(g.p2)===t)) return;
    if(dc && !m.grid.some(g=>discKey(g.p1)===dc||discKey(g.p2)===dc)) return;
    shown++;
    const rows=m.grid.map(g=>{
      const t1 = t && teaFull(g.p1)===t, t2 = t && teaFull(g.p2)===t;
      const hl1 = dc && discKey(g.p1)===dc, hl2 = dc && discKey(g.p2)===dc;
      // оставляем только строки, где есть пара выбранного преподавателя / дисциплины
      if(t && !t1 && !t2) return "";
      if(dc && !hl1 && !hl2) return "";
      // приглушаем ячейку, если активен фильтр и пара ему не соответствует
      const dim1 = ((t && !t1) || (dc && !hl1)) ? ' style="opacity:.32"' : '';
      const dim2 = ((t && !t2) || (dc && !hl2)) ? ' style="opacity:.32"' : '';
      const tt=g.time.split(" · ");
      return `<tr>
        <td class="time"><b>${tt[0]}</b>${tt[1]||""}</td>
        <td${dim1}>${cell(g.p1)}</td>
        <td${dim2}>${cell(g.p2)}</td>
      </tr>`;
    }).join("");
    grid.insertAdjacentHTML("beforeend",`
      <div class="mod">
        <div class="mhead">
          <div class="mtop"><span class="mname">${m.name}</span><span class="mday">${m.day} · ${m.date}</span></div>
          <div class="mmeta">
            <span class="chip venue">📍 ${m.venue}</span>
            <span class="chip fmt">${m.fmt}</span>
          </div>
          <div class="subs">Подразделения: <b>${m.subs.join(", ")}</b></div>
        </div>
        <table>
          <thead><tr><th>Пара</th><th>Поток 1 · ${audName(m.aud1)}</th><th>Поток 2 · ${audName(m.aud2)}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`);
  });
  document.getElementById("count").textContent = `Показано модулей: ${shown} из ${DATA.length}`;
}
[fDay,fVenue,fTeach,fDisc].forEach(s=>s.addEventListener("change",render));
render();

const pop=document.getElementById("pop");
function showPop(el){
  const k=el.dataset.tk, p=PEOPLE[k];
  if(!p) return;
  pop.innerHTML=`<div class="pf">${p.full}</div><a href="https://t.me/${p.tg}" target="_blank">@${p.tg}</a>`;
  pop.style.display="block";
  const r=el.getBoundingClientRect();
  let top=r.bottom+8, left=r.left;
  const pw=pop.offsetWidth, ph=pop.offsetHeight;
  if(left+pw>innerWidth-10) left=innerWidth-pw-10;
  if(top+ph>innerHeight-10) top=r.top-ph-8;
  pop.style.left=Math.max(10,left)+"px";
  pop.style.top=Math.max(10,top)+"px";
}
function hidePop(){pop.style.display="none";}
document.addEventListener("mouseover",e=>{const el=e.target.closest(".ptea.has");if(el)showPop(el);});
document.addEventListener("mouseout",e=>{
  if(e.target.closest(".ptea.has") && !e.relatedTarget?.closest("#pop")) hidePop();
});
document.addEventListener("click",e=>{
  const el=e.target.closest(".ptea.has");
  if(el){e.stopPropagation();showPop(el);}
  else if(!e.target.closest("#pop")) hidePop();
});
document.addEventListener("focusin",e=>{const el=e.target.closest(".ptea.has");if(el)showPop(el);});
addEventListener("scroll",hidePop,true);
</script>
</body>
</html>
"""


def build_html():
    dump = lambda obj: json.dumps(obj, ensure_ascii=False)
    rules = [[sub, key] for sub, key in TEACHER_RULES]
    return (TEMPLATE
            .replace("__DATA__", dump(DATA))
            .replace("__PEOPLE__", dump(PEOPLE))
            .replace("__TEACHERS__", dump(TEACHERS))
            .replace("__RULES__", dump(rules)))


def publish():
    """Коммитит и пушит raspisanie.html в GitHub через publish.sh."""
    script = Path(__file__).resolve().parent / "publish.sh"
    if not script.exists():
        print(f"Не найден {script} — пропускаю публикацию.", file=sys.stderr)
        return
    subprocess.run(["bash", str(script)], check=True)


def main():
    html = build_html()
    out = Path(OUTPUT)
    out.write_text(html, encoding="utf-8")
    print(f"Готово: {out.resolve()}")

    if "--publish" in sys.argv[1:]:
        publish()


if __name__ == "__main__":
    main()
