#!/usr/bin/env python3
"""
My Crew Schedule Monitor & Downloader - Server Edition
Optimized for Koyeb deployment
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
from datetime import datetime
import schedule

class CrewScheduleBot:
    def __init__(self, headless=True):
        self.setup_logging()
        self.driver = None
        self.is_logged_in = False
        self.headless = headless
        self.setup_driver()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Setup Chrome driver for server environment"""
        chrome_options = Options()
        
        # Required for server environment
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--window-size=1920,1080')
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Mobile emulation for better compatibility
        mobile_emulation = {
            "deviceMetrics": { "width": 375, "height": 812, "pixelRatio": 3.0 },
            "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        }
        chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
        
        # Anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def login(self, email, password):
        """Login to mycrew.avianca.com"""
        try:
            self.logger.info("Navigating to login page...")
            self.driver.get('https://mycrew.avianca.com')
            
            # Wait for login form
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            
            # Fill email
            email_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            email_field.clear()
            email_field.send_keys(email)
            
            # Fill password
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.clear()
            password_field.send_keys(password)
            
            # Click login button
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            # Wait for login to complete
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .schedule, [class*='menu'], button"))
            )
            
            self.is_logged_in = True
            self.logger.info("✅ Login successful!")
            return True
            
        except TimeoutException:
            self.logger.error("❌ Login failed - timeout waiting for elements")
            return False
        except Exception as e:
            self.logger.error(f"❌ Login failed: {str(e)}")
            return False
    
    def download_schedule(self, schedule_type="actual", crew_id="", month="", year="2025"):
        """Download schedule PDF"""
        try:
            if not self.is_logged_in:
                self.logger.error("Not logged in. Please login first.")
                return False
            
            self.logger.info(f"Downloading {schedule_type} schedule...")
            
            # Navigate to schedule page
            self.driver.get('https://mycrew.avianca.com/MonthlyAssignments')
            
            # Wait for schedule page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form, button, input"))
            )
            
            # Fill form data
            forms = self.driver.find_elements(By.CSS_SELECTOR, "form")
            target_form = None
            
            for form in forms:
                if schedule_type.lower() == "scheduled" and "SCHEDULED" in form.text.upper():
                    target_form = form
                    break
                elif schedule_type.lower() == "actual" and "ACTUAL" in form.text.upper():
                    target_form = form
                    break
            
            if not target_form:
                self.logger.error(f"Could not find {schedule_type} form")
                return False
            
            # Fill form fields
            holding_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Holding']")
            crew_id_field = target_form.find_element(By.CSS_SELECTOR, "input[name='CrewMemberUniqueId']")
            year_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Year']")
            month_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Month']")
            
            holding_field.clear()
            holding_field.send_keys("AV")
            
            crew_id_field.clear()
            crew_id_field.send_keys(crew_id or "32385184")
            
            year_field.clear()
            year_field.send_keys(year)
            
            month_field.clear()
            month_field.send_keys(month or str(datetime.now().month))
            
            # Find and click download button
            download_btn = target_form.find_element(By.CSS_SELECTOR, "button")
            download_btn.click()
            
            # Wait for download
            time.sleep(10)
            
            self.logger.info(f"✅ {schedule_type.capitalize()} schedule download initiated!")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Download failed: {str(e)}")
            return False
    
    def check_schedule_updates(self):
        """Check for schedule updates (simplified)"""
        try:
            self.logger.info("🔍 Checking for schedule updates...")
            
            if not self.is_logged_in:
                # Get credentials from environment
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return False
            
            # Navigate to schedule page
            self.driver.get('https://mycrew.avianca.com/MonthlyAssignments')
            
            # Simple check - just see if page loads successfully
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            
            self.logger.info("✅ Schedule check completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Schedule check failed: {str(e)}")
            return False
    
    def save_session(self):
        """Save cookies for persistent login"""
        try:
            cookies = self.driver.get_cookies()
            with open('/tmp/session_cookies.json', 'w') as f:
                json.dump(cookies, f)
            self.logger.info("Session cookies saved")
        except Exception as e:
            self.logger.error(f"Could not save session: {e}")
    
    def load_session(self):
        """Load saved session cookies"""
        try:
            with open('/tmp/session_cookies.json', 'r') as f:
                cookies = json.load(f)
            
            self.driver.get('https://mycrew.avianca.com')
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            
            self.driver.refresh()
            time.sleep(3)
            
            # Check if still logged in
            if "login" not in self.driver.current_url.lower():
                self.is_logged_in = True
                self.logger.info("Session restored from cookies")
                return True
            else:
                return False
                
        except FileNotFoundError:
            self.logger.info("No saved session found")
            return False
        except Exception as e:
            self.logger.error(f"Could not load session: {e}")
            return False
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.save_session()
            self.driver.quit()
            self.logger.info("Browser closed")

def run_scheduled_check():
    """Function to run scheduled checks"""
    bot = CrewScheduleBot(headless=True)
    try:
        # Try to load session first
        if not bot.load_session():
            # Fresh login
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            if bot.login(email, password):
                bot.save_session()
        
        bot.check_schedule_updates()
        
    except Exception as e:
        logging.error(f"Scheduled check failed: {e}")
    finally:
        bot.close()

def main():
    """Main function for Koyeb deployment"""
    bot = CrewScheduleBot(headless=True)
    
    try:
        # Get credentials from environment variables
        email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
        password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
        
        # Try to load existing session
        if not bot.load_session():
            # Fresh login
            if bot.login(email, password):
                bot.save_session()
        
        # Set up scheduled tasks
        schedule.every(1).hour.do(run_scheduled_check)
        schedule.every().day.at("06:00").do(lambda: bot.download_schedule("actual"))
        schedule.every().day.at("06:05").do(lambda: bot.download_schedule("scheduled"))
        
        logging.info("🚀 Crew Schedule Bot started on Koyeb!")
        logging.info("Scheduled tasks:")
        logging.info("  - Schedule check: every 1 hour")
        logging.info("  - Download actual schedule: daily at 06:00")
        logging.info("  - Download scheduled schedule: daily at 06:05")
        
        # Keep the application running
        while True:
            schedule.run_pending()
            time.sleep(60)
            
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Application error: {e}")
    finally:
        bot.close()

if __name__ == "__main__":
    main()