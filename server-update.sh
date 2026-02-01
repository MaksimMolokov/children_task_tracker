#!/bin/bash
# Единый скрипт: обновление кода и перезапуск бота на сервере.
#
# Вариант 1 — запуск НА СЕРВЕРЕ (после ssh):
#   cd ~/children_task_tracker
#   ./server-update.sh
#
# Вариант 2 — запуск ЛОКАЛЬНО (скрипт сам зайдёт по SSH):
#   SERVER=root@200.234.239.58 ./server-update.sh
#
# Если удалили себя из админов: в .env на сервере должен быть ADMIN_TELEGRAM_ID=ваш_telegram_id.
# После перезапуска бот при старте вернёт этого пользователя в админы.

set -e

PROJECT_DIR="${PROJECT_DIR:-$HOME/children_task_tracker}"
SERVER="${SERVER:-}"

# Docker Compose V2 (docker compose) или V1 (docker-compose)
if command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

do_update() {
    cd "$PROJECT_DIR" || { echo "Ошибка: директория $PROJECT_DIR не найдена."; exit 1; }
    echo "=== Обновление и перезапуск бота ==="
    echo "Директория: $PWD"
    echo ""
    echo "Обновляю код из репозитория..."
    git fetch origin
    # Если server-update.sh создан вручную (не в git), удаляем, чтобы pull подтянул версию из репо
    if [ -f server-update.sh ] && ! git ls-files --error-unmatch server-update.sh &>/dev/null; then
        rm -f server-update.sh
    fi
    git pull origin main || git pull origin master || true
    echo ""
    echo "Пересобираю и перезапускаю контейнеры..."
    $DOCKER_COMPOSE up -d --build
    echo ""
    echo "Жду запуска PostgreSQL..."
    sleep 5
    echo "Применяю миграции БД..."
    $DOCKER_COMPOSE exec -T bot python -m alembic upgrade head || echo "(миграции уже применены или ошибка)"
    echo ""
    echo "Статус контейнеров:"
    $DOCKER_COMPOSE ps
    echo ""
    echo "=== Готово ==="
    echo "Логи бота: $DOCKER_COMPOSE logs -f bot"
    echo ""
    echo "Если вы удалили себя из админов: проверьте, что в .env указан ваш Telegram ID:"
    echo "  ADMIN_TELEGRAM_ID=ваш_telegram_id"
    echo "После перезапуска бот автоматически вернёт этого пользователя в админы."
}

if [ -n "$SERVER" ]; then
    echo "Подключение к серверу $SERVER..."
    # На сервере используем $HOME/children_task_tracker (или PROJECT_DIR_ON_SERVER, если задан)
    ssh "$SERVER" "PROJECT_DIR=\${PROJECT_DIR:-\$HOME/children_task_tracker} bash -s" < "$0"
else
    do_update
fi
exit 0
