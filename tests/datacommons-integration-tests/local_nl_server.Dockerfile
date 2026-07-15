FROM python:3.11-slim
RUN pip install --no-cache-dir sentence-transformers google-cloud-spanner
WORKDIR /app
