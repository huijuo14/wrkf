#!/usr/bin/env python3
"""
AdShare Daily Visitor Assigner
Runs once daily to find completed campaigns and assign 50 new visitors.
"""
import os
import re
import time
import random
import requests
from bs4 import BeautifulSoup
import pytz
from adshare_login import get_session

ADVERTS_URL = "https://adsha.re/adverts"

def get_completed_campaigns(session):
    """Finds campaigns marked as 'COMPLETE' that can have visitors assigned."""
    try:
        response = session.get(ADVERTS_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        completed_campaigns = []

        # A campaign block is a div with a border style
        campaign_blocks = soup.find_all('div', style=lambda s: s and 'border' in s)

        for block in campaign_blocks:
            # We only care about campaigns that are explicitly marked 'COMPLETE'
            if 'complete' in block.get_text().lower():
                assign_link = block.find('a', href=lambda href: href and '/adverts/assign/' in href)
                if assign_link:
                    campaign_id_match = re.search(r'/assign/(\d+)/', assign_link['href'])
                    if campaign_id_match:
                        completed_campaigns.append({
                            'id': campaign_id_match.group(1),
                            'assign_url': f"https://adsha.re{assign_link['href']}",
                        })
                        print(f"Found COMPLETE campaign {campaign_id_match.group(1)} to reactivate.")
        return completed_campaigns
    except requests.exceptions.RequestException as e:
        print(f"Network error getting campaigns: {e}")
    except Exception as e:
        print(f"An error occurred while getting campaigns: {e}")
    return []

def assign_visitors(session, assign_url, num_visitors=50):
    """Submits the form to assign more visitors to a campaign."""
    try:
        response = session.get(assign_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        form = soup.find('form')
        if not form:
            print("  Could not find assignment form.")
            return False

        action_url = form.get('action')
        campaign_id = assign_url.split('/')[4]
        
        payload = {
            'vis': str(num_visitors),
            'bid': '0',
            'spe': '2', # 'Faster - Revisit in 12 hours'
            'txt': '0', 'url': '0', 'aid': campaign_id,
        }

        submit_response = session.post(action_url, data=payload, timeout=15)
        submit_response.raise_for_status()
        print(f"  Successfully submitted assignment of {num_visitors} visitors.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  Failed to assign visitors: {e}")
        return False

def run_daily_assignment():
    """Main function to find and reactivate a completed campaign."""
    print(f"--- Starting Daily Visitor Assignment at {datetime.now():%Y-%m-%d %H:%M:%S} ---")
    
    USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
    PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")

    session = get_session(USERNAME, PASSWORD)
    if not session:
        print("Could not establish a session. Exiting.")
        return

    completed_campaigns = get_completed_campaigns(session)

    if not completed_campaigns:
        print("No completed campaigns found to reactivate. Nothing to do.")
        return
        
    campaign_to_reactivate = completed_campaigns[0]
    print(f"\nAttempting to reactivate campaign {campaign_to_reactivate['id']}...")
    
    if assign_visitors(session, campaign_to_reactivate['assign_url'], num_visitors=50):
        print(f"Successfully assigned 50 visitors to campaign {campaign_to_reactivate['id']}.")
    else:
        print(f"Failed to assign visitors to campaign {campaign_to_reactivate['id']}.")

    print("\n--- Daily Visitor Assignment Finished ---")

if __name__ == "__main__":
    if os.environ.get("GITHUB_ACTIONS") == "true":
        delay = random.randint(0, 900) # 0-15 min random delay
        print(f"Running in GitHub Actions. Waiting for {delay} seconds for time randomization...")
        time.sleep(delay)
        
    run_daily_assignment()