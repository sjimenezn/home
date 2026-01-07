#!/usr/bin/env python3
"""
My Crew Schedule Monitor - Optimized Version with Paxlist Integration
"""

import os
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, jsonify

DEFAULT_CREW_ID = "32385184"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)

def get_utc_minus_5():
    return datetime.utcnow() - timedelta(hours=5)

def load_crew_names():
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
        self.last_token_time = None
        
    def _should_renew_token(self):
        """Check if token is older than 5 hours"""
        if not self.last_token_time or not self.auth_token:
            return True
        elapsed_hours = (datetime.utcnow() - self.last_token_time).total_seconds() / 3600
        logger.info(f"🔍 Token age: {elapsed_hours:.2f} hours")
        return elapsed_hours >= 5
    
    def _login(self, force=False):
        """Login only if token is older than 5 hours or forced"""
        try:
            if not force and not self._should_renew_token():
                logger.info("🔄 Using existing token (less than 5 hours old)")
                return True
                
            logger.info("🔄 Token expired or not present, requesting new token...")
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
                self.last_token_time = datetime.utcnow()
                logger.info(f"✅ New token acquired at {self.last_token_time}")
                return True
            else:
                logger.error(f"❌ Login failed with status: {response.status_code}")
                self.auth_token = None
                self.last_token_time = None
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            self.auth_token = None
            self.last_token_time = None
        return False

    def get_schedule_data(self, crew_id=None):
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
        try:
            target_crew_id = crew_id or current_crew_id
            now = get_utc_minus_5()
            year = year or now.year
            month = month or now.month
            
            first_day = datetime(year, month, 1)
            last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
            
            current_month = datetime(now.year, now.month, 1)
            requested_month = datetime(year, month, 1)
            
            if requested_month > current_month:
                last_day_of_current = (datetime(now.year + 1, 1, 1) if now.month == 12 
                                     else datetime(now.year, now.month + 1, 1)) - timedelta(days=1)
                start_date = last_day_of_current
                logger.info(f"🔮 Future month: starting from {start_date.strftime('%Y-%m-%d')}")
            else:
                start_date = first_day
                logger.info(f"📅 Current/Past month: starting from {start_date.strftime('%Y-%m-%d')}")
            
            change_days = 34
            logger.info(f"📊 Unified request: {change_days} days from {start_date.strftime('%Y-%m-%d')}")
            
            if not self._login():
                return None
            
            url = f"{self.base_url}/Assignements/GetAssignementsByUser"
            params = {
                "date": start_date.strftime('%Y-%m-%dT00:00:00Z'),
                "changeDays": change_days,
                "crewMemberUniqueId": target_crew_id,
                "holding": "AV",
                "timeZoneOffset": -300
            }
            
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
                logger.info(f"✅ Fetched {len(data)} assignments for {year}-{month:02d}")
                return {'year': year, 'month': month, 'assignments': data}
                
        except Exception as e:
            logger.error(f"❌ Error fetching assignments: {e}")
        return None

    def get_flight_details(self, airline, flight_number, departure_date, origin_airport, operational_number):
        try:
            if not self._login():
                return None
            
            url = f"{self.base_url}/FlightDetails/{airline}/{flight_number}/{departure_date}/{origin_airport}/{operational_number}"
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }
            
            body = {
                "holding": airline,
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "originAirportIATACode": origin_airport
            }
            
            logger.info(f"🛫 Fetching flight details: {airline}{flight_number}")
            
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            
            if response.status_code == 200:
                flight_data = response.json()
                logger.info(f"✅ Flight details fetched for {airline}{flight_number}")
                return flight_data
                
        except Exception as e:
            logger.error(f"❌ Error fetching flight details: {e}")
        return None

    def get_flight_crew_members(self, airline, flight_number, departure_date, origin_airport, operational_number):
        try:
            if not self._login():
                return None
            
            url = f"{self.base_url}/FlightDetails/FlightMembersTeam/{airline}/{flight_number}/{departure_date}/{origin_airport}/{operational_number}"
            
            headers = {
                "Authorization": self.auth_token,
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }
            
            body = {
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "holding": airline,
                "originAirportIATACode": operational_number
            }
            
            logger.info(f"👥 Fetching crew for: {airline}{flight_number}")
            
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            
            if response.status_code == 200:
                crew_data = response.json()
                logger.info(f"✅ Crew fetched for {airline}{flight_number}")
                return crew_data
                
        except Exception as e:
            logger.error(f"❌ Error fetching crew: {e}")
        return None

    def get_flight_details_from_assignment(self, assignment):
        try:
            flight_assignment = assignment.get('FlighAssignement', {})
            
            airline = flight_assignment.get('Airline', 'AV')
            flight_number = flight_assignment.get('CommercialFlightNumber', '')
            operational_number = flight_assignment.get('OperationalNumber', '')
            departure_date_utc = flight_assignment.get('ScheduledDepartureDate', '')
            origin_airport = flight_assignment.get('OriginAirportIATACode', '')
            
            if not all([flight_number, operational_number, departure_date_utc, origin_airport]):
                return None
            
            return self.get_flight_details(
                airline=airline,
                flight_number=flight_number,
                departure_date=departure_date_utc,
                origin_airport=origin_airport,
                operational_number=operational_number
            )
            
        except Exception as e:
            logger.error(f"❌ Error extracting flight details: {e}")
            return None
    
    def download_schedule_pdf(self, crew_id, schedule_type="actual", month="", year=""):
        try:
            if not self._login():
                return None
            
            endpoint = "Scheduled/Export" if schedule_type.lower() == "scheduled" else "Export"
            url = f"{self.base_url}/MonthlyAssignements/{endpoint}"
            
            boundary = "----WebKitFormBoundary" + str(int(time.time() * 1000))
            current_month = month or str(get_utc_minus_5().month)
            current_year = year or str(get_utc_minus_5().year)
            
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
                filename = f"{schedule_type}_schedule_{crew_id}_{get_utc_minus_5().strftime('%Y%m%d_%H%M%S')}.pdf"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return filename
                
        except Exception as e:
            logger.error(f"PDF download error: {e}")
        return None


