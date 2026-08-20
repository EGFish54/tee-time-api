from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime
import os
import logging
import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import threading
from functools import wraps

# CONFIG
USERNAME = os.getenv("PRESTONWOOD_USERNAME")
PASSWORD = os.getenv("PRESTONWOOD_PASSWORD")

LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"
LOG_FILE = "available_tee_times.txt"
CACHE_FILE = "cached_results.json"
SCREENSHOT_DIR = "screenshots"

# Logging setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
today_str = datetime.today().strftime("%Y-%m-%d")
log_path = os.path.join(log_dir, f"tee_times_{today_str}.log")
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Email setup
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

# Global lock to prevent concurrent scraper runs
scraper_lock = threading.Lock()

def retry_on_failure(max_attempts=3, delay=5):
    """Decorator to retry functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logging.error(f"❌ {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    logging.warning(f"⚠️ {func.__name__} attempt {attempt} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def send_email(subject, body):
    """Send email using Gmail SMTP with App Password"""
    
    # Get Gmail credentials from environment
    gmail_user = os.getenv("GMAIL_USER")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
    
    if not gmail_user or not gmail_app_password:
        logging.error("Gmail credentials not set. Cannot send email.")
        return
    
    # Send only to SMS gateway
    recipient = "9196010286@vtext.com"
    
    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Use Gmail's SMTP server on port 587
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
            server.starttls()  # Upgrade connection to secure
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, [recipient], msg.as_string())
        logging.info("📧 SMS notification sent successfully via Gmail!")
    except smtplib.SMTPException as e:
        logging.error(f"❌ SMTP error sending SMS: {e}")
    except Exception as e:
        logging.error(f"❌ Failed to send SMS: {e}")

def take_screenshot(page, name):
    """Take screenshot with extended timeout and better error handling"""
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    try:
        # Increased timeout to 30 seconds
        page.screenshot(path=screenshot_path, timeout=30000)
        logging.info(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        # Don't let screenshot failures break the scraper
        logging.warning(f"⚠️ Screenshot skipped ({name}): {e}")

@retry_on_failure(max_attempts=2, delay=3)
def perform_login(page):
    """Handle login with retry logic"""
    logging.info(f"🔐 Navigating to login page: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=120000)
    
    page.wait_for_selector("#lgUserName", state='visible', timeout=30000)
    page.fill("#lgUserName", USERNAME)
    page.fill("#lgPassword", PASSWORD)
    page.click("#lgLoginButton")
    
    page.wait_for_url(lambda url: url != LOGIN_URL, timeout=60000)
    time.sleep(2)  # Allow session to stabilize
    take_screenshot(page, "after_successful_initial_login_redirect")
    logging.info("✅ Initial login successful and redirected.")

def handle_member_area_button(page):
    """Check and click 'ENTER MEMBER AREA' button if present"""
    member_area_button_selector = "button:has-text('ENTER MEMBER AREA')"
    try:
        if page.locator(member_area_button_selector).is_visible(timeout=5000):
            logging.info("✅ 'ENTER MEMBER AREA' button found. Clicking to proceed.")
            page.click(member_area_button_selector, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=60000)
            take_screenshot(page, "after_enter_member_area_click")
            
            logging.info("➡️ Navigating to Member Central page.")
            page.goto("https://www.prestonwood.com/member-central-18.html", 
                     wait_until="networkidle", timeout=90000)
            take_screenshot(page, "after_member_central_navigation")
            time.sleep(2)
    except Exception as e:
        logging.info(f"No 'ENTER MEMBER AREA' button found or error clicking it: {e}")

@retry_on_failure(max_attempts=2, delay=5)
def navigate_to_tee_sheet(page):
    """Navigate to tee sheet with extended timeout"""
    logging.info(f"➡️ Navigating to tee sheet page: {TEE_SHEET_URL}")
    page.goto(TEE_SHEET_URL, wait_until="load", timeout=120000)
    
    # Wait for network to be idle
    page.wait_for_load_state('networkidle', timeout=90000)
    time.sleep(3)  # Additional stability wait

def wait_for_iframe(page):
    """Wait for iframe to load and return frame handle"""
    logging.info("🔍 Searching for iframe 'ifrforetees'.")
    iframe_handle = page.wait_for_selector("iframe#ifrforetees", timeout=60000)
    
    if not iframe_handle:
        raise Exception("Iframe 'ifrforetees' not found")
    
    logging.info("✅ Found iframe 'ifrforetees'. Waiting for content to load.")
    iframe = iframe_handle.content_frame()
    
    # Wait for iframe content to stabilize
    iframe.wait_for_load_state("domcontentloaded", timeout=90000)
    time.sleep(2)
    take_screenshot(page, "after_iframe_dom_load")
    
    iframe.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(5)  # Extra wait for dynamic content
    take_screenshot(page, "after_iframe_network_idle_and_wait")
    
    return iframe

def get_calendar_month_year(iframe):
    """Read the currently displayed month/year from the jQuery UI datepicker header (handles both text and <select> headers)"""
    calendar = iframe.locator("#member_select_calendar1")
    month_el = calendar.locator(".ui-datepicker-month").first
    year_el = calendar.locator(".ui-datepicker-year").first

    def read_el(el):
        tag = el.evaluate("node => node.tagName").lower()
        if tag == "select":
            return el.evaluate("node => node.options[node.selectedIndex].text").strip()
        return el.text_content().strip()

    month_text = read_el(month_el)
    year_text = read_el(year_el)

    try:
        month_num = datetime.strptime(month_text, "%B").month
    except ValueError:
        month_num = datetime.strptime(month_text, "%b").month
    year_num = int("".join(c for c in year_text if c.isdigit()))

    return month_num, year_num

def navigate_calendar_to_month(iframe, page, target_month, target_year):
    """Click the datepicker's prev/next controls until the displayed month/year matches the target"""
    max_clicks = 24  # safety cap (2 years worth of months)

    for _ in range(max_clicks):
        try:
            current_month, current_year = get_calendar_month_year(iframe)
        except Exception as e:
            logging.warning(f"⚠️ Could not read calendar header month/year: {e}")
            return False

        if current_month == target_month and current_year == target_year:
            logging.info(f"📅 Calendar already showing {current_month}/{current_year}.")
            return True

        diff = (target_year - current_year) * 12 + (target_month - current_month)
        direction = "next" if diff > 0 else "prev"
        selector = f"#member_select_calendar1 a.ui-datepicker-{direction}"

        logging.info(f"📅 Navigating calendar '{direction}' from {current_month}/{current_year} toward {target_month}/{target_year}.")
        try:
            iframe.locator(selector).first.click(timeout=15000)
        except Exception as e:
            logging.warning(f"⚠️ Could not click calendar '{direction}' control: {e}")
            return False

        iframe.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(1.5)  # allow calendar to re-render

    logging.warning(f"⚠️ Could not navigate calendar to {target_month}/{target_year} after {max_clicks} clicks.")
    return False

