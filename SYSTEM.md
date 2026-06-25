# CRM — 3D мастерская

## Описание проекта
CRM-система для управления 3D мастерской (ремонт и 3D печать). FastAPI + SQLite + vanilla JS (SPA в одном HTML-файле). Развёрнута на VPS.

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
├── requirements.txt
└── SYSTEM.md                # Этот файл — описание для нейросети
```

## Модели
- **User** — пользователь (username, hashed_password, role_id, full_name, is_active)
- **Role** — роль с правами: can_view_clients, can_edit_clients, can_view_services, can_edit_services, can_view_orders, can_edit_orders, can_delete_orders, can_manage_users, can_view_reports, can_edit_reports, can_view_warehouse, can_edit_warehouse, can_assign_tasks
- **Client** — клиент (full_name, phone)
- **Service** — услуга (name, price, category: repair/print)
- **Order** — заказ (client_id, order_type: repair/print, status: active/done/delivered)
- **OrderItem** — услуга в заказе (service_id, custom_name для ручных услуг, quantity, price)
- **Task** — задача для сотрудника (name, price, unit, admin_controlled)
- **WorkReport** — отчёт сотрудника (task_id, quantity)
- **Attendance** — отметка о приходе/уходе
- **Schedule** — расписание сотрудника
- **Lead** — заявка с сайта
- **Product** — товар на складе (name, color, article, quantity, image)
- **StockMovement** — движение товара (supply/write-off, reason: пополнение/ozon/wb/другое)
- **OrderTemplate** — шаблон заказа
- **OrderComment** — комментарий к заказу
- **OrderLog** — лог изменений заказа
- **TaskAssignment** — задание сотруднику (title, description, assigned_to, status: new/in_progress/done)
- **AuditLog** — лог всех действий

## Функционал по разделам (вкладки/табы)

| Таб | id | Описание |
|-----|-----|---------|
| 📊 Панель | tab-dashboard | Статистика, быстрые действия, задания, склад |
| 👥 Клиенты | tab-clients | Карточки клиентов, поиск, история заказов |
| 📨 Заявки | tab-leads | Заявки с сайта, смена статуса |
| 📋 Канбан | tab-kanban | Drag-n-drop колонки: В работе/Сделано/Выдано |
| 🔧 Ремонт | tab-repair | Активные заказы ремонта карточками |
| 🖨️ 3D Печать | tab-print | Активные заказы печати |
| 📦 Выполненные | tab-archive | Выданные, кнопка "Вернуть в работу" |
| 🛠️ Услуги | tab-services | Справочник услуг |
| 📦 Склад | tab-warehouse | Товары карточками, движения, поиск, лимит, Excel |
| 🧮 Калькулятор | tab-calc | Расчёт стоимости |
| 📌 Задачи | tab-tasks | Справочник работ (цена/единица) |
| 📋 Задания | tab-assignments | Назначенные задания, статусы |
| 📝 Мои работы | tab-my-reports | Отчёты сотрудника |
| ⏱️ Явка | tab-attendance | Приход/уход с отчётом |
| 🗓️ Расписание | tab-schedule | График работы календарём |
| 📊 Отчёты | tab-reports | Все отчёты (админ + can_view_reports) |
| ⏱️ Все явки | tab-all-attendance | Админ |
| 🗓️ Все графики | tab-all-schedule | Админ |
| 💰 Зарплата | tab-summary | Сводка доходов |
| 🔐 Доступ | tab-users | Пользователи + роли с правами |
| 📋 Журнал | tab-logs | Логи всех действий |

## Ключевые особенности
- Дашборд настраивается через ✎ Настроить
- Быстрый доступ — настраиваемые кнопки перехода
- Ручные услуги в заказах (custom_name + цена)
- Шаблоны заказов для быстрого заполнения
- Права доступа через роли (гибкая настройка)
- Уведомления браузера о малом остатке и новых заявках
- Автообновление данных на дашборде

## Авторизация
- JWT токен, 30 дней
- Хранится в localStorage
- При 401 — редирект на /login
- Админ: admin / admin123

## Команды для сервера
```bash
cd /root/crmlite && git pull && pkill -9 -f uvicorn && sleep 1 && source venv/bin/activate && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > crm.log 2>&1 &
```

## Миграции БД
```bash
python3 -c "
import sqlite3
c = sqlite3.connect('crm.db')
for col in ['can_assign_tasks']:
    try:
        c.execute(f'ALTER TABLE roles ADD COLUMN {col} BOOLEAN DEFAULT 0')
        c.commit()
        print(f'column {col} added')
    except Exception as e:
        print(f'{col}: {e}')
c.commit(); c.close()
"
```
