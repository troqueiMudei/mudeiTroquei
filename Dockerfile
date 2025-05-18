FROM python:3.10-slim

# Environment configuration
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome-stable \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    SELENIUM_DISABLE_MANAGER=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg unzip xvfb \
    fonts-liberation libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libc6 libcairo2 libcups2 libdbus-1-3 libdrm2 libexpat1 \
    libfontconfig1 libgbm1 libgcc1 libglib2.0-0 libgtk-3-0 \
    libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 \
    libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 \
    libxrandr2 libxrender1 libxss1 libxtst6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome (latest stable version)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && google-chrome-stable --version

# Install Chromedriver (versão específica compatível)
# Versão do Chrome: 125.0.6422.141
# Chromedriver correspondente: 125.0.6422.78
RUN wget -q https://chromedriver.storage.googleapis.com/125.0.6422.78/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/ \
    && chmod +x /usr/bin/chromedriver \
    && rm chromedriver_linux64.zip \
    && chromedriver --version

# Create non-root user
RUN useradd -m appuser && mkdir /app && chown appuser:appuser /app
WORKDIR /app
USER appuser

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application
COPY --chown=appuser:appuser . .

# Set execute permission
RUN chmod +x start.sh

# Entry point
CMD ["./start.sh"]