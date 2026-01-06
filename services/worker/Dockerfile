FROM python:3.11-slim

WORKDIR /app

COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/worker/main.py .

CMD ["python", "main.py"]

