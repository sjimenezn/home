#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Koyeb Deployment
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CrewScheduleBot:
    def __init__(self, headless=True):
        self.driver = None
        self.is_logged_in = False
        self.headless = headless
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome driver for server environment"""
        try:
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
            logger.info("✅ Chrome driver initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Chrome driver: {e}")
            raise
    
    def login(self, email, password):
        """Login to mycrew.avianca.com"""
        try:
            logger.info("🌐 Navigating to login page...")
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
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .schedule, [class*='menu'], button, form"))
            )
            
            self.is_logged_in = True
            logger.info("✅ Login successful!")
            return True
            
        except TimeoutException:
            logger.error("❌ Login failed - timeout waiting for elements")
            # Take screenshot for debugging
            try:
                self.driver.save_screenshot('/tmp/login_timeout.png')
                logger.info("📸 Screenshot saved to /tmp/login_timeout.png")
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"❌ Login failed: {str(e)}")
            return False
    
    def health_check(self):
        """Check if the service is working"""
        try:
            logger.info("🏥 Running health check...")
            
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
            
            # Check for forms
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            logger.info(f"📋 Found {len(forms)} forms on schedule page")
            
            logger.info("✅ Health check passed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {str(e)}")
            return False
    
    def download_schedule(self, schedule_type="actual"):
        """Download schedule PDF"""
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return False
            
            logger.info(f"📥 Attempting to download {schedule_type} schedule...")
            
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
                logger.error(f"❌ Could not find {schedule_type} form")
                return False
            
            logger.info(f"✅ Found {schedule_type} form")
            
            # Fill form fields
            current_month = str(datetime.now().month)
            current_year = str(datetime.now().year)
            
            # Try to fill each field, but continue if some fail
            fields_to_fill = [
                ("input[name='Holding']", "AV"),
                ("input[name='CrewMemberUniqueId']", "32385184"),
                ("input[name='Year']", current_year),
                ("input[name='Month']", current_month)
            ]
            
            for selector, value in fields_to_fill:
                try:
                    field = target_form.find_element(By.CSS_SELECTOR, selector)
                    field.clear()
                    field.send_keys(value)
                    logger.info(f"✅ Filled {selector} with {value}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not fill {selector}: {e}")
            
            # Find and click download button
            download_btn = target_form.find_element(By.TAG_NAME, "button")
            download_btn.click()
            
            logger.info(f"✅ Clicked download button for {schedule_type} schedule")
            
            # Wait for download to initiate
            time.sleep(10)
            
            logger.info(f"✅ {schedule_type.capitalize()} schedule download process completed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Download failed: {str(e)}")
            return False
    
    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Browser closed")
            except Exception as e:
                logger.error(f"❌ Error closing browser: {e}")

def run_health_check():
    """Function to run health checks"""
    bot = CrewScheduleBot(headless=True)
    try:
        success = bot.health_check()
        if success:
            logger.info("🏥 Health check: PASSED")
        else:
            logger.error("🏥 Health check: FAILED")
        return success
    except Exception as e:
        logger.error(f"🏥 Health check error: {e}")
        return False
    finally:
        bot.close()

def run_daily_download():
    """Function to run daily downloads"""
    bot = CrewScheduleBot(headless=True)
    try:
        logger.info("🔄 Starting daily download cycle...")
        
        # Download both schedule types
        actual_success = bot.download_schedule("actual")
        time.sleep(5)
        scheduled_success = bot.download_schedule("scheduled")
        
        if actual_success and scheduled_success:
            logger.info("✅ Daily downloads completed successfully!")
        else:
            logger.warning("⚠️ Some downloads may have failed")
            
    except Exception as e:
        logger.error(f"❌ Daily download error: {e}")
    finally:
        bot.close()

def main():
    """Main function for Koyeb deployment"""
    logger.info("🚀 Crew Schedule Bot starting on Koyeb...")
    logger.info(f"📧 Using email: {os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')}")
    
    # Initial health check
    if run_health_check():
        logger.info("🎉 Application started successfully!")
    else:
        logger.error("💥 Application failed initial health check!")
    
    # Set up scheduled tasks
    schedule.every(30).minutes.do(run_health_check)
    schedule.every().day.at("06:00").do(run_daily_download)
    
    logger.info("📅 Scheduled tasks configured:")
    logger.info("  - Health check: every 30 minutes")
    logger.info("  - Daily downloads: 06:00 UTC")
    logger.info("⏰ Current UTC time: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Keep the application running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down...")
            break
        except Exception as e:
            logger.error(f"⚠️ Scheduler error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()