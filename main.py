#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Version with Flight Details and Crew Members
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, jsonify

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

    def get_schedule_data(self, crew_id=None):
        """Get schedule data using the old endpoint (for schedule view)"""
        try:
            target_crew_id = crew_id or current_crew_id
            logger.info(f"📊 Fetching schedule data for crew: {target_crew_id}...")
            
            if not self._login():
                return None
            
            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {
                "timeZoneOffset": -300,
                "crewMemberUniqueId": target_crew_id
            }
            headers = {
                "Authorization": self.auth_token, 
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Accept": "application/json", 
                "Origin": "https://mycrew.avianca.com", 
                "Referer": "https://mycrew.avianca.com/",
            }
            
            logger.info(f"🌐 Making API request for crew {target_crew_id}...")
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Schedule data fetched for crew {target_crew_id}! Structure: {len(data)} months")
                return data
                
            logger.error(f"❌ Failed to fetch schedule data for crew {target_crew_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching data for crew {crew_id}: {e}")
            return None

    def get_assignments_by_user(self, crew_id=None, year=None, month=None):
        """Get assignments for specific month (for calendar view)"""
        try:
            target_crew_id = crew_id or current_crew_id
            now = datetime.now()
            year = year or now.year
            month = month or now.month
            
            # Calculate month range
            first_day = datetime(year, month, 1)
            last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
            days_in_month = (last_day - first_day).days + 1
            
            # Determine if we're requesting a future month
            current_month = datetime(now.year, now.month, 1)
            requested_month = datetime(year, month, 1)
            
            if requested_month > current_month:
                # FUTURE MONTH: Start from last day of current month
                last_day_of_current = (datetime(now.year + 1, 1, 1) if now.month == 12 
                                     else datetime(now.year, now.month + 1, 1)) - timedelta(days=1)
                start_date = last_day_of_current
                change_days = (last_day - last_day_of_current).days + 1
                logger.info(f"🔮 Future month detected: starting from {start_date.date()}, changeDays: {change_days}")
            else:
                # CURRENT OR PAST MONTH: Start from first day of requested month
                start_date = first_day
                change_days = days_in_month
                logger.info(f"📅 Current/Past month: starting from {start_date.date()}, changeDays: {change_days}")
            
            logger.info(f"📅 Requesting data for {year}-{month:02d} (Days in month: {days_in_month}, First: {first_day.date()}, Last: {last_day.date()})")
            
            if not self._login():
                return None
            
            url = f"{self.base_url}/Assignements/GetAssignementsByUser"
            params = {
                "date": start_date.strftime('%Y-%m-%dT00:00:00Z'),
                "changeDays": change_days,
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

    def get_flight_details(self, airline, flight_number, departure_date, origin_airport, operational_number):
        """
        Get detailed flight information using the FlightDetails endpoint
        
        Parameters:
        - airline: e.g., "AV"
        - flight_number: e.g., "210"
        - departure_date: e.g., "2025-10-01T06:57:00Z"
        - origin_airport: e.g., "BOG"
        - operational_number: e.g., "42307372"
        """
        try:
            if not self._login():
                return None
            
            # Construct the URL as shown in your example
            url = f"{self.base_url}/FlightDetails/{airline}/{flight_number}/{departure_date}/{origin_airport}/{operational_number}"
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }
            
            # Request body as shown in your example
            body = {
                "holding": airline,
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "originAirportIATACode": origin_airport
            }
            
            logger.info(f"🛫 Fetching flight details: {airline}{flight_number} on {departure_date}")
            
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            
            if response.status_code == 200:
                flight_data = response.json()
                logger.info(f"✅ Flight details fetched successfully for {airline}{flight_number}")
                return flight_data
            else:
                logger.error(f"❌ Failed to fetch flight details: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching flight details: {e}")
            return None

    def get_flight_crew_members(self, airline, flight_number, departure_date, origin_airport, operational_number):
        """
        Get crew members for a specific flight
        
        Parameters:
        - airline: e.g., "AV"
        - flight_number: e.g., "0211"
        - departure_date: e.g., "2025-10-01T15:24:00Z"
        - origin_airport: e.g., "JFK"
        - operational_number: e.g., "42307373"
        """
        try:
            if not self._login():
                return None
            
            # Construct the URL for crew members
            url = f"{self.base_url}/FlightDetails/FlightMembersTeam/{airline}/{flight_number}/{departure_date}/{origin_airport}/{operational_number}"
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }
            
            # Request body as shown in your example
            body = {
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "holding": airline,
                "originAirportIATACode": operational_number
            }
            
            logger.info(f"👥 Fetching crew members for: {airline}{flight_number} on {departure_date}")
            
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            
            if response.status_code == 200:
                crew_data = response.json()
                logger.info(f"✅ Crew members fetched successfully for {airline}{flight_number}")
                return crew_data
            else:
                logger.error(f"❌ Failed to fetch crew members: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching crew members: {e}")
            return None

    def get_flight_details_from_assignment(self, assignment):
        """
        Extract flight details from an assignment and fetch detailed flight info
        
        Parameters:
        - assignment: A flight assignment dictionary from schedule data
        """
        try:
            flight_assignment = assignment.get('FlighAssignement', {})
            
            # Extract required parameters from assignment
            airline = flight_assignment.get('Airline', 'AV')
            flight_number = flight_assignment.get('CommercialFlightNumber', '')
            operational_number = flight_assignment.get('OperationalNumber', '')
            departure_date_utc = flight_assignment.get('ScheduledDepartureDate', '')
            origin_airport = flight_assignment.get('OriginAirportIATACode', '')
            
            # Validate required fields
            if not all([flight_number, operational_number, departure_date_utc, origin_airport]):
                logger.warning(f"⚠️ Missing required flight data in assignment: {flight_assignment}")
                return None
            
            return self.get_flight_details(
                airline=airline,
                flight_number=flight_number,
                departure_date=departure_date_utc,
                origin_airport=origin_airport,
                operational_number=operational_number
            )
            
        except Exception as e:
            logger.error(f"❌ Error extracting flight details from assignment: {e}")
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

