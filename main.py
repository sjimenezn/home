#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Display Version
"""

import os
import time
import logging
import requests
import json
import io # NEW: For in-memory file handling (PDF)
from datetime import datetime, timedelta
# Added jsonify for the new API endpoint
from flask import Flask, render_template_string, request, send_file, jsonify 

# Configuration
DEFAULT_CREW_ID = "32385184"
CREW_NAMES_FILE = 'name_list.txt' # Configuration for the list file

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Data Loading Functions ---

def load_crew_name_list():
    """Loads the large list of crew names from the text file."""
    try:
        # Assumes name_list.txt is in the same directory (workspace)
        with open(CREW_NAMES_FILE, 'r') as f:
            crew_list = [line.strip() for line in f if line.strip()]
            logger.info(f"✅ Successfully loaded {len(crew_list)} crew names from {CREW_NAMES_FILE}.")
            return crew_list
    except FileNotFoundError:
        logger.error(f"🚨 Error: Crew names file '{CREW_NAMES_FILE}' not found. Datalist will be empty.")
        return []
    except Exception as e:
        logger.error(f"🚨 Error reading crew names file: {e}")
        return []


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
            # SECURITY FIX: ENSURE CREDENTIALS ARE SET
            if not email or not password:
                logger.error("❌ Login failed: CREW_EMAIL or CREW_PASSWORD environment variables are not set.")
                return False
            
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
            
            self.create_new_session()
            
            # SECURITY FIX: REMOVED HARDCODED FALLBACKS
            email = os.getenv('CREW_EMAIL')
            password = os.getenv('CREW_PASSWORD')
            
            if not self.login(email, password):
                return None
            
            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {
                "timeZoneOffset": -300,
                "crewMemberUniqueId": target_crew_id
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
                if isinstance(data, list):
                    logger.info(f"✅ Schedule data fetched for crew {target_crew_id}! Structure: {len(data)} months")
                logger.info(f"✅ Schedule data fetched successfully for crew {target_crew_id}!")
                return data
                
            logger.error(f"❌ Failed to fetch schedule data for crew {target_crew_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data for crew {crew_id}: {e}")
            return None

    def download_schedule_pdf(self, crew_id, schedule_type="actual", month="", year=""):
        """Download schedule PDF using multipart form data, returning data buffer and filename."""
        try:
            logger.info(f"📥 Downloading {schedule_type} schedule PDF for crew {crew_id}...")
            
            self.create_new_session()
            
            # SECURITY FIX: REMOVED HARDCODED FALLBACKS
            email = os.getenv('CREW_EMAIL')
            password = os.getenv('CREW_PASSWORD')
            
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
                f"--{boundary}", 'Content-Disposition: form-data; name="Holding"', '', 'AV',
                f"--{boundary}", 'Content-Disposition: form-data; name="CrewMemberUniqueId"', '', crew_id,
                f"--{boundary}", 'Content-Disposition: form-data; name="Year"', '', current_year,
                f"--{boundary}", 'Content-Disposition: form-data; name="Month"', '', current_month,
                f"--{boundary}--", ''
            ]
            form_data = "\r\n".join(body_parts)
            
            headers = {
                "Authorization": self.auth_token, "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Origin": "https://mycrew.avianca.com", "Referer": "https://mycrew.avianca.com/",
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = self.session.post(url, data=form_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # STABILITY FIX: RETURN IN-MEMORY BUFFER (io.BytesIO) INSTEAD OF SAVING TO DISK
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    pdf_data = io.BytesIO(response.content) # Store PDF in memory
                    filename = f"{schedule_type}_schedule_{crew_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    logger.info(f"✅ PDF data prepared in memory for: {filename}")
                    return pdf_data, filename # Return the buffer and the desired filename
                
                elif 'application/json' in content_type:
                    logger.warning(f"⚠️ Got JSON response instead of PDF: {response.text[:200]}")
                    return None
                else:
                    logger.warning(f"⚠️ Unexpected content type: {content_type}")
                    return None
            else:
                logger.error(f"❌ PDF download failed with status: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ PDF download error: {e}")
            return None


# --- GLOBAL APPLICATION STATE ---
client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID
CREW_DATALIST = load_crew_name_list() # <-- LOAD THE LIST ON STARTUP


# --- HTML TEMPLATES (Truncated for readability, only PDF_VIEW is modified) ---

SCHEDULE_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>My Crew Schedule</title>
    <style>
        /* ... (CSS code) ... */
    </style>
</head>
<body>
    <div class="container">
        </div>
    <script>
    /* ... (JavaScript content) ... */
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
        /* ... (CSS code) ... */
    </style>
</head>
<body>
    <div class="container">
        </div>
    <script>
    /* ... (JavaScript content) ... */
    </script>
</body>
</html>
"""

