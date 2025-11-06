#!/usr/bin/env python3
"""
My Crew Schedule - With Calendar View
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
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
    
    def get_schedule_data(self, crew_id=None):
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
current_crew_id = "32385184"

def create_calendar_data(schedule_data, center_date=None):
    """Convert schedule data to calendar format"""
    if not schedule_data or not isinstance(schedule_data, list):
        return []
    
    # Flatten all days from all months
    all_days = []
    for month in schedule_data:
        if isinstance(month, list):
            for day in month:
                if isinstance(day, dict) and day.get('StartDate'):
                    all_days.append(day)
    
    # Create calendar centered on current UTC date or provided date
    if not center_date:
        center_date = datetime.utcnow()
    
    # Start 15 days before center date to create 30-day window
    start_date = center_date - timedelta(days=15)
    
    calendar_days = []
    for i in range(30):  # 30-day calendar
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Find matching schedule day
        schedule_day = None
        for day in all_days:
            if day.get('StartDate', '').startswith(date_str):
                schedule_day = day
                break
        
        calendar_days.append({
            'date': current_date,
            'date_str': date_str,
            'schedule_data': schedule_day,
            'is_today': current_date.date() == datetime.utcnow().date(),
            'has_assignments': schedule_day and schedule_day.get('AssignementList') and len(schedule_day.get('AssignementList', [])) > 0,
            'assignment_count': len(schedule_day.get('AssignementList', [])) if schedule_day else 0,
            'dem': schedule_day.get('Dem', 0) if schedule_day else 0
        })
    
    return calendar_days

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; }
        .nav-buttons { text-align: center; margin: 15px 0; }
        .nav-button { background: #6c757d; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px; text-decoration: none; display: inline-block; }
        .nav-button:hover { background: #5a6268; }
        .nav-button.active { background: #007bff; }
        .search-box { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .input-group { display: inline-flex; gap: 10px; align-items: center; }
        .crew-input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; width: 150px; }
        .button { background: #007bff; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .month-section { border: 2px solid #007bff; padding: 15px; margin: 20px 0; border-radius: 8px; }
        .month-header { background: #007bff; color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        .day-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .day-header { background: #17a2b8; color: white; padding: 8px; border-radius: 3px; margin-bottom: 10px; }
        .assignment { background: #f8f9fa; padding: 10px; margin: 5px 0; border-left: 4px solid #28a745; }
        .flight-info { color: #666; font-size: 0.9em; margin-top: 5px; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; }
        .error { color: #dc3545; text-align: center; padding: 20px; background: #f8d7da; border-radius: 5px; }
        .current-crew { background: #d4edda; padding: 5px 10px; border-radius: 3px; margin-left: 10px; }
        
        /* Calendar Styles */
        .calendar-container { max-width: 1200px; }
        .calendar-header { text-align: center; margin: 20px 0; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin: 20px 0; }
        .calendar-day { border: 1px solid #ddd; border-radius: 8px; padding: 10px; min-height: 120px; background: white; position: relative; }
        .calendar-day.today { border: 2px solid #007bff; background: #e7f3ff; }
        .calendar-day.has-assignments { background: #f8f9fa; border-left: 4px solid #28a745; }
        .calendar-date { font-weight: bold; margin-bottom: 5px; }
        .calendar-weekday { font-size: 0.8em; color: #666; }
        .calendar-assignments { font-size: 0.75em; margin-top: 5px; }
        .calendar-assignment { background: #e9ecef; padding: 2px 4px; margin: 1px 0; border-radius: 2px; }
        .calendar-dem { position: absolute; bottom: 5px; right: 5px; font-size: 0.7em; color: #6c757d; }
        .calendar-empty { background: #f8f9fa; color: #6c757d; text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ Crew Schedule Lookup</h1>
        </div>

        <div class="nav-buttons">
            <a href="/?crew_id={{ current_crew_id }}" class="nav-button {% if request.path == '/' %}active{% endif %}">📋 List View</a>
            <a href="/calendar?crew_id={{ current_crew_id }}" class="nav-button {% if request.path == '/calendar' %}active{% endif %}">📅 Calendar View</a>
        </div>

        <div class="search-box">
            <div class="input-group">
                <label for="crewId"><strong>Crew Member ID:</strong></label>
                <input type="text" id="crewId" class="crew-input" placeholder="Enter Crew ID" value="{{ current_crew_id }}">
                <button class="button" onclick="loadSchedule()">🔍 Load Schedule</button>
            </div>
            {% if current_crew_id %}
            <div style="margin-top: 10px;">
                <small>Currently viewing: <span class="current-crew">{{ current_crew_id }}</span></small>
            </div>
            {% endif %}
        </div>

        {% if last_fetch %}
        <div class="info-box">
            <h3>Last updated: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }} | Total assignments: {{ total_assignments }}</p>
        </div>
        {% endif %}

        {% block content %}{% endblock %}
    </div>

    <script>
    function loadSchedule() {
        const crewId = document.getElementById('crewId').value.trim();
        if (!crewId) {
            alert('Please enter a Crew Member ID');
            return;
        }
        
        const button = event.target;
        button.disabled = true;
        button.textContent = '⏳ Loading...';
        
        // Update URL with crew ID for current view
        const currentPath = window.location.pathname;
        const url = new URL(window.location);
        url.searchParams.set('crew_id', crewId);
        window.location.href = url.toString();
    }

    // Allow Enter key to trigger search
    document.getElementById('crewId').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            loadSchedule();
        }
    });

    // Focus on input when page loads
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('crewId').focus();
    });
    </script>
</body>
</html>
'''

LIST_VIEW_TEMPLATE = '''
{% extends "base.html" %}

{% block content %}
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
                        <strong>{{ day.StartDate[:10] if day.StartDate else "Unknown" }}</strong>
                        <span style="float: right;">DEM: {{ day.Dem }}</span>
                    </div>
                    
                    {% if day.AssignementList and day.AssignementList|length > 0 %}
                        {% for assignment in day.AssignementList %}
                        <div class="assignment">
                            <strong>{{ assignment.ActivityCode.strip() if assignment.ActivityCode else "N/A" }}</strong>
                            - {{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else "No Description" }}
                            <div class="flight-info">
                                <strong>Time:</strong> {{ assignment.StartDateLocal[:16] if assignment.StartDateLocal else "N/A" }} 
                                to {{ assignment.EndDateLocal[:16] if assignment.EndDateLocal else "N/A" }}
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
    {% elif last_fetch %}
        <div class="error">
            <h3>No schedule data available for Crew ID: {{ current_crew_id }}</h3>
            <p>Try a different Crew ID or check if the ID is correct.</p>
        </div>
    {% else %}
        <div class="error">
            <h3>Enter a Crew Member ID to load schedule</h3>
            <p>Use the input box above to search for a crew member's schedule.</p>
        </div>
    {% endif %}
{% endblock %}
'''

CALENDAR_VIEW_TEMPLATE = '''
{% extends "base.html" %}

{% block content %}
<div class="calendar-container">
    {% if calendar_data %}
        <div class="calendar-header">
            <h2>📅 30-Day Calendar View</h2>
            <p>Centered on {{ center_date.strftime('%Y-%m-%d') }} (Today: {{ today_date.strftime('%Y-%m-%d') }})</p>
        </div>
        
        <div class="calendar-grid">
            {% for day in calendar_data %}
            <div class="calendar-day {% if day.is_today %}today{% endif %} {% if day.has_assignments %}has-assignments{% endif %}">
                <div class="calendar-date">
                    {{ day.date.day }}
                </div>
                <div class="calendar-weekday">
                    {{ day.date.strftime('%a') }}
                </div>
                
                {% if day.schedule_data %}
                    <div class="calendar-assignments">
                        {% if day.schedule_data.AssignementList %}
                            {% for assignment in day.schedule_data.AssignementList %}
                            <div class="calendar-assignment" title="{{ assignment.ActivityCode }} - {{ assignment.ActivityDesc }}">
                                {{ assignment.ActivityCode|replace(' ', '') }}
                                {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                <br><small>{{ assignment.FlighAssignement.CommercialFlightNumber }}</small>
                                {% endif %}
                            </div>
                            {% endfor %}
                        {% else %}
                            <div class="calendar-empty">No assignments</div>
                        {% endif %}
                    </div>
                {% else %}
                    <div class="calendar-empty">No data</div>
                {% endif %}
                
                {% if day.schedule_data and day.schedule_data.Dem > 0 %}
                <div class="calendar-dem">DEM: {{ day.schedule_data.Dem }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <small>
                <strong>Legend:</strong> 
                <span style="border-left: 4px solid #28a745; padding: 0 10px;">Has Assignments</span>
                <span style="border: 2px solid #007bff; padding: 0 10px; background: #e7f3ff;">Today</span>
            </small>
        </div>
    {% elif last_fetch %}
        <div class="error">
            <h3>No schedule data available for Crew ID: {{ current_crew_id }}</h3>
            <p>Try a different Crew ID or check if the ID is correct.</p>
        </div>
    {% else %}
        <div class="error">
            <h3>Enter a Crew Member ID to load schedule</h3>
            <p>Use the input box above to search for a crew member's schedule.</p>
        </div>
    {% endif %}
</div>
{% endblock %}
'''

@app.route('/')
def index():
    global current_crew_id
    
    crew_id = request.args.get('crew_id', '32385184')
    current_crew_id = crew_id
    
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
    
    return render_template_string(LIST_VIEW_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        current_crew_id=current_crew_id
    )

@app.route('/calendar')
def calendar_view():
    global current_crew_id
    
    crew_id = request.args.get('crew_id', '32385184')
    current_crew_id = crew_id
    
    # Create calendar data centered on current UTC date
    center_date = datetime.utcnow()
    calendar_data = create_calendar_data(schedule_data, center_date)
    
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
    
    return render_template_string(CALENDAR_VIEW_TEMPLATE,
        calendar_data=calendar_data,
        center_date=center_date,
        today_date=datetime.utcnow(),
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        current_crew_id=current_crew_id
    )

@app.route('/fetch')
def fetch_data():
    global schedule_data, last_fetch_time, current_crew_id
    
    crew_id = request.args.get('crew_id', '32385184')
    current_crew_id = crew_id
    
    try:
        new_data = client.get_schedule_data(crew_id)
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"success": True, "crew_id": crew_id}
        return {"success": False, "error": "Failed to fetch data"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    initial_data = client.get_schedule_data()
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    
    app.run(host='0.0.0.0', port=8000, debug=False)