# repair_crm — AI Developer Reference

> Этот файл читается ИИ-ассистентом в начале каждого нового чата. Содержит всё необходимое для мгновенного понимания архитектуры проекта.

---

## 1. Что это за проект

**CRM-система для мастерской по ремонту 3D-принтеров.**

**Стек**: Python 3 + FastAPI + SQLAlchemy 2.0 + SQLite + Jinja2 + Bootstrap 5.3 (CDN)

**Тип приложения**: Server-Side Rendered (SSR). Все HTML генерируются на сервере Jinja2. JS — только модалки, confirm, Chart.js. **SPA нет.**

---

## 2. Развёртывание на сервер

Репозиторий: `https://github.com/SmallePlayer/crmlite.git`
Сервер: `root@tasha` (или другой)
Путь на сервере: `~/crmlite/repair_crm/`

**Команда деплоя** (одной строкой):
```bash
cd ~/crmlite && git fetch origin && git reset --hard origin/main && kill -9 $(lsof -ti:8000) 2>/dev/null && sleep 1 && find repair_crm -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null && cd repair_crm && nohup venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 &
```

**Локальный запуск**:
```bash
cd repair_crm && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**После деплоя всегда нужен Ctrl+Shift+R в браузере** (сброс кеша).

**Остановка сервера**:
```bash
kill -9 $(lsof -ti:8000) 2>/dev/null
```

**Доступ к БД на сервере** (sqlite3 не установлен, использовать Python):
```bash
cd ~/crmlite/repair_crm && venv/bin/python3 -c "
from sqlalchemy import create_engine, text
e = create_engine('sqlite:///repair_crm.db')
with e.connect() as c:
    rows = c.execute(text('YOUR SQL')).fetchall()
    for r in rows: print(r)
