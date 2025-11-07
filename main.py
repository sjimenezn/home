#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Display Version
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
    
    def get_schedule_data(self, crew_id=None):
        try:
            target_crew_id = crew_id or current_crew_id
            logger.info(f"📊 Fetching schedule data for crew: {target_crew_id}...")
            
            # Always create a new session to ensure fresh data
            self.create_new_session()
            
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            
            if not self.login(email, password):
                return None
            
            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {
                "timeZoneOffset": -300,
                "crewMemberUniqueId": target_crew_id  # THIS IS THE KEY LINE!
            }
            headers = {
                "Authorization": self.auth_token, "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json", "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            
            logger.info(f"🌐 Making API request for crew {target_crew_id}...")
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # Log data structure for debugging
                if isinstance(data, list):
                    logger.info(f"✅ Schedule data fetched for crew {target_crew_id}! Structure: {len(data)} months")
                    if data and isinstance(data[0], list):
                        logger.info(f"📅 First month has {len(data[0])} days")
                logger.info(f"✅ Schedule data fetched successfully for crew {target_crew_id}!")
                return data
                
            logger.error(f"❌ Failed to fetch schedule data for crew {target_crew_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data for crew {crew_id}: {e}")
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
        .flight-info { background: #e7f3ff; padding: 10px; margin: 8px 0; border-radius: 4px; border-left: 3px solid #007bff; }
        .flight-header { font-weight: bold; color: #0056b3; margin-bottom: 5px; }
        .flight-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; font-size: 0.85em; }
        .flight-detail { padding: 3px 0; }
        .flight-detail strong { color: #495057; }
        .status-advanced { color: #28a745; font-weight: bold; }
        .status-delayed { color: #dc3545; font-weight: bold; }
        .no-data { color: #6c757d; text-align: center; padding: 10px; }
        .error { color: #dc3545; text-align: center; padding: 20px; }
        .success { color: #155724; background: #d4edda; padding: 10px; border-radius: 5px; margin: 10px 0; text-align: center; }
        .assignment-id { color: #999; font-size: 0.7em; float: right; }
        .current-day { border: 3px solid #ffc107; background: #fff3cd; }
        .actual-time { color: #dc3545; font-weight: bold; }
        .scheduled-time { color: #6c757d; }
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
                    <h3>📅 {{ month_names[loop.index0] }}</h3>
                </div>
                {% for day in month %}
                    {% if day and day is mapping %}
                    <div class="day-card {% if day.StartDate[:10] == current_date %}current-day{% endif %}" id="day-{{ day.StartDate[:10] }}">
                        <div class="day-header">
                            <strong>{{ day.StartDate[:10] if day.StartDate else 'Unknown' }}</strong>
                            <span style="float: right;">DEM: {{ day.Dem }}</span>
                        </div>
                        
                        {% if day.AssignementList and day.AssignementList|length > 0 %}
                            {% for assignment in day.AssignementList %}
                            <div class="assignment">
                                <div class="assignment-header">
                                    <div>
                                        <span class="activity-code">{{ assignment.ActivityCode.strip() if assignment.ActivityCode else 'FLIGHT' }}</span>
                                        <span class="activity-desc">{{ assignment.ActivityDesc.strip() if assignment.ActivityDesc else 'Flight Duty' }}</span>
                                        {% if assignment.AssignementCategory %}
                                        <span class="assignment-category">{{ assignment.AssignementCategory }}</span>
                                        {% endif %}
                                        {% if assignment.ActivityType %}
                                        <span class="assignment-type">{{ assignment.ActivityType }}</span>
                                        {% endif %}
                                    </div>
                                    <span class="assignment-id">#{{ assignment.Id }}</span>
                                </div>
                                
                                <div class="time-info">
                                    <strong>🕐 Time:</strong> 
                                    <span class="actual-time">{{ assignment.StartDateLocal[11:16] if assignment.StartDateLocal else 'N/A' }}</span> 
                                    to <span class="actual-time">{{ assignment.EndDateLocal[11:16] if assignment.EndDateLocal else 'N/A' }}</span>
                                    ({{ assignment.StartDateLocal[:10] if assignment.StartDateLocal else '' }})
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
                                    <div class="flight-header">
                                        🛫 Flight: {{ assignment.FlighAssignement.Airline }} {{ assignment.FlighAssignement.CommercialFlightNumber }}
                                    </div>
                                    
                                    <div class="flight-details">
                                        <div class="flight-detail">
                                            <strong>Route:</strong> {{ assignment.FlighAssignement.OriginAirportIATACode }} → {{ assignment.FlighAssignement.FinalAirportIATACode }}
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Duration:</strong> {{ assignment.FlighAssignement.Duration }} min (Scheduled: {{ assignment.FlighAssignement.ScheduledDuration }} min)
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Departure:</strong> 
                                            <span class="scheduled-time">{{ assignment.FlighAssignement.ScheduledDepartureDate[11:16] if assignment.FlighAssignement.ScheduledDepartureDate else 'N/A' }}</span>
                                            {% if assignment.FlighAssignement.DepartureDate %}
                                            → <span class="actual-time">{{ assignment.FlighAssignement.DepartureDate[11:16] if assignment.FlighAssignement.DepartureDate else 'N/A' }}</span>
                                            {% endif %}
                                            {% if assignment.FlighAssignement.DepartureStand %}
                                            | Stand: {{ assignment.FlighAssignement.DepartureStand }}
                                            {% endif %}
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Arrival:</strong> 
                                            <span class="scheduled-time">{{ assignment.FlighAssignement.ScheduledArrivalDate[11:16] if assignment.FlighAssignement.ScheduledArrivalDate else 'N/A' }}</span>
                                            {% if assignment.FlighAssignement.ArrivalDate %}
                                            → <span class="actual-time">{{ assignment.FlighAssignement.ArrivalDate[11:16] if assignment.FlighAssignement.ArrivalDate else 'N/A' }}</span>
                                            {% endif %}
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

    // Scroll to current date on page load
    document.addEventListener('DOMContentLoaded', function() {
        const currentDayElement = document.querySelector('.current-day');
        if (currentDayElement) {
            currentDayElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
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
        .nav-button.active { background: #28a745; }
        .button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #0056b3; }
        .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; margin: 20px 0; }
        .calendar-day { border: 1px solid #ddd; padding: 5px; border-radius: 5px; min-height: 110px; background: white; }
        .calendar-day-header { background: #6c757d; color: white; padding: 5px; border-radius: 3px; margin-bottom: 5px; text-align: center; font-weight: bold; font-size: 1.5em; }
        .calendar-day.current-day { border: 3px solid #dc3545; background: #f8d7da; }
        .calendar-day.weekend { background: #f8f9fa; }
        .calendar-day.empty { background: #f5f5f5; border: 1px dashed #ddd; }
        .assignment-item { background: #e7f3ff; padding: 3px; margin: 2px 0; border-radius: 3px; border-left: none; font-size: 0.8em; }
        .assignment-flight { background: #f8f9fa; border-left: none; }
        .assignment-ground { background: #fff3cd; border-left: none; }
        .flight-number { font-weight: bold; color: #dc3545; font-size: 1.6em; display: inline; }
        .departure-stand { font-weight: bold; color: #0056b3; font-size: 1.6em; display: inline; margin-left: 8px; }
        .route { font-size: 1.4em; color: #000; font-weight: bold; margin: 3px 0; }
        .flight-times { font-size: 1.2em; color: #000; font-weight: bold; margin-top: 3px; }
        .status-on-time { color: #28a745; font-weight: bold; margin-left: 5px; }
        .status-delayed { color: #dc3545; font-weight: bold; margin-left: 5px; }
        .no-assignments { color: #6c757d; text-align: center; font-size: 0.8em; padding: 10px; }
        .month-section { margin: 30px 0; }
        .month-header { background: #000; color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; text-align: center; position: relative; }
        .month-navigation { display: flex; justify-content: center; align-items: center; gap: 20px; }
        .chevron { background: none; border: none; color: white; font-size: 2em; cursor: pointer; padding: 0 15px; }
        .chevron:hover { color: #ffc107; }
        .chevron:disabled { color: #6c757d; cursor: not-allowed; }
        .month-title { font-size: 1.5em; margin: 0 20px; }
        .week-days { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-bottom: 10px; }
        .week-day { text-align: center; font-weight: bold; padding: 8px; background: #6c757d; color: white; border-radius: 4px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>My Crew Schedule - Calendar View</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button">Schedule View</a>
                <a href="/calendar" class="nav-button active">Calendar View</a>
                <a href="/pdf" class="nav-button">PDF Download</a>
            </div>
            <button class="button" onclick="fetchData()" id="refreshBtn">Refresh Schedule</button>
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
            <div class="month-section {% if loop.index0 != current_month_index %}hidden{% endif %}" id="month-{{ loop.index0 }}" data-month-index="{{ loop.index0 }}">
                <div class="month-header">
                    <div class="month-navigation">
                        <button class="chevron" onclick="navigateMonth(-1)" id="prevMonth">〈</button>
                        <div class="month-title">{{ month_names[loop.index0] }}</div>
                        <button class="chevron" onclick="navigateMonth(1)" id="nextMonth">〉</button>
                    </div>
                </div>
                
                <div class="week-days">
                    <div class="week-day">MON</div>
                    <div class="week-day">TUE</div>
                    <div class="week-day">WED</div>
                    <div class="week-day">THU</div>
                    <div class="week-day">FRI</div>
                    <div class="week-day">SAT</div>
                    <div class="week-day">SUN</div>
                </div>
                
                <div class="calendar-grid">
                    {% for day in month_calendars[loop.index0] %}
                        {% if day %}
                            <div class="calendar-day {% if day.date == current_date %}current-day{% endif %} {% if day.weekend %}weekend{% endif %}" id="cal-day-{{ day.date }}">
                                <div class="calendar-day-header">
                                    {{ day.day_number }}
                                </div>
                                
                                {% if day.assignments and day.assignments|length > 0 %}
                                    {% for assignment in day.assignments %}
                                    <div class="assignment-item {% if assignment.is_flight %}assignment-flight{% else %}assignment-ground{% endif %}">
                                        {% if assignment.is_flight %}
                                            <div>
                                                <span class="flight-number">{{ assignment.flight_number }}</span>
                                                {% if assignment.departure_stand %}
                                                    <span class="departure-stand">{{ assignment.departure_stand }}</span>
                                                {% endif %}
                                            </div>
                                            <div class="route">
                                                {{ assignment.origin }}-{{ assignment.destination }}
                                            </div>
                                            <div class="flight-times">
                                                {{ assignment.departure_time }} - {{ assignment.arrival_time }}
                                                {% if assignment.time_advanced %}<span class="status-on-time">On Time</span>{% endif %}
                                                {% if assignment.time_delayed %}<span class="status-delayed">Delayed</span>{% endif %}
                                                {% if assignment.aircraft_registration %} | {{ assignment.aircraft_registration }}{% endif %}
                                            </div>
                                        {% else %}
                                            <div style="font-weight: bold; color: #000; font-size: 1.4em;">
                                                {{ assignment.activity_code }}
                                            </div>
                                            <div style="font-size: 1.2em; color: #000; font-weight: bold;">
                                                {{ assignment.start_time }} - {{ assignment.end_time }}
                                            </div>
                                        {% endif %}
                                    </div>
                                    {% endfor %}
                                {% else %}
                                    <div class="no-assignments">No assignments</div>
                                {% endif %}
                            </div>
                        {% else %}
                            <div class="calendar-day empty"></div>
                        {% endif %}
                    {% endfor %}
                </div>
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
    let currentMonthIndex = {{ current_month_index }};
    const totalMonths = {{ schedule_data|length if schedule_data else 0 }};

    function navigateMonth(direction) {
        const newIndex = currentMonthIndex + direction;
        
        // Check bounds
        if (newIndex >= 0 && newIndex < totalMonths) {
            // Hide current month
            document.getElementById(`month-${currentMonthIndex}`).classList.add('hidden');
            
            // Show new month
            document.getElementById(`month-${newIndex}`).classList.remove('hidden');
            
            // Update current index
            currentMonthIndex = newIndex;
            
            // Update button states
            updateNavigationButtons();
            
            // Scroll to top of month section
            document.getElementById(`month-${newIndex}`).scrollIntoView({ behavior: 'smooth' });
        }
    }

    function updateNavigationButtons() {
        document.getElementById('prevMonth').disabled = currentMonthIndex === 0;
        document.getElementById('nextMonth').disabled = currentMonthIndex === totalMonths - 1;
    }

    function fetchData() {
        const button = document.getElementById('refreshBtn');
        button.disabled = true;
        button.textContent = 'Loading...';
        
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
                    button.textContent = 'Refresh Schedule';
                }
            })
            .catch(err => {
                alert('Error: ' + err);
                button.disabled = false;
                button.textContent = 'Refresh Schedule';
            });
    }

    // Initialize on page load - SCROLL MONTH TO TOP instead of current date
    document.addEventListener('DOMContentLoaded', function() {
        updateNavigationButtons();
        
        // Scroll the current month to the very top of the viewport
        const currentMonthElement = document.getElementById(`month-${currentMonthIndex}`);
        if (currentMonthElement) {
            currentMonthElement.scrollIntoView({ behavior: 'smooth' });
        }
    });
    </script>
</body>
</html>
"""

PDF_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Download - My Crew Schedule</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* --- Sober & Mobile-First Redesign --- */
        
        /* Base settings */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 10px;
            background: #121212; /* Very dark background */
            color: #f0f0f0;      /* Light text */
            font-size: 18px;     /* Larger base font for mobile */
            line-height: 1.6;
        }
        
        /* Main content container */
        .container {
            max-width: 600px; /* Constrains width on desktop, 100% on mobile */
            margin: 10px auto;
            background: #2a2a2a; /* Dark card background */
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #444;
        }

        /* Headers */
        .header {
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #444;
            padding-bottom: 20px;
        }
        .header h1 {
            color: #ffffff;
            font-weight: 600;
            margin: 0;
        }
        .header h2 {
            color: #f0f0f0;
            font-weight: 300;
            margin: 10px 0 0;
        }

        /* Navigation buttons */
        .nav-buttons {
            display: flex;
            flex-wrap: wrap; /* Allows buttons to stack on small screens */
            justify-content: center;
            gap: 10px;
            margin: 20px 0;
        }
        .nav-button {
            padding: 10px 15px;
            border: 1px solid #666;
            border-radius: 5px;
            background: #3a3a3a;
            color: #f0f0f0;
            text-decoration: none;
            font-size: 0.9em;
            font-weight: 500;
            flex-grow: 1; /* Makes buttons share space */
            text-align: center;
        }
        .nav-button:hover {
            background: #4a4a4a;
        }
        .nav-button.active {
            background: #f0f0f0; /* Active button is light */
            color: #121212;
            border-color: #f0f0f0;
            font-weight: 700;
        }

        /* Input groups */
        .input-group {
            margin-bottom: 25px;
        }
        .input-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #ccc;
            font-size: 0.95em;
        }
        
        /* Main text input style */
        .crew-input {
            width: 100%;
            padding: 14px 16px; /* Large, tappable inputs */
            font-size: 1.1em;   /* Bigger text in input */
            color: #ffffff;
            background: #1e1e1e;
            border: 1px solid #555;
            border-radius: 5px;
            box-sizing: border-box; /* Critical for 100% width */
        }
        
        /* Flex layout for search + clear button */
        .flex-group {
            display: flex;
            gap: 10px;
        }
        .flex-group .crew-input {
            flex-grow: 1; /* Input takes available space */
        }

        /* Button base style */
        .button {
            width: 100%;
            padding: 16px; /* Large, tappable buttons */
            font-size: 1.15em;
            font-weight: 700;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            box-sizing: border-box;
        }
        .button:disabled {
            background: #333;
            color: #777;
            cursor: not-allowed;
        }

        /* Specific button colors (Sober) */
        #updateCrewBtn {
            background: #f0f0f0; /* Primary action is light */
            color: #121212;
        }
        #updateCrewBtn:hover {
            background: #ffffff;
        }
        
        .pdf-button {
            background: #555; /* Dark grey for downloads */
            color: #ffffff;
            margin-top: 10px;
        }
        .pdf-button:hover {
            background: #666;
        }
        
        .pdf-button.scheduled {
            background: #444; /* Even darker for secondary download */
        }
        .pdf-button.scheduled:hover {
            background: #555;
        }
        
        .button.clear-btn {
            width: auto; /* Override 100% width */
            flex-shrink: 0;
            background: #4a4a4a;
            color: #f0f0f0;
            font-size: 1.1em;
            padding: 14px 16px;
        }

        /* Info box */
        .info-box {
            background: #1e1e1e;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
            border: 1px solid #444;
        }
        .info-box strong {
            color: #ffffff;
            font-size: 1.2em;
        }

        /* Alerts */
        .success, .error {
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            font-weight: 600;
            text-align: center;
        }
        .success {
            background: #2e4b2e;
            color: #d4edda;
        }
        .error {
            background: #5a3a3a;
            color: #f8d7da;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button">📋 Schedule</a>
                <a href="/calendar" class="nav-button">📅 Calendar</a>
                <a href="/pdf" class="nav-button active">📄 PDF</a>
            </div>
            <h2>Download Schedule PDF</h2>
        </div>

        {% if pdf_message %}
        <div class="{% if pdf_success %}success{% else %}error{% endif %}">
            {{ pdf_message }}
        </div>
        {% endif %}

        <div class="input-group flex-group">
            <div style="flex-grow: 1;">
                <label class="input-label" for="crewSelectorInput">Select Crew Member:</label>
                <input type="text" id="crewSelectorInput" list="crewDatalist" class="crew-input" onchange="handleCrewSelect()" placeholder="Start typing a name...">
                <datalist id="crewDatalist">
                    <option value="ABONDANO COZZARELLI CARLOS ERNESTO 80412229">
                    <option value="ABONDANO VARGAS WILMAN  80815221">
                    <option value="ABRIL COTE CARLOS ALBERTO 91524541">
                    <option value="Sergio Jimenez 32385184">
                    <option value="Jane Doe 12345678">
                    <option value="John Smith 87654321">
                    <option value="ZUÑIGA LOPEZ JUAN ESTEBAN 80038857">
                </datalist>
            </div>
            <button class="button clear-btn" onclick="clearDropdown()">Clear</button>
        </div>

        <div class="input-group">
            <label class="input-label" for="crewId">Selected Crew ID:</label>
            <input type="text" id="crewId" class="crew-input" placeholder="Enter Crew ID" value="{{ current_crew_id }}">
        </div>
        
        <div class="input-group">
            <button class="button" id="updateCrewBtn" onclick="updateCrewId()">💾 Update Crew ID</button>
        </div>

        <div class="info-box">
            <p>Current ID for Download:<br><strong>{{ current_crew_id }}</strong></p>
        </div>

        <div class="input-group" style="margin-top: 30px;">
            <button class="button pdf-button" onclick="downloadPDF('actual')">📥 Download Actual PDF</button>
            <button class="button pdf-button scheduled" onclick="downloadPDF('scheduled')">📥 Download Scheduled PDF</button>
        </div>

    </div>

    <script>
    
    function handleCrewSelect() {
        const input = document.getElementById('crewSelectorInput');
        const selectedValue = input.value.trim();
        
        if (selectedValue.length >= 8) {
            const crewId = selectedValue.slice(-8).trim();
            document.getElementById('crewId').value = crewId;
            document.getElementById('updateCrewBtn').click();
        }
    }

    function clearDropdown() {
        document.getElementById("crewSelectorInput").value = "";
        document.getElementById("crewSelectorInput").focus();
    }

    function updateCrewId() {
        const crewId = document.getElementById('crewId').value.trim();
        if (!crewId) {
            alert('Please enter a Crew Member ID');
            return;
        }
        
        const button = document.getElementById('updateCrewBtn');
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
        
        window.open('/download_pdf?type=' + type, '_blank');
        
        setTimeout(() => {
            button.disabled = false;
            button.textContent = originalText;
        }, 3000);
    }

    document.getElementById('crewId').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            updateCrewId();
        }
    });

    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('crewSelectorInput').focus();
    });
    </script>
</body>
</html>
"""



def get_month_name_from_data(month_data):
    """Extract month name from the first valid day in month data"""
    if not month_data or not isinstance(month_data, list):
        return "Unknown Month"
    
    for day in month_data:
        if day and isinstance(day, dict) and day.get('StartDate'):
            try:
                date_str = day['StartDate'][:10]  # Get YYYY-MM-DD
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%B %Y')  # e.g., "October 2025"
            except (ValueError, KeyError):
                continue
    
    return "Unknown Month"

def get_current_month_index(schedule_data, current_date):
    """Find which month index contains the current date"""
    if not schedule_data or not isinstance(schedule_data, list):
        return 0
    
    for month_index, month in enumerate(schedule_data):
        if month and isinstance(month, list):
            for day in month:
                if day and isinstance(day, dict) and day.get('StartDate', '').startswith(current_date):
                    return month_index
    return 0  # Fallback to first month if not found

def create_calendar_view_data(month_data, month_name):
    """Convert month data to calendar grid format"""
    if not month_data or not isinstance(month_data, list):
        return []
    
    # Find the first day of the month to determine calendar start
    first_day = None
    for day in month_data:
        if day and isinstance(day, dict) and day.get('StartDate'):
            try:
                date_str = day['StartDate'][:10]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                first_day = date_obj.replace(day=1)
                break
            except (ValueError, KeyError):
                continue
    
    if not first_day:
        return []
    
    # Calculate calendar start (first Monday of the calendar view)
    calendar_start = first_day - timedelta(days=first_day.weekday())
    
    # Create 6 weeks of calendar data (42 days)
    calendar_days = []
    for i in range(42):
        current_date = calendar_start + timedelta(days=i)
        calendar_day = None
        
        # Check if this date exists in our month data
        date_str = current_date.strftime('%Y-%m-%d')
        for day_data in month_data:
            if day_data and isinstance(day_data, dict) and day_data.get('StartDate', '').startswith(date_str):
                # Process assignments for this day
                assignments = []
                for assignment in day_data.get('AssignementList', []):
                    # Check if it's a flight assignment
                    flight_data = assignment.get('FlighAssignement')
                    if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                        assignment_data = {
                            'is_flight': True,
                            'flight_number': flight_data.get('CommercialFlightNumber', ''),
                            'airline': flight_data.get('Airline', ''),
                            'origin': flight_data.get('OriginAirportIATACode', '').strip(),
                            'destination': flight_data.get('FinalAirportIATACode', '').strip(),
                            'departure_stand': flight_data.get('DepartureStand', '').strip(),
                            'departure_time': flight_data.get('ScheduledDepartureDate', '')[11:16] if flight_data.get('ScheduledDepartureDate') else 'N/A',
                            'arrival_time': flight_data.get('ScheduledArrivalDate', '')[11:16] if flight_data.get('ScheduledArrivalDate') else 'N/A',
                            'time_advanced': flight_data.get('TimeAdvanced', False),
                            'time_delayed': flight_data.get('TimeDelayed', False),
                            'aircraft_registration': assignment.get('AircraftRegistrationNumber', '').strip()
                        }
                    else:
                        assignment_data = {
                            'is_flight': False,
                            'activity_code': assignment.get('ActivityCode', '').strip() or 'DUTY',
                            'start_time': assignment.get('StartDateLocal', '')[11:16] if assignment.get('StartDateLocal') else 'N/A',
                            'end_time': assignment.get('EndDateLocal', '')[11:16] if assignment.get('EndDateLocal') else 'N/A'
                        }
                    
                    assignments.append(assignment_data)
                
                calendar_day = {
                    'date': date_str,
                    'day_number': current_date.day,
                    'weekend': current_date.weekday() >= 5,  # Saturday=5, Sunday=6
                    'assignments': assignments
                }
                break
        
        # If no data for this date, create empty day if it's in the current month
        if not calendar_day and current_date.month == first_day.month:
            calendar_day = {
                'date': date_str,
                'day_number': current_date.day,
                'weekend': current_date.weekday() >= 5,
                'assignments': []
            }
        
        calendar_days.append(calendar_day)
    
    return calendar_days

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    
    # 🔄 ADDED: Automatically fetch fresh data on every page load
    logger.info("🔄 Auto-fetching fresh data on page load...")
    new_data = client.get_schedule_data(current_crew_id)
    if new_data is not None:
        schedule_data = new_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Auto-fetch completed successfully!")
    # If fetch fails, keep existing data but log warning
    elif schedule_data is None:
        logger.warning("⚠️ Auto-fetch failed and no existing data available")
    
    total_days = 0
    total_assignments = 0
    month_names = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    if schedule_data and isinstance(schedule_data, list):
        # Generate month names for display
        month_names = [get_month_name_from_data(month) for month in schedule_data]
        
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
        month_names=month_names,
        current_date=current_date
    )

@app.route('/calendar')
def calendar_view():
    global schedule_data, last_fetch_time
    
    # Auto-fetch data if needed
    if schedule_data is None:
        logger.info("🔄 Auto-fetching data for calendar view...")
        new_data = client.get_schedule_data(current_crew_id)
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total_days = 0
    total_assignments = 0
    month_names = []
    month_calendars = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    if schedule_data and isinstance(schedule_data, list):
        # Generate month names and calendar data
        for month in schedule_data:
            month_name = get_month_name_from_data(month)
            month_names.append(month_name)
            calendar_data = create_calendar_view_data(month, month_name)
            month_calendars.append(calendar_data)
            
            if isinstance(month, list):
                total_days += len(month)
                for day in month:
                    if isinstance(day, dict):
                        assignments = day.get('AssignementList', [])
                        total_assignments += len(assignments)
    
    # Find current month index
    current_month_index = get_current_month_index(schedule_data, current_date)
    
    refresh_message = "Data refreshed successfully!" if request.args.get('refresh') == 'success' else None
    
    return render_template_string(CALENDAR_VIEW_TEMPLATE,
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        refresh_message=refresh_message,
        current_crew_id=current_crew_id,
        month_names=month_names,
        month_calendars=month_calendars,
        current_date=current_date,
        current_month_index=current_month_index
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
    global current_crew_id, schedule_data, last_fetch_time
    new_crew_id = request.args.get('crew_id', '').strip()
    
    if new_crew_id:
        current_crew_id = new_crew_id
        logger.info(f"✅ Crew ID updated to: {current_crew_id}")
        
        # Clear cached data so it fetches fresh data for the new crew member
        schedule_data = None
        last_fetch_time = None
        
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
        new_data = client.get_schedule_data(current_crew_id)
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


@app.route('/debug_test')
def debug_test():
    """Better test to see what data we're actually getting"""
    test_crew_id = "26559705"
    
    # Get data for test crew
    test_data = client.get_schedule_data(test_crew_id)
    
    # Get your data for comparison  
    your_data = client.get_schedule_data()
    
    # Compare the actual content
    if test_data == your_data:
        return "❌ SAME DATA - API is ignoring crew ID, returning YOUR data"
    else:
        # Check if it's actually different
        if test_data and your_data:
            # Compare specific fields
            your_first_flight = None
            test_first_flight = None
            
            # Extract first flight number from each dataset
            for month in your_data:
                for day in month:
                    for assignment in day.get('AssignementList', []):
                        flight_data = assignment.get('FlighAssignement')
                        if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                            your_first_flight = flight_data.get('CommercialFlightNumber')
                            break
            
            for month in test_data:
                for day in month:
                    for assignment in day.get('AssignementList', []):
                        flight_data = assignment.get('FlighAssignement')
                        if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                            test_first_flight = flight_data.get('CommercialFlightNumber')
                            break
            
            if your_first_flight == test_first_flight:
                return f"❌ SAME FLIGHTS - Both have flight {your_first_flight}"
            else:
                return f"✅ DIFFERENT DATA! Your flight: {your_first_flight}, Their flight: {test_first_flight}"
        else:
            return "❌ One dataset is empty"
            
def main():
    global schedule_data, last_fetch_time
    logger.info("🚀 Starting Crew Schedule Application...")
    initial_data = client.get_schedule_data(current_crew_id)
    if initial_data is not None:
        schedule_data = initial_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Initial data fetch successful!")
    app.run(host='0.0.0.0', port=8000, debug=False)

if __name__ == "__main__":
    main()