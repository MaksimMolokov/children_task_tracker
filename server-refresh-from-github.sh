#!/bin/bash
#
# Перезапись проекта с GitHub на сервере и запуск.
# Запускать на сервере (в любой директории). Проект должен быть в ~/children_task_tracker.
#
# Использование:
#   bash server-refresh-from-github.sh
#   ./server-refresh-from-github.sh
#
# Перезаписывает локальные изменения веткой main с GitHub, пересобирает и запускает контейнеры.
#
set -e

REPO_URL="https://github.com/MaksimMolokov/children_task_tracker.git"
PROJECT_DIR="${PROJECT_DIR:-$HOME/children_task_tracker}"

echo "=== Children Task Tracker — перезапись с GitHub и запуск ==="
echo "Директория проекта: $PROJECT_DIR"
echo ""

# Переход в директорию проекта
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Директория не найдена. Клонирую репозиторий..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
else
    cd "$PROJECT_DIR"
    if [ ! -d ".git" ]; then
        echo "Ошибка: в $PROJECT_DIR нет .git. Удалите каталог и запустите скрипт снова для клонирования."
        exit 1
    fi
    echo "Обновляю код из GitHub (перезапись локальных изменений)..."
    git fetch origin
    if git show-ref -q refs/remotes/origin/main; then
        git checkout main
        git reset --hard origin/main
    else
        git checkout master
        git reset --hard origin/master
    fi
    git clean -fd
fi

# .env не трогаем при reset (в .gitignore). Создаём только если нет.
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "Создан .env из .env.example. Отредактируйте его и перезапустите скрипт:"
    echo "  nano $PROJECT_DIR/.env"
    echo "  $0"
    exit 0
fi

# Пересборка и запуск
echo "Пересобираю образы и запускаю контейнеры..."
docker-compose up -d --build

# Миграции
echo "Применяю миграции БД..."
sleep 5
docker-compose exec -T bot python -m alembic upgrade head || echo "Миграции: уже применены или ошибка (проверьте логи)."

echo ""
echo "=== Готово ==="
echo "Статус контейнеров:"
docker-compose ps
echo ""
echo "Логи бота:  docker-compose logs -f bot"
echo "Логи всех:  docker-compose logs -f"
