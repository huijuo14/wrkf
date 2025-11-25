#!/usr/bin/env python3
"""
AdShare Refined Bid Monitor
Monitors active campaigns and intelligently adjusts bids to stay competitive.
Combines the working bid detection logic with the single-cycle execution pattern.
"""
import os
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from adshare_login import get_session

ADVERTS_URL = "https://adsha.re/adverts"

def get_all_campaigns(session):
    """Dynamically get all campaigns from the adverts page"""
    try:
        response = session.get(ADVERTS_URL)
        if response.status_code != 200:
            print("Failed to get adverts page")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all campaign-related links to extract campaign IDs
        all_links = soup.find_all('a', href=True)

        # Use regex to find campaign IDs from various campaign action URLs
        campaign_ids = set()  # Use set to avoid duplicates

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

        for link in all_links:
            href = link.get('href', '')
            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    campaign_id = match.group(1)
                    if campaign_id not in campaign_ids:
                        campaign_ids.add(campaign_id)
                        print(f"Found campaign {campaign_id} from action link")

        # Also check our known campaign that has bid functionality
        # This ensures we don't miss campaigns that may not appear on the main page
        # but still need bid monitoring
        known_campaigns_with_bidding = ['2641']  # Add others if discovered later
        for known_campaign in known_campaigns_with_bidding:
            if known_campaign not in campaign_ids:
                campaign_ids.add(known_campaign)
                print(f"Added known campaign with bidding: {known_campaign}")

        # Now attempt to find bid URLs for each campaign ID
        final_campaigns = []
        for campaign_id in campaign_ids:
            bid_url = find_bid_url_for_campaign_id(session, campaign_id)
            if bid_url:
                campaign_info = {
                    'id': campaign_id,
                    'bid_url': bid_url
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
    # The bid URL format is: /adverts/bid/{campaign_id}/{long_hex_token}

    # First, try to find bid links on the main page for this specific campaign ID
    response = session.get(ADVERTS_URL)
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Look for bid links that contain this specific campaign ID
    bid_links = soup.find_all('a', href=lambda href: href and f'/adverts/bid/{campaign_id}/' in href)

    if bid_links:
        # Return the first bid link we found
        return bid_links[0].get('href')

    # If not found on main page, check known bid tokens
    known_bid_tokens = {
        '2641': '9c11d5c78ca339eee3c02533cae3aaabd292f7711a35ed4575a5e9eacb1100396ec99c4f8c0cd807ac1acac44ab85e847cebbae08b90a3575d3aca99128ad1ec'
    }

    if campaign_id in known_bid_tokens:
        return f"{ADVERTS_URL}/bid/{campaign_id}/{known_bid_tokens[campaign_id]}"

    # For other campaigns, if we can't find the specific token, return None
    return None

def get_active_campaigns(session):
    """Finds campaigns with bidding functionality (completion check is secondary)."""
    try:
        response = session.get(ADVERTS_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get all campaigns with bidding functionality
        all_campaigns = get_all_campaigns(session)

        # Try to get completion status for each campaign
        active_campaigns = []

        for campaign in all_campaigns:
            # Get the campaign details page to check completion and bid info
            bid_response = session.get(campaign['bid_url'])
            if bid_response.status_code == 200:
                bid_soup = BeautifulSoup(bid_response.text, 'html.parser')

                # Look for visitor information on the bid page
                page_text = bid_soup.get_text()
                visitor_match = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:visitors|visitor)', page_text, re.IGNORECASE)

                if visitor_match:
                    current_visitors, max_visitors = map(int, visitor_match.groups())
                    completion = (current_visitors / max_visitors) * 100 if max_visitors > 0 else 0

                    # Only include campaigns under 95% completion
                    if completion < 95:
                        campaign['completion'] = completion
                        active_campaigns.append(campaign)
                        print(f"Found active campaign {campaign['id']} at {completion:.1f}% completion")
                    else:
                        print(f"Skipped campaign {campaign['id']} at {completion:.1f}% completion (≥95%)")
                else:
                    # If no visitor info but bid page is accessible, include it (likely active)
                    campaign['completion'] = 0
                    active_campaigns.append(campaign)
                    print(f"Found campaign {campaign['id']} with bid functionality (no completion info)")
            else:
                # If can't access bid page, it might be a different type of campaign
                print(f"Could not access bid page for campaign {campaign['id']}, skipping")
                continue

        return active_campaigns
    except requests.exceptions.RequestException as e:
        print(f"Network error getting campaigns: {e}")
    except Exception as e:
        print(f"An error occurred while getting campaigns: {e}")
    return []

def get_bid_info(session, bid_url):
    """Extracts the current and top bid from a campaign's bid page."""
    try:
        headers = {'Referer': ADVERTS_URL}
        response = session.get(bid_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        bid_input = soup.find('input', {'name': 'bid', 'id': 'bid'})
        current_bid = int(bid_input.get('value', 0)) if bid_input else 0

        top_bid = 0
        page_text = soup.get_text()

        # Multiple methods to find the top bid
        # Method 1: Look for "top bid is X credits" pattern
        top_bid_match = re.search(r'top\s+bid\s+is\s+(\d+)\s+credits?', page_text, re.IGNORECASE)
        if top_bid_match:
            top_bid = int(top_bid_match.group(1))
        else:
            # Method 2: Look for the label div containing "Bid" and top bid info
            label_divs = soup.find_all('div', class_='label')
            for label_div in label_divs:
                label_text = label_div.get_text()
                top_bid_match = re.search(r'top\s+bid\s+is\s+(\d+)', label_text, re.IGNORECASE)
                if top_bid_match:
                    top_bid = int(top_bid_match.group(1))
                    break

        # Method 3: Look for other possible patterns in the entire response
        if top_bid == 0:
            # Try to find patterns like "(X credits)" or similar near bid-related text
            bid_related_text = re.findall(r'bid.*?(\d+)\s*credits?|(\d+)\s*credits?.*?bid', page_text, re.IGNORECASE)
            for match in bid_related_text:
                # Each match is a tuple, get the non-empty value
                found_bid = match[0] or match[1]
                if found_bid and found_bid.isdigit():
                    found_bid_int = int(found_bid)
                    # Only update top_bid if it's reasonable (not the current bid)
                    if found_bid_int != current_bid and found_bid_int > top_bid:
                        top_bid = found_bid_int
                        break

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
    print(f"--- Starting Refined Bid Monitor Cycle at {datetime.now():%Y-%m-%d %H:%M:%S} ---")

    USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
    PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")

    session = get_session(USERNAME, PASSWORD)
    if not session:
        print("Could not establish a session. Exiting.")
        return

    print("Waiting 15 seconds for session to stabilize...")
    time.sleep(15)

    active_campaigns = get_active_campaigns(session)

    if not active_campaigns:
        print("No campaigns with bid functionality found. Nothing to do.")
        return

    for campaign in active_campaigns:
        print(f"\nChecking campaign {campaign['id']} ({campaign['completion']:.1f}% complete)...")

        # We need both current and top bid for the calculation
        current_bid, top_bid = get_bid_info(session, campaign['bid_url'])

        if current_bid is None or top_bid is None:
            print("  Could not retrieve bid info. Skipping.")
            continue

        desired_bid = top_bid + 2  # Bid 2 credits higher than the top bid

        if current_bid < desired_bid:
            print(f"  Action: Your bid ({current_bid}) is less than desired ({desired_bid}). Adjusting...")
            if adjust_bid(session, campaign['bid_url'], desired_bid):
                time.sleep(3)  # Wait 3 seconds for the site to process the change
        else:
            print(f"  OK: Your bid ({current_bid}) is sufficient (at or above {desired_bid}).")

    print("\n--- Refined Bid Monitor Cycle Finished ---")

if __name__ == "__main__":
    run_bid_monitor_once()