PDF_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Download</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* --- Sober & Mobile-First Redesign (v2) --- */
        
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
            max-width: 600px;
            margin: 10px auto;
            background: #2a2a2a; /* Dark card background */
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #444;
        }

        /* Header (now just a container for the nav banner) */
        .header {
            text-align: center;
            margin-bottom: 25px;
        }

        /* NEW: Navigation Banner */
        .nav-banner {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr; /* 3-column layout */
            gap: 1px;
            background: #444; /* Gaps will show this color */
            border: 1px solid #444;
            border-radius: 8px;
            overflow: hidden; /* To keep rounded corners */
        }
        .nav-button {
            padding: 12px 5px;
            background: #3a3a3a;
            color: #f0f0f0;
            text-decoration: none;
            font-size: 0.9em;
            font-weight: 500;
            text-align: center;
        }
        .nav-button:hover {
            background: #4a4a4a;
        }
        .nav-button.active {
            background: #f0f0f0; /* Active button is light */
            color: #121212;
            font-weight: 700;
        }

        /* Input groups */
        .input-group {
            margin-bottom: 20px;
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
            padding: 14px 16px;
            font-size: 1.1em;
            color: #ffffff;
            background: #1e1e1e;
            border: 1px solid #555;
            border-radius: 5px;
            box-sizing: border-box;
        }
        
        /* Flex layout for search + clear button */
        .flex-group {
            display: flex;
            gap: 10px;
            align-items: flex-end; /* Aligns button with input */
        }
        .flex-group .crew-input {
            flex-grow: 1;
        }

        /* Button base style */
        .button {
            width: 100%;
            padding: 16px;
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
        
        .button.clear-btn {
            width: auto;
            flex-shrink: 0;
            background: #4a4a4a;
            color: #f0f0f0;
            font-size: 1.1em;
            padding: 14px 16px;
        }
        
        /* NEW: Square Download Buttons */
        .square-button-group {
            display: grid;
            grid-template-columns: 1fr 1fr; /* Side-by-side */
            gap: 15px;
            margin-top: 20px;
        }
        .pdf-button {
            background: #555;
            color: #ffffff;
            aspect-ratio: 1 / 1; /* Makes it square */
            width: 100%;
            
            /* Center text in the square */
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            
            padding: 10px;
            font-size: 1em;
            line-height: 1.3;
            font-weight: 600;
        }
        .pdf-button:hover {
            background: #666;
        }
        .pdf-button.scheduled {
            background: #444; /* Darker for secondary */
        }
        .pdf-button.scheduled:hover {
            background: #555;
        }
        
        /* --- NEW: Footer Section --- */
        .divider {
            border: none;
            border-top: 1px solid #444;
            margin: 30px 0 25px 0;
        }
        .footer-section {
            text-align: center;
        }
        /* MOVED: Update button */
        #updateCrewBtn {
            background: #f0f0f0; /* Primary action is light */
            color: #121212;
            max-width: 350px; /* Constrain width */
            margin: 0 auto;
        }
        #updateCrewBtn:hover {
            background: #ffffff;
        }
        
        /* MOVED: Crew ID input */
        .footer-section .crew-input {
            max-width: 350px;
            margin: 0 auto;
            text-align: center;
        }
        .footer-section .input-label {
            text-align: center;
        }

        /* MODIFIED: Info box */
        .info-box {
            background: #3a3a3a;
            padding: 0.5em 1em; /* Much smaller padding */
            border-radius: 5px;
            text-align: center;
            display: inline-block; /* Fits content */
            margin: 15px 0 25px 0;
        }
        .info-box p {
            margin: 0;
            font-size: 1.05em;
            color: #ccc;
        }
        .info-box strong {
            color: #ffffff;
            font-weight: 600;
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
            <div class="nav-banner">
                <a href="/" class="nav-button">📋 Schedule</a>
                <a href="/calendar" class="nav-button">📅 Calendar</a>
                <a href="/pdf" class="nav-button active">📄 PDF</a>
            </div>
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
                    </datalist>
            </div>
            <button class="button clear-btn" onclick="clearDropdown()">Clear</button>
        </div>

        <div class="square-button-group">
            <button class="button pdf-button" onclick="downloadPDF('actual')">📥<br>Actual PDF</button>
            <button class="button pdf-button scheduled" onclick="downloadPDF('scheduled')">📥<br>Scheduled PDF</button>
        </div>

        <hr class="divider">
        <div class="footer-section">

            <div class="info-box">
                <p>ID: <strong>{{ current_crew_id }}</strong></p>
            </div>

            <div class="input-group">
                <label class="input-label" for="crewId">Selected Crew ID:</label>
                <input type="text" id="crewId" class="crew-input" placeholder="Enter Crew ID" value="{{ current_crew_id }}">
            </div>
            
            <div class="input-group">
                <button class="button" id="updateCrewBtn" onclick="updateCrewId()">💾 Update Crew ID</button>
            </div>

        </div>

    </div>

    <script>
    
    // NEW: Function to fetch names from API and populate the datalist
    function loadCrewDatalist() {
        const datalist = document.getElementById('crewDatalist');
        
        fetch('/api/crew-names')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(crewList => {
                crewList.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item; 
                    datalist.appendChild(option);
                });
                console.log(`Successfully loaded ${crewList.length} crew names into datalist.`);
            })
            .catch(error => {
                console.error('Error loading crew names:', error);
            });
    }

    function handleCrewSelect() {
        const input = document.getElementById('crewSelectorInput');
        const selectedValue = input.value.trim();
        
        if (selectedValue.length >= 8) {
            // Find the ID (the last 8 digits)
            const match = selectedValue.match(/\d{8}$/);
            const crewId = match ? match[0] : null;

            if (crewId) {
                document.getElementById('crewId').value = crewId;
                document.getElementById('updateCrewBtn').click();
            }
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
        button.textContent = '⏳'; // Just a spinner for the square
        
        window.open('/download_pdf?type=' + type, '_blank');
        
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText; // Use innerHTML to restore line breaks
        }, 3000);
    }

    document.getElementById('crewId').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            updateCrewId();
        }
    });

    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('crewSelectorInput').focus();
        loadCrewDatalist(); // Call the function to load names
    });
    </script>
</body>
</html>
"""

# --- Helper Functions (Identical to user's code) ---

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


# --- FLASK ROUTES ---

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    
    logger.info("🔄 Auto-fetching fresh data on page load...")
    new_data = client.get_schedule_data(current_crew_id)
    if new_data is not None:
        schedule_data = new_data
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Auto-fetch completed successfully!")
    elif schedule_data is None:
        logger.warning("⚠️ Auto-fetch failed and no existing data available")
    
    total_days = 0
    total_assignments = 0
    month_names = []
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    if schedule_data and isinstance(schedule_data, list):
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

@app.route('/api/crew-names') # NEW: API endpoint
def get_crew_names_api():
    """Endpoint to return the large list of crew names as JSON."""
    logger.info(f"Serving API request for crew names. {len(CREW_DATALIST)} items.")
    return jsonify(CREW_DATALIST)


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
        # Client now returns a tuple (data_buffer, filename)
        pdf_result = client.download_schedule_pdf(current_crew_id, schedule_type)
        
        if pdf_result and len(pdf_result) == 2:
            pdf_data, filename = pdf_result
            
            # Use send_file with the in-memory buffer
            return send_file(
                pdf_data, 
                as_attachment=True, 
                download_name=filename, 
                mimetype='application/pdf'
            )
        else:
            logger.error("❌ PDF generation failed - no data buffer returned.")
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
