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
from flask import Flask, render_template, request, send_file

# Configuration
DEFAULT_CREW_ID = "32385184"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

def load_crew_names():
    """Load crew names from name_list.txt file and handle semicolon format"""
    try:
        if os.path.exists('name_list.txt'):
            with open('name_list.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            crew_list = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    # Handle the format: "GRACIA GRANADOS ALVARO HERNANDO;1;79150332"
                    if ';' in line:
                        parts = line.split(';')
                        if len(parts) >= 3:
                            # parts[0] = name, parts[1] = number, parts[2] = crew ID
                            crew_name = f"{parts[0].strip()} {parts[2].strip()}"
                            crew_list.append(crew_name)
                        else:
                            # Fallback if semicolon format is incomplete
                            crew_list.append(line.replace(';', ' '))
                    else:
                        # If no semicolons, use the line as is
                        crew_list.append(line)
            
            logger.info(f"✅ Loaded {len(crew_list)} crew names from name_list.txt")
            return crew_list
        else:
            logger.warning("⚠️ name_list.txt not found, using default crew list")
            return [
                "GRACIA GRANADOS ALVARO HERNANDO 79150332",
                "HERNANDEZ MONTES CARLOS AUGUSTO 79154225", 
                "RAMIREZ PLAZAS CARLOS AUGUSTO 19466758",
                "LUNA RIOS SANTIAGO 79157055",
                "CAYCEDO BALLESTEROS CARLOS EDUARDO 79234161",
                "MUSTAFA LOTERO ANDRES ANTONIO 71660758",
                "VELASCO BARRIGA JUAN CARLOS 79152641"
            ]
    except Exception as e:
        logger.error(f"❌ Error loading name_list.txt: {e}")
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

    def get_assignments_by_user(self, crew_id=None, days_before=45, days_after=45):
        """Get assignments using the working endpoint that respects crewMemberUniqueId"""
        try:
            target_crew_id = crew_id or current_crew_id
            logger.info(f"📊 Fetching assignments for crew: {target_crew_id} using GetAssignementsByUser...")
            
            # Always create a new session to ensure fresh data
            self.create_new_session()
            
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            
            if not self.login(email, password):
                return None
            
            # Calculate date range - start from days_before ago, get assignments for days_before + days_after days
            start_date = (datetime.now() - timedelta(days=days_before)).strftime('%Y-%m-%dT00:00:00Z')
            total_days = days_before + days_after
            
            url = f"{self.base_url}/Assignements/GetAssignementsByUser"
            params = {
                "date": start_date,  # 45 days ago
                "changeDays": total_days,  # 90 days total (45 past + 45 future)
                "crewMemberUniqueId": target_crew_id,
                "holding": "AV",
                "timeZoneOffset": "+300"
            }
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            
            logger.info(f"🌐 Making GetAssignementsByUser request for crew {target_crew_id}...")
            logger.info(f"📅 Date range: {start_date[:10]} to {(datetime.now() + timedelta(days=days_after)).strftime('%Y-%m-%d')}")
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Assignments data fetched for crew {target_crew_id}! Found {len(data)} assignments")
                return data
                
            logger.error(f"❌ Failed to fetch assignments for crew {target_crew_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching assignments for crew {crew_id}: {e}")
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

def transform_assignments_to_calendar_data(assignments_data, days_before=45, days_after=45):
    """Transform the linear assignments list into calendar month structure"""
    if not assignments_data or not isinstance(assignments_data, list):
        return []
    
    # Group assignments by month
    months_assignments = {}
    
    for assignment in assignments_data:
        if assignment and isinstance(assignment, dict) and assignment.get('StartDate'):
            try:
                date_str = assignment['StartDate'][:10]  # Get YYYY-MM-DD
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                month_key = date_obj.strftime('%Y-%m')  # e.g., "2025-11"
                
                if month_key not in months_assignments:
                    months_assignments[month_key] = []
                
                months_assignments[month_key].append(assignment)
            except (ValueError, KeyError):
                continue
    
    # Convert to the expected calendar structure
    calendar_data = []
    for month_key in sorted(months_assignments.keys()):
        month_assignments = months_assignments[month_key]
        
        # Group assignments by day
        days_dict = {}
        for assignment in month_assignments:
            date_str = assignment['StartDate'][:10]
            if date_str not in days_dict:
                days_dict[date_str] = {
                    'StartDate': assignment['StartDate'],
                    'Dem': '',  # You might need to calculate this
                    'AssignementList': []
                }
            days_dict[date_str]['AssignementList'].append(assignment)
        
        # Convert to list format
        month_data = list(days_dict.values())
        calendar_data.append(month_data)
    
    return calendar_data

client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID

# Load crew names at startup
crew_names = load_crew_names()

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
                            'origin': flight_data.get('OriginAirportIATACode', '').strip() if flight_data.get('OriginAirportIATACode') else '',
                            'destination': flight_data.get('FinalAirportIATACode', '').strip() if flight_data.get('FinalAirportIATACode') else '',
                            'departure_stand': flight_data.get('DepartureStand', '').strip() if flight_data.get('DepartureStand') else '',
                            'departure_time': flight_data.get('ScheduledDepartureDate', '')[11:16] if flight_data.get('ScheduledDepartureDate') else 'N/A',
                            'arrival_time': flight_data.get('ScheduledArrivalDate', '')[11:16] if flight_data.get('ScheduledArrivalDate') else 'N/A',
                            'time_advanced': flight_data.get('TimeAdvanced', False),
                            'time_delayed': flight_data.get('TimeDelayed', False),
                            'aircraft_registration': assignment.get('AircraftRegistrationNumber', '').strip() if assignment.get('AircraftRegistrationNumber') else ''
                        }
                    else:
                        assignment_data = {
                            'is_flight': False,
                            'activity_code': assignment.get('ActivityCode', '').strip() if assignment.get('ActivityCode') else 'DUTY',
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
    
    return render_template('schedule_view.html',
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
    global schedule_data, last_fetch_time, current_crew_id
    
    # 🔄 USE THE WORKING ENDPOINT: Fetch assignments using GetAssignementsByUser
    logger.info(f"🔄 Calendar view - fetching assignments for crew: {current_crew_id}")
    assignments_data = client.get_assignments_by_user(current_crew_id, days_before=45, days_after=45)  # 45 days past + 45 days future
    
    if assignments_data is not None:
        # Transform the assignments data into calendar format
        schedule_data = transform_assignments_to_calendar_data(assignments_data, days_before=45, days_after=45)
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"✅ Calendar data transformed for crew {current_crew_id}!")
    elif schedule_data is None:
        logger.warning("⚠️ Calendar data fetch failed and no existing data available")
    
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
    
    return render_template('calendar_view.html',
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
    
    return render_template('pdf_view.html',
        current_crew_id=current_crew_id,
        pdf_message=pdf_message,
        pdf_success=pdf_success,
        crew_names=crew_names
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
    month = request.args.get('month', '').strip()
    year = request.args.get('year', '').strip()
    
    try:
        logger.info(f"📄 PDF download requested for {schedule_type} schedule, crew {current_crew_id}, month: {month if month else 'current'}, year: {year if year else 'current'}")
        filename = client.download_schedule_pdf(current_crew_id, schedule_type, month, year)
        
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
        logger.info("🔄 Manual data refresh requested - using GetAssignementsByUser...")
        assignments_data = client.get_assignments_by_user(current_crew_id, days_before=45, days_after=45)
        if assignments_data is not None:
            schedule_data = transform_assignments_to_calendar_data(assignments_data, days_before=45, days_after=45)
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info("✅ Data updated successfully with GetAssignementsByUser!")
            return {"success": True}
        logger.error("❌ Data refresh failed - no data received")
        return {"success": False, "error": "Failed to fetch data"}
    except Exception as e:
        logger.error(f"❌ Error in /fetch endpoint: {e}")
        return {"success": False, "error": str(e)}

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
