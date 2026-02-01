#!/bin/bash
# Перезапуск бота на удалённом сервере (запускать локально — скрипт сам зайдёт по SSH)
# Перед первым запуском: укажите SERVER (например user@200.234.239.58 или алиас из ~/.ssh/config)

set -e

# Укажите ваш сервер: user@host или алиас из ~/.ssh/config
SERVER="${SERVER:-200.234.239.58}"
PROJECT_DIR_ON_SERVER="${PROJECT_DIR_ON_SERVER:-~/children_task_tracker}"

if [ -z "$SERVER" ]; then
    echo "Укажите сервер: SERVER=user@host ./restart-on-server.sh"
    echo "Или отредактируйте переменную SERVER в этом скрипте."
    exit 1
fi

echo "=== Перезапуск бота на сервере $SERVER ==="
ssh "$SERVER" "cd $PROJECT_DIR_ON_SERVER && docker-compose up -d --build && sleep 3 && docker-compose ps"
echo ""
echo "Готово. Логи: ssh $SERVER 'cd $PROJECT_DIR_ON_SERVER && docker-compose logs -f bot'"
