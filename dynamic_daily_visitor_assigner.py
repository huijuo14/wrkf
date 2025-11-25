#!/usr/bin/env python3
"""
Dynamic Daily Visitor Assignment for AdShare
Automatically assigns visitors to completed campaigns daily at 5:45 PM IST
"""

import requests
from bs4 import BeautifulSoup
import time
import pickle
import os
from datetime import datetime
import pytz

def load_cookies():
    """Load cookies from file if it exists"""
    if os.path.exists('session_cookies.pkl'):
        try:
            with open('session_cookies.pkl', 'rb') as f:
                jar = pickle.load(f)
                return jar
        except Exception as e:
            print(f"Error loading cookies: {e}")
    return None

def save_cookies(jar):
    """Save cookies to file"""
    try:
        with open('session_cookies.pkl', 'wb') as f:
            pickle.dump(jar, f)
        print("Cookies saved to session_cookies.pkl")
    except Exception as e:
        print(f"Error saving cookies: {e}")

def dynamic_login(session):
    """Perform login with dynamic form field detection"""
    # Fetch login page to get dynamic elements
    response = session.get("https://adsha.re/login")
    if response.status_code != 200:
        print("Failed to fetch login page")
        return False
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the login form
    login_form = soup.find('form')
    if not login_form:
        print("Could not find login form")
        return False
    
    # Get the actual form action URL
    form_action = login_form.get('action')
    if form_action.startswith('/'):
        login_url = "https://adsha.re" + form_action
    elif not form_action.startswith('http'):
        login_url = "https://adsha.re/" + form_action
    else:
        login_url = form_action
    
    # Find email and password fields by analyzing their properties
    email_field = None
    password_field = None
    
    all_inputs = login_form.find_all('input')
    for inp in all_inputs:
        inp_type = inp.get('type', 'text')
        inp_value = inp.get('value', '')
        inp_name = inp.get('name', '')
        
        # Look for email field
        if inp_type == 'text' or inp_type == 'email':
            inp_value_lower = inp_value.lower()
            if 'email' in inp_value_lower or 'mail' in inp_value_lower or 'address' in inp_value_lower or 'email' in inp_name.lower():
                email_field = inp
        # Look for password field (has 'Password' as the value)
        elif inp_value == 'Password':
            password_field = inp

    if not email_field or not password_field:
        print("Could not find email or password fields")
        return False
    
    # Prepare login data with dynamic field names
    login_data = {
        email_field.get('name'): "jiocloud90@gmail.com",
        password_field.get('name'): "@Sd2007123",
    }
    
    # Send login request
    login_response = session.post(login_url, data=login_data)
    
    if login_response.status_code == 200:
        print("Re-login successful")
        save_cookies(session.cookies)
        return True
    else:
        print(f"Re-login failed with status {login_response.status_code}")
        return False

def get_completed_campaigns_with_assign_links(session):
    """Get all completed campaigns and their assign links from the adverts page"""
    try:
        response = session.get("https://adsha.re/adverts")
        if response.status_code != 200:
            print("Failed to get adverts page")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all campaign elements that mention "COMPLETE" 
        import re
        campaign_elements = soup.find_all(string=re.compile(r'complete', re.IGNORECASE))
        
        completed_campaigns = []
        for element in campaign_elements:
            parent = element.find_parent()
            if parent:
                # Look for assign links in this campaign block
                assign_links = parent.find_all('a', href=lambda href: href and 'assign' in href.lower() if href else False)
                if assign_links:
                    assign_link = assign_links[0]
                    assign_url = assign_link.get('href')
                    
                    # Extract campaign info from the URL
                    campaign_match = re.search(r'/adverts/assign/(\d+)/([a-fA-F0-9]+)/', assign_url)
                    if campaign_match:
                        campaign_info = {
                            'campaign_id': campaign_match.group(1),
                            'assign_url': assign_url,
                            'status': 'COMPLETE',
                            'element_text': element.get_text()
                        }
                        completed_campaigns.append(campaign_info)
                        print(f"Found COMPLETE campaign {campaign_info['campaign_id']}: {assign_url}")
        
        return completed_campaigns
    except Exception as e:
        print(f"Error getting completed campaigns: {e}")
        return []

