#!/usr/bin/env python3
"""
My Crew Schedule Monitor - JSON Data Fetcher
"""

import os
import time
import logging
import requests
import json
from datetime import datetime
from flask import Flask, jsonify, render_template_string
import threading

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
            
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            
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
        """Get schedule JSON data (like the 'reload schedule data' button)"""
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return None
            
            logger.info(f"📊 Fetching schedule JSON data...")
            
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
            
            logger.info(f"🌐 Making request to: {url}")
            logger.info(f"📋 With timezone offset: {timezone_offset}")
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            logger.info(f"📡 Response status: {response.status_code}")
            logger.info(f"📡 Content-Type: {response.headers.get('content-type', 'Unknown')}")
            logger.info(f"📡 Content-Length: {response.headers.get('content-length', 'Unknown')}")
            
            if response.status_code == 200:
                schedule_data = response.json()
                logger.info(f"✅ Successfully fetched schedule data")
                logger.info(f"📅 Data covers {len(schedule_data)} days")
                
                # Log some basic info about the data
                for day in schedule_data[:3]:  # First 3 days
                    date = day.get('StartDate', 'Unknown')
                    assignments = len(day.get('AssignementList', []))
                    logger.info(f"   📋 {date}: {assignments} assignments")
                
                return schedule_data
            else:
                logger.error(f"❌ Failed to fetch schedule data: {response.status_code}")
                if response.text:
                    logger.error(f"Error response: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching schedule data: {e}")
            return None

# Global client instance
client = CrewAPIClient()

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule Data</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .button { 
            background: #007bff; color: white; padding: 10px 20px; 
            border: none; border-radius: 5px; cursor: pointer; margin: 10px;
        }
        .data-section { margin: 20px 0; }
        .day-card { 
            border: 1px solid #ddd; padding: 15px; margin: 10px 0; 
            border-radius: 5px; background: #f9f9f9;
        }
        .assignment { 
            background: white; padding: 10px; margin: 5px 0; 
            border-left: 4px solid #007bff;
        }
        .flight-info { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 My Crew Schedule Data</h1>
        
        <div>
            <button class="button" onclick="fetchData()">🔄 Fetch Schedule Data</button>
            <button class="button" onclick="location.reload()">🔄 Refresh Page</button>
        </div>

        {% if last_fetch %}
        <div class="data-section">
            <h3>Last fetched: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }}</p>
            <p>Total assignments: {{ total_assignments }}</p>
        </div>
        {% endif %}

        {% if schedule_data %}
        <div class="data-section">
            <h2>📅 Schedule Data (First 5 days)</h2>
            {% for day in schedule_data[:5] %}
            <div class="day-card">
                <h3>{{ day.StartDate }} - {{ day.Dem }} DEM</h3>
                <p><strong>Assignments:</strong> {{ day.AssignementList|length }}</p>
                
                {% for assignment in day.AssignementList %}
                <div class="assignment">
                    <strong>{{ assignment.ActivityCode }} - {{ assignment.ActivityDesc }}</strong>
                    <div class="flight-info">
                        {{ assignment.StartDateLocal }} to {{ assignment.EndDateLocal }}
                        {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                        | Flight: {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }}
                        | {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
            
            <details>
                <summary>📋 View Raw JSON Data (First 1000 chars)</summary>
                <pre>{{ raw_json_preview }}</pre>
            </details>
        </div>
        {% endif %}

        {% if error %}
        <div class="data-section" style="color: red;">
            <h3>❌ Error</h3>
            <p>{{ error }}</p>
        </div>
        {% endif %}
    </div>

    <script>
    function fetchData() {
        window.location.href = '/fetch-data';
    }
    </script>
</body>
</html>
"""

# Global variables to store fetched data
schedule_data = None
last_fetch_time = None
fetch_error = None

@app.route('/')
def index():
    """Main page showing schedule data"""
    total_days = len(schedule_data) if schedule_data else 0
    total_assignments = 0
    if schedule_data:
        for day in schedule_data:
            total_assignments += len(day.get('AssignementList', []))
    
    raw_json_preview = json.dumps(schedule_data[:1] if schedule_data else [], indent=2)[:1000] + "..." if schedule_data else ""
    
    return render_template_string(HTML_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        raw_json_preview=raw_json_preview,
        error=fetch_error
    )

@app.route('/fetch-data')
def fetch_data():
    """Endpoint to fetch fresh schedule data"""
    global schedule_data, last_fetch_time, fetch_error
    
    try:
        logger.info("🔄 Manual data fetch requested")
        new_data = client.get_schedule_data()
        
        if new_data:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fetch_error = None
            logger.info("✅ Data updated successfully")
        else:
            fetch_error = "Failed to fetch schedule data"
            logger.error("❌ Data fetch failed")
            
    except Exception as e:
        fetch_error = f"Error: {str(e)}"
        logger.error(f"❌ Error in fetch-data: {e}")
    
    return jsonify({
        "success": schedule_data is not None,
        "data_count": len(schedule_data) if schedule_data else 0,
        "last_fetch": last_fetch_time,
        "error": fetch_error
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_available": schedule_data is not None
    })

def start_flask():
    """Start Flask server in a thread"""
    app.run(host='0.0.0.0', port=8000, debug=False)

def main():
    """Main function"""
    logger.info("🚀 Crew Schedule Data Fetcher starting...")
    
    # Start Flask in background thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Web server started on port 8000")
    
    # Initial data fetch
    logger.info("📥 Performing initial data fetch...")
    global schedule_data, last_fetch_time
    schedule_data = client.get_schedule_data()
    if schedule_data:
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    else:
        logger.error("❌ Initial data fetch failed")
    
    logger.info("🎉 Application ready! Visit http://your-koyeb-url.koyeb.app")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")

if __name__ == "__main__":
    main()