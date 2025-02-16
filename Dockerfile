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

# Configurações do sistema
RUN echo "kernel.unprivileged_userns_clone=1" > /etc/sysctl.d/00-local-userns.conf && \
    echo "user.max_user_namespaces=10000" > /etc/sysctl.d/10-user-ns.conf

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    unzip \
    xvfb \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxss1 \
    libasound2 \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    python3-dev \
    default-mysql-client \
    curl \
    libglib2.0-0 \
    libnss3 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    xdg-utils \
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
    && rm -rf /var/lib/apt/lists/*

# Criar usuário chrome
RUN useradd -m -s /bin/bash chrome_user

# Instalar Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-archive-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver com versão fixa
RUN wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /tmp/ && \
    mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 && \
    chmod 755 /usr/local/bin/chromedriver

# Configurar diretórios e preferências do Chrome
RUN mkdir -p /home/chrome_user/.config/google-chrome/Default && \
    echo '{ \
        "download_prompt_for_download": false, \
        "download.default_directory": "/tmp/downloads", \
        "browser": { \
            "custom_chrome_frame": false, \
            "show_home_button": false \
        }, \
        "safebrowsing": { \
            "enabled": false \
        } \
    }' > /home/chrome_user/.config/google-chrome/Default/Preferences

# Configurar permissões
RUN chown -R chrome_user:chrome_user /home/chrome_user && \
    chown -R chrome_user:chrome_user /home/chrome_user/.config && \
    chown -R chrome_user:chrome_user /usr/local/bin/chromedriver && \
    chown -R chrome_user:chrome_user /var/run/chrome && \
    chown -R chrome_user:chrome_user /data && \
    chown -R chrome_user:chrome_user /tmp/chrome && \
    chmod -R 777 /tmp/chrome

# Configurar ambiente virtual Python
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Configurar diretório de trabalho
WORKDIR /app

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY . .
RUN chown -R chrome_user:chrome_user /app

# Mudar para usuário não-root
USER chrome_user

# Tornar script de inicialização executável
RUN chmod +x start.sh

# Expor porta
EXPOSE 8000

# Configurar Gunicorn
ENV GUNICORN_CMD_ARGS="--workers=1 --timeout=120 --threads=4 --worker-class=gthread"

# Comando de inicialização
CMD ["./start.sh"]