#!/usr/bin/env python3
"""
AdShare Dynamic Bid Monitor
Monitors active campaigns and intelligently adjusts bids to stay competitive.
"""
import os
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from adshare_login import get_session

ADVERTS_URL = "https://adsha.re/adverts"

def get_active_campaigns(session):
    """Finds active campaigns under 95% completion."""
    try:
        response = session.get(ADVERTS_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        campaigns = []
        
        # A campaign block is a div with a border style
        campaign_blocks = soup.find_all('div', style=lambda s: s and 'border' in s)

        for block in campaign_blocks:
            block_text = block.get_text()
            if 'active' not in block_text.lower():
                continue

            visitor_match = re.search(r'(\d+)\s*/\s*(\d+)\s+visitors', block_text)
            if not visitor_match:
                continue

            current_visitors, max_visitors = map(int, visitor_match.groups())
            completion = (current_visitors / max_visitors) * 100 if max_visitors > 0 else 100

            if completion < 95:
                bid_link = block.find('a', href=lambda href: href and '/adverts/bid/' in href)
                if bid_link:
                    campaign_id_match = re.search(r'/bid/(\d+)/', bid_link['href'])
                    if campaign_id_match:
                        campaigns.append({
                            'id': campaign_id_match.group(1),
                            'bid_url': f"https://adsha.re{bid_link['href']}",
                            'completion': completion
                        })
                        print(f"Found ACTIVE campaign {campaign_id_match.group(1)} at {completion:.1f}%")
        return campaigns
    except requests.exceptions.RequestException as e:
        print(f"Network error getting campaigns: {e}")
    except Exception as e:
        print(f"An error occurred while getting campaigns: {e}")
    return []

def get_bid_info(session, bid_url):
    """Extracts the current and top bid from a campaign's bid page."""
    try:
        response = session.get(bid_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        bid_input = soup.find('input', {'name': 'bid', 'id': 'bid'})
        current_bid = int(bid_input.get('value', 0))

        top_bid = 0
        label_div = soup.find('div', class_='label', string=lambda t: t and 'Bid' in t)
        if label_div and label_div.find('span'):
            match = re.search(r'top bid is (\d+)', label_div.find('span').text, re.IGNORECASE)
            if match:
                top_bid = int(match.group(1))
        
        print(f"  Parsed bid info: Your Bid={current_bid}, Top Bid={top_bid}")
        return current_bid, top_bid
    except Exception as e:
        print(f"  Error getting bid info: {e}")
    return None, None

def adjust_bid(session, bid_url, new_bid):
    """Submits a new bid for a campaign."""
    try:
        response = session.post(bid_url, data={'bid': str(new_bid), 'vis': '0'}, timeout=15)
        response.raise_for_status()
        print(f"  Successfully submitted new bid of {new_bid}.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  Failed to adjust bid: {e}")
        return False

def run_bid_monitor_once():
    """Main function to run one cycle of the bid monitor."""
    print(f"--- Starting Bid Monitor Cycle at {datetime.now():%Y-%m-%d %H:%M:%S} ---")
    
    USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
    PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")

    session = get_session(USERNAME, PASSWORD)
    if not session:
        print("Could not establish a session. Exiting.")
        return

    active_campaigns = get_active_campaigns(session)

    if not active_campaigns:
        print("No active campaigns under 95% completion found. Nothing to do.")
        return

    for campaign in active_campaigns:
        print(f"\nChecking campaign {campaign['id']} ({campaign['completion']:.1f}% complete)....")
        current_bid, top_bid = get_bid_info(session, campaign['bid_url'])
        
        if current_bid is None:
            print("  Could not retrieve bid info. Skipping.")
            continue
        
        desired_bid = top_bid + 2
        
        if current_bid < desired_bid:
            print(f"  Action: Your bid ({current_bid}) is less than desired ({desired_bid}). Adjusting...")
            adjust_bid(session, campaign['bid_url'], desired_bid)
        else:
            print(f"  OK: Your bid ({current_bid}) is sufficient.")

    print("\n--- Bid Monitor Cycle Finished ---")

if __name__ == "__main__":
    run_bid_monitor_once()