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

import csv
import io
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

OUTPUT = "raspisanie.html"

# Источники данных — Google-таблицы (вкладки «Потоки»), с локальным кэшем на случай,
# если сеть недоступна.
def _csv_url(sheet_id, gid):
    return (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/export?format=csv&gid={gid}")

BACH_CSV_URL = _csv_url("1cpllz5oY2lV1VbO_AzLNVkyrn6g9-8SHAuwjLOAgQkM", "1702931394")
BACH_CACHE = "potoki.csv"
MAG_CSV_URL = _csv_url("1olj3EdemHiCbQFngPi9d4oWCUctYEZIN75PHwkKP__E", "875729294")
MAG_CACHE = "potoki_mag.csv"

# ---------------------------------------------------------------------------
# 1. ПРЕПОДАВАТЕЛИ:  ключ -> полное ФИО + telegram (без @)
# ---------------------------------------------------------------------------
PEOPLE = {
    "Двойникова": {"full": "Двойникова Анастасия Александровна", "tg": "nastya_dvoynikova"},
    "Азимов":     {"full": "Азимов Рустам Шухратуллович",        "tg": "rustamazimov95"},
    "Колцун":     {"full": "Колцун Никита Валерьевич",           "tg": "KoltsNik"},
    "Акопян":     {"full": "Акопян Анжела Артаковна",            "tg": "nglicae"},
    "Носань":     {"full": "Носань Марк",                        "tg": "doyouseemegod"},
    "Романов":    {"full": "Романов Алексей Андреевич",          "tg": "gorumo"},
    "Волчек":     {"full": "Волчек Дмитрий Геннадьевич",         "tg": "dvolchek"},
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
    # Романов
    "КультИИ: МиК (Мод 2) 1.1": "Романов",
    # Волчек
    "КультИИ: КЗ (Мод 3) 1.1": "Волчек",
    "КультИИ: МиК (Мод 3) 1.1": "Волчек",
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
  tr.grp td{background:#15181f;color:var(--accent);font-weight:600;font-size:11.5px}
  tr.mrow td{background:#0c0e12;color:var(--txt);font-weight:700;font-size:12.5px;letter-spacing:.05em;text-transform:uppercase}
  tr.drow td{background:#191c24;color:var(--muted);font-weight:600;font-size:11px;padding-left:18px}
  .mod.load{grid-column:1/-1}
  td.time{white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums;font-size:11.5px}
  td.time b{display:block;color:var(--txt);font-size:13px}
  .cell{display:flex;align-items:flex-start;gap:7px}
  .disc{display:block}
  .ptea{display:block;font-size:10.5px;color:var(--muted);margin-top:2px}
  .ptea.has{color:var(--accent);cursor:pointer;border-bottom:1px dashed rgba(106,160,255,.5);
    display:inline-block;line-height:1.5;outline:none}
  .ptea.has:hover,.ptea.has:focus{color:#9dc0ff}
  .sname{color:var(--txt);cursor:pointer;border-bottom:1px dashed rgba(154,163,178,.55);outline:none}
  .sname:hover,.sname:focus{color:#fff}
  #pop{position:fixed;z-index:50;background:var(--card2);border:1px solid var(--accent);
    border-radius:10px;padding:11px 13px;max-width:260px;box-shadow:0 8px 28px rgba(0,0,0,.55);
    font-size:13px;display:none;animation:pf .12s ease}
  @keyframes pf{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
  #pop .pf{font-weight:650;margin-bottom:5px;color:var(--txt)}
  #pop .pl{font-size:12px;color:var(--muted);margin-top:3px}
  #pop .pl b{color:var(--txt);font-weight:600}
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
  <div class="sub">2026–2027 · переключайте «Магистратуру» и «Бакалавриат» в фильтре «Программа»</div>
  <div class="controls">
    <div class="ctl"><label>Программа</label><select id="fLevel"></select></div>
    <div class="ctl" id="ctlDay"><label>День недели</label><select id="fDay"></select></div>
    <div class="ctl" id="ctlVenue"><label>Площадка</label><select id="fVenue"></select></div>
    <div class="ctl" id="ctlTeach"><label id="lblTeach">Преподаватель</label><select id="fTeach"></select></div>
    <div class="ctl" id="ctlDisc"><label id="lblDisc">Дисциплина</label><select id="fDisc"></select></div>
    <span class="count" id="count"></span>
  </div>
  <div class="legend" id="legend">
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
const BACH_DATA = __DATA_B__;
const STREAMS = __STREAMS__;
const MAG_STREAMS = __MAG_STREAMS__;   // название пары -> подразделение (магистратура)
let MODE = "mag";   // "mag" — магистратура, "bach" — бакалавриат

// --- Учебный календарь: якорь = понедельник 1-й недели, дальше всё считаем по 7 дней ---
const ANCHOR_MS = Date.parse("__ANCHOR__" + "T00:00:00Z");
const WD_OFF = {"ПОНЕДЕЛЬНИК":0,"ВТОРНИК":1,"СРЕДА":2,"ЧЕТВЕРГ":3,"ПЯТНИЦА":4,"СУББОТА":5,"ВОСКРЕСЕНЬЕ":6};
function weekDate(week, dayName){
  return new Date(ANCHOR_MS + ((week-1)*7 + (WD_OFF[dayName]||0))*86400000);
}
function fmtDate(d){
  const p=n=>String(n).padStart(2,"0");
  return p(d.getUTCDate())+"."+p(d.getUTCMonth()+1)+"."+d.getUTCFullYear();
}
function weeksOf(str){ return (str.match(/\d+/g)||[]).map(Number); }
function dateToWeek(ddmmyyyy){
  const m=String(ddmmyyyy).match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if(!m || isNaN(ANCHOR_MS)) return null;
  const ms=Date.parse(`${m[3]}-${m[2]}-${m[1]}T00:00:00Z`);
  return Math.floor((ms-ANCHOR_MS)/(7*86400000))+1;
}

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
  const disc = (s in MAG_STREAMS)
    ? `<span class="disc"><span class="sname" tabindex="0" data-md="${s}">${prettyName(s)}</span></span>`
    : `<span class="disc">${prettyName(s)}</span>`;
  return `<span class="cell"><span class="bar" style="background:${discColor(s)}"></span>`+
    `<span>${disc}${tea}</span></span>`;
}
function uniq(arr){return [...new Set(arr.filter(Boolean))];}
function fill(sel,vals,allLabel){
  sel.innerHTML = `<option value="">${allLabel}</option>` +
    vals.map(v=>`<option value="${v}">${v}</option>`).join("");
}

const DISCS=[["КЗ","КультИИ КЗ"],["АД","КультИИ АД"],["МиК","КультИИ МиК"],["НиТ","ИИ Прод"],["AI","AI Culture"]];
function showCtl(el,on){el.style.display=on?"":"none";}
function setupFilters(){
  if(MODE==="load"){
    lblTeach.textContent="Преподаватель";
    fill(fTeach,Object.keys(buildLoad()).sort((a,b)=>a.localeCompare(b,"ru")),"Все преподаватели");
    showCtl(ctlDay,false); showCtl(ctlVenue,false); showCtl(ctlDisc,false); showCtl(ctlTeach,true);
    legend.style.display="none";
    return;
  }
  showCtl(ctlDay,true); showCtl(ctlVenue,true); showCtl(ctlDisc,true); showCtl(ctlTeach,true);
  const data = MODE==="bach" ? BACH_DATA : DATA;
  fill(fDay,uniq(data.map(m=>m.day)),"Все дни");
  fill(fVenue,uniq(data.map(m=>m.venue)),"Все площадки");
  if(MODE==="mag"){
    lblTeach.textContent="Преподаватель"; lblDisc.textContent="Дисциплина";
    fill(fTeach,Object.keys(PEOPLE).map(k=>PEOPLE[k].full),"Все преподаватели");
    fDisc.innerHTML='<option value="">Все дисциплины</option>'+
      DISCS.map(([v,l])=>`<option value="${v}">${l}</option>`).join("");
    legend.style.display="";
  } else {
    lblTeach.textContent="ОП"; lblDisc.textContent="Неделя";
    fill(fTeach,uniq(Object.values(STREAMS).map(s=>s.op)),"Все ОП");
    fill(fDisc,uniq(BACH_DATA.map(m=>m.parity)),"Все недели");
    legend.style.display="none";
  }
}
fLevel.innerHTML='<option value="mag">Магистратура</option>'+
  (BACH_DATA.length?'<option value="bach">Бакалавриат</option>':'')+
  '<option value="load">Нагрузка</option>';

// --- НАГРУЗКА: реальная нагрузка преподавателя по неделям семестра ---
const DAY_ORD={"ВТОРНИК":0,"ПЯТНИЦА":1,"ПОНЕДЕЛЬНИК":2,"СРЕДА":3,"ЧЕТВЕРГ":4,"СУББОТА":5};
const DAY_ABBR={"ПОНЕДЕЛЬНИК":"ПН","ВТОРНИК":"ВТ","СРЕДА":"СР","ЧЕТВЕРГ":"ЧТ","ПЯТНИЦА":"ПТ","СУББОТА":"СБ"};
const DAY_NICE={"ПОНЕДЕЛЬНИК":"Понедельник","ВТОРНИК":"Вторник","СРЕДА":"Среда","ЧЕТВЕРГ":"Четверг","ПЯТНИЦА":"Пятница","СУББОТА":"Суббота"};
const RU_MONTH_NOM=["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
function buildLoad(){
  const T={};
  function add(name,tg,s){
    if(!name) return;
    if(!T[name]) T[name]={tg:"",sessions:[]};
    if(tg && !T[name].tg) T[name].tg=tg;
    T[name].sessions.push(s);
  }
  // магистратура: каждая пара идёт 8 недель подряд от даты старта модуля
  DATA.forEach((m,mi)=>{
    const sw=dateToWeek(m.date);
    const weeks=sw?Array.from({length:8},(_,i)=>sw+i):[];
    m.grid.forEach(g=>{
      [["p1",m.aud1],["p2",m.aud2]].forEach(([key,aud])=>{
        const s=g[key]; if(!s) return;
        const k=teachKey(s); if(!k) return; const p=PEOPLE[k];
        add(p.full,p.tg,{ord:100+mi,day:m.day,weeks:weeks,
          time:g.time,title:prettyName(s),place:`${m.venue} · ауд. ${aud}`});
      });
    });
  });
  // бакалавриат: пара идёт по неделям своей волны
  BACH_DATA.forEach((m,bi)=>{
    const weeks=weeksOf(m.weeks);
    m.grid.forEach(g=>{
      [["p1",m.aud1],["p2",m.aud2]].forEach(([key,aud])=>{
        streamsIn(g[key]).forEach(sid=>{
          const st=STREAMS[sid]; if(!st||!st.tname) return;
          add(st.tname,st.ttg,{ord:bi,day:m.day,weeks:weeks,
            time:g.time,title:shortStream(sid),place:`${m.venue} · ауд. ${aud}`});
        });
      });
    });
  });
  // склеенные потоки в одном слоте — одна пара
  Object.values(T).forEach(info=>{
    const map={}, merged=[];
    info.sessions.forEach(s=>{
      const k=s.ord+"|"+s.day+"|"+s.time+"|"+s.place;
      if(map[k]) map[k].title+=", "+s.title;
      else { map[k]={...s}; merged.push(map[k]); }
    });
    info.sessions=merged;
  });
  return T;
}
function weekMonth(w){ return weekDate(w,"ЧЕТВЕРГ").getUTCMonth(); }
function weekRange(w){
  const a=weekDate(w,"ПОНЕДЕЛЬНИК"), b=weekDate(w,"ПЯТНИЦА"), p=n=>String(n).padStart(2,"0");
  return a.getUTCMonth()===b.getUTCMonth()
    ? `${p(a.getUTCDate())}–${p(b.getUTCDate())}.${p(b.getUTCMonth()+1)}`
    : `${p(a.getUTCDate())}.${p(a.getUTCMonth()+1)}–${p(b.getUTCDate())}.${p(b.getUTCMonth()+1)}`;
}
function parityRu(w){ return (w%2===1)?"нечёт":"чёт"; }
function renderLoad(){
  const t=fTeach.value;
  const grid=document.getElementById("grid"); grid.innerHTML="";
  const load=buildLoad();
  const names=(t?[t]:Object.keys(load)).filter(n=>load[n]).sort((a,b)=>a.localeCompare(b,"ru"));
  let shown=0;
  names.forEach(name=>{
    const info=load[name]; shown++;
    // разворачиваем каждую пару в её недели — реальная нагрузка по семестру
    const occ=[];
    info.sessions.forEach(s=>(s.weeks||[]).forEach(w=>
      occ.push({week:w,day:s.day,time:s.time,title:s.title,place:s.place})));
    occ.sort((a,b)=>a.week-b.week || (DAY_ORD[a.day]||0)-(DAY_ORD[b.day]||0) || parseInt(a.time)-parseInt(b.time));
    const total=occ.length;
    const byWeek={}; occ.forEach(o=>byWeek[o.week]=(byWeek[o.week]||0)+1);
    const nWeeks=Object.keys(byWeek).length;
    const avg=nWeeks?(total/nWeeks):0, maxW=nWeeks?Math.max(...Object.values(byWeek)):0;
    let body="", curMonth=-1, curWeek=-1, curDay="";
    occ.forEach(o=>{
      const mo=weekMonth(o.week);
      if(mo!==curMonth){ curMonth=mo; curWeek=-1; curDay="";
        body+=`<tr class="mrow"><td colspan="3">${RU_MONTH_NOM[mo]}</td></tr>`; }
      if(o.week!==curWeek){ curWeek=o.week; curDay="";
        body+=`<tr class="grp"><td colspan="3">Неделя ${o.week} · ${parityRu(o.week)} · ${weekRange(o.week)} — ${byWeek[o.week]} пар.</td></tr>`; }
      if(o.day!==curDay){ curDay=o.day;
        const cd=occ.filter(x=>x.week===o.week && x.day===o.day).length;
        body+=`<tr class="drow"><td colspan="3">${DAY_NICE[o.day]||o.day} · ${fmtDate(weekDate(o.week,o.day))} — ${cd} пар.</td></tr>`; }
      const tt=o.time.split(" · ");
      body+=`<tr><td class="time"><b>${tt[1]||tt[0]}</b></td><td>${o.title}</td><td>${o.place}</td></tr>`;
    });
    const tg=info.tg?`<span class="chip fmt"><a href="https://t.me/${info.tg}" target="_blank" style="color:inherit;text-decoration:none">@${info.tg}</a></span>`:"";
    grid.insertAdjacentHTML("beforeend",`
      <div class="mod load">
        <div class="mhead">
          <div class="mtop"><span class="mname">${name}</span><span class="mday">пар за семестр: ${total}</span></div>
          <div class="mmeta">${tg}<span class="chip">недель с парами: ${nWeeks}</span><span class="chip">~${avg.toFixed(1)} пар/нед</span><span class="chip">пик: ${maxW}/нед</span></div>
        </div>
        <table>
          <thead><tr><th>Время</th><th>Пара</th><th>Где</th></tr></thead>
          <tbody>${body||'<tr><td colspan="3" class="empty">— нет нагрузки —</td></tr>'}</tbody>
        </table>
      </div>`);
  });
  document.getElementById("count").textContent = t?`Преподаватель: ${shown}`:`Преподавателей: ${shown}`;
}
setupFilters();

// --- БАКАЛАВРИАТ: ячейка = поток(и); клик показывает ОП и детали ---
const STREAM_RE=/ИвИИ\s+\d+\s+\(ВШ ЦК1\)\s+\S+\s+\d+\.\d+/g;
function streamsIn(s){return s ? (s.match(STREAM_RE)||[]) : [];}
function opOf(sid){const x=STREAMS[sid];return x?x.op:null;}
function shortStream(sid){return sid.replace(/\s*\(ВШ ЦК1\)\s*/," · ");}
function bukvaColor(b){
  if(!b) return "var(--muted)";
  let h=0; for(const c of b) h=(h*37+c.charCodeAt(0))%360;
  return `hsl(${h},55%,58%)`;
}
function cellB(raw){
  const list=streamsIn(raw);
  if(!list.length) return '<span class="empty">—</span>';
  const s0=STREAMS[list[0]]||{};
  // склеенные потоки = одна пара: перечисляем через запятую (ОП — по наведению)
  const names=list.map(sid=>
    `<span class="sname" tabindex="0" data-sid="${sid}">${shortStream(sid)}</span>`).join(", ");
  // преподаватели под названием (уникальные), как в магистратуре
  const teas=[];
  list.forEach(sid=>{const t=STREAMS[sid];
    if(t&&t.tname&&!teas.some(x=>x.tname===t.tname)) teas.push(t);});
  const teaLine = teas.length
    ? teas.map(t=>t.ttg
        ? `<span class="ptea has" tabindex="0" data-tn="${t.tname}" data-tg="${t.ttg}">👤 ${shortName(t.tname)}</span>`
        : `<span class="ptea">👤 ${shortName(t.tname)}</span>`).join(", ")
    : '<span class="ptea">👤 не указан</span>';
  return `<span class="cell"><span class="bar" style="background:${bukvaColor(s0.bukva)}"></span>`+
    `<span><span class="disc">${names}</span>${teaLine}</span></span>`;
}
function renderBach(){
  const d=fDay.value,v=fVenue.value,op=fTeach.value,wk=fDisc.value;
  const grid=document.getElementById("grid");
  grid.innerHTML=""; let shown=0;
  BACH_DATA.forEach(m=>{
    if(d && m.day!==d) return;
    if(v && m.venue!==v) return;
    if(wk && m.parity!==wk) return;
    if(op && !m.grid.some(g=>[...streamsIn(g.p1),...streamsIn(g.p2)].some(x=>opOf(x)===op))) return;
    shown++;
    const rows=m.grid.map(g=>{
      const s1=streamsIn(g.p1), s2=streamsIn(g.p2);
      if(!s1.length && !s2.length) return "";
      const o1=op && s1.some(x=>opOf(x)===op), o2=op && s2.some(x=>opOf(x)===op);
      if(op && !o1 && !o2) return "";
      const dim1=(op && !o1)?' style="opacity:.32"':'';
      const dim2=(op && !o2)?' style="opacity:.32"':'';
      const tt=g.time.split(" · ");
      return `<tr><td class="time"><b>${tt[0]}</b>${tt[1]||""}</td>`+
        `<td${dim1}>${cellB(g.p1)}</td><td${dim2}>${cellB(g.p2)}</td></tr>`;
    }).join("");
    const wks=weeksOf(m.weeks);
    const first=(wks.length && !isNaN(ANCHOR_MS)) ? fmtDate(weekDate(Math.min(...wks), m.day)) : "";
    grid.insertAdjacentHTML("beforeend",`
      <div class="mod">
        <div class="mhead">
          <div class="mtop"><span class="mname">${m.day}</span><span class="mday">${m.parity} · ${m.wave}</span></div>
          <div class="mmeta">
            <span class="chip venue">📍 ${m.venue}</span>
            ${first?`<span class="chip">📅 первое занятие: ${first}</span>`:""}
            <span class="chip fmt">недели: ${m.weeks}</span>
          </div>
        </div>
        <table>
          <thead><tr><th>Пара</th><th>Поток 1 · ${m.aud1}</th><th>Поток 2 · ${m.aud2}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`);
  });
  document.getElementById("count").textContent=`Показано: ${shown} из ${BACH_DATA.length}`;
}

function teaFull(s){const k=teachKey(s);return k?PEOPLE[k].full:null;}
function render(){
  if(MODE==="load") return renderLoad();
  return MODE==="bach" ? renderBach() : renderMag();
}
function renderMag(){
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
    const sw=dateToWeek(m.date);
    const weeksTxt = sw ? `${sw}–${sw+7}` : "";
    grid.insertAdjacentHTML("beforeend",`
      <div class="mod">
        <div class="mhead">
          <div class="mtop"><span class="mname">${m.name}</span><span class="mday">${m.day} · ${m.date}</span></div>
          <div class="mmeta">
            <span class="chip venue">📍 ${m.venue}</span>
            <span class="chip fmt">${m.fmt}</span>
            <span class="chip">📅 первое занятие: ${m.date}</span>
            ${weeksTxt?`<span class="chip">недели: ${weeksTxt} (8 нед.)</span>`:""}
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
fLevel.addEventListener("change",()=>{
  MODE=fLevel.value;
  [fDay,fVenue,fTeach,fDisc].forEach(s=>s.value="");
  setupFilters();
  render();
});
[fDay,fVenue,fTeach,fDisc].forEach(s=>s.addEventListener("change",render));
render();

const pop=document.getElementById("pop");
function showPop(el){
  if(el.dataset.md!==undefined){
    const podr=MAG_STREAMS[el.dataset.md];
    pop.innerHTML=`<div class="pf">${prettyName(el.dataset.md)}</div>`+
      (podr?`<div class="pl">Подразделение: <b>${podr}</b></div>`:"");
  } else if(el.dataset.sid!==undefined){
    const s=STREAMS[el.dataset.sid];
    if(!s) return;
    pop.innerHTML=`<div class="pf">${s.op||el.dataset.sid}</div>`+
      (s.podr?`<div class="pl">Подразделение: <b>${s.podr}</b></div>`:"");
  } else if(el.dataset.tg!==undefined){
    pop.innerHTML=`<div class="pf">${el.dataset.tn}</div>`+
      `<a href="https://t.me/${el.dataset.tg}" target="_blank">@${el.dataset.tg}</a>`;
  } else {
    const p=PEOPLE[el.dataset.tk];
    if(!p) return;
    pop.innerHTML=`<div class="pf">${p.full}</div><a href="https://t.me/${p.tg}" target="_blank">@${p.tg}</a>`;
  }
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
const POP_SEL=".ptea.has,.sname";
document.addEventListener("mouseover",e=>{const el=e.target.closest(POP_SEL);if(el)showPop(el);});
document.addEventListener("mouseout",e=>{
  if(e.target.closest(POP_SEL) && !e.relatedTarget?.closest("#pop")) hidePop();
});
document.addEventListener("click",e=>{
  const el=e.target.closest(POP_SEL);
  if(el){e.stopPropagation();showPop(el);}
  else if(!e.target.closest("#pop")) hidePop();
});
document.addEventListener("focusin",e=>{const el=e.target.closest(POP_SEL);if(el)showPop(el);});
addEventListener("scroll",hidePop,true);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# БАКАЛАВРИАТ: данные тянутся из Google-таблицы (вкладка «Потоки»).
#   • потоки      — колонка E (id) + B (ОП) + остальные метаданные (A,C,D,F,H–L)
#   • расписание  — блоки матрицы в колонках N–T (день/чёт-нечёт/время/аудитории)
# ---------------------------------------------------------------------------
_MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль",
           "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
_DAYS = {"ПН": "ПОНЕДЕЛЬНИК", "ВТ": "ВТОРНИК", "СР": "СРЕДА",
         "ЧТ": "ЧЕТВЕРГ", "ПТ": "ПЯТНИЦА"}


def fetch_csv_rows(url, cache_name, label):
    """Скачивает CSV-вкладку; при сбое берёт локальный кэш."""
    cache = Path(__file__).resolve().parent / cache_name
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            text = resp.read().decode("utf-8")
        cache.write_text(text, encoding="utf-8")
        print(f"{label}: данные загружены из Google Sheets.")
    except Exception as exc:                       # noqa: BLE001
        if cache.exists():
            print(f"{label}: не удалось скачать ({exc}), использую кэш {cache_name}.",
                  file=sys.stderr)
            text = cache.read_text(encoding="utf-8")
        else:
            print(f"{label}: не удалось скачать ({exc}) и кэша нет — пропускаю.",
                  file=sys.stderr)
            return []
    return list(csv.reader(io.StringIO(text)))


def _g(rows, ri, ci):
    return (rows[ri][ci] if ci < len(rows[ri]) else "").strip()


# Преподаватели бакалавриата: id потока -> (ФИО, telegram без @).
# Заполняется вручную по мере появления данных (в таблице колонка пока пустая).
BACH_TEACHERS = {
    "ИвИИ 2 (ВШ ЦК1) U 1.1": ("Иванова Кристина Юрьевна", "unoivansson"),
    "ИвИИ 2 (ВШ ЦК1) U 1.3": ("Иванова Кристина Юрьевна", "unoivansson"),
    "ИвИИ 4 (ВШ ЦК1) J 1.2": ("Волков Александр Романович", "alexandrr_volkov"),
    "ИвИИ 4 (ВШ ЦК1) GVн 1.4": ("Волков Александр Романович", "alexandrr_volkov"),
    "ИвИИ 3 (ВШ ЦК1) H 1.1": ("Волков Александр Романович", "alexandrr_volkov"),
    "ИвИИ 3 (ВШ ЦК1) L 1.6": ("Волков Александр Романович", "alexandrr_volkov"),
    "ИвИИ 4 (ВШ ЦК1) J 1.1": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 4 (ВШ ЦК1) J 1.3": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 4 (ВШ ЦК1) C 1.3": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 2 (ВШ ЦК1) U 1.2": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 2 (ВШ ЦК1) U 1.4": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 2 (ВШ ЦК1) OVф 1.6": ("Романов Алексей Андреевич", "gorumo"),
    "ИвИИ 1 (ВШ ЦК1) P 1.5": ("Волчек Дмитрий Геннадьевич", "dvolchek"),
    "ИвИИ 1 (ВШ ЦК1) P 1.6": ("Волчек Дмитрий Геннадьевич", "dvolchek"),
    "ИвИИ 1 (ВШ ЦК1) K 1.4": ("Волчек Дмитрий Геннадьевич", "dvolchek"),
}


STREAM_ID_RE = re.compile(r"^ИвИИ\s+\d+\s+\(ВШ ЦК1\)\s+\S+\s+\d+\.\d+$")


def parse_streams(rows):
    """Колонка E (id потока) -> {ОП, подразделение, буква, преподаватель}.

    Берём только реальные потоки (по шаблону id) и разворачиваем объединённые
    ячейки: в CSV значение объединённой ячейки стоит лишь в первой строке, поэтому
    пустые ОП/подразделение/буква наследуем от предыдущего потока. На разрыве
    (строка без потока) наследование сбрасываем.
    """
    streams = {}
    last = {"podr": "", "op": "", "bukva": ""}
    for ri in range(2, len(rows)):
        sid = _g(rows, ri, 4)
        if not STREAM_ID_RE.match(sid):
            last = {"podr": "", "op": "", "bukva": ""}
            continue
        podr = _g(rows, ri, 0) or last["podr"]
        op = _g(rows, ri, 1) or last["op"]
        bukva = _g(rows, ri, 2) or last["bukva"]
        last = {"podr": podr, "op": op, "bukva": bukva}
        tname, ttg = BACH_TEACHERS.get(sid, (_g(rows, ri, 10), ""))
        streams.setdefault(sid, {"op": op, "podr": podr, "bukva": bukva,
                                 "tname": tname, "ttg": ttg})
    return streams


def _fix_time(o):
    m = re.match(r"(\d+)\s*\((.+?)\)", o)
    return f'{m.group(1)} · {m.group(2).replace(" - ", "–").replace(" ", "")}' if m else o


def _venue_of(aud):
    if aud.endswith("Л"):
        return "ЛОМО"
    if aud.endswith("К"):
        return "КРОН"
    return aud or "—"


def _parse_marker(s):
    m = re.match(r"(ВТ|ПТ|ПН|СР|ЧТ)\s*(\d+)?\s*ВОЛНА\s*([\d, ]*)", s)
    if not m:
        return None
    return (_DAYS[m.group(1)], m.group(2) or "", (m.group(3) or "").strip().rstrip(","))


def parse_bachelor(rows):
    """Строит карточки расписания (день · чётность) из матрицы N–T."""
    boundary = next((ri for ri in range(len(rows))
                     if _g(rows, ri, 15).lower() in _MONTHS), len(rows))
    cards = []
    for ri in range(boundary):
        if _g(rows, ri, 14) != "Аудитория":           # строка с аудиториями
            continue
        parity = "Нечётная" if _g(rows, ri, 13).lower().startswith("неч") else "Чётная"
        # строки времени/пар идут ниже до первого «не-времени»
        grid_rows = []
        rj = ri + 1
        while rj < boundary and re.match(r"\d+\s*\(", _g(rows, rj, 14)):
            grid_rows.append(rj)
            rj += 1
        # два дня в блоке: (P,Q)=колонки 15,16 и (S,T)=18,19; маркер дня — строкой выше
        for c1, c2 in [(15, 16), (18, 19)]:
            marker = _parse_marker(_g(rows, ri - 1, c1))
            if not marker:
                continue
            day, wave, weeks = marker
            aud1, aud2 = _g(rows, ri, c1), _g(rows, ri, c2)
            grid = [{"time": _fix_time(_g(rows, r, 14)),
                     "p1": _g(rows, r, c1), "p2": _g(rows, r, c2)} for r in grid_rows]
            cards.append({"day": day, "parity": parity,
                          "wave": (wave + " волна" if wave else ""),
                          "weeks": weeks, "venue": _venue_of(aud1),
                          "aud1": aud1, "aud2": aud2, "grid": grid})
    return cards


def parse_calendar_anchor(rows):
    """Из учебного календаря (внизу вкладки) вычисляет понедельник 1-й недели.

    Колонки: N(13)=номер недели, O(14)=чёт/нечёт (н/ч), P–T(15–19)=даты ПН…ПТ,
    заголовки месяцев — в колонке P. Возвращает ISO-дату якоря или "".
    """
    cur_month = None
    for ri in range(len(rows)):
        p = _g(rows, ri, 15).lower()
        if p in _MONTHS:
            cur_month = _MONTHS.index(p) + 1
        wk, par, vt = _g(rows, ri, 13), _g(rows, ri, 14).lower(), _g(rows, ri, 16)
        if cur_month and wk.isdigit() and par in ("н", "ч") and vt.isdigit():
            year = 2026 if cur_month >= 8 else 2027  # осенний семестр 2026/27
            anchor = date(year, cur_month, int(vt)) - timedelta(days=(int(wk) - 1) * 7 + 1)
            return anchor.isoformat()
    return ""


def load_bachelor():
    rows = fetch_csv_rows(BACH_CSV_URL, BACH_CACHE, "Бакалавриат")
    if not rows:
        return [], {}, ""
    return parse_bachelor(rows), parse_streams(rows), parse_calendar_anchor(rows)


def parse_mag_streams(rows):
    """Колонка E (название пары) -> подразделение (колонка D). Без ОП."""
    out = {}
    for ri in range(1, len(rows)):
        name = _g(rows, ri, 4)
        podr = _g(rows, ri, 3)
        if not name or not re.search(r"\((?:Мод|Mod)\s*\d+\)", name):
            continue
        out.setdefault(name, podr)
    return out


def load_mag_streams():
    rows = fetch_csv_rows(MAG_CSV_URL, MAG_CACHE, "Магистратура")
    return parse_mag_streams(rows) if rows else {}


def build_html():
    dump = lambda obj: json.dumps(obj, ensure_ascii=False)
    rules = [[sub, key] for sub, key in TEACHER_RULES]
    data_b, streams, anchor = load_bachelor()
    mag_streams = load_mag_streams()
    return (TEMPLATE
            .replace("__DATA__", dump(DATA))
            .replace("__PEOPLE__", dump(PEOPLE))
            .replace("__TEACHERS__", dump(TEACHERS))
            .replace("__RULES__", dump(rules))
            .replace("__DATA_B__", dump(data_b))
            .replace("__STREAMS__", dump(streams))
            .replace("__MAG_STREAMS__", dump(mag_streams))
            .replace("__ANCHOR__", anchor))


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
