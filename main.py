#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Simplified
"""

import os
import time
import logging
import requests
import json
from datetime import datetime
from flask import Flask, render_template_string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class CrewAPIClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://api-avianca.avianca.com/MycreWFlights/api"
        self.auth_url = "https://api-avianca.avianca.com/MyCrewSecurity/connect/token"
        self.is_logged_in = False
        self.auth_token = None
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        
    def login(self, email, password):
        """Login using the API"""
        try:
            logger.info("🔐 Attempting API login...")
            
            form_data = {
                'username': email,
                'password': password,
                'grant_type': 'password',
                'client_id': 'angularclient', 
                'client_secret': 'angularclient',
                'scope': 'email openid profile CrewApp offline_access'
            }
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = self.session.post(
                self.auth_url,
                data=form_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = f"Bearer {token_data['access_token']}"
                self.is_logged_in = True
                logger.info("✅ API login successful!")
                return True
            else:
                logger.error(f"❌ API login failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    def get_schedule_data(self, timezone_offset=-300):
        """Get schedule JSON data"""
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return None
            
            logger.info(f"📊 Fetching schedule data...")
            
            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {"timeZoneOffset": timezone_offset}
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                schedule_data = response.json()
                logger.info(f"✅ Successfully fetched {len(schedule_data)} months of data")
                return schedule_data
            else:
                logger.error(f"❌ Failed to fetch schedule data: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching schedule data: {e}")
            return None

# Global client and data
client = CrewAPIClient()
schedule_data = None
last_fetch_time = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .button { 
            background: #007bff; color: white; padding: 12px 24px; 
            border: none; border-radius: 5px; cursor: pointer; margin: 10px;
            font-size: 16px;
        }
        .button:hover { background: #0056b3; }
        .info-box { 
            background: #e9ecef; padding: 15px; border-radius: 5px; 
            margin: 20px 0; text-align: center;
        }
        .month-section { 
            border: 2px solid #007bff; padding: 15px; margin: 25px 0; 
            border-radius: 8px; background: #f8f9fa;
        }
        .month-header { 
            background: #007bff; color: white; padding: 12px; 
            border-radius: 5px; margin-bottom: 15px; text-align: center;
            font-size: 18px;
        }
        .day-card { 
            border: 1px solid #ddd; padding: 15px; margin: 10px 0; 
            border-radius: 5px; background: white;
        }
        .day-header { 
            background: #17a2b8; color: white; padding: 10px; 
            border-radius: 5px; margin-bottom: 10px;
        }
        .assignment { 
            background: #f8f9fa; padding: 10px; margin: 8px 0; 
            border-left: 4px solid #28a745; border-radius: 3px;
        }
        .flight-info { color: #666; font-size: 0.9em; margin-top: 5px; }
        .no-data { color: #6c757d; text-align: center; padding: 20px; }
        .error { color: #dc3545; text-align: center; padding: 20px; background: #f8d7da; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule</h1>
            <button class="button" onclick="fetchData()">🔄 Refresh Schedule</button>
        </div>

        {% if last_fetch %}
        <div class="info-box">
            <h3>Last updated: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }} | Total assignments: {{ total_assignments }}</p>
        </div>
        {% endif %}

        {% if schedule_data %}
            {% for month_index, month in months %}
            <div class="month-section">
                <div class="month-header">
                    <h3>📅 Month {{ month_index + 1 }}</h3>
                </div>
                {% for day in month %}
                    {% if day and day is mapping %}
                    <div class="day-card">
                        <div class="day-header">
                            <strong>{{ day.StartDate[:10] if day.StartDate else 'Unknown' }}</strong>
                            <span style="float: right;">DEM: {{ day.Dem }}</span>
                        </div>
                        
                        {% if day.AssignementList and day.AssignementList|length > 0 %}
                            {% for assignment in day.AssignementList %}
                            <div class="assignment">
                                <strong>{{ assignment.ActivityCode.strip() if assignment.ActivityCode else 'N/A' }}</strong>
                                - {{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else 'No Description' }}
                                <div class="flight-info">
                                    <strong>Time:</strong> {{ assignment.StartDateLocal[:16] if assignment.StartDateLocal else 'N/A' }} 
                                    to {{ assignment.EndDateLocal[:16] if assignment.EndDateLocal else 'N/A' }}
                                    {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                    <br><strong>Flight:</strong> {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }}
                                    | {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}
                                    | {{ assignment.FlighAssignement.Duration }} min
                                    {% if assignment.Fleet %}| Aircraft: {{ assignment.Fleet }}{% endif %}
                                    {% endif %}
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div class="no-data">No assignments for this day</div>
                        {% endif %}
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
            {% endfor %}
        {% else %}
            <div class="error">
                <h3>No schedule data available</h3>
                <p>Click "Refresh Schedule" to load your schedule.</p>
            </div>
        {% endif %}
    </div>

    <script>
    function fetchData() {
        const button = event.target;
        button.disabled = true;
        button.textContent = '⏳ Loading...';
        
        fetch('/fetch')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Failed to fetch data: ' + (data.error || 'Unknown error'));
                    button.disabled = false;
                    button.textContent = '🔄 Refresh Schedule';
                }
            })
            .catch(error => {
                alert('Error: ' + error);
                button.disabled = false;
                button.textContent = '🔄 Refresh Schedule';
            });
    }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page showing schedule data"""
    total_days = 0
    total_assignments = 0
    months_data = []
    
    if schedule_data and isinstance(schedule_data, list):
        # Prepare months data with index for template
        months_data = list(enumerate(schedule_data))
        
        # Count totals
        for month in schedule_data:
            if isinstance(month, list):
                total_days += len(month)
                for day in month:
                    if isinstance(day, dict):
                        assignments = day.get('AssignementList', [])
                        total_assignments += len(assignments)
    
    return render_template_string(HTML_TEMPLATE,
        schedule_data=schedule_data,
        months=months_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments
    )

@app.route('/fetch')
def fetch_data():
    """Endpoint to fetch fresh schedule data"""
    global schedule_data, last_fetch_time
    
    try:
        logger.info("🔄 Manual data fetch requested")
        new_data = client.get_schedule_data()
        
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("✅ Data updated successfully")
            return {"success": True, "message": "Data fetched successfully"}
        else:
            logger.error("❌ Data fetch failed")
            return {"success": False, "error": "Failed to fetch schedule data"}
            
    except Exception as e:
        logger.error(f"❌ Error in fetch: {e}")
        return {"success": False, "error": str(e)}

def main():
    """Main function"""
    logger.info("🚀 Crew Schedule starting...")
    
    # Initial data fetch
    global schedule_data, last_fetch_time
    initial_data = client.get_schedule_data()
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    
    # Start Flask
    app.run(host='0.0.0.0', port=8000, debug=False)

if __name__ == "__main__":
    main()