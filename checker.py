from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import os
import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# CONFIG
USERNAME = "C399"
PASSWORD = "Goblue8952"
LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"
# CHECK_DAY will be dynamically set from date_str now
LOG_FILE = "available_tee_times.txt"
CACHE_FILE = "cached_results.json"
SCREENSHOT_DIR = "screenshots" # Directory to save screenshots

# Logging setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
today_str = datetime.today().strftime("%Y-%m-%d")
log_path = os.path.join(log_dir, f"tee_times_{today_str}.log")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s",
                    handlers=[
                        logging.FileHandler(log_path),
                        logging.StreamHandler()
                    ])

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Email setup
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_PASS or not RECIPIENT_EMAIL:
        logging.error("Email credentials or recipient not set. Cannot send email.")
        return

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.send_message(msg)
        logging.info("Email sent successfully!")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def take_screenshot(page, name):
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    try:
        page.screenshot(path=screenshot_path)
        logging.info(f"Screenshot saved: {screenshot_path}")
    except Exception as e:
        logging.error(f"Failed to take screenshot: {e}")


def check_tee_times(date_str, start_time_str, end_time_str):
    logging.info(f"Starting check for date: {date_str}, {start_time_str}-{end_time_str}")
    browser = None
    found_times = []
    
    try:
        START_TIME = datetime.strptime(start_time_str, "%I:%M %p").time()
        END_TIME = datetime.strptime(end_time_str, "%I:%M %p").time()
        # Parse CHECK_DATE for CHECK_DAY
        check_date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        CHECK_DAY = str(check_date_obj.day)

        with sync_playwright() as p:
            # --- IMPORTANT: ADD THESE ARGUMENTS TO REDUCE MEMORY USAGE ---
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',             # Required for Render
                    '--disable-setuid-sandbox', # Required for Render
                    '--disable-dev-shm-usage',  # Reduces memory use by disabling /dev/shm
                    '--no-zygote',              # Might help with memory
                    '--single-process'          # Can reduce overhead
                ]
            )
            # --- END IMPORTANT ADDITION ---
            
            page = browser.new_page()
            page.set_default_timeout(60000) # 60 seconds timeout for page operations

            # 1. Navigate to login
            logging.info(f"Navigating to login page: {LOGIN_URL}")
            page.goto(LOGIN_URL)
            page.wait_for_load_state('networkidle')

            # 2. Fill login form
            logging.info("Filling login form...")
            page.fill('input#ctl00_ContentPlaceHolder1_Login1_UserName', USERNAME)
            page.fill('input#ctl00_ContentPlaceHolder1_Login1_Password', PASSWORD)
            page.click('input#ctl00_ContentPlaceHolder1_Login1_LoginButton')
            page.wait_for_load_state('networkidle')

            if "Password incorrect" in page.content() or "Login failed" in page.content():
                error_msg = "Login failed: Incorrect username or password."
                logging.error(error_msg)
                take_screenshot(page, "login_failed")
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": [error_msg]}, cache_file)
                return [error_msg]
            
            # 3. Navigate to tee sheet
            logging.info(f"Navigating to tee sheet page: {TEE_SHEET_URL}")
            page.goto(TEE_SHEET_URL)
            page.wait_for_load_state('networkidle')

            # Wait for the specific element that indicates page is loaded
            WebDriverWait(page, 30).until(
                lambda p: p.query_selector("select#dnn_ctr433_ModuleContent_TeeTime_ddlCourse")
            )
            
            # 4. Select the correct date from the calendar
            logging.info(f"Selecting date: {date_str} (day {CHECK_DAY})...")
            # Click the calendar icon to open the date picker
            page.click('img#dnn_ctr433_ModuleContent_TeeTime_imgCalendar')

            # Wait for the calendar to be visible (e.g., a known element within the calendar)
            page.wait_for_selector('table.RadCalendar_Default')

            # Navigate calendar to the correct month/year if needed (not implemented here, assumes current month/year view)
            # Find the day element and click it
            # This XPath assumes a specific structure, might need adjustment if calendar HTML changes
            try:
                # Find the exact day cell. This might be fragile and need robust selector.
                # Example: page.click(f'//td[contains(@class, "rcWeekend") or contains(@class, "rcWeekDay")]/a[text()="{CHECK_DAY}"]')
                # A more robust approach would be to iterate through the calendar cells
                page.evaluate(f"""
                    Array.from(document.querySelectorAll('table.RadCalendar_Default td')).forEach(td => {{
                        if (td.querySelector('a') && td.querySelector('a').textContent === '{CHECK_DAY}') {{
                            td.querySelector('a').click();
                        }}
                    }});
                """)
                logging.info(f"Clicked on day {CHECK_DAY}")
            except Exception as e:
                logging.error(f"Could not click on day {CHECK_DAY} in calendar: {e}")
                take_screenshot(page, "calendar_error")
                error_msg = f"Failed to select date {date_str} on calendar."
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": [error_msg]}, cache_file)
                return [error_msg]
            
            page.wait_for_load_state('networkidle') # Wait for new tee times to load after date selection

            # 5. Extract tee times using BeautifulSoup
            logging.info("Extracting tee times...")
            soup = BeautifulSoup(page.content(), 'html.parser')
            tee_time_table = soup.find('table', {'class': 'TeeTimeGrid'})
            
            found = []
            if tee_time_table:
                rows = tee_time_table.find_all('tr', class_=['rgRow', 'rgAltRow'])
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) > 4: # Ensure there are enough columns
                        time_text = cols[0].get_text(strip=True)
                        open_slots_text = cols[4].get_text(strip=True)
                        
                        try:
                            slot_time = datetime.strptime(time_text, "%I:%M %p").time()
                            # Check if within time range and slots are open
                            if START_TIME <= slot_time <= END_TIME and "Open" in open_slots_text:
                                num_open = open_slots_text.split(" ")[0] # Gets the number before "Open"
                                course_name = cols[2].get_text(strip=True)
                                found.append(f"{time_text} - {course_name} - {num_open} slots open")
                        except ValueError:
                            # Skip rows that don't have a valid time format
                            continue
            
            if not found:
                found.append(f"No tee times found for {date_str} between {start_time_str} and {end_time_str}.")
            
            # Cache results
            with open(CACHE_FILE, "w") as cache_file:
                json.dump({"results": found}, cache_file)
            
            # Check for new times and send email
            previous_times = []
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r") as f:
                    previous_times = [line.strip() for line in f.readlines()]
            
            new_times = [t for t in found if t not in previous_times]
            
            if new_times:
                logging.info("✅ New tee times found:\\n" + "\\n".join(new_times))
                with open(LOG_FILE, "w") as f:
                    f.write("\n".join(found)) # Overwrite log with current found times
                send_email("New Tee Times Available", "\n".join(new_times))
                return found # Return all found times, not just new ones, for consistency with UI
            else:
                logging.info("🟢 No new tee times found (or no changes since last check).")
                return found # Return all found times even if no new ones


    except Exception as e:
        logging.error(f"💥 Error during scraping: {e}")
        error_message = f"An error occurred during scraping: {e}"
        take_screenshot(page, "error_state")
        
        with open(CACHE_FILE, "w") as cache_file:
            json.dump({"results": [error_message]}, cache_file)
        return [error_message]
    finally:
        if browser:
            browser.close()
            logging.info("Browser closed.")


def get_cached_tee_times():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                return data.get("results", ["No cached tee times found or error in cache file."])
        except json.JSONDecodeError:
            return ["Error reading cached_results.json, file might be corrupted."]
    else:
        return ["No cached tee times found (cache file does not exist)."]
