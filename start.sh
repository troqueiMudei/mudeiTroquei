#!/bin/bash

# Configura Xvfb
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
export DISPLAY=:99

# Verifica dependências críticas
echo "=== Verificando dependências ==="
if ! command -v google-chrome &> /dev/null; then
    echo "❌ Chrome não encontrado"
    exit 1
fi

if ! command -v chromedriver &> /dev/null; then
    echo "❌ ChromeDriver não encontrado"
    exit 1
fi

echo "✅ Chrome $(google-chrome --version)"
echo "✅ ChromeDriver $(chromedriver --version)"

# Configura variáveis de ambiente adicionais
export SELENIUM_DISABLE_MANAGER=1

# Inicia a aplicação
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -