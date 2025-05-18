#!/bin/bash

# ========= DIAGNÓSTICO INICIAL =========
echo "=== INÍCIO DO DIAGNÓSTICO ===" > /tmp/startup.log
date >> /tmp/startup.log

# 1. Verifica dependências
echo "1. VERIFICANDO DEPENDÊNCIAS..." >> /tmp/startup.log
{
    echo "Chrome: $(google-chrome --version || echo 'FALHA')" >> /tmp/startup.log
    echo "ChromeDriver: $(chromedriver --version || echo 'FALHA')" >> /tmp/startup.log
    echo "Python: $(python --version)" >> /tmp/startup.log
    echo "PIP: $(pip --version)" >> /tmp/startup.log
} 2>&1 | tee -a /tmp/startup.log

# 2. Configura Xvfb
echo "2. INICIANDO XVFB..." >> /tmp/startup.log
Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset >> /tmp/xvfb.log 2>&1 &
export DISPLAY=:99
echo "XVFB PID: $(pgrep Xvfb)" >> /tmp/startup.log

# 3. Verifica processos
echo "3. PROCESSOS EM EXECUÇÃO:" >> /tmp/startup.log
ps aux >> /tmp/startup.log

# 4. Teste do Selenium
echo "4. TESTE DO SELENIUM..." >> /tmp/startup.log
python -c "
from selenium import webdriver
options = webdriver.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
try:
    driver = webdriver.Chrome(options=options)
    print('✅ Selenium funcionando')
    driver.quit()
except Exception as e:
    print(f'❌ Erro no Selenium: {str(e)}')
" >> /tmp/startup.log 2>&1

# 5. Inicia a aplicação
echo "5. INICIANDO APLICAÇÃO..." >> /tmp/startup.log
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile -