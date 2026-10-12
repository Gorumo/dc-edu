#!/usr/bin/env python3
"""Слоты для листа «Слоты» из CONSULT в schedule-data.js.

Использование:
  python3 apps-script/gen_slots.py                      # текущая неделя (пн–вс)
  python3 apps-script/gen_slots.py --monday 19.10.2026 --weeks 2

Результат — apps-script/slots.csv: Файл → Импорт → Загрузить → «Заменить текущий лист»
на листе «Слоты», затем ещё раз запустить setup (вернёт галочки и форматы).
"""
import argparse, csv, datetime as dt, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "slots.csv"

DAYS = {"Понедельник": 0, "Вторник": 1, "Среда": 2, "Четверг": 3,
        "Пятница": 4, "Суббота": 5, "Воскресенье": 6}
# курс для тех, у кого он не указан в CONSULT
DEFAULT_COURSE = {("Бакалавриат", ""): "Инструментальные возможности ИИ",
                  ("Магистратура", "Продвинутый"): "Наука и технологии"}
# названия курсов в форме записи; id слота считается от короткого названия
COURSE_TITLE = {"Инструментальные возможности ИИ": "Инструментальные возможности ИИ (Бакалавриат)",
                "Наука и технологии": "ИИ-мышление: Наука и технологии",
                "Аналитика данных": "Культура ИИ: Аналитика данных",
                "Квалифицированный заказчик": "Культура ИИ: Квалифицированный заказчик",
                "Медиа и креативность": "Культура ИИ: Медиа и Креативность"}
SEATS_PER_90_MIN = 18


def load_consult():
    js = (ROOT / "schedule-data.js").read_text(encoding="utf-8")
    body = re.search(r"const CONSULT = (\{.*?\n\});", js, re.S).group(1)
    body = re.sub(r"//[^\n]*", "", body)                  # комментарии
    body = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', body)  # ключи в кавычки
    body = re.sub(r",(\s*[}\]])", r"\1", body)            # висячие запятые
    return json.loads(body)


def minutes(t):
    m = re.match(r"(\d{1,2}):(\d{2})\D+(\d{1,2}):(\d{2})", t)
    return (int(m[3]) * 60 + int(m[4])) - (int(m[1]) * 60 + int(m[2])) if m else 90


def main():
    ap = argparse.ArgumentParser()
    today = dt.date.today()
    ap.add_argument("--monday", default=(today - dt.timedelta(days=today.weekday())).strftime("%d.%m.%Y"))
    ap.add_argument("--weeks", type=int, default=1)
    a = ap.parse_args()
    monday = dt.datetime.strptime(a.monday, "%d.%m.%Y").date()

    rows = []
    for prog, people in load_consult().items():
        for p in people:
            teacher = p.get("name") or ("@" + p["tg"] if p.get("tg") else "")
            for sl in p.get("slots", []):
                day, time, *rest = sl
                course = next((x for x in rest if x != "backup"), None) or p.get("course") \
                    or DEFAULT_COURSE.get((prog, p.get("track", "")), "")
                title = COURSE_TITLE.get(course, course)
                seats = round(minutes(time) / 90 * SEATS_PER_90_MIN)
                for w in range(a.weeks):
                    date = monday + dt.timedelta(days=7 * w + DAYS[day])
                    key = f"{prog}|{course}|{teacher}|{date}|{time}"
                    sid = "s" + hashlib.md5(key.encode()).hexdigest()[:7]   # стабильный id; буква — чтобы Sheets не принял за число
                    rows.append([sid, title, teacher, date, time, "", seats, "TRUE"])

    rows.sort(key=lambda r: (r[3], int(re.match(r"\d+", r[4])[0]), r[1], r[2]))
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "Курс", "Преподаватель", "Дата", "Время", "Ссылка", "Мест", "Активен"])
        for r in rows:
            w.writerow([*r[:3], r[3].isoformat(), *r[4:]])   # ISO-дата читается в любой локали
    print(f"{len(rows)} слотов → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