class PaxlistClient:
    def __init__(self):
        self.base_url = "https://paxlist.avianca.com"
        self.token_url = "https://login.microsoftonline.com/a2addd3e-8397-4579-ba30-7a38803fc3bf/oauth2/v2.0/token"
        self.client_id = "1d866ed3-bdb0-47d1-bfac-8ebfd47360d3"
        self.redirect_uri = "https://paxlist.avianca.com/dashboard"
        self.scope = "api://1d866ed3-bdb0-47d1-bfac-8ebfd47360d3/access_as_user openid profile offline_access"
        
        self.session = None
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.refresh_expiry = None
        self.token_file = "paxlist_tokens.json"
        
        self.load_tokens()
        self.create_session()
    
    def create_session(self):
        """Create requests session"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,es-419;q=0.8,es;q=0.7",
            "Origin": "https://paxlist.avianca.com",
            "Referer": "https://paxlist.avianca.com/",
        })
    
    def load_tokens(self):
        """Load saved tokens from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                
                self.access_token = data.get('access_token')
                self.refresh_token = data.get('refresh_token')
                self.token_expiry = data.get('token_expiry')
                self.refresh_expiry = data.get('refresh_expiry')
                
                current_time = time.time()
                
                if self.refresh_token:
                    if self.refresh_expiry and current_time < self.refresh_expiry:
                        hours_left = int((self.refresh_expiry - current_time) / 3600)
                        logger.info(f"✅ Paxlist refresh token valid for {hours_left} hours")
                    else:
                        logger.warning("⚠️ Paxlist refresh token expired")
                
                if self.access_token:
                    if self.token_expiry and current_time < self.token_expiry:
                        minutes_left = int((self.token_expiry - current_time) / 60)
                        logger.info(f"✅ Paxlist access token valid for {minutes_left} minutes")
                    else:
                        logger.info("🔄 Paxlist access token needs refresh")
                        if self.refresh_token and self.refresh_expiry and current_time < self.refresh_expiry:
                            self.refresh_access_token()
                
                return True
                    
        except Exception as e:
            logger.error(f"Error loading Paxlist tokens: {e}")
        
        return False
    
    def save_tokens(self, access_token=None, refresh_token=None, expires_in=3700, refresh_expires_in=86399):
        """Save tokens to file"""
        try:
            current_time = time.time()
            
            if access_token:
                self.access_token = access_token
                self.token_expiry = current_time + expires_in
            
            if refresh_token:
                self.refresh_token = refresh_token
                self.refresh_expiry = current_time + refresh_expires_in
            
            data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'token_expiry': self.token_expiry,
                'refresh_expiry': self.refresh_expiry,
                'last_updated': current_time
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info("💾 Paxlist tokens saved")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Paxlist tokens: {e}")
            return False
    
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        try:
            if not self.refresh_token:
                logger.error("❌ No Paxlist refresh token available")
                return False
            
            current_time = time.time()
            if self.refresh_expiry and current_time >= self.refresh_expiry:
                logger.error("❌ Paxlist refresh token expired")
                return False
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                "Accept": "*/*",
                "Origin": "https://paxlist.avianca.com",
                "Referer": "https://paxlist.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            }
            
            data = {
                "client_id": self.client_id,
                "scope": self.scope,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "client_info": "1"
            }
            
            logger.info("🔄 Refreshing Paxlist access token...")
            
            response = requests.post(self.token_url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                
                new_access_token = token_data.get('access_token')
                new_refresh_token = token_data.get('refresh_token', self.refresh_token)
                expires_in = token_data.get('expires_in', 3700)
                refresh_expires_in = token_data.get('refresh_token_expires_in', 86399)
                
                success = self.save_tokens(
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                    expires_in=expires_in,
                    refresh_expires_in=refresh_expires_in
                )
                
                if success:
                    logger.info(f"✅ Paxlist access token refreshed (valid {expires_in//60} minutes)")
                    return True
            else:
                logger.error(f"❌ Paxlist token refresh failed: {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"❌ Error refreshing Paxlist token: {e}")
        
        return False
    
    def set_initial_tokens(self, access_token, refresh_token):
        """Set initial tokens from browser extraction"""
        try:
            success = self.save_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3700,
                refresh_expires_in=86399
            )
            
            if success:
                logger.info("✅ Paxlist initial tokens set successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error setting Paxlist initial tokens: {e}")
        
        return False
    
    def get_passenger_list(self, flight_carrier, flight_number, flight_departure_station, flight_date):
        """Get passenger list with automatic token refresh"""
        try:
            current_time = time.time()
            
            if not self.access_token or not self.token_expiry or current_time >= self.token_expiry:
                if not self.refresh_access_token():
                    return {
                        "error": "token_expired",
                        "message": "Token expired and could not refresh",
                        "needs_new_tokens": True
                    }
            
            url = f"{self.base_url}/crew_devices/consulta_pasajeros"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://paxlist.avianca.com",
                "Referer": "https://paxlist.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty"
            }
            
            payload = {
                "flight_carrier": flight_carrier,
                "flight_number": flight_number,
                "flight_departure_station": flight_departure_station,
                "flight_date": flight_date
            }
            
            logger.info(f"🛫 Requesting passenger list: {flight_carrier}{flight_number}")
            
            response = self.session.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                passenger_count = len(data.get('passengers', []))
                logger.info(f"✅ Got {passenger_count} passengers")
                return data
            elif response.status_code == 401:
                logger.warning("🔄 Got 401, forcing token refresh...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    response = self.session.post(url, json=payload, headers=headers, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        logger.info("✅ Request succeeded after token refresh")
                        return data
                
                return {
                    "error": "authentication_failed",
                    "message": "Authentication failed",
                    "status_code": 401
                }
            else:
                logger.error(f"❌ Paxlist API error {response.status_code}")
                return {
                    "error": "api_error",
                    "status_code": response.status_code,
                    "message": response.text[:500] if response.text else "No response"
                }
                
        except Exception as e:
            logger.error(f"❌ Error in Paxlist request: {e}")
            return {"error": "request_error", "message": str(e)}
    
    def get_token_status(self):
        """Get current token status"""
        current_time = time.time()
        
        access_valid = False
        refresh_valid = False
        access_expires_in = 0
        refresh_expires_in = 0
        
        if self.access_token and self.token_expiry:
            access_valid = current_time < self.token_expiry
            access_expires_in = max(0, int(self.token_expiry - current_time))
        
        if self.refresh_token and self.refresh_expiry:
            refresh_valid = current_time < self.refresh_expiry
            refresh_expires_in = max(0, int(self.refresh_expiry - current_time))
        
        return {
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "access_token_valid": access_valid,
            "refresh_token_valid": refresh_valid,
            "access_expires_in_seconds": access_expires_in,
            "refresh_expires_in_seconds": refresh_expires_in,
            "access_expires_in_minutes": access_expires_in // 60,
            "refresh_expires_in_hours": refresh_expires_in // 3600
        }


def create_empty_month_data(year, month):
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
    if not assignments_data or not isinstance(assignments_data, list):
        logger.warning(f"⚠️ No assignments data for {year}-{month:02d}")
        return create_empty_month_data(year, month)
    
    first_day = datetime(year, month, 1)
    last_day = (datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)) - timedelta(days=1)
    
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
    if not month_data or not isinstance(month_data, list):
        return []
    
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
    
    calendar_start = first_day - timedelta(days=first_day.weekday())
    calendar_days = []
    
    for i in range(42):
        current_date = calendar_start + timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        calendar_day = None
        
        for day_data in month_data:
            if day_data and day_data.get('StartDate', '').startswith(date_str):
                assignments = []
                for assignment in day_data.get('AssignementList', []):
                    flight_data = assignment.get('FlighAssignement')
                    if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                        local_date = assignment.get('StartDateLocal', '')[:10]
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
                            'operational_number': flight_data.get('OperationalNumber', ''),
                            'local_date': local_date
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


