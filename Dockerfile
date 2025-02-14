# Usa uma imagem que já tem suporte ao MySQL
FROM python:3.10-slim

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia o requirements.txt primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto dos arquivos do projeto
COPY . .

# Expõe a porta
EXPOSE 8000

# Comando para iniciar o app
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]