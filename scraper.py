import sys
import os
import re
import time
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

DUTCH_MONTHS = {
    'januari': 1, 'februari': 2, 'maart': 3, 'april': 4,
    'mei': 5, 'juni': 6, 'juli': 7, 'augustus': 8,
    'september': 9, 'oktober': 10, 'november': 11, 'december': 12
}

HA_URL = os.environ.get("HA_URL", "http://localhost:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

WAIT_TIMEOUT = 30


def log(msg):
    print(msg, file=sys.stderr)


def parse_date(month_year_str, day_number):
    try:
        match = re.search(r'(\w+)\s*-?\s*(\d{4})', month_year_str)
        if match:
            month_name = match.group(1).lower()
            year = int(match.group(2))
            month = DUTCH_MONTHS.get(month_name)
            if month:
                return datetime(year, month, int(day_number))
    except (ValueError, AttributeError):
        pass
    return None


def send_to_homeassistant(collections):
    if not collections:
        log("No collections to send")
        return False

    if not HA_TOKEN:
        log("HA_TOKEN not set, skipping Home Assistant update")
        return False

    grouped_by_month = {}
    today = datetime.now()

    for collection in collections:
        collection_date = datetime.strptime(collection['date'], '%Y-%m-%d')
        days_until = (collection_date - today).days
        year_month = collection['date'][:7]

        if year_month not in grouped_by_month:
            grouped_by_month[year_month] = {
                'month_label': collection_date.strftime('%B %Y'),
                'collections': []
            }

        grouped_by_month[year_month]['collections'].append({
            'date': collection['date'],
            'waste_type': collection['waste_type'],
            'days_until_collection': days_until
        })

    sorted_months = sorted(grouped_by_month.items())

    headers = {
        'Authorization': HA_TOKEN,
        'Content-Type': 'application/json'
    }

    success_count = 0
    for i, (year_month, data) in enumerate(sorted_months[:2]):
        month_id = i + 1

        future_collections = [c for c in data['collections'] if c['days_until_collection'] >= 0]
        next_collection = future_collections[0] if future_collections else None

        payload = {
            'state': data['month_label'],
            'attributes': {
                'year_month': year_month,
                'collections': data['collections'],
                'next_collection_date': next_collection['date'] if next_collection else 'None',
                'next_collection_type': next_collection['waste_type'] if next_collection else 'None',
                'next_collection_days': next_collection['days_until_collection'] if next_collection else 0
            }
        }

        url = f"{HA_URL}/api/states/sensor.waste_collection_month_{month_id}"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code in (200, 201):
                log(f"Successfully updated sensor.waste_collection_month_{month_id}")
                success_count += 1
            else:
                log(f"Failed to update month {month_id}: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            log(f"Error sending to Home Assistant for month {month_id}: {e}")

    return success_count > 0


def create_driver(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--log-level=3')

    chrome_bin = os.environ.get("CHROME_BIN")
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if chrome_bin:
        chrome_options.binary_location = chrome_bin

    if chromedriver_path:
        service = Service(chromedriver_path)
    else:
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=chrome_options)


def save_debug(driver):
    try:
        os.makedirs("/app/debug", exist_ok=True)
        driver.save_screenshot("/app/debug/screenshot.png")
        with open("/app/debug/page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log(f"[DEBUG] Screenshot and HTML saved to /app/debug/")
        log(f"[DEBUG] URL: {driver.current_url}")
        log(f"[DEBUG] Title: {driver.title}")
    except Exception:
        pass


def scrape_waste_calendar(postcode="5000AA", huisnummer="1", months_ahead=2, headless=True):
    driver = create_driver(headless)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)
    collections = []

    try:
        # Step 1: Load page
        log("[1/5] Loading page...")
        driver.get("https://21burgerportaal.mendixcloud.com/p/tilburg/landing/")
        log(f"[1/5] Page loaded: {driver.title} ({driver.current_url})")

        # Step 2: Fill address - wait for visible inputs then use fixed delay like original
        log(f"[2/5] Waiting for address input fields...")
        time.sleep(3)

        visible_inputs = [inp for inp in driver.find_elements(By.TAG_NAME, "input")
                         if inp.is_displayed() and inp.get_attribute('type') == 'text']

        if len(visible_inputs) < 2:
            # Retry with longer wait
            log(f"[2/5] Found {len(visible_inputs)} inputs, retrying with longer wait...")
            time.sleep(5)
            visible_inputs = [inp for inp in driver.find_elements(By.TAG_NAME, "input")
                             if inp.is_displayed() and inp.get_attribute('type') == 'text']

        if len(visible_inputs) < 2:
            save_debug(driver)
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            log(f"[DEBUG] Total <input> elements: {len(all_inputs)}")
            for i, inp in enumerate(all_inputs):
                log(f"  [{i}] type={inp.get_attribute('type')} displayed={inp.is_displayed()} id={inp.get_attribute('id')}")
            raise Exception(f"Could not find address fields (found {len(visible_inputs)} visible text inputs)")

        log(f"[2/5] Found {len(visible_inputs)} fields, filling in {postcode} / {huisnummer}...")
        visible_inputs[0].click()
        visible_inputs[0].clear()
        visible_inputs[0].send_keys(postcode)
        time.sleep(0.5)

        visible_inputs[1].click()
        visible_inputs[1].clear()
        visible_inputs[1].send_keys(huisnummer)
        visible_inputs[1].send_keys(Keys.RETURN)
        time.sleep(3)

        # Step 3: Click "Informatie" card
        log("[3/5] Clicking 'Informatie' card...")
        informatie_h2 = driver.find_element(By.XPATH, "//h2[contains(text(), 'Informatie')]")
        card = informatie_h2.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", card)
        time.sleep(3)

        # Step 4: Click "Afvalkalender" card
        log("[4/5] Clicking 'Afvalkalender' card...")
        afvalkalender_h2 = driver.find_element(By.XPATH, "//h2[contains(text(), 'Afvalkalender')]")
        card = afvalkalender_h2.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", card)
        time.sleep(3)

        # Step 5: Wait for calendar to fully load
        log("[5/5] Waiting for calendar to load...")
        time.sleep(2)

        # Extract calendar data
        for month_num in range(months_ahead):
            time.sleep(1)

            # Get current month/year
            current_month_year = "Unknown"
            try:
                month_spans = driver.find_elements(By.CSS_SELECTOR, "span.mx-name-text195")
                for span in month_spans:
                    if span.is_displayed():
                        text = span.text.strip()
                        if text and ("-" in text or any(m in text.lower() for m in DUTCH_MONTHS)):
                            current_month_year = text
                            break
            except Exception:
                pass

            log(f"  Parsing month: {current_month_year}")

            # Find all calendar day items
            day_items = driver.find_elements(By.CSS_SELECTOR, "div.mx-templategrid-item")
            log(f"  Found {len(day_items)} calendar day items")

            for item in day_items:
                try:
                    day_span = item.find_element(By.CSS_SELECTOR, "span.mx-name-text199")
                    day_number = day_span.text.strip()

                    if not day_number or not day_number.isdigit():
                        continue

                    if "agendaitem-box-notmonth" in item.get_attribute("class"):
                        continue

                    images = item.find_elements(By.CSS_SELECTOR, "img.mx-name-imageViewer9")
                    for img in images:
                        try:
                            alt = (img.get_attribute("alt") or "").lower()

                            waste_type = None
                            if "papier" in alt or "pmd" in alt:
                                waste_type = "Papier/PMD"
                            elif "rest" in alt or "gft" in alt:
                                waste_type = "Rest/GFT"

                            if waste_type:
                                date_obj = parse_date(current_month_year, day_number)
                                if date_obj:
                                    collections.append({
                                        "date": date_obj.strftime("%Y-%m-%d"),
                                        "waste_type": waste_type
                                    })
                        except Exception:
                            continue
                except Exception:
                    continue

            # Navigate to next month
            if month_num < months_ahead - 1:
                log(f"  Navigating to next month...")
                try:
                    button_selectors = [
                        "//button[contains(@class, 'mx-name-actionButton57')]",
                        "//button[@data-button-id and contains(@data-button-id, 'actionButton57')]",
                        "//button[contains(text(), 'Volgende') and contains(@class, 'mx-button')]",
                    ]

                    next_btns = []
                    for selector in button_selectors:
                        try:
                            btns = driver.find_elements(By.XPATH, selector)
                            for btn in btns:
                                if btn.is_displayed() and btn not in next_btns:
                                    next_btns.append(btn)
                        except Exception:
                            continue

                    if len(next_btns) == 0:
                        log("  No next-month button found, stopping")
                        break

                    btn = next_btns[0]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except Exception:
                    log("  Failed to navigate to next month")
                    break

        collections.sort(key=lambda x: x.get("date", ""))
        log(f"Scraping complete: {len(collections)} collection dates found")
        return collections

    except Exception as e:
        log(f"Error: {e}")
        save_debug(driver)
        return None
    finally:
        driver.quit()


if __name__ == "__main__":
    postcode = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("POSTCODE", "5000AA")
    huisnummer = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HUISNUMMER", "1")

    log("Starting waste calendar scraper...")
    result = scrape_waste_calendar(postcode, huisnummer, months_ahead=2, headless=True)

    if result:
        log(f"Found {len(result)} collection dates")
        if send_to_homeassistant(result):
            log("Successfully updated Home Assistant sensors")
            sys.exit(0)
        else:
            log("Failed to update Home Assistant sensors")
            sys.exit(1)
    else:
        log("Failed to scrape data")
        sys.exit(1)
