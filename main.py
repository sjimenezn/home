#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Fixed Version
"""

import os
import logging
import requests
import json
from datetime import datetime
from flask import Flask, render_template_string

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
        try:
            form_data = {
                'username': email, 'password': password, 'grant_type': 'password',
                'client_id': 'angularclient', 'client_secret': 'angularclient',
                'scope': 'email openid profile CrewApp offline_access'
            }
            headers = {
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://mycrew.avianca.com", "Referer": "https://mycrew.avianca.com/",
            }
            response = self.session.post(self.auth_url, data=form_data, headers=headers, timeout=30)
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = f"Bearer {token_data['access_token']}"
                self.is_logged_in = True
                return True
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def get_schedule_data(self):
        try:
            if not self.is_logged_in:
                email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
                password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
                if not self.login(email, password):
                    return None
            
            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {"timeZoneOffset": -300}
            headers = {
                "Authorization": self.auth_token, "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json", "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None

client = CrewAPIClient()
schedule_data = None
last_fetch_time = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .month-section { border: 2px solid #007bff; padding: 15px; margin: 20px 0; border-radius: 8px; }
        .month-header { background: #007bff; color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        .day-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .day-header { background: #17a2b8; color: white; padding: 8px; border-radius: 3px; margin-bottom: 10px; }
        .assignment { background: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 4px solid #28a745; }
        .flight-info { color: #666; font-size: 0.9em; margin-top: 5px; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; }
        .error { color: #dc3545; text-align: center; padding: 20px; }
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
            {% for month in schedule_data %}
            <div class="month-section">
                <div class="month-header">
                    <h3>📅 Month {{ loop.index }}</h3>
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
        fetch('/fetch').then(r => r.json()).then(data => {
            if (data.success) location.reload();
            else {
                alert('Failed: ' + (data.error || 'Unknown error'));
                button.disabled = false;
                button.textContent = '🔄 Refresh Schedule';
            }
        }).catch(err => {
            alert('Error: ' + err);
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
    total_days = 0
    total_assignments = 0
    
    if schedule_data and isinstance(schedule_data, list):
        for month in schedule_data:
            if isinstance(month, list):
                total_days += len(month)
                for day in month:
                    if isinstance(day, dict):
                        assignments = day.get('AssignementList', [])
                        total_assignments += len(assignments)
    
    return render_template_string(HTML_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments
    )

@app.route('/fetch')
def fetch_data():
    global schedule_data, last_fetch_time
    try:
        new_data = client.get_schedule_data()
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"success": True}
        return {"success": False, "error": "Failed to fetch data"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    global schedule_data, last_fetch_time
    initial_data = client.get_schedule_data()
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    app.run(host='0.0.0.0', port=8000, debug=False)

if __name__ == "__main__":
    main()