def select_date_on_calendar(iframe, page, check_day, target_month=None, target_year=None):
    """Select date on the calendar, navigating to the correct month/year first if provided"""
    logging.info(f"📅 Attempting to select date (Day: {check_day})")

    iframe.wait_for_selector("#member_select_calendar1", timeout=60000)
    time.sleep(2)  # Let calendar render
    take_screenshot(page, "before_date_selection_in_iframe")

    if target_month is not None and target_year is not None:
        navigate_calendar_to_month(iframe, page, target_month, target_year)
        take_screenshot(page, "after_calendar_month_navigation")

    logging.info(f"📆 Clicking on target date: {check_day}")
    try:
        iframe.locator(f"td a:has-text('{check_day}')").first.click(timeout=30000)
    except Exception as click_e:
        logging.warning(f"⚠️ Could not click date '{check_day}' directly: {click_e}. Trying alternative.")
        iframe.locator(
            f"//td[contains(@class, 'ui-datepicker-week-end') or "
            f"contains(@class, 'ui-datepicker-unselectable') or "
            f"contains(@class, 'ui-datepicker-current-day')]//a[text()='{check_day}']"
        ).click(timeout=30000)
    
    take_screenshot(page, "after_date_click_in_iframe")
    
    # Wait for date selection to process
    iframe.wait_for_load_state("networkidle", timeout=90000)
    time.sleep(5)
    take_screenshot(page, "after_date_selection_refresh_iframe_and_wait")
    
    # Ensure tee sheet table is present after date selection
    iframe.wait_for_selector("div.member_sheet_table", state='visible', timeout=60000)
    logging.info("✅ Tee sheet table visible after date selection.")

