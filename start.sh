#!/bin/bash

# Configura Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Verifica dependências
echo "=== Dependências verificadas ==="
google-chrome --version || exit 1
chromedriver --version || exit 1
python --version || exit 1

# Configura variáveis críticas
export SELENIUM_DISABLE_MANAGER=1
export PATH=$PATH:/home/appuser/.local/bin

# Inicia a aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -