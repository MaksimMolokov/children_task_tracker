#!/bin/bash
# Скрипт деплоя бота Children Task Tracker на сервер
# Запускать на сервере из домашней директории или нужной папки

set -e

REPO_URL="https://github.com/MaksimMolokov/children_task_tracker.git"
PROJECT_DIR="children_task_tracker"

echo "=== Деплой Children Task Tracker ==="

# Создаём директорию и клонируем (или обновляем)
if [ -d "$PROJECT_DIR" ]; then
    echo "Директория $PROJECT_DIR существует. Обновляю репозиторий..."
    cd "$PROJECT_DIR"
    git fetch origin
    git checkout main
    git pull origin main
else
    echo "Клонирую репозиторий..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# Создаём .env если не существует
if [ ! -f .env ]; then
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo ""
    echo "ВАЖНО: Отредактируйте .env и укажите BOT_TOKEN и ADMIN_TELEGRAM_ID!"
    echo "  nano .env"
    echo ""
    read -p "Нажмите Enter после редактирования .env..."
else
    echo ".env уже существует, пропускаю."
fi

# Запускаем Docker
echo "Собираю и запускаю контейнеры..."
docker-compose up -d --build

# Применяем миграции
echo "Применяю миграции БД..."
sleep 5  # Ждём запуска PostgreSQL
docker-compose exec -T bot python -m alembic upgrade head || true

echo ""
echo "=== Деплой завершён ==="
echo "Бот запущен. Проверьте логи: docker-compose logs -f bot"
