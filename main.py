#!/usr/bin/env python3
"""
My Crew Schedule Monitor - With Calendar View
"""

import os
import time
import logging
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, send_file

# Configuration
DEFAULT_CREW_ID = "32385184"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

class CrewAPIClient:
    def __init__(self):
        self.base_url = "https://api-avianca.avianca.com/MycreWFlights/api"
        self.auth_url = "https://api-avianca.avianca.com/MyCrewSecurity/connect/token"
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        
    def create_new_session(self):
        """Create a fresh session to clear all cookies and cache"""
        self.session = requests.Session()
        self.is_logged_in = False
        self.auth_token = None
        logger.info("🆕 Created new session (cleared cookies/cache)")
        
    def login(self, email, password):
        try:
            logger.info("🔐 Attempting API login...")
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
                logger.info("✅ API login successful!")
                return True
            logger.error(f"❌ API login failed: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    def get_schedule_data(self):
        try:
            logger.info("📊 Fetching schedule data...")
            
            # Always create a new session to ensure fresh data
            self.create_new_session()
            
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
            
            logger.info(f"🌐 Making fresh API request...")
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # Log data structure for debugging
                if isinstance(data, list):
                    logger.info(f"✅ Schedule data fetched! Structure: {len(data)} months")
                    if data and isinstance(data[0], list):
                        logger.info(f"📅 First month has {len(data[0])} days")
                logger.info("✅ Schedule data fetched successfully!")
                return data
                
            logger.error(f"❌ Failed to fetch schedule data: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            return None

    def download_schedule_pdf(self, crew_id, schedule_type="actual", month="", year=""):
        """Download schedule PDF using multipart form data"""
        try:
            logger.info(f"📥 Downloading {schedule_type} schedule PDF for crew {crew_id}...")
            
            # Always create a new session to ensure fresh data
            self.create_new_session()
            
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            
            if not self.login(email, password):
                logger.error("❌ Cannot download PDF - login failed")
                return None
            
            # Determine endpoint
            if schedule_type.lower() == "scheduled":
                url = f"{self.base_url}/MonthlyAssignements/Scheduled/Export"
            else:
                url = f"{self.base_url}/MonthlyAssignements/Export"
            
            # Create multipart form data for schedule request
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            current_month = month or str(datetime.now().month)
            current_year = year or str(datetime.now().year)
            
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
                current_year,
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
            
            logger.info(f"🌐 Making PDF request to: {url}")
            logger.info(f"📦 With data: Holding=AV, CrewID={crew_id}, Year={current_year}, Month={current_month}")
            
            response = self.session.post(url, data=form_data, headers=headers, timeout=30)
            
            logger.info(f"📡 PDF response status: {response.status_code}")
            logger.info(f"📡 Content-Type: {response.headers.get('content-type', 'Unknown')}")
            logger.info(f"📡 Content-Length: {response.headers.get('content-length', 'Unknown')}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    # Save PDF file
                    filename = f"{schedule_type}_schedule_{crew_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    file_size = len(response.content)
                    logger.info(f"✅ PDF downloaded: {filename} ({file_size} bytes)")
                    return filename
                elif 'application/json' in content_type:
                    # JSON response - might be error
                    logger.warning(f"⚠️ Got JSON response instead of PDF: {response.text[:200]}")
                    return None
                else:
                    logger.warning(f"⚠️ Unexpected content type: {content_type}")
                    return None
            else:
                logger.error(f"❌ PDF download failed with status: {response.status_code}")
                if response.text:
                    logger.error(f"Error response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ PDF download error: {e}")
            return None

client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID

SCHEDULE_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; }
        .nav-buttons { text-align: center; margin: 15px 0; }
        .nav-button { background: #6c757d; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px; text-decoration: none; display: inline-block; }
        .nav-button:hover { background: #5a6268; }
        .nav-button.active { background: #007bff; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .button:disabled { background: #6c757d; cursor: not-allowed; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .month-section { border: 2px solid #007bff; padding: 15px; margin: 20px 0; border-radius: 8px; }
        .month-header { background: #007bff; color: white; padding: 10px; border-radius: 5px; margin-bottom: 15px; }
        .day-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .day-header { background: #17a2b8; color: white; padding: 8px; border-radius: 3px; margin-bottom: 10px; }
        .assignment { background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #28a745; border-radius: 5px; }
        .assignment-header { display: flex; justify-content: between; align-items: center; margin-bottom: 10px; }
        .activity-code { font-weight: bold; font-size: 1.1em; color: #007bff; }
        .activity-desc { color: #495057; margin-left: 10px; }
        .assignment-category { background: #6c757d; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-left: 10px; }
        .assignment-type { background: #17a2b8; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-left: 5px; }
        .time-info { color: #666; font-size: 0.9em; margin: 5px 0; }
        .real-times { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 8px 0; }
        .time-block { background: #f8f9fa; padding: 8px; border-radius: 4px; border-left: 3px solid #28a745; }
        .time-label { font-weight: bold; color: #495057; font-size: 0.85em; }
        .time-value { font-size: 1em; color: #212529; }
        .flight-info { background: #e7f3ff; padding: 10px; margin: 8px 0; border-radius: 4px; border-left: 3px solid #007bff; }
        .flight-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; font-size: 0.85em; }
        .flight-detail { padding: 3px 0; }
        .flight-detail strong { color: #495057; }
        .status-advanced { color: #28a745; font-weight: bold; }
        .status-delayed { color: #dc3545; font-weight: bold; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; }
        .error { color: #dc3545; text-align: center; padding: 20px; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button active">📋 Schedule View</a>
                <a href="/calendar" class="nav-button">📅 Calendar View</a>
                <a href="/pdf" class="nav-button">📄 PDF Download</a>
            </div>
            <button class="button" onclick="fetchData()" id="refreshBtn">🔄 Refresh Schedule</button>
        </div>

        {% if refresh_message %}
        <div class="success">
            {{ refresh_message }}
        </div>
        {% endif %}

        {% if last_fetch %}
        <div class="info-box">
            <h3>Last updated: {{ last_fetch }}</h3>
            <p>Total days: {{ total_days }} | Total assignments: {{ total_assignments }}</p>
            <p>Current Crew ID: <strong>{{ current_crew_id }}</strong></p>
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
                            <strong>{{ format_date(day.StartDate) if day.StartDate else 'Unknown' }}</strong>
                            <span style="float: right;">DEM: {{ day.Dem }}</span>
                        </div>
                        
                        {% if day.AssignementList and day.AssignementList|length > 0 %}
                            {% for assignment in day.AssignementList %}
                            <div class="assignment">
                                <div class="assignment-header">
                                    <div>
                                        <span class="activity-code">{{ assignment.ActivityCode.strip() if assignment.ActivityCode else 'FLIGHT' }}</span>
                                        <span class="activity-desc">
                                            {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                            {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }} - 
                                            {% endif %}
                                            {{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else 'Flight Duty' }}
                                        </span>
                                        {% if assignment.AssignementCategory %}
                                        <span class="assignment-category">{{ assignment.AssignementCategory }}</span>
                                        {% endif %}
                                        {% if assignment.ActivityType %}
                                        <span class="assignment-type">{{ assignment.ActivityType }}</span>
                                        {% endif %}
                                    </div>
                                </div>
                                
                                <div class="real-times">
                                    <div class="time-block">
                                        <div class="time-label">Departure:</div>
                                        <div class="time-value">{{ format_time(assignment.StartDateLocal) if assignment.StartDateLocal else 'N/A' }}</div>
                                    </div>
                                    <div class="time-block">
                                        <div class="time-label">Arrival:</div>
                                        <div class="time-value">{{ format_time(assignment.EndDateLocal) if assignment.EndDateLocal else 'N/A' }}</div>
                                    </div>
                                </div>

                                {% if assignment.AircraftRegistrationNumber %}
                                <div class="time-info">
                                    <strong>✈️ Aircraft:</strong> {{ assignment.AircraftRegistrationNumber }}
                                    {% if assignment.Fleet %}({{ assignment.Fleet }}){% endif %}
                                </div>
                                {% elif assignment.Fleet %}
                                <div class="time-info">
                                    <strong>✈️ Fleet:</strong> {{ assignment.Fleet }}
                                </div>
                                {% endif %}

                                {% if assignment.FlighAssignement and assignment.FlighAssignement.CommercialFlightNumber != "XXX" %}
                                <div class="flight-info">
                                    <div class="flight-details">
                                        <div class="flight-detail">
                                            <strong>Route:</strong> {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Duration:</strong> {{ assignment.FlighAssignement.Duration }} min (Scheduled: {{ assignment.FlighAssignement.ScheduledDuration }} min)
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Departure:</strong> {{ format_time(assignment.FlighAssignement.ScheduledDepartureDate) }}
                                            {% if assignment.FlighAssignement.DepartureStand %}
                                            | Stand: {{ assignment.FlighAssignement.DepartureStand }}
                                            {% endif %}
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Arrival:</strong> {{ format_time(assignment.FlighAssignement.ScheduledArrivalDate) }}
                                            {% if assignment.FlighAssignement.ArrivalStand %}
                                            | Stand: {{ assignment.FlighAssignement.ArrivalStand }}
                                            {% endif %}
                                        </div>
                                        {% if assignment.FlighAssignement.TimeAdvanced or assignment.FlighAssignement.TimeDelayed %}
                                        <div class="flight-detail">
                                            <strong>Status:</strong>
                                            {% if assignment.FlighAssignement.TimeAdvanced %}
                                            <span class="status-advanced">Advanced</span>
                                            {% endif %}
                                            {% if assignment.FlighAssignement.TimeDelayed %}
                                            <span class="status-delayed">Delayed</span>
                                            {% endif %}
                                        </div>
                                        {% endif %}
                                        {% if assignment.FlighAssignement.OriginAirportICAOCode or assignment.FlighAssignement.FinalAirportICAOCode %}
                                        <div class="flight-detail">
                                            <strong>ICAO Codes:</strong>
                                            {% if assignment.FlighAssignement.OriginAirportICAOCode %}
                                            {{ assignment.FlighAssignement.OriginAirportICAOCode }}
                                            {% endif %}
                                            {% if assignment.FlighAssignement.FinalAirportICAOCode %}
                                            → {{ assignment.FlighAssignement.FinalAirportICAOCode }}
                                            {% endif %}
                                        </div>
                                        {% endif %}
                                    </div>
                                </div>
                                {% endif %}
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
        const button = document.getElementById('refreshBtn');
        button.disabled = true;
        button.textContent = '⏳ Loading...';
        
        fetch('/fetch?refresh=true')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const url = new URL(window.location);
                    url.searchParams.set('refresh', 'success');
                    window.location.href = url.toString();
                } else {
                    alert('Failed: ' + (data.error || 'Unknown error'));
                    button.disabled = false;
                    button.textContent = '🔄 Refresh Schedule';
                }
            })
            .catch(err => {
                alert('Error: ' + err);
                button.disabled = false;
                button.textContent = '🔄 Refresh Schedule';
            });
    }
    </script>
</body>
</html>
"""

CALENDAR_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule - Calendar View</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; }
        .nav-buttons { text-align: center; margin: 15px 0; }
        .nav-button { background: #6c757d; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px; text-decoration: none; display: inline-block; }
        .nav-button:hover { background: #5a6268; }
        .nav-button.active { background: #007bff; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .calendar-container { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .month-calendar { border: 2px solid #007bff; border-radius: 8px; padding: 15px; background: white; }
        .month-header { background: #007bff; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; text-align: center; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
        .calendar-day { border: 1px solid #ddd; min-height: 120px; padding: 5px; background: #f8f9fa; position: relative; }
        .calendar-day.weekend { background: #e9ecef; }
        .calendar-day.empty { background: #f5f5f5; border: none; }
        .day-number { font-weight: bold; font-size: 0.9em; color: #495057; margin-bottom: 3px; }
        .day-dem { position: absolute; top: 5px; right: 5px; font-size: 0.7em; color: #6c757d; }
        .assignment-item { font-size: 0.7em; margin: 1px 0; padding: 1px 3px; border-radius: 2px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
        .assignment-flight { background: #d4edda; border-left: 2px solid #28a745; }
        .assignment-ground { background: #e2e3e5; border-left: 2px solid #6c757d; }
        .assignment-dayoff { background: #fff3cd; border-left: 2px solid #ffc107; }
        .assignment-standby { background: #cce7ff; border-left: 2px solid #007bff; }
        .flight-number { font-weight: bold; color: #0056b3; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; font-size: 0.8em; }
        .weekday-header { background: #17a2b8; color: white; padding: 5px; text-align: center; font-size: 0.8em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule - Calendar View</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button">📋 Schedule View</a>
                <a href="/calendar" class="nav-button active">📅 Calendar View</a>
                <a href="/pdf" class="nav-button">📄 PDF Download</a>
            </div>
            <button class="button" onclick="fetchData()" id="refreshBtn">🔄 Refresh Schedule</button>
        </div>

        {% if refresh_message %}
        <div class="info-box" style="background: #d4edda;">
            {{ refresh_message }}
        </div>
        {% endif %}

        {% if last_fetch %}
        <div class="info-box">
            <h3>Last updated: {{ last_fetch }}</h3>
            <p>Current Crew ID: <strong>{{ current_crew_id }}</strong></p>
        </div>
        {% endif %}

        {% if schedule_data %}
        <div class="calendar-container">
            {% for month in schedule_data %}
            <div class="month-calendar">
                <div class="month-header">
                    <h3>📅 Month {{ loop.index }} - {{ get_month_year(month) }}</h3>
                </div>
                
                <div class="calendar-grid">
                    <!-- Weekday headers -->
                    <div class="weekday-header">Mon</div>
                    <div class="weekday-header">Tue</div>
                    <div class="weekday-header">Wed</div>
                    <div class="weekday-header">Thu</div>
                    <div class="weekday-header">Fri</div>
                    <div class="weekday-header">Sat</div>
                    <div class="weekday-header">Sun</div>
                    
                    <!-- Calendar days -->
                    {% set days_data = get_calendar_days(month) %}
                    {% for day in days_data %}
                    <div class="calendar-day {% if day.weekday >= 5 %}weekend{% endif %} {% if not day.has_data %}empty{% endif %}">
                        {% if day.has_data %}
                        <div class="day-number">{{ day.day }}</div>
                        <div class="day-dem">DEM: {{ day.dem }}</div>
                        
                        {% if day.assignments %}
                            {% for assignment in day.assignments %}
                            <div class="assignment-item {{ assignment.css_class }}" title="{{ assignment.tooltip }}">
                                <span class="flight-number">{{ assignment.flight_number }}</span>
                                {{ assignment.time }}
                            </div>
                            {% endfor %}
                        {% else %}
                            <div class="no-data">No assignments</div>
                        {% endif %}
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
            <div class="info-box" style="background: #f8d7da; color: #721c24;">
                <h3>No schedule data available</h3>
                <p>Click "Refresh Schedule" to load your schedule.</p>
            </div>
        {% endif %}
    </div>

    <script>
    function fetchData() {
        const button = document.getElementById('refreshBtn');
        button.disabled = true;
        button.textContent = '⏳ Loading...';
        
        fetch('/fetch?refresh=true')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const url = new URL(window.location);
                    url.searchParams.set('refresh', 'success');
                    window.location.href = url.toString();
                } else {
                    alert('Failed: ' + (data.error || 'Unknown error'));
                    button.disabled = false;
                    button.textContent = '🔄 Refresh Schedule';
                }
            })
            .catch(err => {
                alert('Error: ' + err);
                button.disabled = false;
                button.textContent = '🔄 Refresh Schedule';
            });
    }
    </script>
</body>
</html>
"""

PDF_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Download - My Crew Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 20px; }
        .nav-buttons { text-align: center; margin: 15px 0; }
        .nav-button { background: #6c757d; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px; text-decoration: none; display: inline-block; }
        .nav-button:hover { background: #5a6268; }
        .nav-button.active { background: #007bff; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .button:disabled { background: #6c757d; cursor: not-allowed; }
        .pdf-button { background: #28a745; }
        .pdf-button:hover { background: #218838; }
        .input-group { margin: 15px 0; text-align: center; }
        .input-label { display: block; margin-bottom: 5px; font-weight: bold; }
        .crew-input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; width: 200px; margin: 0 10px; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; }
        .error { color: #dc3545; text-align: center; padding: 20px; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button">📋 Schedule View</a>
                <a href="/calendar" class="nav-button">📅 Calendar View</a>
                <a href="/pdf" class="nav-button active">📄 PDF Download</a>
            </div>
            <h2>📄 Download Schedule PDF</h2>
        </div>

        {% if pdf_message %}
        <div class="{% if pdf_success %}success{% else %}error{% endif %}">
            {{ pdf_message }}
        </div>
        {% endif %}

        <div class="input-group">
            <label class="input-label">Crew Member ID:</label>
            <input type="text" id="crewId" class="crew-input" placeholder="Enter Crew ID" value="{{ current_crew_id }}">
            <button class="button pdf-button" onclick="updateCrewId()">💾 Update Crew ID</button>
        </div>

        <div class="info-box">
            <h3>Current Crew ID: <strong>{{ current_crew_id }}</strong></h3>
            <p>This ID will be used for PDF downloads</p>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <button class="button pdf-button" onclick="downloadPDF('actual')">📥 Download Actual Schedule PDF</button>
            <button class="button pdf-button" onclick="downloadPDF('scheduled')" style="background: #ffc107; color: black;">📥 Download Scheduled PDF</button>
        </div>

        <div style="text-align: center; color: #666; margin-top: 20px;">
            <p><strong>Note:</strong> PDF downloads may take a few moments to generate and download.</p>
        </div>

    <script>
    function updateCrewId() {
        const crewId = document.getElementById('crewId').value.trim();
        if (!crewId) {
            alert('Please enter a Crew Member ID');
            return;
        }
        
        const button = event.target;
        button.disabled = true;
        button.textContent = '⏳ Updating...';
        
        fetch('/update_crew_id?crew_id=' + crewId)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Failed: ' + (data.error || 'Unknown error'));
                    button.disabled = false;
                    button.textContent = '💾 Update Crew ID';
                }
            })
            .catch(err => {
                alert('Error: ' + err);
                button.disabled = false;
                button.textContent = '💾 Update Crew ID';
            });
    }

    function downloadPDF(type) {
        const button = event.target;
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = '⏳ Generating PDF...';
        
        // Open in new tab to download
        window.open('/download_pdf?type=' + type, '_blank');
        
        // Re-enable button after a delay
        setTimeout(() => {
            button.disabled = false;
            button.textContent = originalText;
        }, 3000);
    }

    // Allow Enter key to update crew ID
    document.getElementById('crewId').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            updateCrewId();
        }
    });

    // Focus on input when page loads
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('crewId').focus();
    });
    </script>
</body>
</html>
"""

def format_date(date_string):
    """Format date string to MMM-DD-YYYY format"""
    try:
        if date_string:
            # Parse the date string
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            # Format as MMM-DD-YYYY (e.g., OCT-01-2025)
            return dt.strftime('%b-%d-%Y').upper()
    except (ValueError, AttributeError):
        pass
    return date_string[:10] if date_string else 'Unknown'

def format_time(date_string):
    """Format date string to HH:MM format"""
    try:
        if date_string:
            # Parse the date string
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            # Format as HH:MM (e.g., 14:30)
            return dt.strftime('%H:%M')
    except (ValueError, AttributeError):
        pass
    return date_string[11:16] if date_string and len(date_string) >= 16 else 'N/A'

def get_month_year(month_data):
    """Extract month and year from the first day of the month"""
    try:
        if month_data and len(month_data) > 0:
            first_day = month_data[0]
            if first_day and 'StartDate' in first_day:
                dt = datetime.fromisoformat(first_day['StartDate'].replace('Z', '+00:00'))
                return dt.strftime('%B %Y')
    except (ValueError, AttributeError, KeyError):
        pass
    return "Unknown Month"

def get_calendar_days(month_data):
    """Convert month data to calendar grid format with 42 days (6 weeks)"""
    calendar_days = []
    
    if not month_data:
        # Return empty calendar if no data
        return [{'has_data': False} for _ in range(42)]
    
    try:
        # Get the first day of the month to determine weekday
        first_day = month_data[0]
        if first_day and 'StartDate' in first_day:
            first_date = datetime.fromisoformat(first_day['StartDate'].replace('Z', '+00:00'))
            # Get weekday (0=Monday, 6=Sunday)
            first_weekday = (first_date.weekday()) % 7
            
            # Add empty days for the beginning of the month
            for _ in range(first_weekday):
                calendar_days.append({'has_data': False})
            
            # Add actual days
            for day in month_data:
                if day and isinstance(day, dict):
                    date_obj = datetime.fromisoformat(day['StartDate'].replace('Z', '+00:00'))
                    assignments_list = []
                    
                    if day.get('AssignementList'):
                        for assignment in day['AssignementList']:
                            # Determine assignment type and styling
                            css_class = "assignment-ground"
                            flight_number = ""
                            time_display = ""
                            tooltip = ""
                            
                            if assignment.get('FlighAssignement') and assignment['FlighAssignement'].get('CommercialFlightNumber') != "XXX":
                                css_class = "assignment-flight"
                                flight_number = f"{assignment['FlighAssignement'].get('Airline', '')} {assignment['FlighAssignement'].get('CommercialFlightNumber', '')}"
                                if assignment.get('StartDateLocal'):
                                    time_display = format_time(assignment['StartDateLocal'])
                            elif "DAY_OFF" in assignment.get('AssignementCategory', ''):
                                css_class = "assignment-dayoff"
                                flight_number = "DAY OFF"
                            elif "STAND_BY" in assignment.get('AssignementCategory', ''):
                                css_class = "assignment-standby"
                                flight_number = "STANDBY"
                            else:
                                flight_number = assignment.get('ActivityCode', 'GROUND').strip()
                            
                            tooltip = assignment.get('ActivityDesc', '').strip()
                            if not tooltip and flight_number:
                                tooltip = flight_number
                            
                            assignments_list.append({
                                'css_class': css_class,
                                'flight_number': flight_number,
                                'time': time_display,
                                'tooltip': tooltip
                            })
                    
                    calendar_days.append({
                        'has_data': True,
                        'day': date_obj.day,
                        'weekday': date_obj.weekday(),
                        'dem': day.get('Dem', 0),
                        'assignments': assignments_list
                    })
            
            # Fill remaining days to complete 6 weeks (42 days total)
            while len(calendar_days) < 42:
                calendar_days.append({'has_data': False})
                
    except (ValueError, AttributeError, KeyError) as e:
        logger.error(f"Error processing calendar data: {e}")
        # Return empty calendar on error
        return [{'has_data': False} for _ in range(42)]
    
    return calendar_days

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    
    # 🔄 Automatically fetch fresh data on every page load
    logger.info("🔄 Auto-fetching fresh data on page load...")
    new_data = client.get_schedule_data()
    if new_data is not None:
        schedule_data = new_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Auto-fetch completed successfully!")
    # If fetch fails, keep existing data but log warning
    elif schedule_data is None:
        logger.warning("⚠️ Auto-fetch failed and no existing data available")
    
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
    
    refresh_message = "Data refreshed successfully!" if request.args.get('refresh') == 'success' else None
    
    return render_template_string(SCHEDULE_VIEW_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        refresh_message=refresh_message,
        current_crew_id=current_crew_id,
        format_date=format_date,
        format_time=format_time
    )

@app.route('/calendar')
def calendar_view():
    global schedule_data, last_fetch_time
    
    # Auto-fetch data if needed
    if schedule_data is None:
        logger.info("🔄 Auto-fetching fresh data for calendar view...")
        new_data = client.get_schedule_data()
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    refresh_message = "Data refreshed successfully!" if request.args.get('refresh') == 'success' else None
    
    return render_template_string(CALENDAR_VIEW_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        current_crew_id=current_crew_id,
        refresh_message=refresh_message,
        get_month_year=get_month_year,
        get_calendar_days=get_calendar_days,
        format_time=format_time
    )

@app.route('/pdf')
def pdf_view():
    pdf_message = request.args.get('pdf_message')
    pdf_success = request.args.get('pdf_success') == 'true'
    
    return render_template_string(PDF_VIEW_TEMPLATE,
        current_crew_id=current_crew_id,
        pdf_message=pdf_message,
        pdf_success=pdf_success
    )

@app.route('/update_crew_id')
def update_crew_id():
    global current_crew_id
    new_crew_id = request.args.get('crew_id', '').strip()
    
    if new_crew_id:
        current_crew_id = new_crew_id
        logger.info(f"✅ Crew ID updated to: {current_crew_id}")
        return {"success": True, "new_crew_id": current_crew_id}
    else:
        return {"success": False, "error": "No crew ID provided"}

@app.route('/download_pdf')
def download_pdf():
    schedule_type = request.args.get('type', 'actual')
    
    try:
        logger.info(f"📄 PDF download requested for {schedule_type} schedule, crew {current_crew_id}")
        filename = client.download_schedule_pdf(current_crew_id, schedule_type)
        
        if filename and os.path.exists(filename):
            logger.info(f"✅ Sending PDF file: {filename}")
            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
        else:
            logger.error(f"❌ PDF file not found: {filename}")
            return {"success": False, "error": "PDF generation failed"}, 400
            
    except Exception as e:
        logger.error(f"❌ PDF download error: {e}")
        return {"success": False, "error": str(e)}, 500

@app.route('/fetch')
def fetch_data():
    global schedule_data, last_fetch_time
    try:
        logger.info("🔄 Manual data refresh requested - creating fresh session...")
        new_data = client.get_schedule_data()
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("✅ Data updated successfully with fresh session!")
            return {"success": True}
        logger.error("❌ Data refresh failed - no data received")
        return {"success": False, "error": "Failed to fetch data"}
    except Exception as e:
        logger.error(f"❌ Error in /fetch endpoint: {e}")
        return {"success": False, "error": str(e)}

def main():
    global schedule_data, last_fetch_time
    logger.info("🚀 Starting Crew Schedule Application...")
    initial_data = client.get_schedule_data()
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    app.run(host='0.0.0.0', port=8000, debug=False)

if __name__ == "__main__":
    main()