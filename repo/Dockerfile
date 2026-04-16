FROM python:3.11-slim

WORKDIR /app

# Install gcc (needed by some Python packages) plus Chromium system dependencies
# We install Chromium deps manually so playwright install works without --with-deps,
# which avoids the ttf-unifont package that is unavailable in Debian Bookworm slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --default-timeout=120 --no-cache-dir -r requirements.txt

# Install Chromium browser only (deps already installed above)
RUN playwright install chromium

COPY . .

RUN mkdir -p /app/data /app/backups

ENV FLASK_APP=app
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:create_app('production')"]
