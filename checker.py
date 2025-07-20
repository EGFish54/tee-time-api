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
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL") or GMAIL_USER

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_PASS or not RECIPIENT_EMAIL:
        logging.error("Email credentials (GMAIL_USER, GMAIL_PASS, RECIPIENT_EMAIL) are not fully set. Cannot send email.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        logging.info("📧 Email sent!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        if hasattr(e, 'smtp_code') and hasattr(e, 'smtp_error'):
            logging.error(f"SMTP Error Code: {e.smtp_code}, Message: {e.smtp_error}")

def take_screenshot(page, name_prefix="screenshot"):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{timestamp}.png")
        page.screenshot(path=screenshot_path)
        logging.info(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        logging.error(f"Could not take screenshot {name_prefix}: {e}")

def check_tee_times(date_str, start_str, end_str):
    logging.info(f"Scraper received config: Date={date_str}, Start={start_str}, End={end_str}")

    try:
        target_date = datetime.strptime(date_str, "%m/%d/%Y")
        start_time_obj = datetime.strptime(start_str, "%I:%M %p").time()
        end_time_obj = datetime.strptime(end_str, "%I:%M %p").time()
        check_day = str(target_date.day)

    except ValueError as e:
        logging.error(f"Configuration parsing error: {e}. Please check date/time formats.")
        return [f"Error: Invalid date/time format in config: {e}"]

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()

            logging.info("🔐 Logging in via Playwright")
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=90000)
            take_screenshot(page, "after_initial_login_page_load")

            current_url = page.url
            logging.info(f"Current URL after initial goto: {current_url}")

            try:
                page_content = page.content()
                logging.info(f"Snippet of main page HTML after goto (first 1000 chars):\n{page_content[:1000]}...")
                if "lgUserName" in page_content: # Check for the specific login form elements
                    logging.info("HTML content contains 'lgUserName' (main page).")
                if "lgPassword" in page_content:
                    logging.info("HTML content contains 'lgPassword' (main page).")
                if "lgLoginButton" in page_content:
                    logging.info("HTML content contains 'lgLoginButton' (main page).")
            except Exception as e:
                logging.error(f"Failed to get main page content for debugging: {e}")

            # --- Simplified Login Logic based on main.py ---
            # Assume login elements are directly on the main page for initial login
            try:
                # Wait for the username field, as this is the first interaction
                logging.info("Waiting for initial login form elements: #lgUserName, #lgPassword, #lgLoginButton.")
                page.wait_for_selector("#lgUserName", state='visible', timeout=60000)
                
                logging.info("Filling username and password.")
                page.fill("#lgUserName", USERNAME)
                page.fill("#lgPassword", PASSWORD)
                
                logging.info("Clicking login button.")
                page.click("#lgLoginButton")
                
                # Wait for the URL to change, indicating successful login/redirection
                logging.info("Waiting for URL change after login button click.")
                page.wait_for_url(lambda url: url != LOGIN_URL, timeout=60000)
                take_screenshot(page, "after_successful_initial_login_redirect")
                logging.info("✅ Initial login successful and redirected.")

            except Exception as e:
                logging.error(f"❌ Failed initial login using main.py strategy: {e}")
                take_screenshot(page, "failed_initial_login")
                return [f"Error: Initial login failed: {e}"]

            # --- After initial login, check for "ENTER MEMBER AREA" or proceed ---
            # This part of checker.py's original logic can remain, as it handles the *post-login* page
            member_area_button_selector = "button:has-text('ENTER MEMBER AREA')"

            # Check if we landed on the "ENTER MEMBER AREA" page
            if page.locator(member_area_button_selector).is_visible():
                logging.info("✅ 'ENTER MEMBER AREA' button found after initial login. Clicking to proceed.")
                page.click(member_area_button_selector, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=60000)
                take_screenshot(page, "after_enter_member_area_click")

                logging.info("➡️ Navigating to Member Central page after bypass.")
                page.goto("https://www.prestonwood.com/member-central-18.html", wait_until="networkidle", timeout=90000)
                take_screenshot(page, "after_member_central_navigation")
            else:
                logging.info("No 'ENTER MEMBER AREA' button found. Assuming direct access to member area or proceeding as normal.")
            # --- END LOGIN LOGIC (now it's a 2-stage process if needed) ---

            logging.info("➡️ Navigating to tee times page.")
            page.goto(TEE_SHEET_URL, wait_until="load", timeout=90000)
            take_screenshot(page, "after_tee_sheet_load")
            
            logging.info("Waiting for a key element on the main tee sheet page (#content) to confirm load.")
            page.wait_for_selector("#content", timeout=90000)
            take_screenshot(page, "after_tee_sheet_main_page_loaded_element")

            logging.info("🔍 Searching for iframe 'ifrforetees'.")
            iframe_handle = page.wait_for_selector("iframe#ifrforetees", timeout=60000)
            if iframe_handle:
                logging.info("✅ Found iframe 'ifrforetees'. Waiting for iframe content to load (domcontentloaded).")
                iframe = iframe_handle.content_frame()
                iframe.wait_for_load_state("domcontentloaded", timeout=90000)
                take_screenshot(page, "after_iframe_dom_load")

                logging.info("✅ Iframe content loaded (domcontentloaded). Waiting for networkidle in iframe.")
                iframe.wait_for_load_state("networkidle", timeout=90000)
                page.wait_for_timeout(5000) # Wait 5 seconds for elements to settle
                take_screenshot(page, "after_iframe_network_idle_and_wait")

                logging.info(f"📅 Attempting to select date: {date_str} (Day: {check_day}) by waiting for #member_select_calendar1 within iframe.")
                iframe.wait_for_selector("#member_select_calendar1", timeout=60000)
                take_screenshot(page, "before_date_selection_in_iframe")
                
                logging.info(f"📆 Clicking on target date: {check_day}")
                try:
                    iframe.locator(f"td a:has-text('{check_day}')").first.click(timeout=30000)
                except Exception as click_e:
                    logging.warning(f"Could not click date '{check_day}' directly: {click_e}. Trying alternative.")
                    iframe.locator(f"//td[contains(@class, 'ui-datepicker-week-end') or contains(@class, 'ui-datepicker-unselectable') or contains(@class, 'ui-datepicker-current-day')]//a[text()='{check_day}']").click(timeout=30000)

                take_screenshot(page, "after_date_click_in_iframe")

                iframe.wait_for_load_state("networkidle", timeout=90000)
                page.wait_for_timeout(5000) # Wait 5 seconds for elements to settle
                take_screenshot(page, "after_date_selection_refresh_iframe_and_wait")

                logging.info("📄 Waiting for tee sheet content to be stable before course selection.")
                # Ensure the tee sheet table is present and stable *before* attempting course dropdown
                iframe.wait_for_selector("div.member_sheet_table", state='visible', timeout=60000)
                logging.info("✅ Tee sheet table visible. Proceeding to course selection.")


                logging.info("🔄 Attempting to set course to '-ALL-' using robust search from main.py logic.")
                course_selected = False
                # Get all select elements within the iframe
                select_elements = iframe.query_selector_all("select") 
                
                for select_el_handle in select_elements:
                    try:
                        # Get the outerHTML of the select element to inspect its options
                        select_html = select_el_handle.evaluate("node => node.outerHTML")
                        
                        # Check if the "-ALL-" option exists within this select element
                        # The 'value' could be different from '-ALL-', but 'label' (visible text) is usually '-ALL-'
                        if "-ALL-" in select_html: 
                            # If we find it, select it by its label
                            select_el_handle.select_option(label="-ALL-")
                            logging.info("✅ Course set to '-ALL-'.")
                            course_selected = True
                            break # Exit loop once found and selected
                    except Exception as select_e:
                        logging.warning(f"Could not process select element or select option: {select_e}")
                
                if not course_selected:
                    logging.warning("❌ '-ALL-' course option not found after iterating through all select elements.")
                    take_screenshot(page, "course_all_not_found_robust_search")
                
                # Wait for page to settle after changing dropdown
                iframe.wait_for_load_state("networkidle", timeout=90000)
                take_screenshot(page, "after_course_select_robust_search")
                
                logging.info("📄 Parsing tee sheet content.")
                iframe.wait_for_selector("div.member_sheet_table", timeout=60000)
                tee_sheet_html = iframe.content()
                
                soup = BeautifulSoup(tee_sheet_html, "html.parser")
                tee_sheet_table = soup.find("div", class_="member_sheet_table")

                if not tee_sheet_table:
                    logging.warning("⚠️ Tee sheet container not found in HTML. Check selector or page load.")
                    take_screenshot(page, "error_tee_sheet_table_missing")
                    return ["No tee sheet table found."]

                logging.info("✅ Tee sheet container found in HTML.")
                
                found = []
                for row in tee_sheet_table.find_all("div", class_="rwdTr"):
                    cols = row.find_all("div", class_="rwdTd")
                    if len(cols) >= 5:
                        try:
                            time_element = cols[0].find("div", class_="time_slot") or cols[0].find("a", class_="teetime_button")
                            time_text = time_element.get_text(strip=True) if time_element else ""
                            course = cols[2].get_text(strip=True)
                            open_slots_text = cols[4].get_text(strip=True)

                            row_time_obj = datetime.strptime(time_text, "%I:%M %p").time()

                            if start_time_obj <= row_time_obj <= end_time_obj and "Open" in open_slots_text:
                                num_open = open_slots_text.split(" ")[0]
                                msg = f"{time_text} - {course} - {num_open} slots open"
                                found.append(msg)
                        except ValueError:
                            continue
                        except IndexError:
                            continue

                previous = []
                if os.path.exists(CACHE_FILE):
                    try:
                        with open(CACHE_FILE, "r") as f:
                            previous_data = json.load(f)
                            previous = previous_data.get("results", [])
                    except json.JSONDecodeError:
                        logging.warning(f"Malformed {CACHE_FILE}, starting fresh for previous times.")
                        previous = []
                
                if "No new tee times" in previous and len(previous) > 1:
                    previous = [item for item in previous if item != "No new tee times"]

                new_times = [t for t in found if t not in previous]

                current_results = found if found else ["No new tee times found for the selected criteria."]
                
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": current_results}, cache_file)


                if new_times:
                    logging.info("✅ New tee times found:\n" + "\n".join(new_times))
                    with open(LOG_FILE, "w") as f:
                        f.write("\n".join(found))
                    send_email("New Tee Times Available", "\n".join(new_times))
                    return new_times
                else:
                    logging.info("🟢 No new tee times found (or no changes since last check).")
                    return ["No new tee times found (or no changes since last check)."]

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
