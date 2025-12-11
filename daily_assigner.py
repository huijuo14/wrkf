#!/usr/bin/env python3
"""
AdShare Daily Visitor Assigner - Fixed URL Issues
Now uses adshare_login module for session management
"""
import os
import re
import time
import requests
import pickle
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# Import the login module
import adshare_login

# Configuration
BASE_URL = "https://adsha.re"
USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")
COOKIE_FILE = "session_cookies.pkl"

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
        print("Cookies saved successfully")
    except Exception as e:
        print(f"Error saving cookies: {e}")

def get_session():
    """Get authenticated session using the adshare_login module"""
    session = adshare_login.get_session(USERNAME, PASSWORD)
    
    if not session:
        print("✗ Could not establish authenticated session using adshare_login module")
        return None
        
    print("✓ Authenticated session established successfully")
    return session

def get_completed_campaigns(session):
    """Find completed campaigns that can have visitors assigned"""
    try:
        response = session.get(f'{BASE_URL}/adverts', timeout=15)
        response.raise_for_status()
        
        # Debug: Check if we're actually logged in
        if 'login' in response.text.lower() and 'email' in response.text.lower():
            print("ERROR: Not logged in - showing login page")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        completed_campaigns = []

        print("DEBUG: Searching for campaigns on adverts page...")
        
        # METHOD 1: Look for "Assign More Visitors" links and check their context
        assign_links = soup.find_all('a', href=lambda href: href and '/adverts/assign/' in href)
        print(f"DEBUG: Found {len(assign_links)} assignment links")
        
        for link in assign_links:
            href = link['href']
            print(f"DEBUG: Checking assignment link: {href}")
            
            # FIX: Check if href is already a full URL
            if href.startswith('http'):
                assign_url = href
            else:
                assign_url = f"{BASE_URL}{href}"
            
            # Get parent context to check if campaign is COMPLETE
            parent_div = link.find_parent('div')
            if parent_div:
                parent_text = parent_div.get_text()
                print(f"DEBUG: Parent context: {parent_text[:150]}...")
                
                # Check if this campaign is COMPLETE
                if 'complete' in parent_text.lower():
                    # Extract campaign ID
                    campaign_id_match = re.search(r'/adverts/assign/(\d+)/', href)
                    if campaign_id_match:
                        campaign_id = campaign_id_match.group(1)
                        completed_campaigns.append({
                            'id': campaign_id,
                            'assign_url': assign_url,  # Use the properly constructed URL
                        })
                        print(f"✓ Found COMPLETE campaign {campaign_id}")
                    else:
                        print("✗ Could not extract campaign ID")
                else:
                    print("✗ Campaign is not COMPLETE")
            else:
                print("✗ No parent div found for assignment link")
        
        return completed_campaigns
        
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        return []

def assign_visitors(session, assign_url, num_visitors=50):
    """Assign visitors to a campaign"""
    try:
        print(f"  Navigating to assignment page: {assign_url}")
        response = session.get(assign_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the assignment form
        form = soup.find('form')
        if not form:
            print("  ✗ Could not find assignment form")
            return False

        # Get form action URL - FIX: Handle relative URLs properly
        action_url = form.get('action')
        print(f"  Raw form action: {action_url}")
        
        if action_url.startswith('http'):
            # Already a full URL
            final_action_url = action_url
        elif action_url.startswith('/'):
            # Relative URL starting with /
            final_action_url = f"{BASE_URL}{action_url}"
        else:
            # Relative URL without leading /
            final_action_url = f"{BASE_URL}/{action_url}"
            
        print(f"  Final form action: {final_action_url}")

        # Extract campaign ID from assign_url
        campaign_id_match = re.search(r'/assign/(\d+)/', assign_url)
        campaign_id = campaign_id_match.group(1) if campaign_id_match else "unknown"
        
        # Prepare form payload - FIX: Use the values from the actual form we found
        payload = {
            'vis': str(num_visitors),
            'bid': '0',  # Set to 15 (top bid + 2) instead of 0
            'spe': '2',   # Faster - Revisit in 12 hours
            'txt': '0',
            'url': '0', 
            'aid': campaign_id,
        }

        print(f"  Submitting assignment of {num_visitors} visitors for campaign {campaign_id}...")
        print(f"  Payload: {payload}")
        
        submit_response = session.post(final_action_url, data=payload, timeout=15)
        submit_response.raise_for_status()
        
        # Check if assignment was successful
        if "visitors" in submit_response.text.lower() or "assign" in submit_response.text.lower() or "update" in submit_response.text.lower():
            print(f"  ✓ Successfully assigned {num_visitors} visitors to campaign {campaign_id}")
            # Save updated cookies using adshare_login module
            adshare_login.save_cookies(session.cookies)
            return True
        else:
            print("  ✗ Assignment may have failed - check response")
            # Debug: print first 500 chars of response
            print(f"  Response preview: {submit_response.text[:500]}...")
            return False
            
    except Exception as e:
        print(f"  ✗ Failed to assign visitors: {e}")
        return False

def run_daily_assignment():
    """Main function to run daily visitor assignment"""
    # Display current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist)
    print(f"--- Starting Daily Visitor Assignment at {current_time_ist:%Y-%m-%d %H:%M:%S} IST ---")
    print(f"Configuration: 50 visitors, 1 max campaign, status: COMPLETE")

    # Get authenticated session using adshare_login module
    session = get_session()
    if not session:
        print("✗ Could not establish authenticated session")
        return

    print("Waiting 3 seconds for session stabilization...")
    time.sleep(3)

    # Find completed campaigns
    print("Searching for COMPLETE campaigns...")
    completed_campaigns = get_completed_campaigns(session)

    if not completed_campaigns:
        print("✗ No COMPLETE campaigns found to reactivate")
        return
        
    # Process up to 1 campaign
    campaign = completed_campaigns[0]
    print(f"✓ Found COMPLETE campaign {campaign['id']}, attempting to reactivate...")
    
    if assign_visitors(session, campaign['assign_url'], num_visitors=1000):
        print(f"✓ Successfully reactivated campaign {campaign['id']} with 1000 visitors")
    else:
        print(f"✗ Failed to reactivate campaign {campaign['id']}")

    print(f"\n--- Daily Visitor Assignment Complete ---")

if __name__ == "__main__":
    run_daily_assignment()
