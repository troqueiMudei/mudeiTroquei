#!/bin/bash

# Configura Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Verifica instalações
echo "=== Verificando dependências ==="
/usr/bin/google-chrome --version || exit 1
/usr/bin/chromedriver --version || exit 1

# Configurações adicionais
export SELENIUM_DISABLE_MANAGER=1

# Inicia a aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level debug