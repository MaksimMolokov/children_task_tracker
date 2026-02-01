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

## Обновление бота на сервере

После `git push origin main` зайдите на сервер и выполните:

```bash
ssh root@200.234.239.58
cd ~/children_task_tracker
git pull origin main
./server-update.sh
```

Скрипт `server-update.sh` (лежит в корне репозитория) сам:
- подтягивает код (`git pull`),
- пересобирает и перезапускает контейнеры (`docker-compose up -d --build`),
- применяет миграции БД.

Если скрипта ещё нет (старая копия репозитория), сначала обновите код и сделайте скрипт исполняемым:

```bash
cd ~/children_task_tracker
git pull origin main
chmod +x server-update.sh
./server-update.sh
```

**Если удалили себя из админов:** в `.env` на сервере должен быть ваш Telegram ID: `ADMIN_TELEGRAM_ID=ваш_id`. После перезапуска бот вернёт этого пользователя в админы.

## Проверка работы

```bash
cd ~/children_task_tracker
docker-compose ps          # Статус контейнеров
docker-compose logs -f bot # Логи бота
```