"
```

---

## 3. Файловая структура

```
repair_crm/
├── main.py                 # ВСЯ логика (~3300 строк) — модели, роуты, middleware, хелперы
├── requirements.txt        # fastapi, uvicorn, sqlalchemy, jinja2, python-jose, openpyxl, fpdf2, python-dotenv
├── .env                    # SECRET_KEY, DATABASE_URL
├── repair_crm.db           # SQLite (НЕ коммитится)
├── templates/              # 20+ Jinja2 шаблонов
│   ├── base.html           # Главный layout: sidebar, mobile header, CSS
│   ├── index.html          # Дашборд + виджет аудита для админа
│   ├── orders.html         # Список заказов: табы, фильтры, batch
│   ├── order_create.html   # Форма создания заказа
│   ├── order_detail.html   # Детали заказа: статус-флоу, услуги, запчасти
│   ├── products.html       # Склад товаров: приход, расход, поставка, варианты, себестоимость
│   ├── filaments.html      # Пластик: карточки, приход/расход, автоартикул, поиск
│   ├── prints.html         # Печать: список, принтеры, результат успех/брак
│   ├── attendance.html     # Посещаемость: чек-ин/аут, месяц, расписание
│   ├── chat.html           # Чат: общий + личные сообщения
│   ├── audit.html          # Аудит: фильтры, пагинация
│   ├── users.html          # Пользователи и роли
│   ├── schedule.html       # Расписание заказов
│   └── receipt.html / receipt_email.html
└── static/                 # uploads/, manifest.json, sw.js
```

---

## 4. ВАЖНЫЕ ПАТТЕРНЫ И ПОДВОДНЫЕ КАМНИ

### 4.1 Jinja2: `namespace` для счётчиков в циклах
`{% set x = x + 1 %}` внутри цикла НЕ меняет внешнюю переменную. Использовать `namespace`:
```jinja2
{% set ns = namespace(count=0) %}
{% for item in items %}
  {% set ns.count = ns.count + 1 %}
{% endfor %}
{{ ns.count }}
```

### 4.2 Jinja2: кастомный фильтр `int`
```python
templates.env.filters["int"] = lambda x: f"{x:,}".replace(",", " ") if x else "0"
```
Этот фильтр возвращает СТРОКУ, не число. `x | int` нельзя использовать в вычислениях (даёт строку). Для арифметики — `| round(0, 'floor')`.

### 4.3 `_audit` и `session.commit()`
`_audit()` вызывает `session.commit()` внутри себя. Поэтому:
- Все изменения ДО `_audit` должны быть уже закоммичены, либо `_audit` закоммитит всё
- `_audit` НЕ вызывать внутри циклов до общего `session.commit()` — будут частичные коммиты
- Уведомления создаются ДО коммита, не после

### 4.4 `date_str` в Attendance
Дата хранится как строка `"YYYY-MM-DD"` (поле `date_str`, не `date`). Сравнения — строковые, без datetime. Это исправляет баги с часовыми поясами.

### 4.5 Мобильная адаптация
- Глобальный CSS в `base.html` (media query max-width:767px)
- Класс `.btn-icon` для компактных иконок в таблицах
- `.hide-mobile` скрывает колонки на телефоне
- Табы заказов: скроллятся горизонтально, короткие названия

---

## 5. Модели БД (текущие)

### Основные
| Модель | Ключевые поля |
|--------|--------------|
| `User` | `username, password_hash, full_name, role_id(FK), inn, position, is_active, last_login` |
| `Role` | `name, permissions(JSON)` |
| `Client` | `full_name, phone, comment` |
| `Service` | `name, price, description` |
| `Part` | `name, article(unique), purchase_price, quantity, min_stock` |
| `Product` | `name, article(unique), color, quantity, image, cost_price, print_cost, pack_cost, variants(JSON)` |
| `Filament` | `name, article, type, color, quantity, min_stock, grams_per_spool, manufacturer` |
| `Printer` | `name(unique)` |

### Заказы
| Модель | Ключевые поля |
|--------|--------------|
| `Order` | `client_id(FK), printer, defect, status, total_price, assigned_to(FK), prepaid, estimated_price, source, order_type, scheduled_at, deadline, is_warranty, is_confirmed` |
| `OrderItem` | `order_id(FK), name, price` |
| `OrderPart` | `order_id(FK), part_id(FK), quantity, price` |

### Печать
| Модель | Ключевые поля |
|--------|--------------|
| `PrintJob` | `name, filament_id(FK), created_by(FK), grams, hours, status(success/fail), waste_grams, printer_name` |

### Посещаемость
| Модель | Ключевые поля |
|--------|--------------|
| `Attendance` | `user_id(FK), date_str(YYYY-MM-DD), check_in, check_out, report` |
| `Schedule` | `user_id(FK), date, time_from, time_to` |

### Прочее
| Модель | Ключевые поля |
|--------|--------------|
| `ChatMessage` | `from_user_id(FK), to_user_id(FK nullable), text` |
| `Task` | `title, description, created_by(FK), assigned_to(FK), status` |
| `Notification` | `user_id(FK), title, text, link, is_read` |
| `AuditLog` | `user_id(FK), user_name, action, entity_type, entity_id, details` |

---

## 6. Ключевые роуты (новые)

### Посещаемость
- `GET /attendance` — страница (чек-ин, месяц, расписание)
- `POST /attendance/check-in` — отметить приход
- `POST /attendance/check-out` — завершить смену (+опциональный report)
- `POST /attendance/edit` — исправить сегодняшнее время
- `POST /attendance/cancel` — отменить ошибочный check-in
- `POST /attendance/{id}/admin-edit` — админ правит любую запись (использует `date_str` записи)

### Чат
- `GET /chat?peer=0` — общий чат
- `GET /chat?peer={user_id}` — личные сообщения
- `POST /chat/send` — отправить (`to_user_id=0` = общий)

### Товары (склад)
- `POST /products/receive` — приход (qty может быть 0 — регистрация без движения)
- `POST /products/supply` — поставка (batch out: выбор товаров, Ozon/WB/Розница)
- `POST /products/{id}/edit` — article, cost_price, print_cost, pack_cost
- `POST /products/{id}/save-variants` — сохранить JSON вариантов наборов
- `GET /export/products-weekly` — отчёт за неделю
- `GET /export/products-monthly` — отчёт за месяц

### Пластик
- `POST /filaments` — создать (автоартикул `FIL-XXXX`)
- `GET /api/filaments/next-article` — API для автоартикула
- `POST /filaments/receive` — приход (JSON batch)
- `POST /filaments/expense` — расход
- `POST /filaments/{id}/edit` — теперь можно менять type

### Печать
- `POST /prints` — создать (принимает `printer_name`)
- `POST /prints/{id}/edit` — редактировать (корректировка пластика)
- `POST /prints/{id}/result` — отметить успех/брак + waste_grams
- `POST /printers/add` — добавить принтер
- `POST /printers/{pid}/delete` — удалить принтер

### Заказы (новые поля)
- `prepaid` — предоплата
- `estimated_price` — оценка стоимости
- `source` — источник клиента (Профи.ру, Авито, Сарафанка, Другое)

### Аудит
- `GET /audit` — фильтры по action, user_id; пагинация 50
- Каждое действие автоматически создаёт уведомление всем (через `_audit → _notify_all`)

---

## 7. Шпаргалка по шаблонам

### base.html sidebar:
```
Главная, Клиенты, Услуги, Заказы, Склад запчастей, Склад товаров,
Пластик, Печать, Посещаемость, Расписание, Задачи, Чат,
Пользователи*, Аудит*  (* = только admin)
```

### Глобальные JS-переменные в шаблонах:
- `FILAMENTS` — в filaments.html
- `PDATA` — в products.html (products_data из контекста)
- `UDATA`, `RDATA` — в users.html

### CSS-классы:
- `.btn-icon` — компактная иконка без отступов (мобильные)
- `.hide-mobile` — скрыто на мобильных
- `.clickable` — курсор pointer + hover
- `.text-truncate-cell` — обрезка текста с `...`

---

## 8. Что НЕ делать

- ❌ НЕ добавлять комментарии без явной просьбы
- ❌ НЕ создавать SPA/React — проект SSR
- ❌ НЕ добавлять npm/webpack — CDN
- ❌ НЕ использовать `{% set x = x + 1 %}` в циклах Jinja2 — только `namespace`
- ❌ НЕ использовать фильтр `| int` в арифметике — он возвращает строку
- ❌ НЕ коммитить `*.db`, `.env`, `arial.ttf`
- ❌ НЕ вызывать `_audit` внутри циклов до общего `session.commit()`
- ❌ НЕ трогать БД без явной команды пользователя
