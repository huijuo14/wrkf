#!/usr/bin/env python3
"""
Bid Monitor Script for AdShare
Automatically monitors and adjusts bids to stay competitive
"""

import requests
from bs4 import BeautifulSoup
import time
import pickle
import os
from datetime import datetime

# Configuration
BASE_URL = "https://adsha.re"
USERNAME = "jiocloud90@gmail.com"
PASSWORD = "@Sd2007123"
COOKIE_FILE = "session_cookies.pkl"

def get_all_campaigns(session):
    """Dynamically get all campaigns from the adverts page"""
    try:
        response = session.get(f'{BASE_URL}/adverts')
        if response.status_code != 200:
            print("Failed to get adverts page")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all campaign-related links to extract campaign IDs
        all_links = soup.find_all('a', href=True)

        # Also look for non-link elements that might contain campaign data
        all_elements = soup.find_all(['a', 'td', 'tr', 'div'], string=lambda text: text and 'My Advert' in text)
        campaign_ids = set()  # Use set to avoid duplicates

        # Use regex to find campaign IDs from various campaign action URLs
        import re

        # Find campaign IDs from action links
        for link in all_links:
            href = link.get('href', '')

            # Look for various campaign-related URL patterns that contain campaign IDs
            # Examples: /adverts/pause/{id}/{token}, /adverts/delete/{id}/{token}, /adverts/assign/{id}/{token}
            # All of these contain a campaign ID after the action type
            patterns = [
                r'/adverts/pause/(\d+)/',
                r'/adverts/delete/(\d+)/',
                r'/adverts/assign/(\d+)/',
                r'/adverts/bid/(\d+)/',
                r'/adverts/speed/(\d+)/'
            ]

            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    campaign_id = match.group(1)
                    if campaign_id not in campaign_ids:
                        campaign_ids.add(campaign_id)
                        print(f"Found campaign {campaign_id} from action link")

        # Look for campaigns that might be identified by name but don't have visible bid links
        # (These may show bid links only when not at the top bid)
        for element in all_elements:
            parent = element.find_parent()
            # Look for any numeric IDs associated with this element
            if parent:
                parent_text = str(parent)
                # Look for patterns that might contain campaign IDs near the "My Advert" text
                campaign_matches = re.findall(r'/adverts/(?:pause|delete|assign|bid)/(\d+)/', parent_text)
                for match in campaign_matches:
                    if match not in campaign_ids:
                        campaign_ids.add(match)
                        print(f"Found campaign {match} from 'My Advert' association")

        # Also check if we can extract campaign IDs by looking for numbers near campaign-like elements
        # This will capture campaigns even if they don't have visible action links
        page_text = soup.get_text()
        # Look for patterns like URLs containing the campaign IDs
        possible_ids = re.findall(r'/adverts/(?:pause|delete|assign|bid|create)/(\d+)', page_text)
        for campaign_id in possible_ids:
            if campaign_id not in campaign_ids:
                campaign_ids.add(campaign_id)
                print(f"Found campaign {campaign_id} from page text")

        # Also check our known campaign that has bid functionality
        # This ensures we don't miss campaigns that may not appear on the main page
        # but still need bid monitoring
        known_campaigns_with_bidding = ['2641']  # Add others if discovered later
        for known_campaign in known_campaigns_with_bidding:
            if known_campaign not in campaign_ids:
                campaign_ids.add(known_campaign)
                print(f"Added known campaign with bidding: {known_campaign}")

        # Now attempt to find bid URLs for each campaign ID by testing if bid pages exist
        final_campaigns = []
        for campaign_id in campaign_ids:
            bid_url = find_bid_url_for_campaign_id(session, campaign_id)
            if bid_url:
                campaign_info = {
                    'campaign_id': campaign_id,
                    'bid_url': bid_url,
                    'bid_buffer': 2  # Bid this amount above the top bid
                }
                final_campaigns.append(campaign_info)
                print(f"  -> Bid URL found for campaign {campaign_id}: {bid_url}")
            else:
                print(f"  -> No bid functionality found for campaign {campaign_id}")

        return final_campaigns
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        return []

def find_bid_url_for_campaign_id(session, campaign_id):
    """Find bid URL for a specific campaign by checking various possible URLs"""
    import re

    # The bid URL format is: /adverts/bid/{campaign_id}/{long_hex_token}
    # This time we'll try to access the bid page directly to see if it exists
    # We'll test with the known successful bid URL pattern

    # First, try to find bid links on the main page for this specific campaign ID
    response = session.get(f'{BASE_URL}/adverts')
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Look for bid links that contain this specific campaign ID
    bid_links = soup.find_all('a', href=lambda href: href and f'/adverts/bid/{campaign_id}/' in href)

    if bid_links:
        # Return the first bid link we found
        return bid_links[0].get('href')

    # If not found on main page, we can try to check if this specific campaign has bid functionality
    # by attempting to access different variations of bid URLs
    # Since we don't know the token, we'll need another approach
    # For now, let's assume if it's a valid campaign it might have bidding

    # We'll return a special marker that will trigger a more detailed search
    # For the most common case, like campaign 2641 that we know has bidding functionality
    known_bid_tokens = {
        '2641': '9c11d5c78ca339eee3c02533cae3aaabd292f7711a35ed4575a5e9eacb1100396ec99c4f8c0cd807ac1acac44ab85e847cebbae08b90a3575d3aca99128ad1ec'
    }

    if campaign_id in known_bid_tokens:
        return f"{BASE_URL}/adverts/bid/{campaign_id}/{known_bid_tokens[campaign_id]}"

    # For other campaigns, if we can't find the specific token, return None
    return None