def assign_visitors_to_campaign(session, assign_url, num_visitors=50):
    """Assign visitors to a specific campaign with 12-hour revisit option"""
    try:
        # First, get the assignment page to extract form data
        response = session.get(assign_url)
        if response.status_code != 200:
            print(f"Failed to access assign page: {response.status_code}")
            return False
        
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        
        if not form:
            print("No form found on assign page")
            return False
        
        action = form.get('action')
        
        # Prepare data to assign visitors with 'Faster' speed (12-hour revisit)
        assign_data = {
            'vis': str(num_visitors),  # Number of visitors to assign
            'bid': '0',                # Keep bid at 0 (bid monitor handles bidding)
            'spe': '2',                # 'Faster' option (revisit in 12 hours)
            'txt': '0',                # Hidden field
            'url': '0',                # Hidden field
            'aid': assign_url.split('/')[4]  # Extract campaign ID from URL
        }
        
        print(f"Assigning {num_visitors} visitors with 12-hour revisit to campaign...")
        
        # Submit the form
        submit_response = session.post(action, data=assign_data)
        
        if submit_response.status_code == 200:
            print(f"Successfully assigned {num_visitors} visitors!")
            
            # Check response to confirm assignment
            result_soup = BeautifulSoup(submit_response.text, 'html.parser')
            page_text = result_soup.get_text()
            
            if 'success' in page_text.lower() or 'assigned' in page_text.lower() or 'updated' in page_text.lower():
                print("Assignment confirmed in response page.")
                return True
            else:
                print("Assignment may have been successful, but no confirmation text found.")
                return True
        else:
            print(f"Error submitting assignment: Status {submit_response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error assigning visitors: {e}")
        return False

def daily_visitor_assignment():
    """Main function that runs the daily visitor assignment"""
    print(f"Starting daily visitor assignment check at {datetime.now()}")
    
    # Create session
    session = requests.Session()
    
    # Try to load existing cookies
    loaded_cookies = load_cookies()
    if loaded_cookies:
        session.cookies = loaded_cookies
        print("Loaded existing cookies")
    else:
        print("No existing cookies, cannot proceed")
        return
    
    # Get all completed campaigns with assign links
    print("Checking for COMPLETE campaigns...")
    campaigns = get_completed_campaigns_with_assign_links(session)
    
    if not campaigns:
        print("No COMPLETE campaigns found to assign visitors to")
        return
    
    # Get visitor credits available
    response = session.get("https://adsha.re/adverts")
    soup = BeautifulSoup(response.text, 'html.parser')
    page_text = soup.get_text()
    
    # Look for available visitor count (format like "Visitors (xxxx available)")
    import re
    visitor_match = re.search(r'Visitors \(([\d,]+) available\)', page_text)
    available_visitors = 0
    if visitor_match:
        available_visitors = int(visitor_match.group(1).replace(',', ''))
        print(f"Available visitors: {available_visitors}")
    
    if available_visitors < 50:
        print(f"Not enough visitors available (need 50, have {available_visitors})")
        return
    
    # Assign visitors to the first COMPLETE campaign
    for campaign in campaigns:
        print(f"Attempting to assign visitors to campaign {campaign['campaign_id']}")
        
        success = assign_visitors_to_campaign(session, campaign['assign_url'], 50)
        if success:
            print(f"Successfully assigned 50 visitors to campaign {campaign['campaign_id']}")
            save_cookies(session.cookies)  # Save cookies after successful action
            break  # Only assign to first eligible campaign
        else:
            print(f"Failed to assign visitors to campaign {campaign['campaign_id']}")
    
    print("Daily visitor assignment check completed.")

import random

def run_daily_at_random_time():
    """Run the daily assignment at a random time between 5:30-6:00 PM when called"""
    ist = pytz.timezone('Asia/Kolkata')

    # Generate a random delay between 30 and 60 minutes past 5 PM
    # Since GitHub Actions runs at 12:15 UTC (5:45 PM IST), we'll add/remove up to 15 minutes
    random_offset = random.randint(-15, 15)  # Random offset in minutes
    target_time = 15 + random_offset  # 15 minutes (5:45 PM) + random offset

    print(f"Scheduled time would be 5:{target_time + 45:02d} PM IST with random offset of {random_offset} minutes")
    print(f"However, since we're running from GitHub Actions, executing immediately at {datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S IST')}")

    # Execute the assignment immediately since we're triggered by GitHub Actions
    daily_visitor_assignment()

def run_scheduler():
    """Run the scheduler continuously, checking daily at a random time between 5:30-6:00 PM IST"""
    ist = pytz.timezone('Asia/Kolkata')

    # For continuous running (not recommended on GitHub Actions)
    # This would be used if running manually on a server
    print("Continuous scheduler mode - checking for daily execution...")

    # Generate a random delay (0-1800 seconds = 0-30 minutes) to add some randomness
    initial_delay = random.randint(0, 1800)
    print(f"Initial random delay: {initial_delay} seconds")
    time.sleep(initial_delay)

    while True:
        # Execute the daily assignment
        daily_visitor_assignment()
        print("Daily assignment completed, waiting 24 hours until next run...")

        # Wait 24 hours
        time.sleep(24 * 3600)

if __name__ == "__main__":
    # For GitHub Actions, run the daily assignment immediately with random behavior
    run_daily_at_random_time()

    # For continuous running on a server (not recommended for GitHub Actions):
    # run_scheduler()