# AdsGen 2.0 - Worker-Based Microservices Platform

Система автоматической генерации объявлений для Avito с использованием AI.

## 🏗️ Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ImportWorker│ ─→ │TextGenWorker│ ─→ │ImageGenWorker│
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                    ┌─────────────┐     ┌──────▼──────┐
                    │PublisherWorker│ ←─ │ValidationWorker│
                    └─────────────┘     └─────────────┘
```

## 🚀 Быстрый старт

### 1. Настройка окружения

```bash
# Скопируйте пример конфигурации
copy .env.example .env

# Заполните API ключи в .env
```

### 2. Запуск всех сервисов

```bash
docker-compose up -d
```

### 3. Проверка состояния

- **API**: http://localhost:8000/docs
- **Flower (мониторинг)**: http://localhost:5555
- **PostgreSQL**: localhost:5432

## 📊 Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/import/csv` | POST | Импорт из CSV файла |
| `/import/excel` | POST | Импорт из Excel файла |
| `/import/google-sheets` | POST | Импорт из Google Таблиц |
| `/generate/text/{id}` | POST | Генерация текста для вакансии |
| `/generate/image/{id}` | POST | Генерация картинки |
| `/generate/batch` | POST | Пакетная генерация |
| `/validate/{id}` | POST | Валидация контента |
| `/publish/xml` | POST | Экспорт в XML для Avito |
| `/vacancies` | GET | Список вакансий |
| `/tasks/{id}` | GET | Статус задачи |

## 🛠️ Технологии

- **Backend**: Python 3.12 + FastAPI
- **Task Queue**: Celery + Redis
- **Database**: PostgreSQL
- **AI Text**: DeepSeek API
- **AI Image**: ComfyUI
- **Storage**: Yandex Disk
- **Container**: Docker Compose

## 📁 Структура проекта

```
services/
├── api/                 # FastAPI gateway
├── import_worker/       # Импорт данных
├── textgen_worker/      # Генерация текста
├── imagegen_worker/     # Генерация картинок
├── validation_worker/   # Валидация Avito
├── publisher_worker/    # Экспорт XML
├── notification_worker/ # Уведомления (опц.)
└── shared/              # Общие модули
    ├── models/          # SQLAlchemy модели
    ├── schemas/         # Pydantic схемы
    ├── config.py        # Конфигурация
    ├── database.py      # Подключение к БД
    ├── celery_app.py    # Celery настройки
    └── mappings.py      # Маппинг должностей
```

## 🔧 Настройка переменных окружения

| Переменная | Описание |
|------------|----------|
| `DEEPSEEK_API_KEY` | API ключ DeepSeek |
| `COMFYUI_URL` | URL сервера ComfyUI |
| `YANDEX_DISK_TOKEN` | OAuth токен Yandex Disk |
| `GOOGLE_CREDENTIALS_JSON` | Base64-encoded Google SA JSON |

## 📝 Миграция с Google Apps Script

Этот проект — полная миграция логики из:
- `avito-vacancies-v3.gs` → TextGenWorker, ImageGenWorker
- `importData.gs` → ImportWorker
- `genXML.gs` → PublisherWorker
- `templates.gs` → shared/mappings.py, textgen_worker/prompts.py

### Легаси скрипты

Оригинальные GAS файлы сохранены в папке `legacy/` для справки.

## 🧪 Разработка

```bash
# Запуск только инфраструктуры
docker-compose up -d postgres redis flower

# Локальный запуск API
cd services/api
pip install -r requirements.txt
uvicorn main:app --reload
```

## 📄 Лицензия

Proprietary - АдсГен
