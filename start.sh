#!/bin/bash

# Configura Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Verifica versões instaladas
echo "=== Versões instaladas ==="
google-chrome --version || { echo "Chrome não instalado corretamente"; exit 1; }
chromedriver --version || { echo "ChromeDriver não instalado corretamente"; exit 1; }

# Configura variáveis críticas
export SELENIUM_DISABLE_MANAGER=1
export PATH=$PATH:/home/appuser/.local/bin

# Inicia a aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level debug