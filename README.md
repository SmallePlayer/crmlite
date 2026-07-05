# repair_crm — CRM для мастерской по ремонту 3D-принтеров

## Структура проекта

```
repair_crm/
├── main.py          # Точка входа: создание app, middleware, lifespan
├── config.py        # Настройки и константы
├── database.py      # SQLAlchemy engine и Base
├── helpers.py       # Утилиты: _audit, _notify, auth helpers
├── models/          # ORM-модели (User, Order, Client, etc.)
├── routers/         # API-роутеры по доменам
├── services/        # Бизнес-логика (для будущего использования)
├── templates/       # Jinja2 шаблоны
├── static/          # Статические файлы и uploads
└── alembic/         # Миграции БД
```

## Быстрый старт

```bash
cd repair_crm
cp .env.example .env
# Отредактируйте .env (SECRET_KEY, SMTP настройки)

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Деплой

```bash
cd ~/crmlite && git pull && kill $(lsof -ti:8000) 2>/dev/null && cd repair_crm && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &
```

## Документация для разработки

См. [repair_crm/AGENTS.md](repair_crm/AGENTS.md) — полная справка по архитектуре.
