FROM python:3.13-slim

# Минимальные системные пакеты для сетевых запросов и сборки wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала зависимости: ускоряет кэш Docker-слоев.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Затем код проекта.
COPY . /app

# Порт Django dev-server.
EXPOSE 8000

# По умолчанию запускаем веб-приложение.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
