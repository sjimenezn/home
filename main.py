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
        """Get schedule data - optionally for specific crew member"""
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
            
            # If crew_id provided, try to use it
            if crew_id:
                params["crewMemberUniqueId"] = crew_id
            
            headers = {
                "Authorization": self.auth_token, "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json", "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            
            logger.info(f"🌐 Making API request to: {url} with params: {params}")
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
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

    def get_crew_schedule_data(self, crew_id):
        """Try multiple endpoints and parameters to fetch other crew data"""
        if not self.is_logged_in:
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            if not self.login(email, password):
                return None
    
        headers = {
            "Authorization": self.auth_token, 
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Accept": "application/json", 
            "Origin": "https://mycrew.avianca.com", 
            "Referer": "https://mycrew.avianca.com/",
        }
        
        # Get your data first for comparison
        your_data = self.get_schedule_data()
        
        # Different endpoint variations to try
        endpoints = [
            f"{self.base_url}/Assignements/AssignmentsComplete",
            f"{self.base_url}/Assignements",
            f"{self.base_url}/MonthlyAssignements/Data",
            f"{self.base_url}/CrewMember/{crew_id}/Assignments",
            f"{self.base_url}/Assignements/Crew/{crew_id}",
        ]
        
        # Different parameter combinations
        param_combinations = [
            {"crewMemberId": crew_id, "timeZoneOffset": -300},
            {"crewMemberUniqueId": crew_id, "timeZoneOffset": -300},
            {"employeeId": crew_id, "timeZoneOffset": -300},
            {"uniqueId": crew_id, "timeZoneOffset": -300},
            {"id": crew_id, "timeZoneOffset": -300},
            {"CrewMemberUniqueId": crew_id, "timeZoneOffset": -300},
            {"timeZoneOffset": -300},  # Some endpoints might get crew from auth
        ]
        
        for endpoint in endpoints:
            for params in param_combinations:
                try:
                    logger.info(f"🔍 Testing: {endpoint} with {params}")
                    response = self.session.get(endpoint, params=params, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Check if we got valid, non-empty data that's different from yours
                        if (data and data != your_data and 
                            ((isinstance(data, list) and len(data) > 0) or 
                             (isinstance(data, dict) and data))):
                            logger.info(f"✅ SUCCESS! Found working endpoint: {endpoint}")
                            logger.info(f"📊 Data structure: {type(data)}, length: {len(data) if isinstance(data, list) else 'dict'}")
                            return data
                        elif response.status_code == 200 and not data:
                            logger.info(f"⚠️ Got 200 but empty data from: {endpoint}")
                        elif data == your_data:
                            logger.info(f"⚠️ Got YOUR data again from: {endpoint}")
                            
                except Exception as e:
                    logger.info(f"❌ Failed {endpoint}: {str(e)}")
                    continue
        
        logger.error("❌ No working endpoint found for other crew members")
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

# [ALL THE TEMPLATES REMAIN EXACTLY THE SAME - SCHEDULE_VIEW_TEMPLATE, CALENDAR_VIEW_TEMPLATE, PDF_VIEW_TEMPLATE]
# Since they are very long, I'm keeping them as they were in your previous code

SCHEDULE_VIEW_TEMPLATE = """
[YOUR EXISTING SCHEDULE_VIEW_TEMPLATE CODE HERE - UNCHANGED]
"""

CALENDAR_VIEW_TEMPLATE = """
[YOUR EXISTING CALENDAR_VIEW_TEMPLATE CODE HERE - UNCHANGED] 
"""

PDF_VIEW_TEMPLATE = """
[YOUR EXISTING PDF_VIEW_TEMPLATE CODE HERE - UNCHANGED]
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
        new_data = client.get_schedule_data()
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

@app.route('/test_crew_data')
def test_crew_data():
    """Test endpoint to try fetching data for other crew members"""
    test_crew_id = "26559705"
    
    logger.info(f"🧪 Testing data fetch for crew ID: {test_crew_id}")
    crew_data = client.get_crew_schedule_data(test_crew_id)
    
    if crew_data:
        return {
            "success": True, 
            "message": f"Found data for crew {test_crew_id}",
            "data_type": type(crew_data).__name__,
            "data_length": len(crew_data) if isinstance(crew_data, list) else "N/A",
            "data_sample": str(crew_data)[:500] + "..." if crew_data else "No data"
        }
    else:
        return {
            "success": False,
            "message": f"Could not fetch data for crew {test_crew_id} - PDF parsing required"
        }

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

@app.route('/test_simple')
def test_simple():
    """Simple test endpoint"""
    try:
        logger.info("🧪 Starting simple test...")
        test_crew_id = "26559705"
        
        # Test basic API connectivity first
        your_data = client.get_schedule_data()
        logger.info(f"✅ Your data fetched: {type(your_data)}")
        
        # Test the new method
        crew_data = client.get_crew_schedule_data(test_crew_id)
        
        if crew_data:
            return f"SUCCESS! Found data for crew {test_crew_id}"
        else:
            return f"NO DATA - Could not fetch data for crew {test_crew_id}"
            
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        return f"ERROR: {str(e)}"

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