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
    """Send email using SendGrid API (works on Render free tier)"""
    
    # Get SendGrid API key from environment
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
    
    if not SENDGRID_API_KEY:
        logging.error("SendGrid API key not set. Cannot send email.")
        return
    
    # Must use the verified sender email from SendGrid
    from_email = "dan.chodos@gmail.com"
    
    # SendGrid API endpoint
    url = "https://api.sendgrid.com/v3/mail/send"
    
    # Send only to Gmail for now
    recipients = [{"email": "dan.chodos@gmail.com"}]
    
    # Prepare the email data
    data = {
        "personalizations": [
            {
                "to": recipients,
                "subject": subject
            }
        ],
        "from": {"email": from_email},
        "content": [
            {
                "type": "text/plain",
                "value": body
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code == 202:
            logging.info("📧 Email sent successfully via SendGrid!")
        else:
            logging.error(f"❌ SendGrid API error: {response.status_code} - {response.text}")
    
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to send email via SendGrid: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error sending email: {e}")

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

def select_date_on_calendar(iframe, page, check_day):
    """Select date on the calendar"""
    logging.info(f"📅 Attempting to select date (Day: {check_day})")
    
    iframe.wait_for_selector("#member_select_calendar1", timeout=60000)
    time.sleep(2)  # Let calendar render
    take_screenshot(page, "before_date_selection_in_iframe")
    
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

def set_course_to_all(iframe, page):
    """Set course dropdown to '-ALL-'"""
    logging.info("🎯 Attempting to set course to '-ALL-'.")
    time.sleep(2)  # Wait for dropdown to be ready
    
    course_selected = False
    select_elements = iframe.query_selector_all("select")
    
    for select_el_handle in select_elements:
        try:
            select_html = select_el_handle.evaluate("node => node.outerHTML")
            if "-ALL-" in select_html:
                select_el_handle.select_option(label="-ALL-")
                logging.info("✅ Course set to '-ALL-'.")
                course_selected = True
                break
        except Exception as select_e:
            logging.warning(f"⚠️ Could not process select element: {select_e}")
    
    if not course_selected:
        logging.warning("⚠️ '-ALL-' course option not found.")
        take_screenshot(page, "course_all_not_found_robust_search")
    else:
        iframe.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(3)  # Wait for tee times to reload
        take_screenshot(page, "after_course_select_robust_search")
    
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

def check_tee_times(date_str, start_time_str, end_time_str):
    """Main function to check tee times with improved error handling and concurrency control"""
    
    # Prevent concurrent runs
    if not scraper_lock.acquire(blocking=False):
        logging.warning("⚠️ Scraper already running, skipping this run")
        return ["Scraper is already running. Please wait for it to complete."]
    
    logging.info(f"🚀 Starting check for date: {date_str}, {start_time_str}-{end_time_str}")
    browser = None
    page = None
    
    try:
        # Validate credentials
        if not USERNAME or not PASSWORD:
            error_msg = "Prestonwood login credentials not set as environment variables."
            logging.error(error_msg)
            return [error_msg]
        
        # Parse configuration
        try:
            START_TIME = datetime.strptime(start_time_str, "%I:%M %p").time()
            END_TIME = datetime.strptime(end_time_str, "%I:%M %p").time()
            check_date_obj = datetime.strptime(date_str, "%m/%d/%Y")
            CHECK_DAY = str(check_date_obj.day)
        except ValueError as e:
            logging.error(f"❌ Configuration parsing error: {e}")
            return [f"Error: Invalid date/time format: {e}"]
        
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
            
            # Step 5: Select date
            select_date_on_calendar(iframe, page, CHECK_DAY)
            
            # Step 6: Set course to ALL
            set_course_to_all(iframe, page)
            
            # Step 7: Parse tee times
            found_times = parse_tee_times(iframe, page, START_TIME, END_TIME)
            
            # Step 8: Handle results
            result = handle_results(found_times)
            
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