# Initialize clients
client = CrewAPIClient()
paxlist_client = PaxlistClient()

# Global variables
schedule_data = None
last_fetch_time = None
current_crew_id = DEFAULT_CREW_ID
current_calendar_year = get_utc_minus_5().year
current_calendar_month = get_utc_minus_5().month
crew_names = load_crew_names()


# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    global schedule_data, last_fetch_time
    
    logger.info("🔄 Auto-fetching fresh data...")
    new_data = client.get_schedule_data(current_crew_id)
    if new_data is not None:
        schedule_data = new_data
        last_fetch_time = get_utc_minus_5().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("✅ Auto-fetch completed!")
    elif schedule_data is None:
        logger.warning("⚠️ Auto-fetch failed")
    
    total_days = 0
    total_assignments = 0
    month_names = []
    current_date = get_utc_minus_5().strftime('%Y-%m-%d')
    
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
    
    logger.info(f"🗓️ Calendar view: {year}-{month:02d}")
    
    assignments_result = client.get_assignments_by_user(current_crew_id, year=year, month=month)
    if assignments_result:
        schedule_data = transform_assignments_to_calendar_data(
            assignments_result['assignments'], 
            assignments_result['year'], 
            assignments_result['month']
        )
        last_fetch_time = get_utc_minus_5().strftime("%Y-%m-%d %H:%M:%S")
    
    month_name = get_month_name(year, month)
    month_calendars = [create_calendar_view_data(schedule_data[0])] if schedule_data else []
    
    total_days = len(schedule_data[0]) if schedule_data else 0
    total_assignments = sum(len(day.get('AssignementList', [])) for day in schedule_data[0]) if schedule_data else 0
    
    total_actual_minutes = 0
    total_scheduled_minutes = 0
    
    if schedule_data:
        for day in schedule_data[0]:
            for assignment in day.get('AssignementList', []):
                flight_data = assignment.get('FlighAssignement', {})
                if flight_data and flight_data.get('CommercialFlightNumber') != "XXX":
                    actual_duration = flight_data.get('Duration')
                    if actual_duration is not None:
                        total_actual_minutes += actual_duration
                    
                    scheduled_duration = flight_data.get('ScheduledDuration')
                    if scheduled_duration is not None:
                        total_scheduled_minutes += scheduled_duration
    
    total_actual_hours = total_actual_minutes // 60
    total_actual_minutes_remainder = total_actual_minutes % 60
    
    total_scheduled_hours = total_scheduled_minutes // 60
    total_scheduled_minutes_remainder = total_scheduled_minutes % 60
    
    refresh_message = "Data refreshed successfully!" if request.args.get('refresh') == 'success' else None
    
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
        current_date=get_utc_minus_5().strftime('%Y-%m-%d'),
        current_month_index=0,
        current_calendar_year=current_calendar_year,
        current_calendar_month=current_calendar_month,
        total_actual_hours=total_actual_hours,
        total_actual_minutes=total_actual_minutes_remainder,
        total_scheduled_hours=total_scheduled_hours,
        total_scheduled_minutes=total_scheduled_minutes_remainder,
        crew_names=crew_names
    )
    
