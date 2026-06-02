FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

EXPOSE 8000

CMD ["python", "agent.py"]
