FROM python:3.12-slim
WORKDIR /app
COPY app.py tracker.py transport.py products.json ./
COPY connectors ./connectors
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