@app.route('/flight_details')
def flight_details_page():
    return render_template('flight_details.html',
        current_crew_id=current_crew_id,
        crew_names=crew_names,
        flight_details=None,
        crew_data=None,
        auto_fetch=False,
        flight_number=None,
        local_date=None,
        origin_airport=None
    )

@app.route('/paxlist')
def paxlist_page():
    """Paxlist search page"""
    return render_template('paxlist.html',
        current_crew_id=current_crew_id,
        crew_names=crew_names,
        has_token=bool(paxlist_client.access_token)
    )

@app.route('/api/paxlist/set_initial_tokens', methods=['POST'])
def set_paxlist_initial_tokens():
    """Set initial tokens from browser extraction"""
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        if access_token and refresh_token:
            success = paxlist_client.set_initial_tokens(access_token, refresh_token)
            if success:
                return jsonify({
                    'success': True, 
                    'message': 'Tokens set successfully. Will auto-refresh for 24 hours.'
                })
    except Exception as e:
        logger.error(f"Error setting Paxlist tokens: {e}")
    return jsonify({'success': False, 'message': 'Failed to set tokens'}), 400

@app.route('/api/paxlist/refresh_token', methods=['POST'])
def refresh_paxlist_token():
    """Manually refresh token"""
    try:
        success = paxlist_client.refresh_access_token()
        if success:
            return jsonify({'success': True, 'message': 'Token refreshed'})
    except Exception as e:
        logger.error(f"Error refreshing Paxlist token: {e}")
    return jsonify({'success': False, 'message': 'Failed to refresh token'}), 400

