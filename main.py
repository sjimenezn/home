#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Simplified for Koyeb
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import schedule
from datetime import datetime

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
            handlers=[logging.StreamHandler()]
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
    
    def check_availability(self):
        """Check if schedule page is accessible"""
        try:
            self.logger.info("🔍 Checking schedule availability...")
            
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return False
            
            # Navigate to schedule page
            self.driver.get('https://mycrew.avianca.com/MonthlyAssignments')
            
            # Check if page loads successfully
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            self.logger.info("✅ Schedule page is accessible")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Schedule check failed: {str(e)}")
            return False
    
    def download_schedule(self, schedule_type="actual"):
        """Download schedule PDF"""
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return False
            
            self.logger.info(f"📥 Downloading {schedule_type} schedule...")
            
            # Navigate to schedule page
            self.driver.get('https://mycrew.avianca.com/MonthlyAssignments')
            
            # Wait for schedule page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "form, button, input"))
            )
            
            # Find the correct form based on schedule type
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            target_form = None
            
            for form in forms:
                form_text = form.text.upper()
                if schedule_type.upper() == "SCHEDULED" and "SCHEDULED" in form_text:
                    target_form = form
                    break
                elif schedule_type.upper() == "ACTUAL" and "ACTUAL" in form_text:
                    target_form = form
                    break
            
            if not target_form:
                self.logger.error(f"❌ Could not find {schedule_type} form")
                return False
            
            # Fill form fields
            current_month = str(datetime.now().month)
            current_year = str(datetime.now().year)
            
            try:
                holding_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Holding']")
                holding_field.clear()
                holding_field.send_keys("AV")
            except:
                pass
            
            try:
                crew_field = target_form.find_element(By.CSS_SELECTOR, "input[name='CrewMemberUniqueId']")
                crew_field.clear()
                crew_field.send_keys("32385184")
            except:
                pass
            
            try:
                year_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Year']")
                year_field.clear()
                year_field.send_keys(current_year)
            except:
                pass
            
            try:
                month_field = target_form.find_element(By.CSS_SELECTOR, "input[name='Month']")
                month_field.clear()
                month_field.send_keys(current_month)
            except:
                pass
            
            # Find and click download button
            download_btn = target_form.find_element(By.TAG_NAME, "button")
            download_btn.click()
            
            # Wait for download to initiate
            time.sleep(10)
            
            self.logger.info(f"✅ {schedule_type.capitalize()} schedule download initiated!")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Download failed: {str(e)}")
            return False
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Browser closed")

def run_health_check():
    """Function to run health checks"""
    bot = CrewScheduleBot(headless=True)
    try:
        success = bot.check_availability()
        if success:
            logging.info("🏥 Health check: PASSED")
        else:
            logging.error("🏥 Health check: FAILED")
    except Exception as e:
        logging.error(f"🏥 Health check error: {e}")
    finally:
        bot.close()

def run_daily_download():
    """Function to run daily downloads"""
    bot = CrewScheduleBot(headless=True)
    try:
        # Download both schedule types
        bot.download_schedule("actual")
        time.sleep(5)
        bot.download_schedule("scheduled")
    except Exception as e:
        logging.error(f"Daily download error: {e}")
    finally:
        bot.close()

def main():
    """Main function for Koyeb deployment"""
    logging.info("🚀 Crew Schedule Bot starting on Koyeb...")
    
    # Initial health check
    run_health_check()
    
    # Set up scheduled tasks
    schedule.every(30).minutes.do(run_health_check)
    schedule.every().day.at("06:00").do(run_daily_download)
    
    logging.info("📅 Scheduled tasks configured:")
    logging.info("  - Health check: every 30 minutes")
    logging.info("  - Daily downloads: 06:00 UTC")
    
    # Keep the application running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
            break
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()