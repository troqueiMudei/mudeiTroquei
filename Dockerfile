FROM python:3.10-slim

# Ativa modo debug
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    DEBUG_MODE=1

# Instala dependências de sistema + ferramentas de diagnóstico
RUN apt-get update && apt-get install -y \
    wget gnupg unzip xvfb \
    fonts-liberation libnss3 libgbm1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    curl procps lsof net-tools \
    && rm -rf /var/lib/apt/lists/*

# Instala Chrome via repositório oficial
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && google-chrome --version

# Instala ChromeDriver 114.0.5735.90 (versão estável)
RUN wget -q https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/ \
    && chmod +x /usr/bin/chromedriver \
    && rm chromedriver_linux64.zip \
    && chromedriver --version

# Configura usuário não-root
RUN useradd -m appuser && mkdir /app && chown appuser:appuser /app
WORKDIR /app
USER appuser

# Instala dependências Python
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Garante permissões corretas para o start.sh
RUN chmod +x start.sh

# Copia a aplicação
COPY --chown=appuser:appuser . .

# Copia aplicação
COPY --chown=appuser:appuser . .

# Script de inicialização com diagnóstico
CMD ["sh", "-c", "./start.sh && tail -f /dev/null"]  # Mantém container vivo para inspeção