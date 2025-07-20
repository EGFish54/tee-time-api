from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import os
import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys # Import sys for stdout

# CONFIG
USERNAME = "C399"
PASSWORD = "Goblue8952"
LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"
# CHECK_DAY will be dynamically set from date_str now
LOG_FILE = "available_tee_times.txt"
CACHE_FILE = "cached_results.json"

# Logging setup: Direct logs to stdout
# No need for log_dir or log_path variables when logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", stream=sys.stdout)

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

def take_screenshot(page, name):
    try:
        # Save screenshots to a writable temporary directory
        temp_screenshot_dir = os.path.join("/tmp", "screenshots")
        os.makedirs(temp_screenshot_dir, exist_ok=True) # Ensure /tmp/screenshots exists
        screenshot_path = os.path.join(temp_screenshot_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        page.screenshot(path=screenshot_path)
        logging.info(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        logging.warning(f"Could not take screenshot {name}: {e}")

def check_tee_times(date_str, start_str, end_str):
    start_time = datetime.strptime(start_str, "%I:%M %p")
    end_time = datetime.strptime(end_str, "%I:%M %p")

    # Extract day for selection from date_str
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        day_for_selection = str(date_obj.day)
    except ValueError:
        logging.error(f"Invalid date format: {date_str}. Could not determine day for selection.")
        return ["Error: Invalid date format provided."]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"]) # Keep headless=True for server deployment
        context = browser.new_context()
        page = context.new_page()

        try:
            logging.info("🔐 Logging in via Playwright")
            page.goto(LOGIN_URL, timeout=60000)
            take_screenshot(page, "after_login_page_load")
            
            page.fill("#lgUserName", USERNAME)
            page.fill("#lgPassword", PASSWORD)
            page.click("#lgLoginButton")
            page.wait_for_url(lambda url: url != LOGIN_URL, timeout=60000)
            take_screenshot(page, "after_successful_login")

            logging.info("➡️ Navigating to tee times")
            page.goto(TEE_SHEET_URL, timeout=60000)
            take_screenshot(page, "after_tee_sheet_load")
            
            frame = page.frame(name="ifrforetees")
            if not frame:
                logging.error("Could not find iframe 'ifrforetees'.")
                take_screenshot(page, "iframe_not_found_error")
                results = ["Error: Tee time iframe not found."]
                with open("cached_results.json", "w") as cache_file: # Use direct filename
                    json.dump({"results": results}, cache_file)
                return results

            logging.info(f"📅 Selecting date: {date_str} (Day: {day_for_selection})")
            frame.wait_for_selector("#member_select_calendar1", timeout=60000)
            take_screenshot(page, "before_date_selection")
            
            date_elements = frame.query_selector_all("#member_select_calendar1 a.ui-state-default")
            target = next((el for el in date_elements if el.inner_text().strip() == day_for_selection), None)

            if not target:
                logging.warning(f"Target date element for day {day_for_selection} not found.")
                take_screenshot(page, "date_element_not_found")
                results = ["Date not found or invalid day selected"]
                with open("cached_results.json", "w") as cache_file: # Use direct filename
                    json.dump({"results": results}, cache_file)
                return results

            target.click()
            frame.wait_for_timeout(5000) # Give some time for content to update after click
            take_screenshot(page, "after_date_click")


            # Set course to ALL
            dropdowns = frame.query_selector_all("select")
            course_selected = False
            for select in dropdowns:
                if "-ALL-" in select.inner_html():
                    select.select_option(label="-ALL-")
                    course_selected = True
                    break
            if not course_selected:
                logging.warning("'-ALL-' course option not found.")
                take_screenshot(page, "course_all_not_found")

            frame.wait_for_timeout(5000) # Give some time for content to update after selection
            take_screenshot(page, "after_course_select")
            
            soup = BeautifulSoup(frame.content(), "html.parser")
            tee_sheet = soup.find("div", class_="member_sheet_table")
            if not tee_sheet:
                logging.warning("Tee sheet table not found.")
                take_screenshot(page, "tee_sheet_not_found")
                results = ["Tee sheet not found"]
                with open("cached_results.json", "w") as cache_file: # Use direct filename
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
            if os.path.exists("cached_results.json"): # Use direct filename
                try:
                    with open("cached_results.json", "r") as f: # Use direct filename
                        previous_data = json.load(f)
                        previous_found = previous_data.get("results", [])
                except json.JSONDecodeError:
                    logging.warning(f"Malformed cached_results.json, starting fresh.")
                    previous_found = []
            
            if "No new tee times" in previous_found and len(previous_found) > 1:
                previous_found = [item for item in previous_found if item != "No new tee times"]

            new_times = [t for t in found if t not in previous_found]

            if found:
                current_results = found
            else:
                current_results = ["No new tee times"]

            with open("cached_results.json", "w") as cache_file: # Use direct filename
                json.dump({"results": current_results}, cache_file)

            if new_times:
                logging.info("✅ New tee times found:\n" + "\n".join(new_times))
                with open(LOG_FILE, "w") as f:
                    f.write("\n".join(found))
                send_email("New Tee Times Available", "\n".join(new_times))
                return new_times
            else:
                logging.info("🟢 No new tee times found.")
                return ["No new tee times"]

        except Exception as e:
            logging.error(f"💥 Error: {e}")
            error_message = f"An error occurred during scraping: {e}"
            take_screenshot(page, "error_state") # Take screenshot on error
            with open("cached_results.json", "w") as cache_file: # Use direct filename
                json.dump({"results": [error_message]}, cache_file)
            return [error_message]
        finally:
            browser.close()

def get_cached_tee_times():
    if os.path.exists("cached_results.json"): # Use direct filename
        try:
            with open("cached_results.json", "r") as f: # Use direct filename
                data = json.load(f)
                return data.get("results", ["No cached tee times found or error in cache file."])
        except json.JSONDecodeError:
            return ["Error reading cached_results.json, file might be corrupted."]
    else:
        return ["No cached tee times found (cache file does not exist)."]
