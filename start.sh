#!/bin/bash

# Configurações de ambiente
set -eo pipefail

# Função para log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Verificação de dependências
log "Verificando dependências..."
check_dep() {
    if ! command -v $1 >/dev/null 2>&1; then
        log "ERRO: $1 não encontrado no PATH"
        exit 1
    fi
    log "$1 encontrado: $(which $1)"
}

check_dep "google-chrome"
check_dep "chromedriver"
check_dep "python"
check_dep "gunicorn"

# 2. Configuração do Xvfb
log "Configurando Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# 3. Configuração do ChromeDriver
log "Configurando ambiente Selenium..."
export CHROME_BIN="/usr/bin/google-chrome"
export CHROMEDRIVER_PATH="/usr/bin/chromedriver"
export WEBDRIVER_CHROME_OPTIONS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless"

# 4. Teste do ChromeDriver
log "Testando ChromeDriver..."
python -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.binary_location = '/usr/bin/google-chrome'
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--remote-debugging-port=9222')

try:
    driver = webdriver.Chrome(options=options)
    driver.get('https://www.google.com')
    print('✅ ChromeDriver testado com sucesso')
    driver.quit()
except Exception as e:
    print(f'❌ Falha no ChromeDriver: {e}')
    raise
"

# 5. Inicialização do Gunicorn
log "Iniciando aplicação..."
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -