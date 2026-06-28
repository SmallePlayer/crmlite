# repair_crm — AI Developer Reference

> **Главное правило**: этот файл читается ИИ-ассистентом в начале каждого нового чата.  
> Он содержит всё необходимое для мгновенного понимания архитектуры проекта.
> Пожалуйста, актуализируй этот файл после любых значительных изменений.

---

## 1. Что это за проект

**CRM-система для мастерской по ремонту 3D-принтеров.**

- Учёт клиентов, заказов, услуг, склада запчастей и товаров
- Посещаемость сотрудников (чек-ин/чекаут), расписание смен
- Задачи (task management) — создание, назначение, выполнение
- Внутренний чат, поиск, экспорт в Excel
- Аудит всех действий

**Стек**: Python 3 + FastAPI + SQLAlchemy 2.0 + SQLite + Jinja2 + Bootstrap 5.3 (CDN)

**Тип приложения**: Server-Side Rendered (SSR). ВСЕ HTML-страницы генерируются на сервере Jinja2.  
JavaScript используется минимально — только для модальных окон Bootstrap, подтверждений удаления, Chart.js на дашборде. **SPA нет.**

**Развёртывание**: одиночный Python-процесс (uvicorn), одна SQLite БД. Статические файлы в `static/`.

---

## 2. Файловая структура

```
repair_crm/
├── main.py                 # ВСЯ логика приложения (~2180 строк) — модели, роуты, middleware, хелперы
├── run.sh                  # Скрипт запуска (detect Rosetta, uvicorn --reload)
├── requirements.txt        # Python-зависимости
├── .env                    # SECRET_KEY, DATABASE_URL, SMTP_*
├── .gitignore              # *.db, *.db-wal, __pycache__, arial.ttf, .env
├── arial.ttf               # Шрифт для PDF-квитанций (Arial Unicode)
├── repair_crm.db           # SQLite база данных (НЕ коммитится)
│
├── templates/              # Jinja2 шаблоны (серверный рендеринг)
│   ├── base.html           # Главный layout: sidebar, search bar, export dropdown, mobile header
│   ├── login.html          # Страница входа
│   ├── error.html          # Страница ошибки (400/403)
│   ├── 404.html            # Страница 404
│   ├── index.html          # Дашборд: карточки, алерты, графики (Chart.js), мои задачи, последние заказы
│   ├── clients.html        # CRUD клиентов (таблица + модальные окна Bootstrap)
│   ├── client_history.html # История заказов конкретного клиента
│   ├── services.html       # CRUD услуг
│   ├── orders.html         # Список заказов: фильтры, вкладки по статусам, пагинация, batch-действия
│   ├── order_create.html   # Форма создания заказа
│   ├── order_detail.html   # Детали заказа: статус-флоу, услуги, запчасти, квитанция
│   ├── warehouse.html      # Склад запчастей: таблица, приход, движения
│   ├── products.html       # Склад товаров: таблица, приход, списание, фото
│   ├── attendance.html     # Посещаемость: чек-ин/аут, обзор месяца (сетка), кто сегодня, расписание
│   ├── chat.html           # Внутренний чат (50 последних сообщений)
│   ├── search.html         # Глобальный поиск по клиентам/заказам/запчастям/товарам/услугам
│   ├── tasks.html          # Задачи: фильтры, создание, отметка «Готово», удаление
│   ├── users.html          # Админ: CRUD пользователей и ролей с правами
│   ├── audit.html          # Админ: лог действий (200 записей)
│   ├── profile.html        # Профиль пользователя: редактирование имени, ИНН, пароля
│   ├── receipt.html        # HTML-квитанция
│   └── receipt_email.html  # HTML-квитанция для email
│
└── static/
    ├── manifest.json        # PWA-манифест
    ├── sw.js                # Service Worker (пустой)
    └── uploads/
        └── .gitkeep         # Папка для загруженных фото товаров
```

---

## 3. Модели базы данных (main.py:61-248)

Все модели используют SQLAlchemy 2.0 Declarative mapping с type-annotations (`Mapped[T]`).

### 3.1 Пользователи и роли

| Модель  | Таблица     | Поля |
|---------|------------|------|
| `User`  | `users`    | `id(PK)`, `username(str,unique)`, `password_hash(str)`, `full_name(str)`, `role_id(FK→roles)`, `role(relationship)`, `inn(str)`, `position(str)`, `is_active(bool)`, `created_at` |
| `Role`  | `roles`    | `id(PK)`, `name(str,unique)`, `permissions(Text→JSON array)`, `created_at` |

**Seed-роли** (main.py:~359):
- `admin` — права `["*"]` (полный доступ)
- `manager` — `manage_clients, manage_services, manage_orders, manage_warehouse, manage_products`
- `worker` — `manage_orders, manage_warehouse, manage_products`

**Доступные пермишены** (`AVAILABLE_PERMISSIONS`, main.py:~1077):
`manage_users`, `manage_clients`, `manage_services`, `manage_orders`, `manage_warehouse`, `manage_products`, `view_audit`

### 3.2 Клиенты, услуги, склад

| Модель | Таблица | Ключевые поля |
|--------|---------|---------------|
| `Client` | `clients` | `id`, `full_name`, `phone`, `comment`, `created_at`, `orders(relationship→Order)` |
| `Service` | `services` | `id`, `name`, `price`, `description`, `created_at` |
| `Part` | `parts` | `id`, `name`, `article(unique)`, `purchase_price`, `quantity`, `min_stock`, `movements(→StockMovement)` |
| `StockMovement` | `stock_movements` | `id`, `part_id(FK)`, `type(in/out)`, `quantity`, `price_per_unit`, `reason`, `order_id(FK→orders,nullable)` |
| `Product` | `products` | `id`, `name`, `article(unique)`, `color`, `quantity`, `image`, `movements(→ProductMovement)` |
| `ProductMovement` | `product_movements` | `id`, `product_id(FK)`, `type(in/out)`, `quantity`, `destination`, `reason` |

### 3.3 Заказы

| Модель | Таблица | Ключевые поля |
|--------|---------|---------------|
| `Order` | `orders` | `id`, `client_id(FK→clients)`, `printer(str)`, `defect(Text)`, `status(str)`, `total_price(float)`, `assigned_to(FK→users,nullable)`, `assignee(relationship→User)`, `created_at`, `closed_at`, `deadline`, `items(→OrderItem)`, `parts(→OrderPart)` |
| `OrderItem` | `order_items` | `id`, `order_id(FK)`, `name(str)`, `price(float)` |
| `OrderPart` | `order_parts` | `id`, `order_id(FK)`, `part_id(FK→parts)`, `quantity(int)`, `price(float)` |

**Статусы заказов** (`ORDER_STATUSES`, main.py:~493):
- `in_progress` → "В работе" (warning)
- `waiting_parts` → "Ожидает запчастей" (info)
- `ready` → "Готов к выдаче" (primary)
- `closed` → "Закрыт" (success)

**Flow переходов** (`ORDER_FLOW`, main.py:~499):
```
in_progress  → waiting_parts, ready, closed
waiting_parts → in_progress, ready, closed
ready        → in_progress, closed
closed       → in_progress  (переоткрытие)
```

### 3.4 Посещаемость и расписание

| Модель | Таблица | Поля |
|--------|---------|------|
| `Attendance` | `attendance` | `id`, `user_id(FK)`, `user(relationship)`, `date(datetime)`, `check_in(datetime)`, `check_out(datetime,nullable)`, `created_at` |
| `Schedule` | `schedules` | `id`, `user_id(FK)`, `user(relationship)`, `date(datetime)`, `time_from(str 5)`, `time_to(str 5)`, `created_at` |

### 3.5 Чат и задачи

| Модель | Таблица | Поля |
|--------|---------|------|
| `ChatMessage` | `chat_messages` | `id`, `from_user_id(FK→users)`, `from_user(relationship)`, `text(Text)`, `created_at` |
| `Task` | `tasks` | `id`, `title(str)`, `description(Text)`, `created_by(FK→users)`, `creator(relationship)`, `assigned_to(FK→users)`, `assignee(relationship)`, `status(str: "pending"/"done")`, `created_at`, `completed_at(datetime,nullable)` |

