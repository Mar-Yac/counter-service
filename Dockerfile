FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd -r app && useradd -r -g app app \
    && mkdir -p /app \
    && chown -R app:app /app

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . /app
RUN chown -R app:app /app

USER app

EXPOSE 8000

# Use Gunicorn as the WSGI server
CMD ["gunicorn", "--config", "config/gunicorn.conf.py", "wsgi:application"]
