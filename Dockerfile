FROM python:3.12-slim AS base

WORKDIR /app

# System deps for psycopg (libpq) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy application source
COPY . .

EXPOSE 8000

CMD ["gunicorn", "nutriplan.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
