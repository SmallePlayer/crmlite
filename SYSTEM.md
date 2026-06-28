# crmlite — Монорепозиторий CRM-систем

## Структура репозитория

```
crmlite/
├── repair_crm/          # ← АКТУАЛЬНЫЙ ПРОЕКТ. SSR на FastAPI+Jinja2.
│   ├── AGENTS.md        # ★ ИИ-документация (читай первой!)
│   ├── main.py          # Вся логика (~2180 строк)
│   ├── templates/       # Jinja2 шаблоны
│   ├── static/          # PWA + uploads
│   ├── run.sh           # Скрипт запуска
│   └── requirements.txt
├── app/                 # ← СТАРЫЙ ПРОЕКТ. SPA на одном HTML-файле.
│   ├── main.py          # FastAPI entry
│   ├── database.py      # SQLAlchemy engine
│   ├── models.py        # ORM-модели
│   ├── schemas.py       # Pydantic
│   ├── auth.py          # JWT
│   ├── routes_*.py      # Роутеры
│   └── static/
│       └── index.html   # SPA (весь фронтенд в одном файле)
├── alembic/             # Миграции (старый проект)
├── tests/               # Тесты (старый проект)
├── venv/                # Python виртуальное окружение
└── requirements.txt     # Зависимости (старый проект)
```

## Актуальный проект: `repair_crm/`

**Полная документация**: [repair_crm/AGENTS.md](repair_crm/AGENTS.md) — читать при любых изменениях.

Кратко:
- FastAPI + SQLAlchemy + SQLite + Jinja2 серверный рендеринг
- Вся логика в одном файле `main.py`
- Bootstrap 5 через CDN, минимум JavaScript
- 13 таблиц, ~50 роутов, 21 шаблон

## Старый проект: `app/`

SPA-версия на одном HTML-файле (`static/index.html`). Больше не поддерживается.

## Команды сервера

```bash
cd ~/crmlite && git pull && kill $(lsof -ti:8000) 2>/dev/null && cd repair_crm && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
```
