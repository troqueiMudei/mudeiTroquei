FROM python:3.10-slim

# Environment configuration
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    SELENIUM_DISABLE_MANAGER=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg unzip xvfb \
    fonts-liberation libnss3 libgbm1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (version 136.0.7103.113)
RUN wget -q -O chrome.deb "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_136.0.7103.113-1_amd64.deb" && \
    apt-get update && \
    apt-get install -y ./chrome.deb && \
    rm chrome.deb && \
    google-chrome --version

# Install matching ChromeDriver (version 136.0.7103.113)
RUN CHROMEDRIVER_VERSION="136.0.7103.113" && \
    wget -q -O chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" && \
    unzip chromedriver.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm -rf chromedriver.zip chromedriver-linux64 && \
    chromedriver --version

# Create non-root user
RUN useradd -m appuser && mkdir /app && chown appuser:appuser /app
WORKDIR /app
USER appuser

# Install Python dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application
COPY --chown=appuser:appuser . .

# Set execute permission
RUN chmod +x start.sh

# Entry point
CMD ["./start.sh"]