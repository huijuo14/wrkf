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
    try:
        response = session.get("https://adsha.re/adverts")
        if response.status_code != 200:
            print("Failed to get adverts page")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        import re
        
        # Find all campaign IDs by looking for any advert action links
        all_links = soup.find_all('a', href=True)
        possible_campaign_ids = set()
        for link in all_links:
            href = link.get('href', '')
            campaign_match = re.search(r'/adverts/(?:pause|delete|assign|bid)/(\d+)/', href)
            if campaign_match:
                possible_campaign_ids.add(campaign_match.group(1))
        
        # Find campaign completion data by looking for visitor counts and active status
        # Look for patterns like "X / Y visitors" in blocks that contain "ACTIVE"
        page_text = soup.get_text()
        
        # Find all visitor count patterns in the page
        visitor_patterns = re.findall(r'(\d+)\s*/\s*(\d+)\s+visitors', page_text)
        
        # More reliable approach: Find elements that contain "active" and visitor counts
        # Search for the specific pattern: "ACTIVE XX / YY visitors" 
        active_with_visitors_pattern = r'ACTIVE.*?(\d+)\s*/\s*(\d+)\s*visitors'
        active_matches = re.findall(active_with_visitors_pattern, page_text, re.IGNORECASE)
        
        campaigns_with_completion = []
        
        for match in active_matches:
            current_visitors = int(match[0])
            max_visitors = int(match[1])
            completion_percentage = (current_visitors / max_visitors) * 100 if max_visitors > 0 else 0
            
            if completion_percentage < 95:
                # Now find which campaign ID this relates to
                # Look for campaign ID in the same general area of the page
                # For this, we'll need to find the specific block containing this data
                
                # Search for the entire block that contains this information
                # We'll search for the pattern that includes "active" and the visitor count
                pattern_to_find = f"ACTIVE.*?{current_visitors}\\s*/\\s*{max_visitors}\\s*visitors"
                match_position = re.search(pattern_to_find, page_text, re.IGNORECASE)
                
                if match_position:
                    # Look for campaign ID in the nearby text (within 200 characters before)
                    start_pos = max(0, match_position.start() - 200)
                    context = page_text[start_pos:match_position.end() + 200]
                    
                    # Find campaign IDs in this context
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
        
        # If the above method doesn't work, try parsing by HTML structure
        if not campaigns_with_completion:
            # Look for all elements that might contain campaign information
            potential_blocks = soup.find_all(['div', 'tr', 'td', 'section'])
            
            for block in potential_blocks:
                block_text = block.get_text()
                
                # Check if this block contains both "active" and visitor pattern
                if 'active' in block_text.lower() and '/' in block_text and 'visitors' in block_text.lower():
                    # Extract visitor count from this block
                    visitor_match = re.search(r'(\d+)\s*/\s*(\d+)\s*visitors', block_text)
                    if visitor_match:
                        current_visitors = int(visitor_match.group(1))
                        max_visitors = int(visitor_match.group(2))
                        completion_percentage = (current_visitors / max_visitors) * 100 if max_visitors > 0 else 0
                        
                        if completion_percentage < 95:
                            # Find campaign ID in the same block
                            block_links = block.find_all('a', href=True)
                            campaign_id = None
                            
                            for link in block_links:
                                href = link.get('href', '')
                                id_match = re.search(r'/adverts/(?:pause|delete|assign|bid)/(\d+)/', href)
                                if id_match:
                                    campaign_id = id_match.group(1)
                                    break
                            
                            if campaign_id:
                                campaign_info = {
                                    'campaign_id': campaign_id,
                                    'completion_percentage': completion_percentage,
                                    'current_visitors': current_visitors,
                                    'max_visitors': max_visitors
                                }
                                campaigns_with_completion.append(campaign_info)
                                print(f"Found ACTIVE campaign {campaign_id} - {completion_percentage:.1f}% completed ({current_visitors}/{max_visitors})")
        
        # Process campaigns that are not 95%+ completed
        campaigns = []
        for campaign in campaigns_with_completion:
            campaign_id = campaign['campaign_id']
            
            # Find bid URL for this campaign
            bid_links = [link for link in all_links if f'/adverts/bid/{campaign_id}/' in link.get('href', '')]
            if bid_links:
                bid_url = bid_links[0].get('href')
            else:
                # Construct bid URL if not found directly
                bid_url = f"https://adsha.re/adverts/bid/{campaign_id}"
            
            campaign_info = {
                'campaign_id': campaign_id,
                'bid_url': bid_url,
                'bid_buffer': 2,  # Bid this amount above the top bid
                'completion_percentage': campaign['completion_percentage']
            }
            campaigns.append(campaign_info)

        if not campaigns:
            print("No campaigns under 95% completion found - bids are only checked for campaigns under 95% completion")
            print("Bid monitor will pause until campaigns are under 95% completion")
        
        return campaigns
    except Exception as e:
        print(f"Error getting campaigns: {e}")
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
    try:
        response = session.get(campaign_url)
        if response.status_code != 200:
            print(f"Failed to get bid info for campaign, status: {response.status_code}")
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
        print(f"Error getting bid info: {e}")
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
    
    # Check if we should monitor based on completion percentage
    should_check, reason = should_check_bids_due_to_completion(campaigns)
    print(f"Monitoring decision: {reason}")
    
    if not should_check:
        print("Skipping bid checks due to high completion percentage on all campaigns")
        return
    
    if not campaigns:
        print("No ACTIVE campaigns found - no bids to adjust")
        return
    
    # Process active campaigns under 95% completion
    for campaign in campaigns:
        print(f"Checking active campaign {campaign['campaign_id']} ({campaign['completion_percentage']:.1f}% completed)")
        
        current_bid, top_bid = get_current_bid_info(session, campaign['bid_url'])
        if current_bid is not None and top_bid is not None:
            print(f"  Current bid: {current_bid}, Top bid: {top_bid}")
            
            # Calculate desired bid (top bid + buffer)
            desired_bid = top_bid + campaign['bid_buffer']
            
            if current_bid < desired_bid:
                print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                if adjust_bid(session, campaign['bid_url'], desired_bid):
                    print(f"  Bid adjusted to {desired_bid}")
                    # Save cookies after successful update
                    save_cookies(session.cookies)
                else:
                    print("  Failed to adjust bid")
            else:
                print(f"  Current bid is sufficient (≥ {desired_bid})")
        else:
            print(f"  Failed to get bid info for campaign {campaign['campaign_id']}, session may need renewal...")
            # Try to re-login
            loaded_cookies = load_cookies()
            if loaded_cookies:
                session.cookies = loaded_cookies
                print("Reloaded cookies")
            else:
                if dynamic_login(session):
                    save_cookies(session.cookies)
                else:
                    print("Re-login failed")