def set_course(iframe, page, course="All"):
    """Set the course dropdown to the requested course ('All', 'Highlands', 'Fairways', 'Meadows')"""
    is_all = not course or course.strip().lower() in ("all", "-all-")
    logging.info(f"🎯 Attempting to set course to '{'-ALL-' if is_all else course}'.")
    time.sleep(2)  # Wait for dropdown to be ready

    course_selected = False
    select_elements = iframe.query_selector_all("select")

    for select_el_handle in select_elements:
        try:
            select_html = select_el_handle.evaluate("node => node.outerHTML")
            if "-ALL-" not in select_html:
                continue

            if is_all:
                select_el_handle.select_option(label="-ALL-")
                logging.info("✅ Course set to '-ALL-'.")
                course_selected = True
                break

            # Find the option whose visible text matches the requested course
            options = select_el_handle.query_selector_all("option")
            target_label = None
            for option in options:
                option_text = option.evaluate("node => node.textContent").strip()
                if option_text.lower() == course.strip().lower() or course.strip().lower() in option_text.lower():
                    target_label = option_text
                    break

            if target_label:
                select_el_handle.select_option(label=target_label)
                logging.info(f"✅ Course set to '{target_label}'.")
                course_selected = True
            else:
                available = [o.evaluate("node => node.textContent").strip() for o in options]
                logging.warning(f"⚠️ Course '{course}' not found among options: {available}")
            break
        except Exception as select_e:
            logging.warning(f"⚠️ Could not process select element: {select_e}")

    if not course_selected:
        logging.warning(f"⚠️ Course option '{course}' not found.")
        take_screenshot(page, "course_select_not_found")
    else:
        iframe.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(3)  # Wait for tee times to reload
        take_screenshot(page, "after_course_select")

    return course_selected

def parse_tee_times(iframe, page, start_time, end_time):
    """Parse tee times from the page"""
    logging.info("⏳ Waiting for tee time rows to be visible.")
    iframe.wait_for_selector("div.member_sheet_table div.rwdTr", 
                            state='visible', timeout=60000)
    time.sleep(2)  # Let content stabilize
    logging.info("✅ Tee time rows visible. Proceeding to parse HTML.")
    
    tee_sheet_html = iframe.content()
    soup = BeautifulSoup(tee_sheet_html, "html.parser")
    tee_sheet_table = soup.find("div", class_="member_sheet_table")
    
    if not tee_sheet_table:
        logging.warning("⚠️ Tee sheet container not found in HTML.")
        take_screenshot(page, "error_tee_sheet_table_missing")
        return []
    
    logging.info("✅ Tee sheet container found in HTML.")
    
    found = []
    for row in tee_sheet_table.find_all("div", class_="rwdTr"):
        cols = row.find_all("div", class_="rwdTd")
        if len(cols) >= 5:
            try:
                time_element = (cols[0].find("div", class_="time_slot") or 
                              cols[0].find("a", class_="teetime_button"))
                time_text = time_element.get_text(strip=True) if time_element else ""
                course = cols[2].get_text(strip=True)
                open_slots_text = cols[4].get_text(strip=True)
                
                row_time_obj = datetime.strptime(time_text, "%I:%M %p").time()
                
                if start_time <= row_time_obj <= end_time and "Open" in open_slots_text:
                    num_open = open_slots_text.split(" ")[0]
                    msg = f"{time_text} - {course} - {num_open} slots open"
                    found.append(msg)
            except (ValueError, IndexError):
                continue
    
    logging.info(f"✅ Found {len(found)} available tee times in time range.")
    return found

def parse_search_entry(entry):
    """Parse and validate a single search entry, returning (date_str, check_day, check_month, check_year, start_time, end_time, course) or raising ValueError"""
    date_str = entry["date"]
    start_time_str = entry["start"]
    end_time_str = entry["end"]
    course = entry.get("course", "All")

    start_time = datetime.strptime(start_time_str, "%I:%M %p").time()
    end_time = datetime.strptime(end_time_str, "%I:%M %p").time()
    check_date_obj = datetime.strptime(date_str, "%m/%d/%Y")
    check_day = str(check_date_obj.day)

    return date_str, check_day, check_date_obj.month, check_date_obj.year, start_time, end_time, course

def handle_results(found_times):
    """Handle results, check for new times, and send notifications"""
    previous = []
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                previous_data = json.load(f)
                previous = previous_data.get("results", [])
        except json.JSONDecodeError:
            logging.warning(f"Malformed {CACHE_FILE}, starting fresh.")
            previous = []
    
    # Clean up previous results
    if "No new tee times" in previous and len(previous) > 1:
        previous = [item for item in previous if item != "No new tee times"]
    
    new_times = [t for t in found_times if t not in previous]
    
    current_results = found_times if found_times else ["No new tee times found for the selected criteria."]
    
    # Save to cache
    with open(CACHE_FILE, "w") as cache_file:
        json.dump({"results": current_results}, cache_file)
    
    if new_times:
        logging.info("🎉 New tee times found:\n" + "\n".join(new_times))
        with open(LOG_FILE, "w") as f:
            f.write("\n".join(found_times))
        send_email("New Tee Times Available", "\n".join(new_times))
    else:
        logging.info("🟢 No new tee times found (or no changes since last check).")
    
    return found_times