### 3.6 Аудит

| Модель | Таблица | Поля |
|--------|---------|------|
| `AuditLog` | `audit_logs` | `id`, `user_id(FK,nullable)`, `user_name(str)`, `action(str)`, `entity_type(str)`, `entity_id(int,nullable)`, `details(Text)`, `created_at` |

---

## 4. Полный список роутов

### 4.1 Страницы (GET, возвращают HTML)

| Шаблон | Маршрут | Обработчик | Данные контекста |
|--------|---------|------------|------------------|
| `index.html` | `GET /` | `dashboard()` | `active_orders, closed_orders, total_clients, total_services, total_parts, total_products, low_stock, overdue, due_soon, my_tasks, total_tasks, my_recent_tasks, recent_orders, ORDER_STATUSES, last_backup, backup_days` |
| `login.html` | `GET /login` | `login_page()` | `user: None` |
| `clients.html` | `GET /clients` | `clients_page()` | `clients, clients_data(List[dict])` |
| `client_history.html` | `GET /clients/{client_id}/orders` | `client_history()` | `client, orders, ORDER_STATUSES, timedelta` |
| `services.html` | `GET /services` | `services_page()` | `services, services_data(List[dict])` |
| `warehouse.html` | `GET /warehouse` | `warehouse_page()` | `parts, movements, parts_data(List[dict])` |
| `products.html` | `GET /products` | `products_page()` | `products, movements, products_data(List[dict])` |
| `orders.html` | `GET /orders` | `orders_page()` | `orders, current_status, counts, page, pages, total, date_from, date_to, client_filter` |
| `order_create.html` | `GET /orders/new` | `order_create_page()` | `clients, users` |
| `order_detail.html` | `GET /orders/{order_id}` | `order_detail_page()` | `order, services, parts, ORDER_STATUSES, ORDER_FLOW, now, services_data` |
| `users.html` | `GET /users` | `users_page()` | admin only: `users, roles, user_data, roles_data` |
| `audit.html` | `GET /audit` | `audit_page()` | admin only: `logs` |
| `search.html` | `GET /search?q=` | `search_page()` | `q, results(dict), total` |
| `profile.html` | `GET /profile` | `profile_page()` | `profile` |
| `attendance.html` | `GET /attendance?month=` | `attendance_page()` | `users, base_month, next_month, prev_month, by_user_date, sched_by_user, today_attendance, today, current_user_id, all_schedules, timedelta` |
| `chat.html` | `GET /chat` | `chat_page()` | `messages(reversed), users, current_user_id` |
| `tasks.html` | `GET /tasks?filter=` | `tasks_page()` | `tasks, users, filter, counts` |
| `receipt.html` | `GET /orders/{order_id}/receipt?format=` | `order_receipt()` | format=html: HTML; format=pdf: PDF file |

**УДАЛЁН в 2026-06**: `GET /calendar` (бывшая страница «Календарь ремонтов», удалена вместе с `calendar.html`)

### 4.2 API endpoints (GET, возвращают JSON)

| Маршрут | Описание |
|---------|----------|
| `GET /api/charts/revenue` | Выручка по месяцам (6 мес), для Chart.js на дашборде |
| `GET /api/charts/top-services` | Топ-8 услуг по выручке |
| `GET /api/task-assignments/my` | Задачи текущего пользователя (pending) |
| `GET /api/sse/events` | Stub, возвращает `{"events": []}` |
| `GET /api/dashboard` | Stub, возвращает `{}` |
| `GET /api/warehouse/products` | Stub, возвращает `[]` |

### 4.3 Экспорт (GET, возвращают Excel/DB)

| Маршрут | Описание |
|---------|----------|
| `GET /export/clients` | Excel: все клиенты |
| `GET /export/orders` | Excel: все заказы |
| `GET /export/services` | Excel: все услуги |
| `GET /export/parts` | Excel: все запчасти |
| `GET /export/products` | Excel: все товары |
| `GET /export/db` | SQLite файл БД (admin only) — **кнопка «Скачать БД» на дашборде** |

