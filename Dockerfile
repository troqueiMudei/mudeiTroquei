FROM python:3.10-slim

# Configurações de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_PATH=/usr/lib/google-chrome \
    DISPLAY=:99 \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-dev-shm-usage --disable-software-rasterizer --remote-debugging-port=9222" \
    TZ=America/Sao_Paulo \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    FLASK_DEBUG=0

# Configuração de timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instalação de dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg2 \
    unzip \
    xvfb \
    procps \
    fonts-liberation \
    libnss3 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
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
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    libglib2.0-0 \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    python3-dev \
    default-mysql-client \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# Instalação específica do Chrome versão 114
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_114.0.5735.198-1_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/* \
    && google-chrome --version

# Instalação específica do ChromeDriver 114.0.5735.90
RUN wget -q -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip -q /tmp/chromedriver_linux64.zip -d /tmp/ \
    && mv /tmp/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver_linux64.zip \
    && chromedriver --version

# Instalação do ChromeDriver
RUN LATEST_RELEASE=$(curl -sL https://chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && echo "Baixando ChromeDriver versão: ${LATEST_RELEASE}" \
    && wget -q -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/${LATEST_RELEASE}/chromedriver_linux64.zip \
    && unzip -q /tmp/chromedriver_linux64.zip -d /tmp/ \
    && mv /tmp/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver_linux64.zip

# Configuração do usuário e diretórios
RUN useradd -m -s /bin/bash appuser \
    && mkdir -p /home/appuser/Downloads \
    && mkdir -p /app \
    && chown -R appuser:appuser /home/appuser \
    && chown -R appuser:appuser /app

WORKDIR /app

# Instalação de dependências Python
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Cópia dos arquivos da aplicação
COPY --chown=appuser:appuser . .

# Permissões e limpeza
RUN chmod +x start.sh \
    && find /usr/local/lib/python3.10 -type d -name __pycache__ -exec rm -r {} + \
    && rm -rf /tmp/* /var/tmp/*

USER appuser

EXPOSE 8000

CMD ["./start.sh"]