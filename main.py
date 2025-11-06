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
        """Login using the API - FIXED SCOPE"""
        try:
            logger.info("🔐 Attempting API login...")
            
            # FIXED: Use the exact scope from the successful traffic capture
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            }
            
            logger.info(f"📡 Sending login request to: {self.auth_url}")
            
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
                logger.info(f"🔑 Token type: {token_data.get('token_type', 'Unknown')}")
                logger.info(f"⏰ Expires in: {token_data.get('expires_in', 'Unknown')} seconds")
                return True
            else:
                logger.error(f"❌ API login failed: {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response body: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            }
            
            logger.info(f"🌐 Making request to: {url}")
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            logger.info(f"📡 Response status: {response.status_code}")
            logger.info(f"📡 Content-Type: {response.headers.get('content-type', 'Unknown')}")
            
            if response.status_code == 200:
                schedule_data = response.json()
                logger.info(f"✅ Successfully fetched schedule data")
                
                # FIXED: Handle nested list structure
                if isinstance(schedule_data, list):
                    logger.info(f"📅 Data structure: list with {len(schedule_data)} items")
                    
                    # Check if it's a nested list structure
                    if schedule_data and isinstance(schedule_data[0], list):
                        logger.info("📊 Nested list structure detected")
                        total_days = 0
                        for i, month_list in enumerate(schedule_data):
                            if isinstance(month_list, list):
                                logger.info(f"   📅 Month {i+1}: {len(month_list)} days")
                                total_days += len(month_list)
                                # Log first few days of first month
                                if i == 0:
                                    for j, day in enumerate(month_list[:3]):
                                        if isinstance(day, dict):
                                            date = day.get('StartDate', 'Unknown')
                                            assignments_count = len(day.get('AssignementList', []))
                                            logger.info(f"     📋 {date}: {assignments_count} assignments")
                        logger.info(f"📅 Total days across all months: {total_days}")
                    else:
                        logger.info("📊 Flat list structure detected")
                        logger.info(f"📅 Data covers {len(schedule_data)} days")
                        for i, day in enumerate(schedule_data[:3]):
                            if isinstance(day, dict):
                                date = day.get('StartDate', 'Unknown')
                                assignments_count = len(day.get('AssignementList', []))
                                logger.info(f"   📋 {date}: {assignments_count} assignments")
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
        .button:disabled { background: #6c757d; cursor: not-allowed; }
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
        .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
        .status-success { background: #d4edda; border: 1px solid #c3e6cb; }
        .status-error { background: #f8d7da; border: 1px solid #f5c6cb; }
        pre { 
            background: #f8f9fa; padding: 15px; border-radius: 5px; 
            border: 1px solid #e9ecef; overflow-x: auto; max-height: 800px;
            overflow-y: auto; white-space: pre-wrap; word-wrap: break-word;
            font-size: 12px;
        }
        .day-header { 
            background: #007bff; color: white; padding: 10px; 
            border-radius: 5px; margin-bottom: 10px;
        }
        .dem-info { 
            background: #17a2b8; color: white; padding: 5px 10px; 
            border-radius: 3px; font-size: 0.9em; display: inline-block;
            margin-left: 10px;
        }
        .month-section { 
            border: 2px solid #007bff; padding: 15px; margin: 20px 0; 
            border-radius: 8px; background: #f0f8ff;
        }
        .month-header { 
            background: #007bff; color: white; padding: 10px; 
            border-radius: 5px; margin-bottom: 15px; text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 My Crew Schedule Data</h1>
        
        <div>
            <button class="button" onclick="fetchData()" id="fetchBtn">🔄 Fetch Schedule Data</button>
            <button class="button" onclick="location.reload()">🔄 Refresh Page</button>
        </div>

        {% if last_fetch %}
        <div class="info-box">
            <h3>Last fetched: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }}</p>
            <p>Total assignments: {{ total_assignments }}</p>
            <p>Data structure: {{ data_structure }}</p>
        </div>
        {% endif %}

        {% if schedule_data %}
        <div class="data-section">
            <h2>📅 Schedule Data ({{ total_days }} days)</h2>
            
            {% if data_structure == 'nested' %}
                <!-- Handle nested list structure (list of months) -->
                {% for month_index, month in enumerate(schedule_data) %}
                <div class="month-section">
                    <div class="month-header">
                        <h3>📅 Month {{ month_index + 1 }}</h3>
                    </div>
                    {% for day in month %}
                        {% if day and day is mapping %}
                        <div class="day-card">
                            <div class="day-header">
                                <strong>{{ day.StartDate[:10] if day.StartDate else 'Unknown Date' }}</strong>
                                <span class="dem-info">DEM: {{ day.Dem }}</span>
                            </div>
                            <p><strong>Assignments:</strong> {{ day.AssignementList|length if day.AssignementList else 0 }}</p>
                            <p><strong>Sync Date:</strong> {{ day.SyncDate[:19] if day.SyncDate else 'Unknown' }}</p>
                            
                            {% if day.AssignementList and day.AssignementList|length > 0 %}
                                {% for assignment in day.AssignementList %}
                                <div class="assignment">
                                    <strong>{{ assignment.ActivityCode.strip() if assignment.ActivityCode else 'N/A' }} - {{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else 'No Description' }}</strong>
                                    <div class="flight-info">
                                        <strong>Time:</strong> {{ assignment.StartDateLocal[:16] if assignment.StartDateLocal else 'N/A' }} to {{ assignment.EndDateLocal[:16] if assignment.EndDateLocal else 'N/A' }}<br>
                                        {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                        <strong>Flight:</strong> {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }}<br>
                                        <strong>Route:</strong> {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}<br>
                                        <strong>Duration:</strong> {{ assignment.FlighAssignement.Duration }} minutes<br>
                                        <strong>Aircraft:</strong> {{ assignment.Fleet }} {% if assignment.AircraftRegistrationNumber %}({{ assignment.AircraftRegistrationNumber }}){% endif %}
                                        {% else %}
                                        <strong>Type:</strong> {{ assignment.AssignementCategory }} - {{ assignment.ActivityType }}
                                        {% endif %}
                                    </div>
                                </div>
                                {% endfor %}
                            {% else %}
                                <p class="loading">No assignments for this day</p>
                            {% endif %}
                        </div>
                        {% endif %}
                    {% endfor %}
                </div>
                {% endfor %}
            {% else %}
                <!-- Handle flat list structure -->
                {% for day in schedule_data %}
                    {% if day and day is mapping %}
                    <div class="day-card">
                        <div class="day-header">
                            <strong>{{ day.StartDate[:10] if day.StartDate else 'Unknown Date' }}</strong>
                            <span class="dem-info">DEM: {{ day.Dem }}</span>
                        </div>
                        <p><strong>Assignments:</strong> {{ day.AssignementList|length if day.AssignementList else 0 }}</p>
                        <p><strong>Sync Date:</strong> {{ day.SyncDate[:19] if day.SyncDate else 'Unknown' }}</p>
                        
                        {% if day.AssignementList and day.AssignementList|length > 0 %}
                            {% for assignment in day.AssignementList %}
                            <div class="assignment">
                                <strong>{{ assignment.ActivityCode.strip() if assignment.ActivityCode else 'N/A' }} - {{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else 'No Description' }}</strong>
                                <div class="flight-info">
                                    <strong>Time:</strong> {{ assignment.StartDateLocal[:16] if assignment.StartDateLocal else 'N/A' }} to {{ assignment.EndDateLocal[:16] if assignment.EndDateLocal else 'N/A' }}<br>
                                    {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                    <strong>Flight:</strong> {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }}<br>
                                    <strong>Route:</strong> {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}<br>
                                    <strong>Duration:</strong> {{ assignment.FlighAssignement.Duration }} minutes<br>
                                    <strong>Aircraft:</strong> {{ assignment.Fleet }} {% if assignment.AircraftRegistrationNumber %}({{ assignment.AircraftRegistrationNumber }}){% endif %}
                                    {% else %}
                                    <strong>Type:</strong> {{ assignment.AssignementCategory }} - {{ assignment.ActivityType }}
                                    {% endif %}
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p class="loading">No assignments for this day</p>
                        {% endif %}
                    </div>
                    {% endif %}
                {% endfor %}
            {% endif %}
            
            <details>
                <summary>📋 View Complete Raw JSON Data</summary>
                <pre id="jsonData">{{ raw_json }}</pre>
            </details>
        </div>
        {% elif error %}
        <div class="data-section status status-error">
            <h3>❌ Error</h3>
            <p>{{ error }}</p>
            <p><small>Check the server logs for more details.</small></p>
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
        const button = document.getElementById('fetchBtn');
        const originalText = button.textContent;
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
                    button.textContent = originalText;
                }
            })
            .catch(error => {
                alert('❌ Network error: ' + error);
                button.disabled = false;
                button.textContent = originalText;
            });
    }
    
    // Auto-expand JSON view if there's an error
    document.addEventListener('DOMContentLoaded', function() {
        const errorSection = document.querySelector('.status-error');
        if (errorSection) {
            const details = document.querySelector('details');
            if (details) {
                details.open = true;
            }
        }
    });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page showing schedule data"""
    total_days = 0
    total_assignments = 0
    data_structure = 'unknown'
    
    if schedule_data:
        # FIXED: Handle nested list structure
        if isinstance(schedule_data, list):
            if schedule_data and isinstance(schedule_data[0], list):
                logger.info("📊 Rendering: Nested list structure")
                data_structure = 'nested'
                # Count days in nested structure
                for month in schedule_data:
                    if isinstance(month, list):
                        total_days += len(month)
                        for day in month:
                            if isinstance(day, dict):
                                assignments = day.get('AssignementList', [])
                                total_assignments += len(assignments)
            else:
                logger.info("📊 Rendering: Flat list structure")
                data_structure = 'flat'
                total_days = len(schedule_data)
                for day in schedule_data:
                    if isinstance(day, dict):
                        assignments = day.get('AssignementList', [])
                        total_assignments += len(assignments)
    
    # Generate complete JSON for display
    raw_json = ""
    if schedule_data:
        try:
            raw_json = json.dumps(schedule_data, indent=2, ensure_ascii=False)
        except Exception as e:
            raw_json = f"Error formatting JSON: {str(e)}\n\nRaw data: {str(schedule_data)}"
    
    return render_template_string(HTML_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        raw_json=raw_json,
        data_structure=data_structure,
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
        "last_fetch": last_fetch_time,
        "logged_in": client.is_logged_in
    })

@app.route('/debug')
def debug():
    """Debug endpoint to see raw data"""
    data_structure = 'unknown'
    if schedule_data:
        if isinstance(schedule_data, list):
            if schedule_data and isinstance(schedule_data[0], list):
                data_structure = 'nested_list'
            else:
                data_structure = 'flat_list'
    
    return jsonify({
        "schedule_data_type": type(schedule_data).__name__ if schedule_data else None,
        "schedule_data_length": len(schedule_data) if isinstance(schedule_data, list) else None,
        "data_structure": data_structure,
        "last_fetch": last_fetch_time,
        "error": fetch_error,
        "is_logged_in": client.is_logged_in,
        "has_auth_token": client.auth_token is not None,
    })

@app.route('/raw-json')
def raw_json():
    """Endpoint to get raw JSON data"""
    if schedule_data:
        return jsonify(schedule_data)
    else:
        return jsonify({"error": "No data available"})

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
    logger.info("   /raw-json   - Raw JSON data")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")

if __name__ == "__main__":
    main()