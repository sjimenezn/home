#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Display Version
"""

import os
import time
import logging
import requests
import json
from datetime import datetime
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✈️ My Crew Schedule</h1>
            <div class="nav-buttons">
                <a href="/" class="nav-button active">📋 Schedule View</a>
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
                                    <strong>🕐 Time:</strong> {{ assignment.StartDateLocal[:16] if assignment.StartDateLocal else 'N/A' }} 
                                    to {{ assignment.EndDateLocal[:16] if assignment.EndDateLocal else 'N/A' }}
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
                                            <strong>Departure:</strong> {{ assignment.FlighAssignement.ScheduledDepartureDate[:16] }}
                                            {% if assignment.FlighAssignement.DepartureStand %}
                                            | Stand: {{ assignment.FlighAssignement.DepartureStand }}
                                            {% endif %}
                                        </div>
                                        <div class="flight-detail">
                                            <strong>Arrival:</strong> {{ assignment.FlighAssignement.ScheduledArrivalDate[:16] }}
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

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    
    # 🔄 ADDED: Automatically fetch fresh data on every page load
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
        current_crew_id=current_crew_id
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