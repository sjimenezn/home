def get_assignments_by_user(self, crew_id=None, year=None, month=None):
    """Get assignments for specific month (for calendar view)"""
    try:
        target_crew_id = crew_id or current_crew_id
        now = datetime.now(UTC_MINUS_5)
        year = year or now.year
        month = month or now.month
        
        # Calculate month range in UTC-5
        first_day = datetime(year, month, 1, tzinfo=UTC_MINUS_5)
        last_day = (datetime(year + 1, 1, 1, tzinfo=UTC_MINUS_5) if month == 12 
                   else datetime(year, month + 1, 1, tzinfo=UTC_MINUS_5)) - timedelta(days=1)
        days_in_month = (last_day - first_day).days + 1
        
        logger.info(f"📅 Requesting calendar data for {year}-{month:02d} (Days: {days_in_month}, First: {first_day.date()}, Last: {last_day.date()})")
        
        # FIX: Request one extra day to ensure we get the last day of the month
        start_date = first_day
        change_days = days_in_month + 1  # Request one extra day
        
        logger.info(f"📅 Requesting {change_days} days starting from {start_date.date()}")
        
        if not self._login():
            return None
        
        url = f"{self.base_url}/Assignements/GetAssignementsByUser"
        params = {
            "date": start_date.strftime('%Y-%m-%dT00:00:00Z'),
            "changeDays": change_days,
            "crewMemberUniqueId": target_crew_id,
            "holding": "AV",
            "timeZoneOffset": "-300"
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
            
            # ENHANCED DEBUG: Check what dates we actually received
            if data:
                dates_received = []
                for assignment in data:
                    if