# База с уже установленным Chromium + всеми системными зависимостями для headless-рендера —
# первый сервис в репозитории, которому нужен настоящий браузер (PDF = печать React-страницы).
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8012", "--reload"]