def check_tee_times(searches):
    """Main function to check tee times across one or more date/time/course searches.

    `searches` is a list of dicts: [{"date": "MM/DD/YYYY", "start": "H:MM AM", "end": "H:MM AM", "course": "All"}, ...]
    A single browser session (one login) is reused across all entries.
    """

    # Prevent concurrent runs
    if not scraper_lock.acquire(blocking=False):
        logging.warning("⚠️ Scraper already running, skipping this run")
        return ["Scraper is already running. Please wait for it to complete."]

    if not searches:
        logging.error("❌ No search entries provided.")
        scraper_lock.release()
        return ["Error: No search configuration provided."]

    logging.info(f"🚀 Starting check for {len(searches)} search(es): {searches}")
    browser = None
    page = None

    try:
        # Validate credentials
        if not USERNAME or not PASSWORD:
            error_msg = "Prestonwood login credentials not set as environment variables."
            logging.error(error_msg)
            return [error_msg]

        # Pre-validate all entries up front so a bad entry doesn't waste a login
        parsed_entries = []
        parse_errors = []
        for entry in searches:
            try:
                parsed_entries.append(parse_search_entry(entry))
            except (ValueError, KeyError) as e:
                logging.error(f"❌ Invalid search entry {entry}: {e}")
                parse_errors.append(f"Error: Invalid search entry {entry}: {e}")

        if not parsed_entries:
            return parse_errors or ["Error: No valid search entries provided."]

        # Launch browser
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--no-zygote',
                    '--single-process',
                    '--disable-blink-features=AutomationControlled'
                ]
            )

            page = browser.new_page()
            page.set_default_timeout(60000)

            # Step 1: Login
            perform_login(page)

            # Step 2: Handle member area button
            handle_member_area_button(page)

            # Step 3: Navigate to tee sheet
            navigate_to_tee_sheet(page)

            # Step 4: Wait for iframe
            iframe = wait_for_iframe(page)

            # Steps 5-7: For each search entry, select date, set course, and parse tee times
            all_found = []
            for date_str, check_day, check_month, check_year, start_time, end_time, course in parsed_entries:
                logging.info(f"🔎 Checking {date_str} ({start_time}-{end_time}), course: {course}")
                select_date_on_calendar(iframe, page, check_day, target_month=check_month, target_year=check_year)
                set_course(iframe, page, course)
                found_times = parse_tee_times(iframe, page, start_time, end_time)
                all_found.extend(f"{date_str}: {t}" for t in found_times)

            all_found.extend(parse_errors)

            # Step 8: Handle results
            result = handle_results(all_found)

            # Close browser before releasing lock
            browser.close()
            browser = None
            logging.info("🔚 Browser closed successfully.")

            return result
    
    except PlaywrightTimeoutError as e:
        logging.error(f"⏰ Playwright timeout error: {e}")
        error_msg = f"Timeout error during scraping: {e}"
        if page:
            take_screenshot(page, "error_timeout")
        with open(CACHE_FILE, "w") as cache_file:
            json.dump({"results": [error_msg]}, cache_file)
        return [error_msg]
    
    except Exception as e:
        logging.error(f"💥 Unexpected error during scraping: {e}")
        error_message = f"An error occurred during scraping: {e}"
        if page:
            take_screenshot(page, "error_state")
        with open(CACHE_FILE, "w") as cache_file:
            json.dump({"results": [error_message]}, cache_file)
        return [error_message]
    
    finally:
        # Ensure browser is closed even if there's an error
        if browser:
            try:
                browser.close()
                logging.info("🔚 Browser closed in finally block.")
            except Exception as e:
                logging.warning(f"⚠️ Error closing browser: {e}")
        
        scraper_lock.release()
        logging.info("=" * 60)

def get_cached_tee_times():
    """Retrieve cached tee times"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                return data.get("results", ["No cached tee times found."])
        except json.JSONDecodeError:
            return ["Error reading cached_results.json, file might be corrupted."]
    else:
        return ["No cached tee times found (cache file does not exist)."]
