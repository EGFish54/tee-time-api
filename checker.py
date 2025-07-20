from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import os
import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# CONFIG
USERNAME = "C399"
PASSWORD = "Goblue8952"
LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"
CHECK_DAY = "23" # This should ideally come from the config, not hardcoded. For now, it matches your config.json which specifies July 23, 2025 or July 24, 2025.
LOG_FILE = "available_tee_times.txt"
CACHE_FILE = "cached_results.json"

# Logging setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
today_str = datetime.today().strftime("%Y-%m-%d")
log_path = os.path.join(log_dir, f"tee_times_{today_str}.log")
logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s - %(message)s")

# Email setup
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL") or GMAIL_USER

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)
            logging.info("📧 Email sent!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")

def check_tee_times(date_str, start_str, end_str):
    start_time = datetime.strptime(start_str, "%I:%M %p")
    end_time = datetime.strptime(end_str, "%I:%M %p")

    # Extract day for CHECK_DAY from date_str
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        day_for_selection = str(date_obj.day)
    except ValueError:
        logging.error(f"Invalid date format: {date_str}. Using default CHECK_DAY.")
        day_for_selection = CHECK_DAY # Fallback to hardcoded if date_str is bad

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        try:
            logging.info("🔐 Logging in via Playwright")
            page.goto(LOGIN_URL, timeout=30000)
            page.fill("#lgUserName", USERNAME)
            page.fill("#lgPassword", PASSWORD)
            page.click("#lgLoginButton")
            page.wait_for_url(lambda url: url != LOGIN_URL, timeout=30000)

            logging.info("➡️ Navigating to tee times")
            page.goto(TEE_SHEET_URL, timeout=30000)
            frame = page.frame(name="ifrforetees")

            logging.info(f"📅 Selecting date: {date_str} (Day: {day_for_selection})")
            frame.wait_for_selector("#member_select_calendar1", timeout=30000)
            date_elements = frame.query_selector_all("#member_select_calendar1 a.ui-state-default")
            target = next((el for el in date_elements if el.inner_text().strip() == day_for_selection), None)

            if not target:
                results = ["Date not found or invalid day selected"]
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": results}, cache_file)
                return results

            target.click()
            frame.wait_for_timeout(5000)

            # Set course to ALL
            dropdowns = frame.query_selector_all("select")
            for select in dropdowns:
                if "-ALL-" in select.inner_html():
                    select.select_option(label="-ALL-")
                    break

            frame.wait_for_timeout(5000)
            soup = BeautifulSoup(frame.content(), "html.parser")
            tee_sheet = soup.find("div", class_="member_sheet_table")
            if not tee_sheet:
                results = ["Tee sheet not found"]
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": results}, cache_file)
                return results

            found = []
            for row in tee_sheet.find_all("div", class_="rwdTr"):
                cols = row.find_all("div", class_="rwdTd")
                if len(cols) >= 5:
                    time_el = cols[0].find("div", class_="time_slot") or cols[0].find("a", class_="teetime_button")
                    time_text = time_el.get_text(strip=True) if time_el else ""
                    course = cols[2].get_text(strip=True)
                    open_slots = cols[4].get_text(strip=True)

                    try:
                        row_time = datetime.strptime(time_text, "%I:%M %p")
                        if start_time <= row_time <= end_time and "Open" in open_slots:
                            num_open = open_slots.split(" ")[0]
                            found.append(f"{time_text} - {course} - {num_open} slots open")
                    except:
                        continue

            # Log and update cache/email
            previous_found = []
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r") as f:
                        previous_data = json.load(f)
                        previous_found = previous_data.get("results", [])
                except json.JSONDecodeError:
                    logging.warning(f"Malformed {CACHE_FILE}, starting fresh.")
                    previous_found = []
            
            # Filter out "No new tee times" if actual times were found in previous_found
            if "No new tee times" in previous_found and len(previous_found) > 1:
                previous_found = [item for item in previous_found if item != "No new tee times"]


            new_times = [t for t in found if t not in previous_found]

            # Determine what to store as current_results
            if found:
                current_results = found
            else:
                current_results = ["No new tee times"]

            # Save the current state (found tee times or "No new tee times") to CACHE_FILE
            with open(CACHE_FILE, "w") as cache_file:
                json.dump({"results": current_results}, cache_file)

            if new_times:
                logging.info("✅ New tee times found:\n" + "\n".join(new_times))
                # This LOG_FILE is now primarily for historical logging, not the source for /check
                with open(LOG_FILE, "w") as f:
                    f.write("\n".join(found))
                send_email("New Tee Times Available", "\n".join(new_times))
                return new_times
            else:
                logging.info("🟢 No new tee times found.")
                # If no new times, but there were previously found times that are still there,
                # we return "No new tee times" but the cache (current_results) holds the actual found times.
                return ["No new tee times"]

        except Exception as e:
            logging.error(f"💥 Error: {e}")
            error_message = f"A timeout occurred or another error: {e}"
            # Still attempt to write an error state to the cache
            with open(CACHE_FILE, "w") as cache_file:
                json.dump({"results": [error_message]}, cache_file)
            return [error_message]
        finally:
            browser.close()

def get_cached_tee_times():
    # Read directly from cached_results.json
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                return data.get("results", ["No cached tee times found or error in cache file."])
        except json.JSONDecodeError:
            return ["Error reading cached_results.json, file might be corrupted."]
    else:
        return ["No cached tee times found (cache file does not exist)."]
