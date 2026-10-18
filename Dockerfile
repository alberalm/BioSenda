FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt --timeout=120

ENV PORT=8080
EXPOSE 8080

# Run the Flask app through Gunicorn
SHELL ["/bin/sh", "-c"]
CMD exec gunicorn --bind ":$PORT" --workers 1 --threads 2 --timeout 0 -k uvicorn.workers.UvicornWorker app:app
