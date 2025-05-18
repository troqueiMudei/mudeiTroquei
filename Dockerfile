# Use a imagem base Python oficial
FROM python:3.10-slim

# Configurações de ambiente
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    SELENIUM_DISABLE_MANAGER=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    fonts-liberation \
    libnss3 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Método PRINCIPAL para instalar Chrome - via repositório oficial
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* \
    && google-chrome --version

# Método ALTERNATIVO para instalar Chrome - via download direto (fallback)
RUN if [ ! -f "/usr/bin/google-chrome" ]; then \
    echo "Usando fallback para instalação do Chrome..."; \
    wget -q -O chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
    && apt-get update \
    && apt-get install -y ./chrome.deb \
    && rm chrome.deb \
    && google-chrome --version; \
    fi

# Instalação ROBUSTA do Chromedriver com múltiplos fallbacks
RUN CHROME_MAJOR_VERSION=$(google-chrome --version | awk -F'[ .]' '{print $3}') \
    && echo "Instalando Chromedriver para Chrome versão $CHROME_MAJOR_VERSION" \
    && (wget -q -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$(wget -q -O - https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR_VERSION)/chromedriver_linux64.zip" || \
       wget -q -O /tmp/chromedriver.zip "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_MAJOR_VERSION.0.0/linux64/chromedriver-linux64.zip" || \
       wget -q -O /tmp/chromedriver.zip "https://registry.npmmirror.com/-/binary/chromedriver/$CHROME_MAJOR_VERSION.0.0/chromedriver_linux64.zip") \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver* /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm /tmp/chromedriver.zip \
    && chromedriver --version

# Fallback FINAL - Usa Chromium se tudo mais falhar
RUN if [ ! -f "/usr/bin/chromedriver" ]; then \
    echo "Usando fallback final com Chromium..."; \
    apt-get update && apt-get install -y chromium chromium-driver \
    && ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/lib/chromium/chromedriver /usr/bin/chromedriver \
    && rm -rf /var/lib/apt/lists/* \
    && google-chrome --version \
    && chromedriver --version; \
    fi

# Verificação final das instalações
RUN echo "Verificando instalações:" \
    && ls -la /usr/bin/google-chrome* \
    && ls -la /usr/bin/chromedriver* \
    && google-chrome --version \
    && chromedriver --version

# Cria usuário não-root
RUN useradd -m appuser && mkdir /app && chown appuser:appuser /app
WORKDIR /app
USER appuser

# Instala dependências Python
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copia a aplicação
COPY --chown=appuser:appuser . .

# Configura permissões
RUN chmod +x start.sh

# Ponto de entrada
CMD ["./start.sh"]