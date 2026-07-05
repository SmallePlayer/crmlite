from pathlib import Path
from datetime import timedelta
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, TIMEZONE_OFFSET

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["money"] = lambda x: f"{x:,.0f}".replace(",", " ") + " ₽"
templates.env.filters["dt"] = lambda x: (x + TIMEZONE_OFFSET).strftime("%d.%m.%Y %H:%M") if x else "—"
templates.env.filters["tm"] = lambda x: (x + TIMEZONE_OFFSET).strftime("%H:%M") if x else "—"
templates.env.filters["int"] = lambda x: f"{x:,}".replace(",", " ") if x else "0"
_MONTHS_RU = ["","январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"]
templates.env.filters["month_ru"] = lambda dt: _MONTHS_RU[(dt + TIMEZONE_OFFSET).month] if dt else "—"
