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
            
            # Use URL-encoded form data as seen in the traffic
            form_data = {
                'username': email,
                'password': password,
                'grant_type': 'password',
                'client_id': 'angularclient',
                'client_secret': 'angularclient',
                'scope': 'openid profile roles mycrew-flight-api offline_access'
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
            
            logger.info(f"📡 Login response status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = f"Bearer {token_data['access_token']}"
                self.is_logged_in = True
                logger.info("✅ API login successful!")
                return True
            else:
                logger.error(f"❌ API login failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
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
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            logger.info(f"📡 Response status: {response.status_code}")
            logger.info(f"📡 Content-Type: {response.headers.get('content-type', 'Unknown')}")
            
            if response.status_code == 200:
                schedule_data = response.json()
                logger.info(f"✅ Successfully fetched schedule data")
                
                # FIXED: Properly handle the data structure based on the traffic analysis
                if isinstance(schedule_data, list):
                    logger.info(f"📅 Data covers {len(schedule_data)} days")
                    
                    # Log basic info about the data - FIXED: Proper dictionary access
                    for i, day in enumerate(schedule_data[:3]):
                        if isinstance(day, dict):
                            date = day.get('StartDate', 'Unknown')
                            # CORRECT: It's 'AssignementList' as seen in the traffic
                            assignments_list = day.get('AssignementList', [])
                            assignments_count = len(assignments_list)
                            logger.info(f"   📋 {date}: {assignments_count} assignments")
                            
                            # Log first assignment details for debugging
                            if assignments_list and len(assignments_list) > 0:
                                first_assignment = assignments_list[0]
                                if isinstance(first_assignment, dict):
                                    activity_code = first_assignment.get('ActivityCode', 'Unknown')
                                    activity_desc = first_assignment.get('ActivityDesc', 'Unknown')
                                    logger.info(f"     ✈️ First assignment: {activity_code} - {activity_desc}")
                        else:
                            logger.info(f"   📋 Day {i+1}: Unexpected type {type(day)}")
                else:
                    logger.info(f"📅 Data type: {type(schedule_data)}")
                    
                return schedule_data
            else:
                logger.error(f"❌ Failed to fetch schedule data: {response.status_code}")
                if response.text:
                    logger.error(f"Error response: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching schedule data: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return None

# Global client instance
client = CrewAPIClient()

# Global variables to store fetched data
schedule_data = None
last_fetch_time = None
fetch_error = None

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
        .button:hover { background: #0056b3; }
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
        .success { color: #28a745; }
        .error { color: #dc3545; }
        .info-box { 
            background: #e9ecef; padding: 15px; border-radius: 5px; 
            margin: 10px 0; border-left: 4px solid #6c757d;
        }
        .loading { color: #6c757d; }
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
        <div class="info-box">
            <h3>Last fetched: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }}</p>
            <p>Total assignments: {{ total_assignments }}</p>
        </div>
        {% endif %}

        {% if schedule_data %}
        <div class="data-section">
            <h2>📅 Schedule Data</h2>
            {% for day in schedule_data %}
            <div class="day-card">
                <h3>{{ day.StartDate }} - {{ day.Dem }} DEM</h3>
                <p><strong>Assignments:</strong> {{ day.AssignementList|length }}</p>
                
                {% if day.AssignementList %}
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
                {% else %}
                    <p class="loading">No assignments for this day</p>
                {% endif %}
            </div>
            {% endfor %}
            
            <details>
                <summary>📋 View Raw JSON Data (First 1000 chars)</summary>
                <pre>{{ raw_json_preview }}</pre>
            </details>
        </div>
        {% elif error %}
        <div class="data-section error">
            <h3>❌ Error</h3>
            <p>{{ error }}</p>
        </div>
        {% else %}
        <div class="data-section loading">
            <h3>No data available</h3>
            <p>Click "Fetch Schedule Data" to load your schedule.</p>
        </div>
        {% endif %}
    </div>

    <script>
    function fetchData() {
        const button = event.target;
        button.disabled = true;
        button.textContent = '⏳ Fetching...';
        
        fetch('/fetch-data')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('✅ Data fetched successfully! Refreshing page...');
                    location.reload();
                } else {
                    alert('❌ Failed to fetch data: ' + (data.error || 'Unknown error'));
                    button.disabled = false;
                    button.textContent = '🔄 Fetch Schedule Data';
                }
            })
            .catch(error => {
                alert('❌ Error: ' + error);
                button.disabled = false;
                button.textContent = '🔄 Fetch Schedule Data';
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
    
    if schedule_data and isinstance(schedule_data, list):
        total_days = len(schedule_data)
        for day in schedule_data:
            if isinstance(day, dict):
                # CORRECT: Using 'AssignementList' as seen in traffic
                assignments = day.get('AssignementList', [])
                total_assignments += len(assignments)
    
    raw_json_preview = ""
    if schedule_data:
        try:
            raw_json_preview = json.dumps(schedule_data[:1] if isinstance(schedule_data, list) else schedule_data, indent=2)[:1000] + "..." 
        except:
            raw_json_preview = str(schedule_data)[:1000] + "..."
    
    return render_template_string(HTML_TEMPLATE,
        schedule_data=schedule_data if isinstance(schedule_data, list) else None,
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
        
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fetch_error = None
            logger.info("✅ Data updated successfully")
            return jsonify({
                "success": True,
                "data_count": len(schedule_data) if isinstance(schedule_data, list) else 1,
                "last_fetch": last_fetch_time,
                "error": None
            })
        else:
            fetch_error = "Failed to fetch schedule data - check logs for details"
            logger.error("❌ Data fetch failed")
            return jsonify({
                "success": False,
                "data_count": 0,
                "last_fetch": last_fetch_time,
                "error": fetch_error
            })
            
    except Exception as e:
        fetch_error = f"Error: {str(e)}"
        logger.error(f"❌ Error in fetch-data: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "data_count": 0,
            "last_fetch": last_fetch_time,
            "error": fetch_error
        })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_available": schedule_data is not None,
        "last_fetch": last_fetch_time
    })

@app.route('/debug')
def debug():
    """Debug endpoint to see raw data"""
    data_preview = None
    if schedule_data:
        if isinstance(schedule_data, list) and schedule_data:
            data_preview = schedule_data[0] if len(schedule_data) > 0 else schedule_data
        else:
            data_preview = schedule_data
    
    return jsonify({
        "schedule_data_type": type(schedule_data).__name__ if schedule_data else None,
        "schedule_data_length": len(schedule_data) if isinstance(schedule_data, list) else None,
        "last_fetch": last_fetch_time,
        "error": fetch_error,
        "is_logged_in": client.is_logged_in,
        "sample_data": data_preview
    })

def start_flask():
    """Start Flask server in a thread"""
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

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
    initial_data = client.get_schedule_data()
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    else:
        logger.error("❌ Initial data fetch failed")
    
    logger.info("🎉 Application ready! Visit http://localhost:8000")
    logger.info("📊 Available endpoints:")
    logger.info("   /          - Main schedule viewer")
    logger.info("   /fetch-data - Manually fetch new data")
    logger.info("   /health     - Health check")
    logger.info("   /debug      - Debug information")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")

if __name__ == "__main__":
    main()