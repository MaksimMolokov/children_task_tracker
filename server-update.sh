#!/bin/bash
# =============================================================================
# Единый скрипт обновления проекта на сервере
# Репозиторий: https://github.com/MaksimMolokov/children_task_tracker
# =============================================================================
#
# Использование:
#
#   Вариант 1 — на сервере (после SSH):
#     cd ~/children_task_tracker
#     ./server-update.sh
#
#   Вариант 2 — с локальной машины (скрипт сам зайдёт по SSH):
#     SERVER=root@ВАШ_СЕРВЕР ./server-update.sh
#
#   Вариант 3 — другая директория на сервере:
#     PROJECT_DIR=/opt/children_task_tracker ./server-update.sh
#
# После обновления: если вы удалили себя из админов, в .env на сервере
# должен быть ADMIN_TELEGRAM_ID=ваш_telegram_id — бот вернёт вас в админы при старте.
# =============================================================================

set -e

PROJECT_DIR="${PROJECT_DIR:-$HOME/children_task_tracker}"
SERVER="${SERVER:-}"

if command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

do_update() {
    cd "$PROJECT_DIR" || { echo "Ошибка: директория $PROJECT_DIR не найдена."; exit 1; }
    echo "=== Обновление проекта children_task_tracker ==="
    echo "Директория: $PWD"
    echo ""

    echo "[1/5] Обновляю код из GitHub..."
    git fetch origin
    if [ -f server-update.sh ] && ! git ls-files --error-unmatch server-update.sh &>/dev/null; then
        rm -f server-update.sh
    fi
    git pull origin main || git pull origin master || true
    echo ""

    echo "[2/5] Останавливаю контейнеры..."
    $DOCKER_COMPOSE down 2>/dev/null || true
    echo ""

    echo "[3/5] Сборка и запуск контейнеров..."
    $DOCKER_COMPOSE up -d --build
    echo ""

    echo "[4/5] Ожидание запуска PostgreSQL (5 сек)..."
    sleep 5
    echo "Применяю миграции БД..."
    $DOCKER_COMPOSE exec -T bot python -m alembic upgrade head 2>/dev/null || echo "(миграции уже применены или контейнер ещё не готов)"
    echo ""

    echo "[5/5] Статус контейнеров:"
    $DOCKER_COMPOSE ps
    echo ""
    echo "=== Готово ==="
    echo ""
    echo "Полезные команды:"
    echo "  Логи бота:    $DOCKER_COMPOSE logs -f bot"
    echo "  Логи всех:    $DOCKER_COMPOSE logs -f"
    echo "  Остановить:   $DOCKER_COMPOSE down"
    echo ""
}

if [ -n "$SERVER" ]; then
    echo "Подключение к серверу $SERVER..."
    ssh "$SERVER" "PROJECT_DIR=\${PROJECT_DIR:-\$HOME/children_task_tracker} bash -s" < "$0"
else
    do_update
fi
exit 0