def load_cookies():
    """Load cookies from file if it exists"""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'rb') as f:
                jar = pickle.load(f)
                return jar
        except Exception as e:
            print(f"Error loading cookies: {e}")
    return None

def save_cookies(jar):
    """Save cookies to file"""
    try:
        with open(COOKIE_FILE, 'wb') as f:
            pickle.dump(jar, f)
        print(f"Cookies saved to {COOKIE_FILE}")
    except Exception as e:
        print(f"Error saving cookies: {e}")

def get_login_form_details(session):
    """Get dynamic login form details"""
    try:
        response = session.get(f'{BASE_URL}/login')
        soup = BeautifulSoup(response.text, 'html.parser')
        login_form = soup.find('form')
        
        if not login_form:
            print("Could not find login form")
            return None, None, None
        
        # Get the actual form action URL
        form_action = login_form.get('action')
        if form_action.startswith('/'):
            login_url = BASE_URL + form_action
        elif not form_action.startswith('http'):
            login_url = BASE_URL + '/' + form_action
        else:
            login_url = form_action
        
        # Find email and password fields
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

        return login_url, email_field, password_field
    except Exception as e:
        print(f"Error getting login form details: {e}")
        return None, None, None

def login(session):
    """Perform login with dynamic form fields"""
    login_url, email_field, password_field = get_login_form_details(session)
    
    if not login_url or not email_field or not password_field:
        print("Failed to get login form details")
        return False
    
    # Prepare login data with correct field names
    login_data = {
        email_field.get('name'): USERNAME,
        password_field.get('name'): PASSWORD,
    }
    
    try:
        response = session.post(login_url, data=login_data)
        if response.status_code == 200:
            print("Login successful")
            return True
        else:
            print(f"Login failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error during login: {e}")
        return False

def get_current_bid_info(session, campaign):
    """Get current bid and top bid information for a campaign"""
    try:
        response = session.get(campaign['bid_url'])
        if response.status_code != 200:
            print(f"Failed to get bid info for campaign {campaign['campaign_id']}")
            return None, None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the bid input field (current bid)
        bid_input = soup.find('input', {'name': 'bid', 'id': 'bid'})
        current_bid = int(bid_input.get('value')) if bid_input else 0
        
        # Look for top bid information in the page text
        page_text = soup.get_text()
        top_bid = current_bid  # Default to current bid if not found
        
        # Try to find the top bid in the page (common format: "(top bid is X credits)")
        import re
        top_bid_match = re.search(r'top bid is (\d+) credits', page_text, re.IGNORECASE)
        if top_bid_match:
            top_bid = int(top_bid_match.group(1))
        
        return current_bid, top_bid
    except Exception as e:
        print(f"Error getting bid info for campaign {campaign['campaign_id']}: {e}")
        return None, None

def adjust_bid(session, campaign, new_bid):
    """Adjust bid to a new value"""
    try:
        bid_data = {
            'bid': str(new_bid),
            'vis': '0'  # Hidden field that's required
        }
        
        response = session.post(campaign['bid_url'], data=bid_data)
        if response.status_code == 200:
            print(f"Successfully adjusted bid for campaign {campaign['campaign_id']} to {new_bid}")
            return True
        else:
            print(f"Failed to adjust bid for campaign {campaign['campaign_id']}: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error adjusting bid for campaign {campaign['campaign_id']}: {e}")
        return False

def monitor_and_adjust_bids():
    """Main function to monitor and adjust bids"""
    print(f"Starting bid monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create session
    session = requests.Session()

    # Try to load existing cookies
    loaded_cookies = load_cookies()
    if loaded_cookies:
        session.cookies = loaded_cookies
        print("Loaded existing cookies")
    else:
        print("No existing cookies, performing fresh login")
        if not login(session):
            print("Login failed, exiting")
            return
        save_cookies(session.cookies)

    while True:
        print(f"\n--- Checking bids at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

        # Dynamically get all campaigns each time in case they change
        campaigns = get_all_campaigns(session)

        if not campaigns:
            print("No campaigns found, will try again in next cycle...")
        else:
            for campaign in campaigns:
                print(f"Checking campaign {campaign['campaign_id']}")

                current_bid, top_bid = get_current_bid_info(session, campaign)
                if current_bid is not None and top_bid is not None:
                    print(f"  Current bid: {current_bid}, Top bid: {top_bid}")

                    # Calculate desired bid (top bid + buffer)
                    desired_bid = top_bid + campaign['bid_buffer']

                    if current_bid < desired_bid:
                        print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                        if adjust_bid(session, campaign, desired_bid):
                            print(f"  Bid adjusted to {desired_bid}")
                            # Save cookies after successful update
                            save_cookies(session.cookies)
                        else:
                            print("  Failed to adjust bid, will try again in next cycle")
                    else:
                        print(f"  Current bid is sufficient (≥ {desired_bid})")
                else:
                    print(f"  Failed to get bid info, attempting fresh login...")
                    # Reload cookies or re-login
                    loaded_cookies = load_cookies()
                    if loaded_cookies:
                        session.cookies = loaded_cookies
                        print("Reloaded cookies")
                    else:
                        if login(session):
                            save_cookies(session.cookies)
                        else:
                            print("Re-login failed")

        print(f"\nWaiting 10 minutes until next check...")
        time.sleep(600)  # Wait 10 minutes (600 seconds)

if __name__ == "__main__":
    monitor_and_adjust_bids()
