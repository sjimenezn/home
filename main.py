#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Version
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file

DEFAULT_CREW_ID = "32385184"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)

def load_crew_names():
    """Load crew names from name_list.txt"""
    try:
        if os.path.exists('name_list.txt'):
            with open('name_list.txt', 'r', encoding='utf-8') as f:
                return [
                    f"{line.split(';')[0].strip()} {line.split(';')[2].strip()}" 
                    if ';' in line and len(line.split(';')) >= 3 
                    else line.replace(';', ' ').strip()
                    for line in f if line.strip() and not line.startswith('#')
                ]
    except Exception as e:
        logger.error(f"Error loading names: {e}")
    return [
        "GRACIA GRANADOS ALVARO HERNANDO 79150332",
        "HERNANDEZ MONTES CARLOS AUGUSTO 79154225", 
        "RAMIREZ PLAZAS CARLOS AUGUSTO 19466758"
    ]

class CrewAPIClient:
    def __init__(self):
        self.base_url = "https://api-avianca.avianca.com/MycreWFlights/api"
        self.auth_url = "https://api-avianca.avianca.com/MyCrewSecurity/connect/token"
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        self.session = None
        self.auth_token = None
        
    def _login(self):
        """Login to API"""
        try:
            self.session = requests.Session()
            email = os.getenv('CREW_EMAIL', 'sergio.jimenez@avianca.com')
            password = os.getenv('CREW_PASSWORD', 'aLogout.8701')
            
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
                self.auth_token = f"Bearer {response.json()['access_token']}"
                return True
        except Exception as e:
            logger.error(f"Login error: {e}")
        return False

    def get_assignments_by_user(self, crew_id=None, year=None, month=None):
        """Get assignments for specific month"""
        try:
            target_crew_id = crew_id or current_crew_id
            now = datetime.now()
            year = year or now.year
            month = month or now.month
            
            # Calculate month range
            first_day = datetime(year, month, 1)
            last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
            days_in_month = (last_day - first_day).days + 1
            
            logger.info(f"📅 Requesting data for {year}-{month:02d} (Days: {days_in_month}, First: {first_day.date()}, Last: {last_day.date()})")
            
            if not self._login():
                return None
            
            url = f"{self.base_url}/Assignements/GetAssignementsByUser"
            params = {
                "date": first_day.strftime('%Y-%m-%dT00:00:00Z'),
                "changeDays": days_in_month,
                "crewMemberUniqueId": target_crew_id,
                "holding": "AV",
                "timeZoneOffset": "+300"
            }
            
            logger.info(f"🌐 API Request: date={params['date']}, changeDays={params['changeDays']}")
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                
                # Debug: Check what dates we actually received
                if data:
                    dates_received = set()
                    for assignment in data[:5]:  # Check first 5 assignments
                        if assignment and assignment.get('StartDate'):
                            dates_received.add(assignment['StartDate'][:10])
                    logger.info(f"📊 Sample dates received: {sorted(dates_received)}")
                
                logger.info(f"✅ Fetched {len(data)} assignments for {year}-{month:02d}")
                return {'year': year, 'month': month, 'assignments': data}
                
        except Exception as e:
            logger.error(f"❌ Error fetching assignments: {e}")
        return None

    def download_schedule_pdf(self, crew_id, schedule_type="actual", month="", year=""):
        """Download schedule PDF"""
        try:
            if not self._login():
                return None
            
            endpoint = "Scheduled/Export" if schedule_type.lower() == "scheduled" else "Export"
            url = f"{self.base_url}/MonthlyAssignements/{endpoint}"
            
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            current_month = month or str(datetime.now().month)
            current_year = year or str(datetime.now().year)
            
            form_data = "\r\n".join([
                f"--{boundary}", 'Content-Disposition: form-data; name="Holding"', '', 'AV',
                f"--{boundary}", 'Content-Disposition: form-data; name="CrewMemberUniqueId"', '', crew_id,
                f"--{boundary}", 'Content-Disposition: form-data; name="Year"', '', current_year,
                f"--{boundary}", 'Content-Disposition: form-data; name="Month"', '', current_month,
                f"--{boundary}--", ''
            ])
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }
            
            response = self.session.post(url, data=form_data, headers=headers, timeout=30)
            if response.status_code == 200 and 'pdf' in response.headers.get('content-type', '').lower():
                filename = f"{schedule_type}_schedule_{crew_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return filename
                
        except Exception as e:
            logger.error(f"PDF download error: {e}")
        return None

