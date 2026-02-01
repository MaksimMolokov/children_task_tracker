#!/bin/bash
# Запустить ЭТОТ скрипт НА СЕРВЕРЕ (после ssh root@200.234.239.58).
# Он создаст server-update.sh в ~/children_task_tracker и сразу запустит его.

set -e
cd ~/children_task_tracker || { echo "Нет директории ~/children_task_tracker"; exit 1; }

cat > server-update.sh << 'SCRIPT'
#!/bin/bash
set -e
PROJECT_DIR="${PROJECT_DIR:-$HOME/children_task_tracker}"
cd "$PROJECT_DIR" || { echo "Ошибка: директория $PROJECT_DIR не найдена."; exit 1; }
echo "=== Обновление и перезапуск бота ==="
echo "Директория: $PWD"
echo ""
echo "Обновляю код из репозитория..."
git fetch origin
git pull origin main || git pull origin master || true
echo ""
echo "Пересобираю и перезапускаю контейнеры..."
docker-compose up -d --build
echo ""
echo "Жду запуска PostgreSQL..."
sleep 5
echo "Применяю миграции БД..."
docker-compose exec -T bot python -m alembic upgrade head || echo "(миграции уже применены или ошибка)"
echo ""
echo "Статус контейнеров:"
docker-compose ps
echo ""
echo "=== Готово ==="
echo "Логи: docker-compose logs -f bot"
echo ""
echo "Если удалили себя из админов: в .env должен быть ADMIN_TELEGRAM_ID=ваш_telegram_id"
SCRIPT

chmod +x server-update.sh
echo "Скрипт создан. Запускаю..."
./server-update.sh
