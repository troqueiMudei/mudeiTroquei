FROM python:3.10-slim

# Configurações de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROME_VERSION="120.0.6099.109-1" \
    CHROMEDRIVER_VERSION="120.0.6099.109" \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROME_PATH=/usr/lib/google-chrome \
    DISPLAY=:99 \
    CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
    CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-dev-shm-usage --disable-software-rasterizer --remote-debugging-port=9222" \
    TZ=America/Sao_Paulo \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

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
    && rm -rf /var/lib/apt/lists/*

# Instalação do Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable=$CHROME_VERSION \
    && rm -rf /var/lib/apt/lists/*

# Instalação do ChromeDriver
RUN wget -q https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip

# Configuração do usuário e diretórios
RUN useradd -m -s /bin/bash chrome_user \
    && mkdir -p /home/chrome_user/Downloads \
    && mkdir -p /app \
    && chown -R chrome_user:chrome_user /home/chrome_user \
    && chown -R chrome_user:chrome_user /app

# Configuração do workspace e instalação de dependências Python
WORKDIR /app
COPY --chown=chrome_user:chrome_user requirements.txt .

RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Cópia dos arquivos da aplicação
COPY --chown=chrome_user:chrome_user . .

# Permissões e limpeza
RUN chmod +x start.sh \
    && find /usr/local/lib/python3.10 -type d -name __pycache__ -exec rm -r {} + \
    && rm -rf /tmp/* /var/tmp/*

USER chrome_user

EXPOSE 8000

# Configuração do Gunicorn (ajuste conforme necessário)
ENV GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000 --workers=1 --threads=4 --worker-class=gthread --timeout=120 --log-level=info"

CMD ["./start.sh"]