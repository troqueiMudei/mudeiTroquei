# Use uma imagem base mais leve do Python
FROM python:3.10-slim

# Definir variáveis de ambiente
ENV DEBIAN_FRONTEND=noninteractive
ENV CHROME_VERSION="120.0.6099.109-1"
ENV CHROMEDRIVER_VERSION="120.0.6099.109"

# Instalar dependências do sistema, Chrome e MySQL
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
    && rm -rf /var/lib/apt/lists/*

# Instalar o Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver
RUN wget -q "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

# Configurar diretório de trabalho
WORKDIR /app

# Instalar wheel primeiro
RUN pip install --no-cache-dir wheel setuptools --upgrade

# Copiar requirements.txt primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código
COPY . .

# Expor a porta 8000
EXPOSE 8000

# Comando para iniciar a aplicação
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app", "--timeout", "120"]