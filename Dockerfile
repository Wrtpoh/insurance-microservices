FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common ./common
COPY client_service ./client_service
COPY product_service ./product_service
COPY policy_service ./policy_service
COPY claim_service ./claim_service
COPY gateway ./gateway

# Приложение выбирается аргументом команды в docker-compose.yml
CMD ["uvicorn", "gateway.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
