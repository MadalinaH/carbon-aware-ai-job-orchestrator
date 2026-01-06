FROM python:3.11-slim

WORKDIR /app

COPY services/scheduler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/scheduler/main.py .
COPY services/scheduler/carbon.py .
COPY policy.yaml /app/policy.yaml

CMD ["python", "main.py"]

