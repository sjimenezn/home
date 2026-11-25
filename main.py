#!/usr/bin/env python3
"""
My Crew Schedule Monitor -  Optimized Version with Paxlist Integration
"""

import os
import time
import json
import logging
import random
import threading
import requests
import jwt
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, jsonify

DEFAULT_CREW_ID = "32385184"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)

# BOG gate mapping: raw stand number -> secondary gate label
BOG_GATE_MAPPING = {
    '11': 'C1', '12': 'C2', '13': 'C3', '15': 'C5',
    '17': 'B8', '19': 'B7', '20': 'B7', '22': 'B6',
    '24': 'B5', '27': 'B3', '29': 'B2', '32': 'B1',
    '34': 'A1', '36': 'A2', '38': 'A3', '39': 'A3',
    '41': 'A4', '43': 'A5', '45': 'A6',
    '47': 'A8', '48': 'A10', '49': 'A10',
    '51': 'A11', '53': 'A12', '54': 'A13', '56': 'A14',
    '71': 'D1', '72': 'D3', '73': 'D5',
    '74': 'D9', '75': 'D11', '76': 'D13',
    '79': 'D15', '80': 'D15', '83': 'D15',
    '84': 'D14', '85': 'D12', '86': 'D10',
    '87': 'D8', '88': 'D4', '89': 'D2'
}

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
    """
    Manual-token client. Tokens are pasted from the browser (via /paxlist)
    and stored in crew_tokens.json. No password login.

    Refresh model:
      - Daemon thread fires every random 55-85 min after a fresh paste.
      - Each cycle: POST /token with the stored refresh_token, save the new
        access_token + rotated refresh_token.
      - On any failure: stop permanently, wait for manual paste.
      - _auth_headers() also lazily refreshes if a request comes in while
        the access token is expired or about to expire.
    """

    TOKEN_URL = "https://login.microsoftonline.com/a2addd3e-8397-4579-ba30-7a38803fc3bf/oauth2/v2.0/token"
    CLIENT_ID = "d4f94e81-080a-4ad3-8513-760529dd325f"
    SCOPE = "api://d4f94e81-080a-4ad3-8513-760529dd325f/access_as_user openid profile offline_access"

    def __init__(self):
        self.base_url = "https://api-avianca.avianca.com/MycreWFlights/api"
        self.subscription_key = "9d32877073ce403795da2254ae9c2de7"
        self.session = requests.Session()
        self.token_file = "crew_tokens.json"

        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None
        self.refresh_expiry = None

        self._timer_thread = None
        self._timer_stop = threading.Event()
        self._timer_lock = threading.Lock()

        self.load_tokens()

    # ---------- token storage ----------

    def load_tokens(self):
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                self.access_token = data.get('access_token')
                self.refresh_token = data.get('refresh_token')
                self.token_expiry = data.get('token_expiry')
                self.refresh_expiry = data.get('refresh_expiry')

                if self.access_token and self.token_expiry and time.time() < self.token_expiry:
                    mins_left = int((self.token_expiry - time.time()) / 60)
                    logger.info(f"✅ Crew access token loaded (valid {mins_left} min)")
                elif self.access_token:
                    logger.warning("⚠️ Crew access token loaded but expired")
                else:
                    logger.warning("⚠️ crew_tokens.json exists but has no access_token")

                # Restart the keep-alive daemon if we have a refresh token
                if self.refresh_token:
                    self._start_refresh_daemon(reason="startup")
        except Exception as e:
            logger.error(f"Error loading crew tokens: {e}")

    def save_tokens(self, access_token=None, refresh_token=None,
                    expires_in=3600, refresh_expires_in=86400):
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
                'last_updated': current_time,
            }
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Crew tokens saved (access valid {expires_in//60} min)")
            return True
        except Exception as e:
            logger.error(f"Error saving crew tokens: {e}")
            return False

    def _decode_jwt_exp(self, token):
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get('exp')
            if exp:
                return max(0, int(exp - time.time()))
        except Exception as e:
            logger.warning(f"Could not decode crew JWT: {e}")
        return None

    def set_initial_tokens(self, access_token, refresh_token,
                           expires_in=3600, refresh_expires_in=86400):
        """Called from /api/crew/set_initial_tokens."""
        if not isinstance(access_token, str) or not access_token.startswith('eyJ'):
            logger.error("❌ Invalid access_token — must be a JWT starting with eyJ")
            return False

        # Prefer the JWT's own exp over the passed expires_in
        jwt_exp = self._decode_jwt_exp(access_token)
        if jwt_exp is not None:
            expires_in = jwt_exp
            logger.info(f"📊 Crew JWT exp: {expires_in} s ({expires_in//60} min)")

        ok = self.save_tokens(
            access_token=access_token,
            refresh_token=refresh_token or self.refresh_token or '',
            expires_in=expires_in,
            refresh_expires_in=refresh_expires_in,
        )
        if ok:
            # Fresh paste -> start a new keep-alive cycle
            self._start_refresh_daemon(reason="fresh paste")
        return ok

    def get_token_status(self):
        current_time = time.time()
        access_valid = bool(
            self.access_token and self.token_expiry and current_time < self.token_expiry
        )
        refresh_valid = bool(
            self.refresh_token and self.refresh_expiry and current_time < self.refresh_expiry
        )
        access_expires_in = max(0, int((self.token_expiry or 0) - current_time))
        refresh_expires_in = max(0, int((self.refresh_expiry or 0) - current_time))

        return {
            'has_access_token': bool(self.access_token),
            'has_refresh_token': bool(self.refresh_token),
            'access_token_valid': access_valid,
            'refresh_token_valid': refresh_valid,
            'access_expires_in_seconds': access_expires_in,
            'refresh_expires_in_seconds': refresh_expires_in,
            'access_expires_in_minutes': access_expires_in // 60,
            'refresh_expires_in_hours': refresh_expires_in // 3600,
            'timer_running': bool(self._timer_thread and self._timer_thread.is_alive()),
        }

    # ---------- refresh + daemon ----------

    def refresh_access_token(self):
        """Exchange the stored refresh_token for a new access_token.
        Returns True on success, False on any failure. No retries."""
        try:
            if not self.refresh_token:
                logger.error("❌ No crew refresh token available")
                return False

            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                "Accept": "*/*",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            }
            data = {
                "client_id": self.CLIENT_ID,
                "scope": self.SCOPE,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
                "client_info": "1",
            }

            logger.info("🔄 Refreshing Crew access token...")
            resp = requests.post(self.TOKEN_URL, data=data, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.error(f"❌ Crew refresh failed: {resp.status_code} {resp.text[:200]}")
                return False

            td = resp.json()
            new_access = td.get('access_token')
            new_refresh = td.get('refresh_token', self.refresh_token)
            expires_in = td.get('expires_in', 3600)
            refresh_expires_in = td.get('refresh_token_expires_in', 86399)

            jwt_exp = self._decode_jwt_exp(new_access) if new_access else None
            if jwt_exp is not None:
                expires_in = jwt_exp

            if not new_access:
                logger.error("❌ Crew refresh response missing access_token")
                return False

            ok = self.save_tokens(
                access_token=new_access,
                refresh_token=new_refresh,
                expires_in=expires_in,
                refresh_expires_in=refresh_expires_in,
            )
            if ok:
                logger.info(f"✅ Crew token refreshed (valid {expires_in//60} min)")
            return ok

        except Exception as e:
            logger.error(f"❌ Crew refresh error: {e}")
            return False

    def _start_refresh_daemon(self, reason=""):
        """(Re)start the keep-alive daemon thread. Safe to call repeatedly."""
        with self._timer_lock:
            # Stop any existing timer
            if self._timer_thread and self._timer_thread.is_alive():
                self._timer_stop.set()
                logger.info(f"🛑 Stopping previous crew refresh daemon ({reason})")
            self._timer_stop = threading.Event()
            self._timer_thread = threading.Thread(
                target=self._refresh_loop,
                args=(self._timer_stop,),
                daemon=True,
                name="crew-refresh-daemon",
            )
            self._timer_thread.start()
            logger.info(f"⏱️ Crew refresh daemon started ({reason})")

    def _refresh_loop(self, stop_event):
        """Random 55-85 min cycle. Stop permanently on any refresh failure."""
        while not stop_event.is_set():
            sleep_seconds = random.randint(55 * 60, 85 * 60)
            logger.info(f"⏱️ Crew next refresh in {sleep_seconds//60} min")
            if stop_event.wait(timeout=sleep_seconds):
                logger.info("🛑 Crew refresh daemon stopped")
                return

            ok = self.refresh_access_token()
            if not ok:
                logger.error("❌ Crew refresh failed — daemon stopping until next manual paste")
                return

    # ---------- internal guard ----------

    def _auth_headers(self):
        """Returns headers dict if we have a valid access token, else None.
        Lazily refreshes if the access token is expired or about to expire."""
        if not self.access_token:
            logger.error("❌ No crew access token — paste one at /paxlist")
            return None

        # Refresh if expired or <300s remaining
        if not self.token_expiry or (self.token_expiry - time.time()) < 300:
            logger.info("🔄 Access token expired/near expiry — refreshing before request")
            if not self.refresh_access_token():
                logger.error("❌ Crew token refresh failed — paste new tokens at /paxlist")
                return None

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Accept": "application/json",
            "Origin": "https://mycrew.avianca.com",
            "Referer": "https://mycrew.avianca.com/",
        }

    # ---------- API methods ----------

    def get_schedule_data(self, crew_id=None):
        try:
            target_crew_id = crew_id or current_crew_id
            headers = self._auth_headers()
            if not headers:
                return None

            url = f"{self.base_url}/Assignements/AssignmentsComplete"
            params = {"timeZoneOffset": -300, "crewMemberUniqueId": target_crew_id}
            response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 401:
                logger.warning("🔄 Got 401 on schedule — refreshing once")
                if self.refresh_access_token():
                    headers = self._auth_headers()
                    if headers:
                        response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ get_schedule_data: {len(data)} months")
                return data
            logger.error(f"❌ get_schedule_data {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"❌ get_schedule_data error: {e}")
        return None

    def get_assignments_by_user(self, crew_id=None, year=None, month=None):
        try:
            target_crew_id = crew_id or current_crew_id
            now = get_utc_minus_5()
            year = year or now.year
            month = month or now.month

            first_day = datetime(year, month, 1)
            current_month = datetime(now.year, now.month, 1)
            requested_month = datetime(year, month, 1)

            if requested_month > current_month:
                last_day_of_current = (
                    datetime(now.year + 1, 1, 1) if now.month == 12
                    else datetime(now.year, now.month + 1, 1)
                ) - timedelta(days=1)
                start_date = last_day_of_current
                logger.info(f"🔮 Future month: starting from {start_date.strftime('%Y-%m-%d')}")
            else:
                start_date = first_day
                logger.info(f"📅 Current/Past month: starting from {start_date.strftime('%Y-%m-%d')}")

            headers = self._auth_headers()
            if not headers:
                return None

            url = f"{self.base_url}/Assignements/GetAssignementsByUser"
            params = {
                "date": start_date.strftime('%Y-%m-%dT00:00:00Z'),
                "changeDays": 34,
                "crewMemberUniqueId": target_crew_id,
                "holding": "AV",
                "timeZoneOffset": -300,
            }
            response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 401:
                logger.warning("🔄 Got 401 on assignments — refreshing once")
                if self.refresh_access_token():
                    headers = self._auth_headers()
                    if headers:
                        response = self.session.get(url, params=params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Fetched {len(data)} assignments for {year}-{month:02d}")
                return {'year': year, 'month': month, 'assignments': data}
            logger.error(f"❌ get_assignments_by_user {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"❌ get_assignments_by_user error: {e}")
        return None

    def get_flight_details(self, airline, flight_number, departure_date,
                           origin_airport, operational_number):
        try:
            headers = self._auth_headers()
            if not headers:
                return None
            headers["Content-Type"] = "application/json"

            url = (f"{self.base_url}/FlightDetails/{airline}/{flight_number}/"
                   f"{departure_date}/{origin_airport}/{operational_number}")
            body = {
                "holding": airline,
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "originAirportIATACode": origin_airport,
            }
            logger.info(f"🛫 Fetching flight details: {airline}{flight_number}")
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"✅ Flight details fetched for {airline}{flight_number}")
                return response.json()
            logger.error(f"❌ get_flight_details {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"❌ get_flight_details error: {e}")
        return None

    def get_flight_crew_members(self, airline, flight_number, departure_date,
                                origin_airport, operational_number):
        try:
            headers = self._auth_headers()
            if not headers:
                return None
            headers["Content-Type"] = "application/json"

            url = (f"{self.base_url}/FlightDetails/FlightMembersTeam/{airline}/"
                   f"{flight_number}/{departure_date}/{origin_airport}/{operational_number}")
            body = {
                "commercialFlightNumber": flight_number,
                "departureflightDate": departure_date,
                "holding": airline,
                "originAirportIATACode": operational_number,
            }
            logger.info(f"👥 Fetching crew for: {airline}{flight_number}")
            response = self.session.post(url, json=body, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"✅ Crew fetched for {airline}{flight_number}")
                return response.json()
            logger.error(f"❌ get_flight_crew_members {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"❌ get_flight_crew_members error: {e}")
        return None

    def get_flight_details_from_assignment(self, assignment):
        try:
            fa = assignment.get('FlighAssignement', {})
            return self.get_flight_details(
                airline=fa.get('Airline', 'AV'),
                flight_number=fa.get('CommercialFlightNumber', ''),
                departure_date=fa.get('ScheduledDepartureDate', ''),
                origin_airport=fa.get('OriginAirportIATACode', ''),
                operational_number=fa.get('OperationalNumber', ''),
            )
        except Exception as e:
            logger.error(f"❌ get_flight_details_from_assignment error: {e}")
            return None

    # ---------- SearchFlight ----------

    def search_flight(self, airline, flight_number, departure_date, origin_airport):
        """Look up the real operational number + exact scheduled departure time."""
        try:
            headers = self._auth_headers()
            if not headers:
                return None
            headers["Content-Type"] = "application/json"

            url = f"{self.base_url}/FlightDetails/SearchFlight"
            body = {
                "departureFlightDate": departure_date,
                "holding": airline,
                "commercialFlightNumber": flight_number,
                "originAirportIATACode": origin_airport,
                "departureAirportIATACode": "",
                "operationalSufix": ""
            }
            logger.info(f"🔎 Searching flight: {airline}{flight_number} {departure_date} {origin_airport}")
            response = self.session.post(url, json=body, headers=headers, timeout=30)

            if response.status_code == 204:
                logger.warning(f"⚠️ SearchFlight 204 (no match) for {airline}{flight_number}")
                return None

            if response.status_code == 200:
                data = response.json()
                fa = data.get('FlighAssignement') or {}
                result = {
                    'operational_number': str(data.get('Id', '')),
                    'scheduled_departure': fa.get('ScheduledDepartureDate', ''),
                    'scheduled_arrival': fa.get('ScheduledArrivalDate', ''),
                    'origin': fa.get('OriginAirportIATACode', ''),
                    'destination': fa.get('FinalAirportIATACode', ''),
                    'flight_number': fa.get('CommercialFlightNumber', ''),
                }
                logger.info(f"✅ Found {airline}{flight_number}: OPN={result['operational_number']}, "
                            f"dep={result['scheduled_departure']}")
                return result

            logger.error(f"❌ SearchFlight {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.error(f"❌ search_flight error: {e}")
        return None

    def download_schedule_pdf(self, crew_id, schedule_type="actual", month="", year=""):
        try:
            if not self.access_token or (self.token_expiry and time.time() >= self.token_expiry):
                logger.error("❌ No valid crew token for PDF download — paste one at /paxlist")
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
                "Authorization": f"Bearer {self.access_token}",
                "Ocp-Apim-Subscription-Key": self.subscription_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Origin": "https://mycrew.avianca.com",
                "Referer": "https://mycrew.avianca.com/",
            }

            response = self.session.post(url, data=form_data, headers=headers, timeout=30)
            if response.status_code == 200 and 'pdf' in response.headers.get('content-type', '').lower():
                filename = (f"{schedule_type}_schedule_{crew_id}_"
                            f"{get_utc_minus_5().strftime('%Y%m%d_%H%M%S')}.pdf")
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return filename
            logger.error(f"❌ PDF {response.status_code}")
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
        self.refresh_failed = False

        self.load_tokens()
        self.create_session()

    def create_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,es-419;q=0.8,es;q=0.7",
            "Origin": "https://paxlist.avianca.com",
            "Referer": "https://paxlist.avianca.com/",
        })

    def decode_jwt_token(self, token):
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        except Exception as e:
            logger.error(f"Failed to decode JWT: {e}")
            return None

    def get_expiry_from_token(self, token):
        try:
            payload = self.decode_jwt_token(token)
            if payload and 'exp' in payload:
                exp_timestamp = payload['exp']
                current_time = time.time()
                seconds_left = max(0, int(exp_timestamp - current_time))

                iat_timestamp = payload.get('iat', 0)
                if iat_timestamp:
                    total_lifetime = exp_timestamp - iat_timestamp
                    logger.info(f"📊 JWT Analysis:")
                    logger.info(f"   - Issued at: {datetime.fromtimestamp(iat_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"   - Expires at: {datetime.fromtimestamp(exp_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"   - Total lifetime: {total_lifetime//60} minutes ({total_lifetime} seconds)")
                    logger.info(f"   - Time left: {seconds_left//60} minutes ({seconds_left} seconds)")

                return seconds_left
            else:
                logger.warning("⚠️ No 'exp' claim found in token")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to get expiry from JWT: {e}")
            return None

    def load_tokens(self):
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
                        jwt_time_left = self.get_expiry_from_token(self.access_token)
                        if jwt_time_left:
                            logger.info(f"🔍 JWT says {jwt_time_left//60} minutes left, stored says {minutes_left} minutes left")
                            if abs(jwt_time_left - (self.token_expiry - current_time)) > 60:
                                logger.warning(f"⚠️ Token expiry mismatch! Updating with JWT value")
                                self.token_expiry = current_time + jwt_time_left
                                self.save_tokens(
                                    access_token=self.access_token,
                                    refresh_token=self.refresh_token,
                                    expires_in=jwt_time_left,
                                    refresh_expires_in=86399
                                )
                    else:
                        logger.info("🔄 Paxlist access token needs refresh")
                        if self.refresh_token and self.refresh_expiry and current_time < self.refresh_expiry:
                            self.refresh_access_token()

                return True

        except Exception as e:
            logger.error(f"Error loading Paxlist tokens: {e}")

        return False

    def save_tokens(self, access_token=None, refresh_token=None, expires_in=3700, refresh_expires_in=86399):
        try:
            current_time = time.time()

            if access_token:
                self.access_token = access_token
                jwt_expiry = self.get_expiry_from_token(access_token)
                if jwt_expiry:
                    expires_in = jwt_expiry
                    logger.info(f"📊 Using JWT expiry: {expires_in//60} minutes")
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

            logger.info(f"💾 Paxlist tokens saved (access valid for {expires_in//60} minutes)")
            return True

        except Exception as e:
            logger.error(f"Error saving Paxlist tokens: {e}")
            return False

    def refresh_access_token(self):
        try:
            if not self.refresh_token:
                logger.error("❌ No Paxlist refresh token available")
                self.refresh_failed = True
                return False

            current_time = time.time()
            if self.refresh_expiry and current_time >= self.refresh_expiry:
                logger.error("❌ Paxlist refresh token expired")
                self.refresh_failed = True
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

                jwt_expiry = self.get_expiry_from_token(new_access_token)
                if jwt_expiry:
                    logger.info(f"📊 Response says {expires_in//60} min, JWT says {jwt_expiry//60} min")
                    expires_in = jwt_expiry

                success = self.save_tokens(
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                    expires_in=expires_in,
                    refresh_expires_in=refresh_expires_in
                )

                if success:
                    self.refresh_failed = False
                    logger.info(f"✅ Paxlist access token refreshed (valid {expires_in//60} minutes)")
                    return True
            else:
                logger.error(f"❌ Paxlist token refresh failed: {response.status_code}")
                if response.text:
                    logger.error(f"Response: {response.text[:200]}")

        except Exception as e:
            logger.error(f"❌ Error refreshing Paxlist token: {e}")

        self.refresh_failed = True
        return False

    def set_initial_tokens(self, access_token, refresh_token):
        try:
            if not isinstance(access_token, str) or not access_token.startswith('eyJ'):
                logger.error("❌ Invalid token format - must be a JWT starting with eyJ")
                return False

            jwt_expiry = self.get_expiry_from_token(access_token)

            if jwt_expiry:
                logger.info(f"📊 Using JWT decoding to set token expiry: {jwt_expiry//60} minutes")
                expires_in = jwt_expiry
            else:
                logger.warning("⚠️ Could not decode JWT, using default 3700 seconds")
                expires_in = 3700

            success = self.save_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                refresh_expires_in=86399
            )

            if success:
                self.refresh_failed = False
                logger.info("✅ Paxlist initial tokens set successfully")
                return True

        except Exception as e:
            logger.error(f"Error setting Paxlist initial tokens: {e}")

        return False

    def get_passenger_list(self, flight_carrier, flight_number, flight_departure_station, flight_date):
        try:
            current_time = time.time()

            # Fast-fail: previous refresh already failed, wait for manual paste
            if self.refresh_failed:
                logger.warning("⛔ Paxlist refresh previously failed — waiting for new tokens")
                return {
                    "error": "token_expired",
                    "message": "Token expired and could not refresh",
                    "needs_new_tokens": True
                }

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
        current_time = time.time()

        access_valid = False
        refresh_valid = False
        access_expires_in = 0
        refresh_expires_in = 0
        jwt_verified = False
        jwt_expires_in = 0

        if self.access_token and self.token_expiry:
            access_valid = current_time < self.token_expiry
            access_expires_in = max(0, int(self.token_expiry - current_time))

            jwt_time_left = self.get_expiry_from_token(self.access_token)
            if jwt_time_left:
                jwt_verified = True
                jwt_expires_in = jwt_time_left
                if abs(jwt_time_left - access_expires_in) > 60:
                    logger.warning(f"⚠️ Token expiry mismatch! Stored: {access_expires_in//60} min, JWT: {jwt_time_left//60} min")

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
            "refresh_expires_in_hours": refresh_expires_in // 3600,
            "jwt_verified": jwt_verified,
            "jwt_expires_in_seconds": jwt_expires_in,
            "jwt_expires_in_minutes": jwt_expires_in // 60,
            "refresh_failed": self.refresh_failed
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

                        raw_stand = flight_data.get('DepartureStand')
                        if raw_stand is None:
                            stand = ''
                        else:
                            stand = str(raw_stand).strip()
                            if stand.lower() in ('null', 'none', 'undefined', 'nan', ''):
                                stand = ''

                        logger.info(f"🧪 Stand for {flight_data.get('CommercialFlightNumber')}: raw={raw_stand!r} → parsed={stand!r}")

                        assignments.append({
                            'is_flight': True,
                            'flight_number': flight_data.get('CommercialFlightNumber', ''),
                            'origin': flight_data.get('OriginAirportIATACode', '').strip() if flight_data.get('OriginAirportIATACode') else '',
                            'destination': flight_data.get('FinalAirportIATACode', '').strip() if flight_data.get('FinalAirportIATACode') else '',
                            'departure_stand': stand,
                            'departure_time': flight_data.get('ScheduledDepartureDate', '')[11:16] if flight_data.get('ScheduledDepartureDate') else 'N/A',
                            'arrival_time': flight_data.get('ScheduledArrivalDate', '')[11:16] if flight_data.get('ScheduledArrivalDate') else 'N/A',
                            'time_advanced': flight_data.get('TimeAdvanced', False),
                            'time_delayed': flight_data.get('TimeDelayed', False),
                            'aircraft_registration': assignment.get('AircraftRegistrationNumber', '').strip() if assignment.get('AircraftRegistrationNumber') else '',
                            'operational_number': flight_data.get('OperationalNumber', ''),
                            'local_date': local_date,
                            'gate_key': f"{flight_data.get('CommercialFlightNumber', '')}_{flight_data.get('OperationalNumber', '')}_{flight_data.get('ScheduledDepartureDate', '')}"
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
previous_crew_id = None
current_calendar_year = get_utc_minus_5().year
current_calendar_month = get_utc_minus_5().month
crew_names = load_crew_names()


# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    paxlist_status = paxlist_client.get_token_status() if paxlist_client else None
    crew_status = client.get_token_status()

    return render_template('paxlist.html',
        current_crew_id=current_crew_id,
        crew_names=crew_names,
        token_status=paxlist_status,
        crew_token_status=crew_status,
        has_token=bool(paxlist_client and paxlist_client.access_token)
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

    now_local = get_utc_minus_5()
    today_str = now_local.strftime('%Y-%m-%d')
    tomorrow_str = (now_local + timedelta(days=1)).strftime('%Y-%m-%d')
    target_dates = {today_str, tomorrow_str}

    lazy_gate_flights = []

    if schedule_data and isinstance(schedule_data, list) and schedule_data:
        for day in schedule_data[0]:
            if not day:
                continue
            day_start = day.get('StartDate', '')
            day_date = day_start[:10] if day_start else ''
            if day_date not in target_dates:
                continue
            for assignment in day.get('AssignementList', []):
                flight_data = assignment.get('FlighAssignement') or {}
                if not flight_data or flight_data.get('CommercialFlightNumber') == "XXX":
                    continue
                flight_number = flight_data.get('CommercialFlightNumber', '')
                operational_number = flight_data.get('OperationalNumber', '')
                departure_date = flight_data.get('ScheduledDepartureDate', '')
                origin_airport = flight_data.get('OriginAirportIATACode', '').strip()
                airline = flight_data.get('Airline', 'AV')
                if not all([flight_number, operational_number, departure_date, origin_airport]):
                    continue
                key = f"{flight_number}_{operational_number}_{departure_date}"
                lazy_gate_flights.append({
                    'key': key,
                    'airline': airline,
                    'flight_number': flight_number,
                    'departure_date': departure_date,
                    'origin_airport': origin_airport,
                    'operational_number': operational_number,
                })

    return render_template('calendar_view.html',
        schedule_data=schedule_data,
        last_fetch=last_fetch_time,
        total_days=total_days,
        total_assignments=total_assignments,
        refresh_message=refresh_message,
        current_crew_id=current_crew_id,
        month_names=[month_name],
        month_calendars=month_calendars,
        current_date=get_utc_minus_5().strftime('%Y-%m-%d'),
        current_month_index=0,
        current_calendar_year=current_calendar_year,
        current_calendar_month=current_calendar_month,
        total_actual_hours=total_actual_hours,
        total_actual_minutes=total_actual_minutes_remainder,
        total_scheduled_hours=total_scheduled_hours,
        total_scheduled_minutes=total_scheduled_minutes_remainder,
        crew_names=crew_names,
        lazy_gate_flights=lazy_gate_flights
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
    paxlist_status = paxlist_client.get_token_status() if paxlist_client else None
    crew_status = client.get_token_status()

    return render_template('paxlist.html',
        current_crew_id=current_crew_id,
        crew_names=crew_names,
        token_status=paxlist_status,
        crew_token_status=crew_status,
        has_token=bool(paxlist_client and paxlist_client.access_token)
    )

@app.route('/api/paxlist/set_initial_tokens', methods=['POST'])
def set_paxlist_initial_tokens():
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')

        if access_token and refresh_token:
            success = paxlist_client.set_initial_tokens(access_token, refresh_token)
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Tokens set successfully with JWT validation. Will auto-refresh for 24 hours.'
                })
    except Exception as e:
        logger.error(f"Error setting Paxlist tokens: {e}")
    return jsonify({'success': False, 'message': 'Failed to set tokens'}), 400

@app.route('/api/paxlist/refresh_token', methods=['POST'])
def refresh_paxlist_token():
    try:
        success = paxlist_client.refresh_access_token()
        if success:
            return jsonify({'success': True, 'message': 'Token refreshed'})
    except Exception as e:
        logger.error(f"Error refreshing Paxlist token: {e}")
    return jsonify({'success': False, 'message': 'Failed to refresh token'}), 400

@app.route('/api/paxlist/token_status')
def paxlist_token_status():
    status = paxlist_client.get_token_status()
    return jsonify({'success': True, 'status': status})


@app.route('/api/crew/set_initial_tokens', methods=['POST'])
def set_crew_initial_tokens():
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token', '')
        expires_in = int(data.get('expires_in', 3600))
        refresh_expires_in = int(data.get('refresh_expires_in', 86399))

        if not access_token:
            return jsonify({'success': False, 'message': 'Missing access_token'}), 400

        if client.set_initial_tokens(access_token, refresh_token,
                                     expires_in=expires_in,
                                     refresh_expires_in=refresh_expires_in):
            return jsonify({'success': True, 'message': 'Crew tokens saved'})
    except Exception as e:
        logger.error(f"Error setting crew tokens: {e}")
    return jsonify({'success': False, 'message': 'Failed to set tokens'}), 400


@app.route('/api/crew/token_status')
def crew_token_status():
    return jsonify({'success': True, 'status': client.get_token_status()})


@app.route('/api/paxlist/search', methods=['POST'])
def paxlist_search():
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

@app.route('/api/search_flight', methods=['POST'])
def search_flight_api():
    try:
        data = request.get_json()
        airline = data.get('airline', 'AV')
        flight_number = data.get('flight_number', '')
        if isinstance(flight_number, str):
            flight_number = flight_number.lstrip('0') or flight_number
        departure_date = data.get('departure_date', '')[:10]
        origin_airport = data.get('origin_airport', '').upper()

        if not all([flight_number, departure_date, origin_airport]):
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        result = client.search_flight(airline, flight_number, departure_date, origin_airport)
        if not result:
            return jsonify({'success': False, 'error': 'Flight not found'}), 404

        return jsonify({'success': True, 'flight': result})
    except Exception as e:
        logger.error(f"Error in search_flight API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
            return jsonify({'success': True, 'flight_details': flight_details})
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch flight details'}), 500

    except Exception as e:
        logger.error(f"Error in flight details API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/today_flight_gates', methods=['POST'])
def get_today_flight_gates():
    try:
        data = request.get_json() or {}
        flights = data.get('flights', [])

        if not flights:
            return jsonify({'success': True, 'gates': {}})

        gates = {}

        for f in flights:
            try:
                airline = f.get('airline', 'AV')
                flight_number = f.get('flight_number')
                departure_date = f.get('departure_date')
                origin_airport = f.get('origin_airport')
                operational_number = f.get('operational_number')
                key = f.get('key')

                if not all([flight_number, departure_date, origin_airport, operational_number, key]):
                    gates[key or flight_number] = {'gate': '', 'terminal': '', 'mapped_gate': ''}
                    continue

                details = client.get_flight_details(
                    airline=airline,
                    flight_number=flight_number,
                    departure_date=departure_date,
                    origin_airport=origin_airport,
                    operational_number=operational_number
                )

                gate = ''
                terminal = ''

                if details:
                    fd = details.get('flight_details') if isinstance(details, dict) else None
                    if not fd and isinstance(details, dict):
                        fd = details

                    if isinstance(fd, dict):
                        raw_gate = fd.get('DepartureGate') or ''
                        raw_stand = fd.get('DepartureParkingStand') or ''
                        raw_terminal = fd.get('DepartureTerminal') or ''

                        gate = str(raw_gate).strip() or str(raw_stand).strip()
                        terminal = str(raw_terminal).strip()

                        if gate.lower() in ('null', 'none', 'undefined', 'nan'):
                            gate = ''
                        if terminal.lower() in ('null', 'none', 'undefined', 'nan'):
                            terminal = ''

                origin_upper = (origin_airport or '').strip().upper()
                mapped_gate = ''
                if origin_upper == 'BOG' and gate:
                    mapped_gate = BOG_GATE_MAPPING.get(gate, '')

                gates[key] = {'gate': gate, 'terminal': terminal, 'mapped_gate': mapped_gate}
                logger.info(f"🚪 Gate for {airline}{flight_number} ({key}): gate='{gate}' mapped='{mapped_gate}' terminal='{terminal}'")

            except Exception as inner_e:
                logger.error(f"Error fetching gate for one flight: {inner_e}")
                gates[f.get('key', '')] = {'gate': '', 'terminal': '', 'mapped_gate': ''}

        return jsonify({'success': True, 'gates': gates})

    except Exception as e:
        logger.error(f"Error in today_flight_gates API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

        crew_data = client.get_flight_crew_members(
            airline=airline,
            flight_number=flight_number,
            departure_date=departure_date,
            origin_airport=origin_airport,
            operational_number=operational_number
        )

        if crew_data:
            return jsonify({'success': True, 'crew_data': crew_data})
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch crew data'}), 500

    except Exception as e:
        logger.error(f"Error in flight crew API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/flight_details_from_assignment', methods=['POST'])
def get_flight_details_from_assignment_api():
    try:
        data = request.get_json()
        assignment = data.get('assignment')

        if not assignment:
            return jsonify({'success': False, 'error': 'No assignment data provided'}), 400

        flight_details = client.get_flight_details_from_assignment(assignment)

        if flight_details:
            return jsonify({'success': True, 'flight_details': flight_details})
        else:
            return jsonify({'success': False, 'error': 'Failed to fetch flight details from assignment'}), 500

    except Exception as e:
        logger.error(f"Error in flight details from assignment API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    global current_crew_id, previous_crew_id, schedule_data, last_fetch_time, current_calendar_year, current_calendar_month

    new_crew_id = request.args.get('crew_id', '').strip()

    if new_crew_id and new_crew_id != current_crew_id:
        previous_crew_id = current_crew_id
        current_crew_id = new_crew_id
        schedule_data = None
        last_fetch_time = None
        current_calendar_year = get_utc_minus_5().year
        current_calendar_month = get_utc_minus_5().month
        return {
            "success": True,
            "new_crew_id": current_crew_id,
            "previous_crew_id": previous_crew_id
        }

    return {"success": False, "error": "No crew ID provided or same as current"}

@app.route('/restore_previous_crew_id')
def restore_previous_crew_id():
    global current_crew_id, previous_crew_id, schedule_data, last_fetch_time, current_calendar_year, current_calendar_month

    target = previous_crew_id or DEFAULT_CREW_ID

    if target == current_crew_id:
        return {"success": False, "error": ""}

    current_crew_id, previous_crew_id = target, current_crew_id

    schedule_data = None
    last_fetch_time = None
    current_calendar_year = get_utc_minus_5().year
    current_calendar_month = get_utc_minus_5().month

    return {
        "success": True,
        "new_crew_id": current_crew_id,
        "previous_crew_id": previous_crew_id
    }

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

@app.route('/minimal')
def minimal_view():
    crew_id = "19043635"
    now = get_utc_minus_5()
    year = now.year
    month = now.month

    assignments_result = client.get_assignments_by_user(crew_id, year=year, month=month)

    schedule_data = None
    month_calendar = []
    month_name = get_month_name(year, month)

    if assignments_result:
        schedule_data = transform_assignments_to_calendar_data(
            assignments_result['assignments'],
            assignments_result['year'],
            assignments_result['month']
        )
        month_calendar = create_calendar_view_data(schedule_data[0])

    now_local = get_utc_minus_5()
    yesterday_str = (now_local - timedelta(days=1)).strftime('%Y-%m-%d')
    today_str = now_local.strftime('%Y-%m-%d')
    tomorrow_str = (now_local + timedelta(days=1)).strftime('%Y-%m-%d')
    target_dates = {yesterday_str, today_str, tomorrow_str}

    lazy_gate_flights = []

    if schedule_data and isinstance(schedule_data, list) and schedule_data:
        for day in schedule_data[0]:
            if not day:
                continue
            day_start = day.get('StartDate', '')
            day_date = day_start[:10] if day_start else ''
            if day_date not in target_dates:
                continue
            for assignment in day.get('AssignementList', []):
                flight_data = assignment.get('FlighAssignement') or {}
                if not flight_data or flight_data.get('CommercialFlightNumber') == "XXX":
                    continue
                flight_number = flight_data.get('CommercialFlightNumber', '')
                operational_number = flight_data.get('OperationalNumber', '')
                departure_date = flight_data.get('ScheduledDepartureDate', '')
                origin_airport = flight_data.get('OriginAirportIATACode', '').strip()
                airline = flight_data.get('Airline', 'AV')
                if not all([flight_number, operational_number, departure_date, origin_airport]):
                    continue
                key = f"{flight_number}_{operational_number}_{departure_date}"
                lazy_gate_flights.append({
                    'key': key,
                    'airline': airline,
                    'flight_number': flight_number,
                    'departure_date': departure_date,
                    'origin_airport': origin_airport,
                    'operational_number': operational_number,
                })

    return render_template('minimal.html',
        current_crew_id=crew_id,
        month_name=month_name,
        month_calendar=month_calendar,
        current_date=now.strftime('%Y-%m-%d'),
        lazy_gate_flights=lazy_gate_flights
    )
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
    logger.info("📊 Crew auth: manual token paste via /paxlist")
    logger.info("⏱️ Crew refresh daemon: random 55-85 min, stops on failure")
    app.run(host='0.0.0.0', port=8000, debug=False)