# Dockerfile
FROM python:3.10-slim

# Configuração de variáveis de ambiente
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Sao_Paulo
ENV CHROMEDRIVER_VERSION=121.0.6167.85

# Configurações do Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/lib/google-chrome
ENV PYTHONPATH=/app
ENV DISPLAY=:99
ENV CHROME_DRIVER_PATH=/usr/local/bin/chromedriver
ENV CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-dev-shm-usage --disable-software-rasterizer --disable-features=VizDisplayCompositor --memory-pressure-off"

# Configurar timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Criar diretórios necessários com permissões adequadas
RUN mkdir -p /etc/sysctl.d /var/run/chrome /data /dev/shm /tmp/chrome && \
    chmod 1777 /dev/shm && \
    chmod 777 /tmp/chrome

# Instalar dependências do sistema (reduzidas ao mínimo necessário)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    xvfb \
    libnss3 \
    libgconf-2-4 \
    default-libmysqlclient-dev \
    default-mysql-client \
    libglib2.0-0 \
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
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário chrome com limites de recursos
RUN useradd -m -s /bin/bash chrome_user && \
    echo "chrome_user soft nproc 1024" >> /etc/security/limits.conf && \
    echo "chrome_user hard nproc 2048" >> /etc/security/limits.conf && \
    echo "chrome_user soft nofile 65536" >> /etc/security/limits.conf && \
    echo "chrome_user hard nofile 65536" >> /etc/security/limits.conf

# Instalar Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-archive-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver
RUN wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /tmp/ && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 && \
    chmod 755 /usr/local/bin/chromedriver

# Configurar ambiente Python
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R chrome_user:chrome_user /app

USER chrome_user

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]

# start.sh
#!/bin/bash
set -e

# Limpar processos antigos
pkill -9 chrome || true
pkill -9 Xvfb || true
pkill -9 chromedriver || true

# Configurar limites de sistema
ulimit -n 65536
ulimit -u 2048

# Limpar arquivos temporários
rm -rf /tmp/chrome_cache/* || true
rm -rf /tmp/.com.google.Chrome.* || true

# Iniciar Xvfb com configurações otimizadas
Xvfb :99 -screen 0 1024x768x16 -ac +extension RANDR > /dev/null 2>&1 &
sleep 2

# Aguardar MySQL (com timeout reduzido)
MAX_TRIES=15
TRIES=0
while ! mysqladmin ping -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent && [ $TRIES -lt $MAX_TRIES ]; do
    echo "Tentando conectar ao MySQL... ($((TRIES++))/$MAX_TRIES)"
    sleep 2
done

if [ $TRIES -eq $MAX_TRIES ]; then
    echo "Não foi possível conectar ao MySQL após $MAX_TRIES tentativas"
    exit 1
fi

# Iniciar aplicação com configurações otimizadas
exec gunicorn --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    app:app