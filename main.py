#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Using undetected-chromedriver
"""

import os
import time
import logging
import requests
import schedule
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CrewAPIClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://api-avianca.avianca.com"
        self.is_logged_in = False
        self.auth_token = None
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        
    def login(self, email, password):
        """Login using the API"""
        try:
            logger.info("🔐 Attempting API login...")
            
            # Prepare login data
            login_data = {
                "username": email,
                "password": password,
                "grant_type": "password",
                "client_id": "angularclient",
                "client_secret": "angularclient"
            }
            
            # Make login request
            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = self.session.post(
                f"{self.base_url}/MyCrewSecurity/connect/token",
                data=login_data,
                headers=headers
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = f"Bearer {token_data['access_token']}"
                self.is_logged_in = True
                logger.info("✅ API login successful!")
                return True
            else:
                logger.error(f"❌ API login failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    def download_schedule(self, schedule_type="actual", crew_id="32385184", month="", year="2025"):
        """Download schedule using API"""
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return False
            
            logger.info(f"📥 Downloading {schedule_type} schedule via API...")
            
            # Determine endpoint
            if schedule_type.lower() == "scheduled":
                url = f"{self.base_url}/MycreWFlights/api/MonthlyAssignements/Scheduled/Export"
            else:
                url = f"{self.base_url}/MycreWFlights/api/MonthlyAssignements/Export"
            
            # Prepare request data
            data = {
                "Holding": "AV",
                "CrewMemberUniqueId": crew_id,
                "Year": year,
                "Month": month or str(datetime.now().month)
            }
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/json"
            }
            
            # Make the request
            response = self.session.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                # Save the PDF file
                filename = f"{schedule_type}_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                logger.info(f"✅ Schedule downloaded: {filename}")
                return True
            else:
                logger.error(f"❌ Download failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return False
    
    def health_check(self):
        """Check if API is accessible"""
        try:
            logger.info("🏥 Running API health check...")
            
            # Try to access a public endpoint or check connectivity
            test_url = f"{self.base_url}/MycreWFlights/api/MonthlyAssignements/Export"
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key
            }
            
            response = self.session.options(test_url, headers=headers)
            
            if response.status_code in [200, 404, 405]:
                logger.info("✅ API connectivity check passed")
                return True
            else:
                logger.error(f"❌ API connectivity check failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            return False

def run_health_check():
    """Function to run health checks"""
    client = CrewAPIClient()
    try:
        success = client.health_check()
        if success:
            logger.info("🏥 Health check: PASSED")
        else:
            logger.error("🏥 Health check: FAILED")
        return success
    except Exception as e:
        logger.error(f"🏥 Health check error: {e}")
        return False

def run_daily_download():
    """Function to run daily downloads"""
    client = CrewAPIClient()
    try:
        logger.info("🔄 Starting daily download cycle...")
        
        # Download both schedule types
        actual_success = client.download_schedule("actual")
        time.sleep(2)
        scheduled_success = client.download_schedule("scheduled")
        
        if actual_success and scheduled_success:
            logger.info("✅ Daily downloads completed successfully!")
        else:
            logger.warning("⚠️ Some downloads may have failed")
            
    except Exception as e:
        logger.error(f"❌ Daily download error: {e}")

def test_download():
    """Test function for immediate download"""
    client = CrewAPIClient()
    try:
        logger.info("🧪 Running test download...")
        success = client.download_schedule("actual")
        if success:
            logger.info("✅ Test download successful!")
        else:
            logger.error("❌ Test download failed")
    except Exception as e:
        logger.error(f"❌ Test error: {e}")

def main():
    """Main function for Koyeb deployment"""
    logger.info("🚀 Crew Schedule Bot starting on Koyeb...")
    logger.info(f"📧 Using email: {os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')}")
    logger.info("🔧 Using API-based approach (no browser required)")
    
    # Initial health check
    if run_health_check():
        logger.info("🎉 Application started successfully!")
        
        # Run a test download immediately
        test_download()
    else:
        logger.error("💥 Application failed initial health check!")
    
    # Set up scheduled tasks
    schedule.every(30).minutes.do(run_health_check)
    schedule.every().day.at("06:00").do(run_daily_download)
    schedule.every().day.at("18:00").do(run_daily_download)  # Additional evening check
    
    logger.info("📅 Scheduled tasks configured:")
    logger.info("  - Health check: every 30 minutes")
    logger.info("  - Daily downloads: 06:00 and 18:00 UTC")
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