@app.route('/api/paxlist/token_status')
def paxlist_token_status():
    """Get token status"""
    status = paxlist_client.get_token_status()
    return jsonify({
        'success': True,
        'status': status
    })

@app.route('/api/paxlist/search', methods=['POST'])
def paxlist_search():
    """Search for passengers"""
    try:
        data = request.get_json()
        
        flight_carrier = data.get('flight_carrier', 'AV')
        flight_number = data.get('flight_number')
        flight_departure_station = data.get('flight_departure_station')
        flight_date = data.get('flight_date')
        
        if not all([flight_number, flight_departure_station, flight_date]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        result = paxlist_client.get_passenger_list(
            flight_carrier=flight_carrier,
            flight_number=flight_number,
            flight_departure_station=flight_departure_station,
            flight_date=flight_date
        )
        
        if isinstance(result, dict) and 'error' in result:
            return jsonify({
                'success': False,
                'message': result.get('message', 'Failed to fetch passenger data'),
                'needs_new_tokens': result.get('needs_new_tokens', False),
                'data': result
            })
        elif result:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to fetch passenger data'
            }), 500
            
    except Exception as e:
        logger.error(f"Paxlist search error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/flight_details', methods=['POST'])
def get_flight_details_api():
    try:
        data = request.get_json()
        
        airline = data.get('airline', 'AV')
        flight_number = data.get('flight_number')
        departure_date = data.get('departure_date')
        origin_airport = data.get('origin_airport')
        operational_number = data.get('operational_number')
        
        if not all([flight_number, departure_date, origin_airport, operational_number]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
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
    try:
        data = request.get_json()
        
        airline = data.get('airline', 'AV')
        flight_number = data.get('flight_number')
        departure_date = data.get('departure_date')
        origin_airport = data.get('origin_airport')
        operational_number = data.get('operational_number')
        
        if not all([flight_number, departure_date, origin_airport, operational_number]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
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
        current_calendar_year = get_utc_minus_5().year
        current_calendar_month = get_utc_minus_5().month
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
            last_fetch_time = get_utc_minus_5().strftime("%Y-%m-%d %H:%M:%S")
            return {"success": True}
    except Exception as e:
        logger.error(f"Error in /fetch: {e}")
    return {"success": False, "error": "Failed to fetch data"}

if __name__ == "__main__":
    logger.info("🚀 Starting Crew Schedule Application with Paxlist Integration...")
    app.run(host='0.0.0.0', port=8000, debug=False)