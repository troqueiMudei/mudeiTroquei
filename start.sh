#!/bin/bash

# Verificar dependências
echo "=== Verificando dependências ==="
google-chrome --version || exit 1
chromedriver --version || exit 1

# Configurar Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Iniciar aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level info