def transform_assignments_to_calendar_data(assignments_data, year, month):
    """Transform assignments into calendar month structure"""
    if not assignments_data or not isinstance(assignments_data, list):
        return []
    
    first_day = datetime(year, month, 1)
    last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    
    # Group assignments by day
    days_dict = {}
    for assignment in assignments_data:
        if assignment and assignment.get('StartDate'):
            try:
                date_str = assignment['StartDate'][:10]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    if date_str not in days_dict:
                        days_dict[date_str] = {'StartDate': assignment['StartDate'], 'Dem': '', 'AssignementList': []}
                    days_dict[date_str]['AssignementList'].append(assignment)
            except (ValueError, KeyError):
                continue
    
    # Create month data with all days
    month_data = []
    current_date = first_day
    while current_date <= last_day:
        date_str = current_date.strftime('%Y-%m-%d')
        month_data.append(days_dict.get(date_str, {
            'StartDate': date_str + 'T00:00:00Z',
            'Dem': '',
            'AssignementList': []
        }))
        current_date += timedelta(days=1)
    
    return [month_data]

def create_calendar_view_data(month_data):
    """Convert month data to calendar grid format"""
    if not month_data or not isinstance(month_data, list):
        return []
    
    # Find first day of month
    first_day = None
    for day in month_data:
        if day and day.get('StartDate'):
            try:
                first_day = datetime.strptime(day['StartDate'][:10], '%Y-%m-%d').replace(day=1)
                break
            except (ValueError, KeyError):
                continue
    
    if not first_day:
        return []
    
    # Create calendar grid (6 weeks)
    calendar_start = first_day - timedelta(days=first_day.weekday())
    calendar_days = []
    
    for i in range(42):
        current_date = calendar_start + timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        calendar_day = None
        
        # Find assignments for this date
        for day_data in month_data:
            if day_data and day_data.get('StartDate', '').startswith(date_str):
                assignments = []
                for assignment in day_data.get('AssignementList', []):
                    flight_data = assignment.get('FlighAssignement')
                    if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                        assignments.append({
                            'is_flight': True,
                            'flight_number': flight_data.get('CommercialFlightNumber', ''),
                            'origin': flight_data.get('OriginAirportIATACode', '').strip() if flight_data.get('OriginAirportIATACode') else '',
                            'destination': flight_data.get('FinalAirportIATACode', '').strip() if flight_data.get('FinalAirportIATACode') else '',
                            'departure_stand': flight_data.get('DepartureStand', '').strip() if flight_data.get('DepartureStand') else '',
                            'departure_time': flight_data.get('ScheduledDepartureDate', '')[11:16] if flight_data.get('ScheduledDepartureDate') else 'N/A',
                            'arrival_time': flight_data.get('ScheduledArrivalDate', '')[11:16] if flight_data.get('ScheduledArrivalDate') else 'N/A',
                            'time_advanced': flight_data.get('TimeAdvanced', False),
                            'time_delayed': flight_data.get('TimeDelayed', False),
                            'aircraft_registration': assignment.get('AircraftRegistrationNumber', '').strip() if assignment.get('AircraftRegistrationNumber') else ''
                        })
                    else:
                        assignments.append({
                            'is_flight': False,
                            'activity_code': assignment.get('ActivityCode', '').strip() if assignment.get('ActivityCode') else 'DUTY',
                            'start_time': assignment.get('StartDateLocal', '')[11:16] if assignment.get('StartDateLocal') else 'N/A',
                            'end_time': assignment.get('EndDateLocal', '')[11:16] if assignment.get('EndDateLocal') else 'N/A'
                        })
                
                calendar_day = {
                    'date': date_str,
                    'day_number': current_date.day,
                    'weekend': current_date.weekday() >= 5,
                    'assignments': assignments
                }
                break
        
        # Create empty day if in current month
        if not calendar_day and current_date.month == first_day.month:
            calendar_day = {
                'date': date_str,
                'day_number': current_date.day,
                'weekend': current_date.weekday() >= 5,
                'assignments': []
            }
        
        calendar_days.append(calendar_day)
    
    return calendar_days

# Global variables
client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID
current_calendar_year = datetime.now().year
current_calendar_month = datetime.now().month
crew_names = load_crew_names()

def get_month_name(year, month):
    return datetime(year, month, 1).strftime('%B %Y')

def get_month_name_from_data(month_data):
    """Extract month name from the first valid day in month data"""
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

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    return render_template('schedule_view.html',
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        current_crew_id=current_crew_id,
        current_date=datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/calendar')
def calendar_view():
    global schedule_data, last_fetch_time, current_crew_id, current_calendar_year, current_calendar_month
    
    year = request.args.get('year', type=int, default=current_calendar_year)
    month = request.args.get('month', type=int, default=current_calendar_month)
    current_calendar_year, current_calendar_month = year, month
    
    logger.info(f"🗓️ Calendar view requested: {year}-{month:02d}")
    
    assignments_result = client.get_assignments_by_user(current_crew_id, year=year, month=month)
    if assignments_result:
        schedule_data = transform_assignments_to_calendar_data(
            assignments_result['assignments'], 
            assignments_result['year'], 
            assignments_result['month']
        )
        last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Debug: Check what we're displaying
        if schedule_data and schedule_data[0]:
            displayed_dates = [day['StartDate'][:7] for day in schedule_data[0] if day.get('StartDate')]
            unique_months = set(displayed_dates)
            logger.info(f"📅 Displaying data for months: {sorted(unique_months)}")
    
    month_name = get_month_name(year, month)
    month_calendars = [create_calendar_view_data(schedule_data[0])] if schedule_data else []
    
    # Calculate totals for the template
    total_days = len(schedule_data[0]) if schedule_data else 0
    total_assignments = sum(len(day.get('AssignementList', [])) for day in schedule_data[0]) if schedule_data else 0
    
    refresh_message = "Data refreshed successfully!" if request.args.get('refresh') == 'success' else None
    
    # Get month names for display (needed by template)
    month_names = [month_name]
    
    return render_template('calendar_view.html',
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        refresh_message=refresh_message,
        current_crew_id=current_crew_id,
        month_names=month_names,  # This was missing
        month_calendars=month_calendars,
        current_date=datetime.now().strftime('%Y-%m-%d'),
        current_month_index=0,
        current_calendar_year=current_calendar_year,
        current_calendar_month=current_calendar_month
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
    global current_crew_id, schedule_data, last_fetch_time, current_calendar_year, current_calendar_month
    new_crew_id = request.args.get('crew_id', '').strip()
    if new_crew_id:
        current_crew_id = new_crew_id
        schedule_data = None
        last_fetch_time = None
        current_calendar_year = datetime.now().year
        current_calendar_month = datetime.now().month
        return {"success": True, "new_crew_id": current_crew_id}
    return {"success": False, "error": "No crew ID provided"}

@app.route('/download_pdf')
def download_pdf():
    schedule_type = request.args.get('type', 'actual')
    month = request.args.get('month', '').strip()
    year = request.args.get('year', '').strip()
    try:
        filename = client.download_schedule_pdf(current_crew_id, schedule_type, month, year)
        if filename and os.path.exists(filename):
            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))
    except Exception as e:
        logger.error(f"PDF download error: {e}")
    return {"success": False, "error": "PDF generation failed"}, 400

@app.route('/fetch')
def fetch_data():
    global schedule_data, last_fetch_time, current_calendar_year, current_calendar_month
    try:
        assignments_result = client.get_assignments_by_user(current_crew_id, current_calendar_year, current_calendar_month)
        if assignments_result:
            schedule_data = transform_assignments_to_calendar_data(
                assignments_result['assignments'],
                assignments_result['year'],
                assignments_result['month']
            )
            last_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"success": True}
    except Exception as e:
        logger.error(f"Error in /fetch: {e}")
    return {"success": False, "error": "Failed to fetch data"}

if __name__ == "__main__":
    logger.info("Starting Crew Schedule Application...")
    app.run(host='0.0.0.0', port=8000, debug=False)