def create_empty_month_data(year, month):
    """Create empty month structure when no data is available"""
    first_day = datetime(year, month, 1)
    last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    
    month_data = []
    current_date = first_day
    while current_date <= last_day:
        date_str = current_date.strftime('%Y-%m-%d')
        month_data.append({
            'StartDate': date_str + 'T00:00:00Z',
            'Dem': '',
            'AssignementList': []
        })
        current_date += timedelta(days=1)
    
    return [month_data]

def transform_assignments_to_calendar_data(assignments_data, year, month):
    """Transform assignments into calendar month structure"""
    if not assignments_data or not isinstance(assignments_data, list):
        logger.warning(f"⚠️ No assignments data for {year}-{month:02d}")
        # Return empty month structure
        return create_empty_month_data(year, month)
    
    first_day = datetime(year, month, 1)
    last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    
    # Group assignments by day
    days_dict = {}
    assignments_found = False
    for assignment in assignments_data:
        if assignment and assignment.get('StartDate'):
            try:
                date_str = assignment['StartDate'][:10]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                if date_obj.year == year and date_obj.month == month:
                    assignments_found = True
                    if date_str not in days_dict:
                        days_dict[date_str] = {'StartDate': assignment['StartDate'], 'Dem': '', 'AssignementList': []}
                    days_dict[date_str]['AssignementList'].append(assignment)
            except (ValueError, KeyError):
                continue
    
    if not assignments_found:
        logger.warning(f"⚠️ No assignments found for the requested month {year}-{month:02d}")
        # Check what months we actually have data for
        actual_months = set()
        for assignment in assignments_data:
            if assignment and assignment.get('StartDate'):
                date_str = assignment['StartDate'][:7]  # YYYY-MM
                actual_months.add(date_str)
        if actual_months:
            logger.info(f"📊 Actual months with data: {sorted(actual_months)}")
    
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
                            'aircraft_registration': assignment.get('AircraftRegistrationNumber', '').strip() if assignment.get('AircraftRegistrationNumber') else '',
                            'operational_number': flight_data.get('OperationalNumber', '')  # Added for flight details
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

# Global variables
client = CrewAPIClient()
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID
current_calendar_year = datetime.now().year
current_calendar_month = datetime.now().month
crew_names = load_crew_names()

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
        
        # Debug: Check what we're actually displaying
        if schedule_data and schedule_data[0]:
            actual_dates = []
            for day in schedule_data[0]:
                if day and day.get('StartDate'):
                    actual_dates.append(day['StartDate'][:7])  # Get YYYY-MM
            unique_months = set(actual_dates)
            logger.info(f"📅 ACTUAL data months: {sorted(unique_months)}")
            logger.info(f"📅 REQUESTED month: {year}-{month:02d}")
            
            # Check if we got data for the requested month
            requested_month = f"{year}-{month:02d}"
            if requested_month not in unique_months and unique_months:
                # We're not showing the requested month, log what we actually have
                actual_month = sorted(unique_months)[0]
                logger.warning(f"⚠️ No data for requested month {requested_month}, showing {actual_month} instead")
    
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
        month_names=month_names,
        month_calendars=month_calendars,
        current_date=datetime.now().strftime('%Y-%m-%d'),
        current_month_index=0,
        current_calendar_year=current_calendar_year,
        current_calendar_month=current_calendar_month
    )

# NEW: Flight Details Endpoints
@app.route('/flight_details')
def flight_details_page():
    """Page to search for flight details"""
    return render_template('flight_details.html',
        current_crew_id=current_crew_id,
        crew_names=crew_names
    )

@app.route('/api/flight_details', methods=['POST'])
def get_flight_details_api():
    """API endpoint to get flight details"""
    try:
        data = request.get_json()
        
        # Required parameters
        airline = data.get('airline', 'AV')
        flight_number = data.get('flight_number')
        departure_date = data.get('departure_date')
        origin_airport = data.get('origin_airport')
        operational_number = data.get('operational_number')
        
        if not all([flight_number, departure_date, origin_airport, operational_number]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: flight_number, departure_date, origin_airport, operational_number'
            }), 400
        
        flight_details = client.get_flight_details(
            airline=airline,
            flight_number=flight_number,
            departure_date=departure_date,
            origin_airport=origin_airport,
            operational_number=operational_number
        )
        
        if flight_details:
            return jsonify({
                'success': True,
                'flight_details': flight_details
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch flight details'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in flight details API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/flight_crew', methods=['POST'])
def get_flight_crew_api():
    """API endpoint to get crew members for a flight"""
    try:
        data = request.get_json()
        
        # Required parameters
        airline = data.get('airline', 'AV')
        flight_number = data.get('flight_number')
        departure_date = data.get('departure_date')
        origin_airport = data.get('origin_airport')
        operational_number = data.get('operational_number')
        
        if not all([flight_number, departure_date, origin_airport, operational_number]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: flight_number, departure_date, origin_airport, operational_number'
            }), 400
        
        crew_data = client.get_flight_crew_members(
            airline=airline,
            flight_number=flight_number,
            departure_date=departure_date,
            origin_airport=origin_airport,
            operational_number=operational_number
        )
        
        if crew_data:
            return jsonify({
                'success': True,
                'crew_data': crew_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch crew data'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in flight crew API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/flight_details_from_assignment', methods=['POST'])
def get_flight_details_from_assignment_api():
    """API endpoint to get flight details from assignment data"""
    try:
        data = request.get_json()
        assignment = data.get('assignment')
        
        if not assignment:
            return jsonify({
                'success': False,
                'error': 'No assignment data provided'
            }), 400
        
        flight_details = client.get_flight_details_from_assignment(assignment)
        
        if flight_details:
            return jsonify({
                'success': True,
                'flight_details': flight_details
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch flight details from assignment'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in flight details from assignment API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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