def monitor_and_adjust_bids():
    """Main function to monitor and adjust bids - continuous version"""
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
    
    while True:
        print(f"\n--- Checking bids at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        # Dynamically get all campaigns each time
        campaigns = get_all_campaigns_with_bidding(session)
        
        # Check if we should monitor based on completion percentage
        should_check, reason = should_check_bids_due_to_completion(campaigns)
        print(f"Monitoring decision: {reason}")
        
        if not should_check:
            print("Pausing bid checks due to high completion percentage on all campaigns...")
            print("Will check again in 60 minutes to see if campaigns need monitoring")
            time.sleep(3600)  # Wait 60 minutes when all campaigns are highly completed
            continue  # Continue to check again
        
        if not campaigns:
            print("No ACTIVE campaigns found - pausing bid monitoring...")
            print("Will check again in 30 minutes to see if campaigns became active")
            time.sleep(1800)  # Wait 30 minutes instead of 10 when no active campaigns
            continue  # Continue to check again
        
        # Process active campaigns under 95% completion
        for campaign in campaigns:
            print(f"Checking active campaign {campaign['campaign_id']} ({campaign['completion_percentage']:.1f}% completed)")
            
            current_bid, top_bid = get_current_bid_info(session, campaign['bid_url'])
            if current_bid is not None and top_bid is not None:
                print(f"  Current bid: {current_bid}, Top bid: {top_bid}")
                
                # Calculate desired bid (top bid + buffer)
                desired_bid = top_bid + campaign['bid_buffer']
                
                if current_bid < desired_bid:
                    print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                    if adjust_bid(session, campaign['bid_url'], desired_bid):
                        print(f"  Bid adjusted to {desired_bid}")
                        # Save cookies after successful update
                        save_cookies(session.cookies)
                    else:
                        print("  Failed to adjust bid, will try again in next cycle")
                else:
                    print(f"  Current bid is sufficient (≥ {desired_bid})")
            else:
                print(f"  Failed to get bid info for campaign {campaign['campaign_id']}, session may need renewal...")
                # Try to re-login
                loaded_cookies = load_cookies()
                if loaded_cookies:
                    session.cookies = loaded_cookies
                    print("Reloaded cookies")
                else:
                    if dynamic_login(session):
                        save_cookies(session.cookies)
                    else:
                        print("Re-login failed")
        
        # Determine sleep time based on campaign completion
        if campaigns:
            # If we have campaigns to monitor, check every 10 minutes
            print(f"\nWaiting 10 minutes until next check...")
            time.sleep(600)  # Wait 10 minutes (600 seconds)
        else:
            # If no campaigns to monitor, wait longer
            print(f"\nWaiting 30 minutes until next check...")
            time.sleep(1800)  # Wait 30 minutes (1800 seconds)

if __name__ == "__main__":
    # For GitHub Actions, run bid monitor once
    run_bid_monitor_once()
    
    # For continuous running on a server:
    # monitor_and_adjust_bids()
