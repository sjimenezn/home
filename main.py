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
# Import jsonify for API response
from flask import Flask, render_template_string, request, send_file, jsonify 

# Configuration
DEFAULT_CREW_ID = "32385184"
CREW_NAMES_FILE = 'names_list.txt'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Data Loading Functions ---

def load_crew_names_list():
    """Loads the large list of crew names from the text file."""
    try:
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

# --- 1. CREW API CLIENT CLASS DEFINITION (MOVED UP) ---
# The class MUST be defined before it is instantiated globally.
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
        """Download schedule PDF using multipart form data"""
        try:
            logger.info(f"📥 Downloading {schedule_type} schedule PDF for crew {crew_id}...")
            
            self.create_new_session()
            
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            
            if not self.login(email, password):
                logger.error("❌ Cannot download PDF - login failed")
                return None
            
            if schedule_type.lower() == "scheduled":
                url = f"{self.base_url}/MonthlyAssignements/Scheduled/Export"
            else:
                url = f"{self.base_url}/MonthlyAssignements/Export"
            
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
                
                if 'application/pdf' in content_type or 'pdf' in content_type:
                    filename = f"{schedule_type}_schedule_{crew_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"✅ PDF downloaded: {filename}")
                    return filename
                else:
                    logger.warning(f"⚠️ Got unexpected response instead of PDF: {content_type}")
                    return None
            else:
                logger.error(f"❌ PDF download failed with status: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ PDF download error: {e}")
            return None


# --- 2. GLOBAL APPLICATION STATE (Now defined AFTER the class) ---
client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID
CREW_DATALIST = load_crew_names_list()


# --- HTML TEMPLATES (Unchanged) ---
SCHEDULE_VIEW_TEMPLATE = """
<!DOCTYPE html>
... (Your SCHEDULE_VIEW_TEMPLATE content) ...
"""

CALENDAR_VIEW_TEMPLATE = """
<!DOCTYPE html>
... (Your CALENDAR_VIEW_TEMPLATE content) ...
"""

PDF_VIEW_TEMPLATE = """
<!DOCTYPE html>
... (Your MODIFIED PDF_VIEW_TEMPLATE content with JS fetch) ...
"""
# Since the PDF_VIEW_TEMPLATE content is large and was correctly modified in the previous step, 
# I am keeping it truncated here for brevity, assuming the full, correct version is used.
# The critical part is that the <datalist id="crewDatalist"></datalist> is empty 
# and the JS `loadCrewDatalist()` function is present and called on DOMContentLoaded.

# --- Helper Functions (Unchanged) ---

def get_month_name_from_data(month_data):
    # ... (function body) ...
    if not month_data or not isinstance(month_data, list):
        return "Unknown Month"
    
    for day in month_data:
        if day and isinstance(day, dict) and day.get('StartDate'):
            try:
                date_str = day['StartDate'][:10]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%B %Y')
            except (ValueError, KeyError):
                continue
    
    return "Unknown Month"

def get_current_month_index(schedule_data, current_date):
    # ... (function body) ...
    if not schedule_data or not isinstance(schedule_data, list):
        return 0
    
    for month_index, month in enumerate(schedule_data):
        if month and isinstance(month, list):
            for day in month:
                if day and isinstance(day, dict) and day.get('StartDate', '').startswith(current_date):
                    return month_index
    return 0

def create_calendar_view_data(month_data, month_name):
    # ... (function body) ...
    if not month_data or not isinstance(month_data, list):
        return []
    
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
    
    calendar_start = first_day - timedelta(days=first_day.weekday())
    calendar_days = []
    for i in range(42):
        current_date = calendar_start + timedelta(days=i)
        calendar_day = None
        date_str = current_date.strftime('%Y-%m-%d')
        
        for day_data in month_data:
            if day_data and isinstance(day_data, dict) and day_data.get('StartDate', '').startswith(date_str):
                assignments = []
                for assignment in day_data.get('AssignementList', []):
                    flight_data = assignment.get('FlighAssignement')
                    if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                        assignment_data = {
                            'is_flight': True,
                            'flight_number': flight_data.get('CommercialFlightNumber', ''),
                            'origin': flight_data.get('OriginAirportIATACode', '').strip(),
                            'destination': flight_data.get('FinalAirportIATACode', '').strip(),
                            'departure_stand': flight_data.get('DepartureStand', '').strip(),
                            'departure_time': assignment.get('StartDateLocal', '')[11:16],
                            'arrival_time': assignment.get('EndDateLocal', '')[11:16],
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
                    'weekend': current_date.weekday() >= 5,
                    'assignments': assignments
                }
                break
        
        if not calendar_day and current_date.month == first_day.month:
            calendar_day = {
                'date': date_str,
                'day_number': current_date.day,
                'weekend': current_date.weekday() >= 5,
                'assignments': []
            }
        
        calendar_days.append(calendar_day)
    
    return calendar_days


# --- FLASK ROUTES (Unchanged logic, just ensure all templates/helpers are present) ---

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
                        total_assignments += len(day.get('AssignementList', []))
    
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
                        total_assignments += len(day.get('AssignementList', []))
    
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

@app.route('/api/crew-names')
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
        filename = client.download_schedule_pdf(current_crew_id, schedule_type)
        if filename and os.path.exists(filename):
            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
        else:
            return {"success": False, "error": "PDF generation failed"}, 400
    except Exception as e:
        logger.error(f"❌ PDF download error: {e}")
        return {"success": False, "error": str(e)}, 500

@app.route('/fetch')
def fetch_data():
    global schedule_data, last_fetch_time
    try:
        new_data = client.get_schedule_data(current_crew_id)
        if new_data is not None:
            schedule_data = new_data
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"success": True}
        return {"success": False, "error": "Failed to fetch data"}
    except Exception as e:
        logger.error(f"❌ Error in /fetch endpoint: {e}")
        return {"success": False, "error": str(e)}

@app.route('/debug_test')
def debug_test():
    test_crew_id = "26559705"
    test_data = client.get_schedule_data(test_crew_id)
    your_data = client.get_schedule_data()
    
    if test_data == your_data:
        return "❌ SAME DATA - API is ignoring crew ID, returning YOUR data"
    else:
        if test_data and your_data:
            your_first_flight = None
            for month in your_data:
                for day in month:
                    for assignment in day.get('AssignementList', []):
                        if (f:=assignment.get('FlighAssignement')) and f.get('CommercialFlightNumber') != "XXX":
                            your_first_flight = f.get('CommercialFlightNumber'); break
            
            test_first_flight = None
            for month in test_data:
                for day in month:
                    for assignment in day.get('AssignementList', []):
                        if (f:=assignment.get('FlighAssignement')) and f.get('CommercialFlightNumber') != "XXX":
                            test_first_flight = f.get('CommercialFlightNumber'); break
            
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
