#!/bin/bash
#
# Единый скрипт обновления бота Children Task Tracker на сервере.
# Использование:
#   ./server-update.sh              — обновить бота (запускать из каталога проекта или из домашнего)
#   ./server-update.sh --deploy      — первый деплой: клонировать в ~/children_task_tracker и запустить
#
set -e

REPO_URL="https://github.com/MaksimMolokov/children_task_tracker.git"
DEFAULT_PROJECT_DIR="$HOME/children_task_tracker"

# Определяем каталог проекта
if [ -n "$PROJECT_DIR" ]; then
    PROJECT_DIR="$PROJECT_DIR"
elif [ -f "docker-compose.yml" ] && [ -d ".git" ]; then
    PROJECT_DIR="$(pwd)"
else
    PROJECT_DIR="$DEFAULT_PROJECT_DIR"
fi

DO_DEPLOY=false
[ "$1" = "--deploy" ] && DO_DEPLOY=true

echo "=== Children Task Tracker — обновление на сервере ==="
echo "Каталог проекта: $PROJECT_DIR"
echo ""

# Первый деплой: клонирование
if [ "$DO_DEPLOY" = true ]; then
    if [ -d "$PROJECT_DIR" ]; then
        echo "Каталог $PROJECT_DIR уже существует. Выполняю обычное обновление."
    else
        echo "Клонирую репозиторий в $PROJECT_DIR ..."
        git clone "$REPO_URL" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
        if [ ! -f .env ]; then
            cp .env.example .env
            echo ""
            echo "Создан .env из .env.example. Обязательно отредактируйте:"
            echo "  nano $PROJECT_DIR/.env"
            echo "Укажите BOT_TOKEN и ADMIN_TELEGRAM_ID, затем снова запустите:"
            echo "  $0"
            echo ""
            exit 0
        fi
    fi
fi

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Ошибка: каталог $PROJECT_DIR не найден."
    echo "Для первого деплоя запустите: $0 --deploy"
    exit 1
fi

cd "$PROJECT_DIR"

if [ ! -d ".git" ]; then
    echo "Ошибка: в $PROJECT_DIR нет репозитория Git. Для деплоя с нуля: $0 --deploy"
    exit 1
fi

# Обновление кода
echo "Обновляю код из репозитория..."
git fetch origin
if git show-ref -q refs/heads/main; then
    git checkout main
    git pull origin main
else
    git checkout master 2>/dev/null || true
    git pull origin master 2>/dev/null || git pull origin main
fi

# .env для обычного обновления (если вдруг отсутствует)
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан .env. Отредактируйте его (BOT_TOKEN, ADMIN_TELEGRAM_ID) и при необходимости запустите скрипт снова."
fi

# Только пересборка образов и перезапуск (ничего не удаляем, данные и тома сохраняются)
echo "Пересобираю образы и перезапускаю контейнеры (rebuild)..."
docker-compose up -d --build

# Миграции
echo "Применяю миграции БД..."
sleep 5
docker-compose exec -T bot python -m alembic upgrade head || echo "Миграции уже применены или ошибка (проверьте логи)."

echo ""
echo "=== Готово ==="
echo "Статус контейнеров:"
docker-compose ps
echo ""
echo "Логи бота:  docker-compose logs -f bot"
echo "Логи всех:  docker-compose logs -f"
