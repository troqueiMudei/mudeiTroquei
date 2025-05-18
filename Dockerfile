FROM python:3.10-slim

# 1. Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    wget gnupg unzip xvfb \
    fonts-liberation libnss3 libgbm1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Instala Chrome e ChromeDriver
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && google-chrome --version

RUN wget -q https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/ \
    && chmod +x /usr/bin/chromedriver \
    && rm chromedriver_linux64.zip \
    && chromedriver --version

# 3. Configura usuário e diretório
RUN useradd -m appuser && mkdir /app && chown appuser:appuser /app
WORKDIR /app
USER appuser

# 4. Copia APENAS o requirements.txt primeiro
COPY --chown=appuser:appuser requirements.txt .

# 5. Instala dependências Python
RUN pip install --no-cache-dir --user -r requirements.txt

# 6. Copia o restante dos arquivos (incluindo start.sh)
COPY --chown=appuser:appuser . .

# 7. Agora sim, define permissões para o start.sh
RUN chmod +x start.sh

# 8. Ponto de entrada
CMD ["./start.sh"]