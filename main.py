#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Fixed Multipart Format
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
        self.base_url = "https://api-avianca.avianca.com/MycreWFlights/api"
        self.auth_url = "https://api-avianca.avianca.com/MyCrewSecurity/connect/token"
        self.is_logged_in = False
        self.auth_token = None
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        
    def login(self, email, password):
        """Login using the API with correct multipart format"""
        try:
            logger.info("🔐 Attempting API login...")
            
            # Create proper multipart form data with exact format from traffic
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            
            # Build multipart body exactly like browser
            body_parts = [
                f"--{boundary}",
                'Content-Disposition: form-data; name="username"',
                '',
                email,
                f"--{boundary}",
                'Content-Disposition: form-data; name="password"', 
                '',
                password,
                f"--{boundary}",
                'Content-Disposition: form-data; name="grant_type"',
                '',
                'password',
                f"--{boundary}",
                'Content-Disposition: form-data; name="client_id"',
                '',
                'angularclient',
                f"--{boundary}",
                'Content-Disposition: form-data; name="client_secret"',
                '',
                'angularclient',
                f"--{boundary}--",
                ''
            ]
            
            form_data = "\r\n".join(body_parts)
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            logger.info(f"📤 Sending login request to: {self.auth_url}")
            
            response = self.session.post(
                self.auth_url,
                data=form_data,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"📥 Login response status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = f"Bearer {token_data['access_token']}"
                self.is_logged_in = True
                logger.info("✅ API login successful!")
                logger.info(f"📝 Token type: {token_data.get('token_type', 'Unknown')}")
                logger.info(f"⏰ Expires in: {token_data.get('expires_in', 'Unknown')} seconds")
                return True
            else:
                logger.error(f"❌ API login failed: {response.status_code}")
                if response.text:
                    logger.error(f"Response body: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during login: {e}")
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
                    logger.error("❌ Cannot download - login failed")
                    return False
            
            logger.info(f"📥 Downloading {schedule_type} schedule...")
            
            # Determine endpoint
            if schedule_type.lower() == "scheduled":
                url = f"{self.base_url}/MonthlyAssignements/Scheduled/Export"
            else:
                url = f"{self.base_url}/MonthlyAssignements/Export"
            
            # Create multipart form data for schedule request
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            current_month = month or str(datetime.now().month)
            
            body_parts = [
                f"--{boundary}",
                'Content-Disposition: form-data; name="Holding"',
                '',
                'AV',
                f"--{boundary}",
                'Content-Disposition: form-data; name="CrewMemberUniqueId"',
                '',
                crew_id,
                f"--{boundary}",
                'Content-Disposition: form-data; name="Year"',
                '',
                year,
                f"--{boundary}",
                'Content-Disposition: form-data; name="Month"',
                '',
                current_month,
                f"--{boundary}--",
                ''
            ]
            
            form_data = "\r\n".join(body_parts)
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            logger.info(f"🌐 Making schedule request to: {url}")
            logger.info(f"📦 With data: Holding=AV, CrewID={crew_id}, Year={year}, Month={current_month}")
            
            response = self.session.post(url, data=form_data, headers=headers, timeout=30)
            
            logger.info(f"📡 Schedule response status: {response.status_code}")
            logger.info(f"📡 Content-Type: {response.headers.get('content-type', 'Unknown')}")
            logger.info(f"📡 Content-Length: {response.headers.get('content-length', 'Unknown')}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    # Save PDF file
                    filename = f"{schedule_type}_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    file_size = len(response.content)
                    logger.info(f"✅ PDF downloaded: {filename} ({file_size} bytes)")
                    return True
                elif 'application/json' in content_type:
                    # JSON response - might be error
                    logger.warning(f"⚠️ Got JSON response instead of PDF: {response.text[:200]}")
                    return False
                else:
                    logger.warning(f"⚠️ Unexpected content type: {content_type}")
                    logger.warning(f"Response preview: {response.text[:500]}")
                    return False
            else:
                logger.error(f"❌ Download failed with status: {response.status_code}")
                if response.text:
                    logger.error(f"Error response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during download: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return False
    
    def health_check(self):
        """Simple health check - just test connectivity"""
        try:
            logger.info("🏥 Running connectivity check...")
            # Just test if we can reach the domain
            response = self.session.get("https://api-avianca.avianca.com", timeout=10)
            logger.info("✅ Basic connectivity check passed")
            return True
        except Exception as e:
            logger.error(f"❌ Connectivity check failed: {e}")
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
        
        # Try actual schedule first
        actual_success = client.download_schedule("actual")
        time.sleep(3)
        
        # Then scheduled
        scheduled_success = client.download_schedule("scheduled")
        
        if actual_success and scheduled_success:
            logger.info("🎉 Daily downloads completed successfully!")
        elif actual_success or scheduled_success:
            logger.info("⚠️ Partial success - some downloads completed")
        else:
            logger.error("💥 All downloads failed")
            
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
    logger.info("🔧 Using API-based approach")
    
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
    schedule.every().day.at("18:00").do(run_daily_download)
    
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