### 4.4 Auth (POST)

| Маршрут | Описание |
|---------|----------|
| `POST /login` | username, password → JWT cookie (30 дней) |
| `GET /logout` | Удаляет cookie, редирект на /login |

### 4.5 Клиенты (POST)

| Маршрут | Параметры |
|---------|-----------|
| `POST /clients` | `full_name, phone, comment` — создать |
| `POST /clients/{id}/edit` | `full_name, phone, comment` — редактировать |
| `POST /clients/{id}/delete` | Удалить (каскадно удаляет заказы) |

### 4.6 Услуги (POST)

| Маршрут | Параметры |
|---------|-----------|
| `POST /services` | `name, price, description` |
| `POST /services/{id}/edit` | `name, price, description` |
| `POST /services/{id}/delete` | |

### 4.7 Склад запчастей (POST)

| Маршрут | Параметры |
|---------|-----------|
| `POST /warehouse/receive` | JSON array: `[{name, article, purchase_price, quantity}]` |
| `POST /warehouse/{id}/edit` | `name, purchase_price, min_stock` |
| `POST /warehouse/{id}/delete` | |

### 4.8 Склад товаров (POST)

| Маршрут | Параметры |
|---------|-----------|
| `POST /products/receive` | JSON array: `[{name, article, color, quantity}]` |
| `POST /products/{id}/stock-out` | `quantity, destination, reason` |
| `POST /products/{id}/edit` | `name, color` |
| `POST /products/{id}/delete` | |
| `POST /products/{id}/upload-image` | Multipart: `file` |

### 4.9 Заказы (POST)

| Маршрут | Параметры |
|---------|-----------|
| `POST /orders` | `client_id, printer, defect, assigned_to, deadline` |
| `POST /orders/{id}/items` | `name, price` — добавить услугу |
| `POST /orders/{id}/items/{item_id}/delete` | Удалить услугу (пересчитывает total) |
| `POST /orders/{id}/parts` | `part_id, quantity, price` — добавить запчасть (списывает со склада) |
| `POST /orders/{id}/parts/{op_id}/delete` | Удалить запчасть (возвращает на склад) |
| `POST /orders/{id}/close` | Закрыть заказ (ставит closed_at) |
| `POST /orders/{id}/status` | `new_status` — изменить статус (проверяет ORDER_FLOW) |
| `POST /orders/{id}/reopen` | Переоткрыть закрытый заказ |
| `POST /orders/{id}/delete` | Удалить (возврат запчастей на склад) |
| `POST /orders/batch-close` | `ids=1,2,3` — массовое закрытие |
| `POST /orders/batch-delete` | `ids=1,2,3` — массовое удаление |
| `POST /orders/{id}/send-receipt` | `email_to` — отправить квитанцию по SMTP |

### 4.10 Пользователи и роли (POST, admin only)

| Маршрут | Параметры |
|---------|-----------|
| `POST /users/create` | `username, password, full_name, role_id, inn, position` |
| `POST /users/{id}/edit` | `full_name, role_id, inn, position, password` |
| `POST /users/{id}/toggle` | Включить/выключить (нельзя admin) |
| `POST /roles` | `name` + form: `perm_manage_users=1, ...` |
| `POST /roles/{id}/edit` | `name` + form чекбоксы прав (нельзя admin) |
| `POST /roles/{id}/delete` | Нельзя если есть пользователи с этой ролью |

### 4.11 Профиль

| Маршрут | Параметры |
|---------|-----------|
| `POST /profile/edit` | `full_name, inn, position, password` |

### 4.12 Задачи

| Маршрут | Параметры |
|---------|-----------|
| `POST /tasks` | `title, description, assigned_to` — создать |
| `POST /tasks/{id}/done` | Отметить выполненной |
| `POST /tasks/{id}/delete` | Удалить (только автор или admin) |

### 4.13 Посещаемость и расписание

| Маршрут | Параметры |
|---------|-----------|
| `POST /attendance/check-in` | Отметиться (текущий пользователь) |
| `POST /attendance/check-out` | Завершить смену |
| `POST /schedule` | `user_id, date, time_from, time_to` |
| `POST /schedule/{id}/delete` | |

### 4.14 Чат

| Маршрут | Параметры |
|---------|-----------|
| `POST /chat/send` | `text` |

---

## 5. Ключевые функции и константы (main.py)

### 5.1 Auth

| Функция | Строка | Описание |
|---------|--------|----------|
| `_hash_password(pw)` | ~268 | PBKDF2-SHA256, 100k итераций, 16-byte salt |
| `_verify_password(pw, stored)` | ~274 | |
| `_create_token(user_id)` | ~280 | JWT HS256, 30 дней |
| `_get_user_from_request(request)` | ~287 | Извлекает юзера из JWT-куки |

### 5.2 Permissions

| Функция | Описание |
|---------|----------|
| `_has_permission(user, perm)` | `True` если admin ИЛИ perm есть в `user.role.permissions` |
| `_check_perm(request, perm)` | Выбрасывает 403 если нет права |

### 5.3 Helpers

| Функция | Описание |
|---------|----------|
| `_user_context(request)` | Возвращает dict `{user, is_admin, can_manage_users, can_manage_clients, can_manage_orders, can_manage_warehouse, can_manage_products}` |
| `_paginate(session, q, page)` | Пагинация: `(items, page, pages, total)`, PER_PAGE=20 |
| `_recalc_total(session, order_id)` | Пересчитывает `order.total_price` из items + parts |
| `_client_dict(c)` | Сериализует клиента в dict |
| `_audit(action, entity_type, entity_id, details, user, session)` | Запись в AuditLog |

### 5.4 Jinja filters

```python
money  → "1 500 ₽"           # x
dt     → "28.06.2026 15:30"  # x.strftime(...)
int    → "1 500"             # x -> str with spaces
month_ru → "июнь"            # dt.month → название
```

### 5.5 Middleware

`auth_middleware` (main.py:~432): проверяет JWT cookie на каждом запросе, кроме:
- `/login`, `/api/*`, `/static/*`, `/favicon.ico`
- `PUBLIC_PATHS = {"/login", "/api/sse/events", "/api/dashboard", "/api/task-assignments", "/api/warehouse/products"}`

При отсутствии токена → редирект на `/login` (303).

### 5.6 Lifespan

`lifespan()` (main.py:~258): при запуске `create_all()` + `_seed_data()`.  
`_seed_data()` создаёт начальные данные ТОЛЬКО если таблица users пуста.

**Seed-данные**: 4 пользователя, 3 роли, 5 клиентов, 8 услуг, 6 запчастей, 4 товара, 8 задач, движения склада.

---

## 6. Конвенции и паттерны

### 6.1 Структура шаблонов

- **`base.html`** — layout-скелет со sidebar, search bar, export dropdown, mobile header
- Все остальные шаблоны: `{% extends "base.html" %}` + `{% set current_page = "имя" %}`
- `current_page` определяет активный пункт в sidebar
- Контент: `{% block content %}...{% endblock %}`
- Доп. скрипты: `{% block scripts %}...{% endblock %}`

### 6.2 Sidebar (base.html:~74-96)

```python
nav_items = [
    ('index',     '/',           'speedometer2',    'Главная'),
    ('clients',   '/clients',    'people',          'Клиенты'),
    ('services',  '/services',   'tools',           'Услуги'),
    ('orders',    '/orders',     'clipboard-check', 'Заказы'),
    ('warehouse', '/warehouse',  'box-seam',        'Склад запчастей'),
    ('products',  '/products',   'boxes',           'Склад товаров'),
    ('attendance','/attendance', 'person-check',    'Посещаемость'),
    ('tasks',     '/tasks',      'check2-square',   'Задачи'),
    ('chat',      '/chat',       'chat-dots',       'Чат'),
]
# Admin-only (добавляются динамически):
# ('users', '/users', 'shield-lock', 'Пользователи')
# ('audit', '/audit', 'journal-text', 'Аудит')
```

### 6.3 Data serialization pattern

Данные для JavaScript-модалок (редактирование) сериализуются как JSON-переменные в шаблоне:
```html
<script>
const CLIENTS = {{ clients_data | tojson | safe }};
const SERVICES = {{ services_data | tojson | safe }};
const PARTS = {{ parts_data | tojson | safe }};
const PDATA = {{ products_data | tojson | safe }};
const UDATA = {{ user_data | tojson | safe }};
const RDATA = {{ roles_data | tojson | safe }};
const SRV = {{ services_data | tojson | safe }};
</script>
```

### 6.4 Формы и подтверждения

- Все мутации — HTML `<form method="post">`, server-side обработка
- Подтверждение удаления: `data-confirm="Вы уверены?"` на форме — обрабатывается глобальным обработчиком `submit` в `base.html:~138`
- После POST — `RedirectResponse(status_code=303)` (PRG-паттерн)

### 6.5 Пагинация

- `PER_PAGE = 20`
- Функция `_paginate(session, query, page)` — принимает SQLAlchemy Query, возвращает `(items, page, pages, total)`
- Используется только на `/orders` и нигде больше

### 6.6 Уведомления и ошибки

- 400 → `error.html` с `title` и `message`
- 403 → `error.html` с "Доступ запрещён"
- 404 → `404.html`
- Flash-сообщения НЕ используются
- НЕТ клиентских toast-уведомлений

---

## 7. Часто изменяемые места

| Что нужно сделать | Куда смотреть |
|-------------------|---------------|
| Добавить новый пункт меню | `templates/base.html:~74-96` (nav_items) |
| Добавить новую страницу | `main.py` — новый `@app.get()` → создать шаблон в `templates/` |
| Добавить новую модель | `main.py:~60-250` (models section) |
| Добавить API endpoint | `main.py` — в соответствующую секцию |
| Изменить seed-данные | `main.py:_seed_data()` |
| Добавить право доступа | `main.py:AVAILABLE_PERMISSIONS`, `_user_context()`, шаблон `users.html` |
| Изменить sidebar | `templates/base.html` (nav_items + mobile header) |
| Изменить статусы заказов | `main.py:ORDER_STATUSES`, `main.py:ORDER_FLOW` |
| Изменить дашборд | `templates/index.html` + `main.py:dashboard()` |
| Добавить экспорт | `main.py:_make_excel()` + новый `@app.get("/export/...")` + `base.html` dropdown |

---

## 8. Переменные окружения (.env)

```
SECRET_KEY=...           # JWT signing key (обязательно сменить на проде!)
DATABASE_URL=sqlite:///repair_crm.db  # путь к БД
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=...
```

---

## 9. Запуск

```bash
# Локально
cd repair_crm && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Или через скрипт
cd repair_crm && ./run.sh

# На сервере (фон)
cd ~/crmlite/repair_crm && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &

# Сбросить БД (пересоздать с seed-данными)
rm repair_crm/repair_crm.db && restart
```

**Учётные записи по умолчанию** (seed):
| Логин | Пароль | Роль |
|-------|--------|------|
| `admin` | `admin` | Администратор |
| `worker1` | `test1234` | Мастер |
| `worker2` | `test1234` | Мастер |
| `manager1` | `test1234` | Менеджер |

---

## 10. Что НЕ нужно делать

- ❌ НЕ добавлять комментарии в код без явной просьбы
- ❌ НЕ создавать SPA-фронтенд — проект сервер-рендеринговый
- ❌ НЕ добавлять npm/webpack/React — весь CSS/JS через CDN
- ❌ НЕ использовать `cd` в bash-командах — используй параметр `workdir`
- ❌ НЕ коммитить БД-файлы, .env, arial.ttf
- ❌ НЕ менять структуру файлов (всё в main.py — осознанный выбор)
- ❌ НЕ добавлять библиотеки без проверки что их ещё нет в проекте
