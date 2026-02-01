#!/bin/bash
# Скрипт обновления бота Children Task Tracker на сервере
# Запускать на сервере из директории проекта

set -e

PROJECT_DIR="~/children_task_tracker"

echo "=== Обновление Children Task Tracker ==="

# Переход в директорию проекта
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
else
    echo "Ошибка: директория $PROJECT_DIR не найдена!"
    echo "Убедитесь, что проект находится в правильной директории."
    exit 1
fi

# Обновление кода из репозитория
echo "Обновляю код из репозитория..."
git fetch origin
git checkout main || git checkout master
git pull origin main || git pull origin master

# Пересборка и перезапуск контейнеров
echo "Пересобираю и перезапускаю контейнеры..."
docker-compose down
docker-compose up -d --build

# Применение миграций (если есть новые)
echo "Проверяю и применяю миграции БД..."
sleep 5  # Ждём запуска PostgreSQL
docker-compose exec -T bot python -m alembic upgrade head || echo "Миграции уже применены или ошибка"

# Проверка статуса
echo ""
echo "=== Обновление завершено ==="
echo "Статус контейнеров:"
docker-compose ps

echo ""
echo "Для просмотра логов бота выполните:"
echo "  docker-compose logs -f bot"
