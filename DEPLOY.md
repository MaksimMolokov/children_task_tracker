# Деплой на сервер

## Быстрый деплой

Подключитесь к серверу и выполните:

```bash
# 1. Подключение к серверу
ssh user@200.234.239.58

# 2. Переход в нужную директорию (например, домашнюю)
cd ~

# 3. Создание директории и клонирование репозитория
mkdir -p children_task_tracker
cd children_task_tracker
git clone https://github.com/MaksimMolokov/children_task_tracker.git .

# 4. Создание и настройка .env
cp .env.example .env
nano .env   # Укажите BOT_TOKEN и ADMIN_TELEGRAM_ID

# 5. Запуск через Docker
docker-compose up -d --build

# 6. Применение миграций (подождите 5–10 сек после запуска postgres)
sleep 10
docker-compose exec bot python -m alembic upgrade head
```

## Через скрипт deploy.sh

```bash
ssh user@200.234.239.58
# Скачайте скрипт или скопируйте содержимое deploy.sh, затем:
chmod +x deploy.sh
./deploy.sh
```

## Требования на сервере

- Docker и Docker Compose
- Git

Установка Docker (если нет):
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Выйдите и зайдите заново для применения группы
```

## Обновление бота

```bash
cd ~/children_task_tracker
git pull origin main
docker-compose up -d --build
docker-compose exec bot python -m alembic upgrade head
```

## Проверка работы

```bash
cd ~/children_task_tracker
docker-compose ps          # Статус контейнеров
docker-compose logs -f bot # Логи бота
```
