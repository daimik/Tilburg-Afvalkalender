# 🗑️ Tilburg Afvalkalender — Home Assistant Integration

Automated scraper that collects waste collection schedules from the [Gemeente Tilburg afvalkalender](https://21burgerportaal.mendixcloud.com/p/tilburg/landing/) and sends them to Home Assistant as sensor entities.

🏠 Built for residents of **Tilburg, Netherlands** who use Home Assistant for home automation.

## ✨ What it does

1. 🌐 Opens the Tilburg municipal waste calendar portal (Mendix-based)
2. 📝 Enters your postcode and house number
3. 📅 Navigates to the Afvalkalender and reads the next 2 months of collection dates
4. 🔍 Detects two waste types from the calendar:
   - 🟢 **Rest/GFT** (residual waste / garden & food waste)
   - 🔵 **Papier/PMD** (paper / plastic, metal & drink cartons)
5. 📡 Sends the data to Home Assistant via the REST API as two sensors:
   - `sensor.waste_collection_month_1` (current month)
   - `sensor.waste_collection_month_2` (next month)
6. ⏰ Runs on a configurable cron schedule (default: daily at 06:00)

## 🐳 Quick Start with Docker

### Using the pre-built image from Docker Hub

Create a `docker-compose.yml`:

```yaml
services:
  scraper:
    image: daimik/waste-scraper:latest
    container_name: waste-scraper
    restart: unless-stopped
    environment:
      - POSTCODE=5000AA
      - HUISNUMMER=1
      - CRON_SCHEDULE=0 6 * * *
      - HA_URL=http://your-homeassistant-ip:8123
      - HA_TOKEN=Bearer your_long_lived_access_token
```

Then run:

```bash
docker compose up -d
```

### 🔧 Building from source

```bash
git clone https://github.com/daimik/Tilburg-Afvalkalender.git
cd Tilburg-Afvalkalender
docker compose up -d --build
```

When building from source, copy `.env.example` to `.env` and fill in your values.

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `POSTCODE` | ✅ | `5000AA` | Your postcode in Tilburg |
| `HUISNUMMER` | ✅ | `1` | Your house number |
| `HA_URL` | ✅ | - | Home Assistant URL (e.g. `http://192.168.1.100:8123`) |
| `HA_TOKEN` | ✅ | - | Home Assistant long-lived access token (include `Bearer ` prefix) |
| `CRON_SCHEDULE` | ❌ | `0 6 * * *` | How often to scrape ([cron format](https://crontab.guru/)) |

### 🔑 Getting a Home Assistant Token

1. In Home Assistant, go to your profile (click your name in the sidebar)
2. Scroll down to **Long-Lived Access Tokens**
3. Click **Create Token**, give it a name, and copy the token
4. Set `HA_TOKEN` to `Bearer <your_token>`

## 📊 Home Assistant Sensor Data

Each sensor contains the following attributes:

```json
{
  "state": "April 2026",
  "attributes": {
    "year_month": "2026-04",
    "collections": [
      {
        "date": "2026-04-07",
        "waste_type": "Rest/GFT",
        "days_until_collection": 5
      },
      {
        "date": "2026-04-14",
        "waste_type": "Papier/PMD",
        "days_until_collection": 12
      }
    ],
    "next_collection_date": "2026-04-07",
    "next_collection_type": "Rest/GFT",
    "next_collection_days": 5
  }
}
```

### 🖥️ Dashboard Card

Add a **Markdown card** to your Home Assistant dashboard to display the waste collection schedule:

```yaml
type: markdown
content: >-
  ## 🗑️ Waste Collection Schedule

  ### 📅 Next Collection
  {% set collections1 = state_attr('sensor.waste_collection_month_1', 'collections') %}
  {% set collections2 = state_attr('sensor.waste_collection_month_2', 'collections') %}
  {% set all_collections = [] %}

  {% if collections1 %}
    {% set all_collections = all_collections + collections1 %}
  {% endif %}
  {% if collections2 %}
    {% set all_collections = all_collections + collections2 %}
  {% endif %}

  {% if all_collections %}
    {% set future = all_collections | selectattr('days_until_collection', '>=', 0) | list %}
    {% if future | length > 0 %}
      {% set next = future | first %}
      {% if next.waste_type == 'Papier/PMD' %}
  🔵 **{{ next.waste_type }}**
      {% else %}
  🟢 **{{ next.waste_type }}**
      {% endif %}

  **{{ next.date }}** - in **{{ next.days_until_collection }}** days
    {% else %}
  ❌ No upcoming collections found
    {% endif %}
  {% else %}
  ⚠️ No data available
  {% endif %}

  ---

  ### 📆 {{ states('sensor.waste_collection_month_1') }}
  <table width="100%">
  {% set collections = state_attr('sensor.waste_collection_month_1', 'collections') %}
  {% if collections %}
  {% for collection in collections %}
  <tr>
  <td>{% if collection.waste_type == 'Papier/PMD' %}🔵{% else %}🟢{% endif %} <b>{{ collection.waste_type }}</b></td>
  <td>{{ collection.date }}</td>
  <td align="right">{% if collection.days_until_collection >= 0 %}in {{ collection.days_until_collection }} days{% else %}{{ collection.days_until_collection * -1 }} days ago{% endif %}</td>
  </tr>
  {% endfor %}
  {% endif %}
  </table>

  ---

  ### 📆 {{ states('sensor.waste_collection_month_2') }}
  <table width="100%">
  {% set collections = state_attr('sensor.waste_collection_month_2', 'collections') %}
  {% if collections %}
  {% for collection in collections %}
  <tr>
  <td>{% if collection.waste_type == 'Papier/PMD' %}🔵{% else %}🟢{% endif %} <b>{{ collection.waste_type }}</b></td>
  <td>{{ collection.date }}</td>
  <td align="right">{% if collection.days_until_collection >= 0 %}in {{ collection.days_until_collection }} days{% else %}{{ collection.days_until_collection * -1 }} days ago{% endif %}</td>
  </tr>
  {% endfor %}
  {% endif %}
  </table>
```

<img width="527" height="611" alt="image" src="https://github.com/user-attachments/assets/7f52e130-584f-4307-afb9-f467edad4739" />


## 🐳 Container Behavior

- 🚀 Runs the scraper **once immediately** on container start
- ⏰ Then continues on the configured cron schedule
- 🔄 Automatically restarts on failure (`restart: unless-stopped`)
- 🖥️ Uses headless Chromium inside the container (no display needed)
- 📋 All logs visible via `docker logs waste-scraper`

## 📋 Logs

```
[1/5] Loading page...
[2/5] Found 2 fields, filling in 5000AA / 1...
[3/5] Clicking 'Informatie' card...
[4/5] Clicking 'Afvalkalender' card...
[5/5] Waiting for calendar to load...
  Parsing month: April - 2026
  Found 80 calendar day items
  Navigating to next month...
  Parsing month: Mei - 2026
  Found 82 calendar day items
Scraping complete: 9 collection dates found
✅ Successfully updated sensor.waste_collection_month_1
✅ Successfully updated sensor.waste_collection_month_2
```

## ⚠️ Disclaimer

This scraper depends on the Gemeente Tilburg waste portal UI structure. If the municipality updates their website, the scraper may need adjustments.
