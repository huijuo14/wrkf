#!/usr/bin/env python3
"""
Dynamic Bid Monitor for AdShare
Automatically monitors and adjusts bids to stay competitive
Only monitors campaigns under 95% completion (intelligent monitoring)
"""

import requests
from bs4 import BeautifulSoup
import time
import pickle
import os
import random
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

def get_all_campaigns_with_bidding(session):
    """Dynamically get all campaigns that have bid functionality and are ACTIVE (not completed)"""
    for attempt in range(3): # Retry up to 3 times
        try:
            response = session.get("https://adsha.re/adverts")
            response.raise_for_status() # Raise an exception for bad status codes
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            import re
            
            # Find all campaign IDs by looking for any advert action links
            all_links = soup.find_all('a', href=True)
            
            page_text = soup.get_text()
            
            active_with_visitors_pattern = r'ACTIVE.*?(\d+)\s*/\s*(\d+)\s*visitors'
            active_matches = re.findall(active_with_visitors_pattern, page_text, re.IGNORECASE)
            
            campaigns_with_completion = []
            
            for match in active_matches:
                current_visitors = int(match[0])
                max_visitors = int(match[1])
                completion_percentage = (current_visitors / max_visitors) * 100 if max_visitors > 0 else 0
                
                if completion_percentage < 95:
                    pattern_to_find = f"ACTIVE.*?{current_visitors}\s*/\s*{max_visitors}\s*visitors"
                    match_position = re.search(pattern_to_find, page_text, re.IGNORECASE)
                    
                    if match_position:
                        start_pos = max(0, match_position.start() - 200)
                        context = page_text[start_pos:match_position.end() + 200]
                        
                        local_campaign_match = re.search(r'/adverts/(?:pause|delete|assign|bid)/(\d+)/', context)
                        if local_campaign_match:
                            campaign_id = local_campaign_match.group(1)
                            
                            campaign_info = {
                                'campaign_id': campaign_id,
                                'completion_percentage': completion_percentage,
                                'current_visitors': current_visitors,
                                'max_visitors': max_visitors
                            }
                            campaigns_with_completion.append(campaign_info)
                            print(f"Found ACTIVE campaign {campaign_id} - {completion_percentage:.1f}% completed ({current_visitors}/{max_visitors})")

            campaigns = []
            for campaign in campaigns_with_completion:
                campaign_id = campaign['campaign_id']
                
                bid_links = [link for link in all_links if f'/adverts/bid/{campaign_id}/' in link.get('href', '')]
                if bid_links:
                    bid_url = bid_links[0].get('href')
                else:
                    pause_links = [link for link in all_links if f'/adverts/pause/{campaign_id}/' in link.get('href', '')]
                    if pause_links:
                        pause_url = pause_links[0].get('href')
                        bid_url = re.sub(r'/pause/', '/bid/', pause_url)
                    else:
                        bid_url = f"https://adsha.re/adverts/bid/{campaign_id}"
                
                campaign_info = {
                    'campaign_id': campaign_id,
                    'bid_url': bid_url,
                    'bid_buffer': 2,
                    'completion_percentage': campaign['completion_percentage']
                }
                campaigns.append(campaign_info)

            if not campaigns:
                print("No campaigns under 95% completion found.")
            
            return campaigns

        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt + 1} failed: Connection error - {e}")
            if attempt < 2:
                time.sleep(5) # Wait 5 seconds before retrying
            else:
                print("All retry attempts failed.")
                return []
        except Exception as e:
            print(f"An unexpected error occurred in get_all_campaigns_with_bidding: {e}")
            return []
    return []


def should_check_bids_due_to_completion(campaigns):
    """Determine if we should check bids based on campaign completion percentages"""
    if not campaigns:
        return False, "No active campaigns to monitor"

    # Check if any campaign is under 90% completion (aggressive monitoring)
    under_90_percent = [c for c in campaigns if c['completion_percentage'] < 90]
    if under_90_percent:
        return True, "At least one campaign is under 90% completion - aggressive monitoring"

    # Check if any campaign is under 95% completion (normal monitoring)
    under_95_percent = [c for c in campaigns if c['completion_percentage'] < 95]
    if under_95_percent:
        return True, "At least one campaign is under 95% completion - normal monitoring"

    # All campaigns are 95%+ completed, reduce check frequency
    return False, "All campaigns are 95%+ completed - reduce monitoring frequency"

def get_current_bid_info(session, campaign_url):
    """Get current bid and top bid information for a campaign"""
    for attempt in range(3):
        try:
            response = session.get(campaign_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the current bid from the input field
            bid_input = soup.find('input', {'name': 'bid', 'id': 'bid'})
            current_bid = int(bid_input.get('value')) if bid_input else 0
            
            # Find the 'top bid' text reliably
            top_bid = 0
            import re

            # Find all label divs and check for the one containing "Bid"
            for label_div in soup.find_all('div', class_='label'):
                if 'Bid' in label_div.get_text():
                    top_bid_span = label_div.find('span')
                    if top_bid_span:
                        top_bid_match = re.search(r'top bid is (\d+)', top_bid_span.text, re.IGNORECASE)
                        if top_bid_match:
                            top_bid = int(top_bid_match.group(1))
                            break # Exit loop once found

            print(f"DEBUG - Current bid: {current_bid}, Parsed top bid: {top_bid}")
            
            return current_bid, top_bid
        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt + 1} failed getting bid info: {e}")
            if attempt < 2:
                time.sleep(5)
        except Exception as e:
            print(f"Error getting bid info: {e}")
            return None, None
    return None, None


def adjust_bid(session, bid_url, new_bid):
    """Adjust bid to a new value"""
    try:
        bid_data = {
            'bid': str(new_bid),
            'vis': '0'  # Hidden field that's required
        }
        
        response = session.post(bid_url, data=bid_data)
        if response.status_code == 200:
            print(f"Successfully adjusted bid to {new_bid}")
            return True
        else:
            print(f"Failed to adjust bid: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error adjusting bid: {e}")
        return False

def run_bid_monitor_once():
    """Run bid monitor once - optimized for GitHub Actions"""
    print(f"Starting bid monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create session
    session = requests.Session()
    
    # Try to load existing cookies
    loaded_cookies = load_cookies()
    if loaded_cookies:
        session.cookies = loaded_cookies
        print("Loaded existing cookies")
    else:
        print("No existing cookies found")
        return
    
    print(f"\n--- Checking bids ---")
    
    # Dynamically get all campaigns
    campaigns = get_all_campaigns_with_bidding(session)
    
    should_check, reason = should_check_bids_due_to_completion(campaigns)
    print(f"Monitoring decision: {reason}")
    
    if not should_check:
        print("Skipping bid checks.")
        return
    
    for campaign in campaigns:
        print(f"Checking active campaign {campaign['campaign_id']} ({campaign['completion_percentage']:.1f}% completed)")
        
        current_bid, top_bid = get_current_bid_info(session, campaign['bid_url'])
        if current_bid is not None and top_bid is not None:
            print(f"  Current bid: {current_bid}, Top bid: {top_bid}")
            
            desired_bid = top_bid + campaign['bid_buffer']
            
            if current_bid < desired_bid:
                print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                if adjust_bid(session, campaign['bid_url'], desired_bid):
                    print(f"  Bid adjusted to {desired_bid}")
                    save_cookies(session.cookies)
                else:
                    print("  Failed to adjust bid")
            else:
                print(f"  Current bid is sufficient (≥ {desired_bid})")
        else:
            print(f"  Failed to get bid info for campaign {campaign['campaign_id']}, trying to re-login...")
            if dynamic_login(session):
                save_cookies(session.cookies)
            else:
                print("Re-login failed")

def monitor_and_adjust_bids():
    """Main function to monitor and adjust bids - continuous version"""
    print(f"Starting bid monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    session = requests.Session()
    
    loaded_cookies = load_cookies()
    if loaded_cookies:
        session.cookies = loaded_cookies
        print("Loaded existing cookies")
    else:
        print("No existing cookies found")
        return
    
    while True:
        print(f"\n--- Checking bids at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        campaigns = get_all_campaigns_with_bidding(session)
        
        should_check, reason = should_check_bids_due_to_completion(campaigns)
        print(f"Monitoring decision: {reason}")
        
        if not should_check:
            print("Pausing bid checks for 60 minutes.")
            time.sleep(3600)
            continue
        
        for campaign in campaigns:
            print(f"Checking active campaign {campaign['campaign_id']} ({campaign['completion_percentage']:.1f}% completed)")
            
            current_bid, top_bid = get_current_bid_info(session, campaign['bid_url'])
            if current_bid is not None and top_bid is not None:
                print(f"  Current bid: {current_bid}, Top bid: {top_bid}")
                
                desired_bid = top_bid + campaign['bid_buffer']
                
                if current_bid < desired_bid:
                    print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                    if adjust_bid(session, campaign['bid_url'], desired_bid):
                        print(f"  Bid adjusted to {desired_bid}")
                        save_cookies(session.cookies)
                    else:
                        print("  Failed to adjust bid")
                else:
                    print(f"  Current bid is sufficient (≥ {desired_bid})")
            else:
                print(f"  Failed to get bid info for campaign {campaign['campaign_id']}, trying to re-login...")
                if dynamic_login(session):
                    save_cookies(session.cookies)
                else:
                    print("Re-login failed")
        
        if campaigns:
            print(f"\nWaiting 10 minutes...")
            time.sleep(600)
        else:
            print(f"\nNo active campaigns under 95%. Waiting 30 minutes...")
            time.sleep(1800)

if __name__ == "__main__":
    run_bid_monitor_once()
