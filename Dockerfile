FROM python:3.10-slim

# Configurações de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome \
    DISPLAY=:99 \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --remote-debugging-port=9222" \
    TZ=America/Sao_Paulo \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    FLASK_DEBUG=0 \
    WDM_PROGRESS_BAR=0

# Instalação de dependências
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg2 \
    unzip \
    xvfb \
    fonts-liberation \
    libnss3 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalação do Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalação do ChromeDriver
RUN CHROME_MAJOR_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1) \
    && CHROMEDRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR_VERSION}) \
    && wget -q https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt \
    && chmod +x start.sh

USER 1000

EXPOSE 8000
CMD ["./start.sh"]