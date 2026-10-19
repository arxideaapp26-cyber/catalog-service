FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

COPY app ./app

USER app
EXPOSE 8080

CMD ["python", "-m", "app.main"]
