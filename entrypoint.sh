#!/bin/bash
set -e

SCHEDULE="${CRON_SCHEDULE:-0 6 * * *}"

# Pass all relevant env vars to the cron job
printenv | grep -E '^(POSTCODE|HUISNUMMER|HA_URL|HA_TOKEN|CHROME_BIN|CHROMEDRIVER_PATH|PYTHON)' > /etc/environment

CRON_CMD="${SCHEDULE} /usr/local/bin/python /app/scraper.py >> /var/log/scraper.log 2>&1"

echo "$CRON_CMD" > /etc/cron.d/scraper
chmod 0644 /etc/cron.d/scraper
crontab /etc/cron.d/scraper
touch /var/log/scraper.log

echo "Cron schedule: ${SCHEDULE}"
echo "Postcode: ${POSTCODE:-5000A}, Huisnummer: ${HUISNUMMER:-1}"
echo "HA URL: ${HA_URL:-not set}"

# Run once at startup
echo "Running initial scrape..."
python /app/scraper.py 2>&1

echo "Starting cron daemon..."
exec cron -f
