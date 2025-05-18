#!/bin/bash

# Enable strict error checking
set -eo pipefail

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Verify installations
log "=== System Verification ==="
log "Chrome: $(google-chrome --version || echo 'NOT FOUND')"
log "ChromeDriver: $(chromedriver --version || echo 'NOT FOUND')"
log "Python: $(python --version)"
log "Gunicorn: $(gunicorn --version || echo 'NOT FOUND')"

# 2. Start Xvfb
log "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset > /tmp/xvfb.log 2>&1 &
export DISPLAY=:99

# 3. Verify Selenium setup
log "Testing ChromeDriver..."
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
    print('✅ ChromeDriver test successful')
    driver.quit()
except Exception as e:
    print(f'❌ ChromeDriver test failed: {e}')
    raise
"

# 4. Start application
log "Starting application..."
exec gunicorn app:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -