#!/bin/bash

# =============================================
# START.SH - SCRIPT DE INICIALIZAÇÃO DA APLICAÇÃO
# =============================================

# Configurações básicas
set -e  # Sai imediatamente se qualquer comando falhar

# Função para log formatado
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Verificação de Dependências Críticas
log "Verificando dependências..."
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        log "ERRO: $1 não encontrado no PATH"
        log "PATH atual: $PATH"
        exit 1
    fi
    log "$1 encontrado: $(command -v $1)"
}

check_dependency "google-chrome"
check_dependency "chromedriver"
check_dependency "python"
check_dependency "gunicorn"

# 2. Configuração do Xvfb
log "Iniciando Xvfb..."
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &> /tmp/xvfb.log &
XVFB_PID=$!
export DISPLAY=:99

# Verifica se o Xvfb está rodando
if ! ps -p $XVFB_PID > /dev/null; then
    log "ERRO: Falha ao iniciar Xvfb"
    cat /tmp/xvfb.log
    exit 1
fi
log "Xvfb iniciado com PID: $XVFB_PID"

# 3. Teste do Selenium
log "Realizando teste do Selenium..."
python -c "
from selenium import webdriver
options = webdriver.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
try:
    driver = webdriver.Chrome(options=options)
    print('✅ Selenium funcionando corretamente')
    driver.quit()
except Exception as e:
    print(f'❌ Erro no Selenium: {str(e)}')
    raise
" || exit 1

# 4. Verificação da Aplicação
log "Verificando a aplicação Flask..."
python -c "
from app import app
with app.test_client() as client:
    response = client.get('/')
    assert response.status_code in [200, 302], f'Status code inesperado: {response.status_code}'
print('✅ Aplicação Flask verificada')
" || exit 1

# 5. Inicialização do Gunicorn
log "Iniciando Gunicorn..."
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --preload