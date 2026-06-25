# CRM — 3D мастерская

## Описание проекта
CRM-система для управления 3D мастерской (ремонт и 3D печать). Работает на FastAPI + SQLite + vanilla JS (SPA в одном HTML-файле). Развёрнута на VPS.

## Архитектура
- **Backend**: Python FastAPI, SQLAlchemy ORM, SQLite
- **Frontend**: Bootstrap 5 (inline CSS), vanilla JS, Chart.js
- **Сервер**: uvicorn, запуск через nohup
- **БД**: `crm.db` (SQLite)

## Структура файлов
```
crm/
├── app/
│   ├── main.py              # Точка входа FastAPI, seed данных
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # Все ORM-модели
│   ├── schemas.py           # Pydantic схемы (клиенты, услуги, заказы)
│   ├── auth.py              # JWT, хеширование паролей, get_current_user
│   ├── audit.py             # Хелпер для логирования действий
│   ├── routes_*.py          # Роуты для каждого модуля
│   ├── static/
│   │   ├── index.html       # SPA — весь клиентский код
│   │   ├── login.html       # Страница входа
│   │   └── bootstrap.min.css
│   └── uploads/             # Загруженные фото товаров
├── crm.db                   # SQLite БД
├── venv/                    # Python virtualenv
└── requirements.txt
```

## Модели
- **User** — пользователь (username, hashed_password, role_id, full_name, is_active)
- **Role** — роль с правами: can_view_clients, can_edit_clients, can_view_services, can_edit_services, can_view_orders, can_edit_orders, can_delete_orders, can_manage_users, can_view_reports, can_edit_reports, can_view_warehouse, can_edit_warehouse, can_assign_tasks
- **Client** — клиент (full_name, phone)
- **Service** — услуга (name, price, category: repair/print)
- **Order** — заказ (client_id, order_type: repair/print, status: active/done/delivered, с полным описанием и услугами)
- **OrderItem** — услуга в заказе (service_id, custom_name для ручных услуг, quantity, price)
- **Task** — задача для сотрудника (name, price, unit, admin_controlled)
- **WorkReport** — отчёт сотрудника о выполненной работе (task_id, quantity)
- **Attendance** — отметка о приходе/уходе
- **Schedule** — расписание сотрудника
- **Lead** — заявка с сайта
- **Product** — товар на складе (name, color, article, quantity, image)
- **StockMovement** — движение товара (supply/write-off, reason: пополнение/ozon/wb/другое)
- **OrderTemplate** — шаблон заказа (для быстрого заполнения)
- **OrderComment** — комментарий к заказу
- **OrderLog** — лог изменений заказа
- **TaskAssignment** — задание сотруднику (title, description, assigned_to, status: new/in_progress/done)
- **AuditLog** — лог всех действий пользователей

## Функционал по разделам

### 📊 Панель управления (tab-dashboard)
- Статистика: заказы в работе, кто на работе, клиенты
- Быстрые действия: отметиться, уйти, переходы по разделам
- Мои последние задания
- Последние товары на складе

### 👥 Клиенты (tab-clients)
- Список клиентов карточками, поиск, добавление, редактирование, удаление
- История заказов клиента при просмотре/редактировании

### 📨 Заявки (tab-leads)
- Заявки с сайта, управление статусами (новая/связались/конвертирован/закрыта)

### 📋 Заказы
- **Канбан (tab-kanban)** — три колонки: В работе / Сделано / Выдано, перетаскивание карточек
- **Ремонт (tab-repair)** — активные заказы ремонта карточками
- **3D Печать (tab-print)** — активные заказы печати
- **Выполненные (tab-archive)** — выданные заказы, можно вернуть в работу

### 🛠️ Услуги (tab-services)
- Справочник услуг с ценой и категорией

### 📦 Склад (tab-warehouse)
- Товары карточками (как маркетплейс), фото, цвет, артикул
- Пополнение и списание (Ozon/WB/Другое)
- История движений
- Поиск, сортировка по названию/количеству
- Лимит остатка с подсветкой "мало"
- Excel-экспорт

### 🧮 Калькулятор (tab-calc)
- Расчёт стоимости заказа по услугам

### 👤 Сотрудники
- **📌 Задачи (tab-tasks)** — справочник работ с ценой/единицей
- **📋 Задания (tab-assignments)** — назначенные задания, смена статуса
- **📝 Мои работы (tab-my-reports)** — отчёты о выполненной работе
- **⏱️ Явка (tab-attendance)** — отметка прихода/ухода с отчётом за смену
- **🗓️ Расписание (tab-schedule)** — график работы с календарём
- **📊 Отчёты (tab-reports)** — отчёты всех сотрудников (админ/право can_view_reports)
- **⏱️ Все явки / 🗓️ Все графики / 💰 Зарплата** — админские отчёты

### 🔐 Доступ (tab-users)
- Управление пользователями и ролями с правами

### 📋 Журнал (tab-logs)
- Все действия пользователей

## Ключевые особенности
- **Дашборд настраивается** remove/add blocks via ✎ Настроить
- **Быстрый доступ** — настраиваемые кнопки перехода по разделам
- **Ручные услуги** в заказах (custom_name + цена)
- **Шаблоны заказов** — быстрое заполнение
- **Права доступа** через роли (гибкая настройка)
- **Уведомления браузера** о малом остатке и новых заявках
- **Автообновление** данных на дашборде

## Авторизация
- JWT токен, срок 30 дней
- Хранится в localStorage
- При 401 — редирект на /login
- Стандартный админ: admin / admin123

## Команды для сервера
```bash
# Перезапуск
cd /root/crmlite && git pull && pkill -9 -f uvicorn && sleep 1 && source venv/bin/activate && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &

# Добавление колонок в БД (при новых миграциях)
python3 -c "
import sqlite3
c = sqlite3.connect('crm.db')
for col in ['can_assign_tasks']:  # менять на нужные колонки
    try:
        c.execute(f'ALTER TABLE roles ADD COLUMN {col} BOOLEAN DEFAULT 0')
        c.commit()
        print(f'column {col} added')
    except Exception as e:
        print(f'{col}: {e}')
c.commit(); c.close()
"
```
