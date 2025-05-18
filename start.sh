#!/bin/bash

# Verifica versões
echo "=== Versões instaladas ==="
google-chrome --version
chromedriver --version

# Configura Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Desativa completamente o Selenium Manager
export SELENIUM_DISABLE_MANAGER=1

# Inicia a aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level debug