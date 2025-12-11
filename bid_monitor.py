#!/usr/bin/env python3
"""
AdShare Smart Bid Monitor with Campaign Status Checking
Fixes the credit wasting issue by checking campaign status before bidding
Now uses adshare_login module for session management
"""
import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Import the login module
import adshare_login

# Configuration
BASE_URL = "https://adsha.re"
USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")
COOKIE_FILE = "cookies.txt"  # Now using Netscape format

def get_campaign_status(session, campaign_id):
    """Get the status of a campaign (ACTIVE, COMPLETE, PAUSED, etc.)"""
    try:
        response = session.get(f'{BASE_URL}/adverts', timeout=15)
        if response.status_code != 200:
            print(f"Failed to get adverts page for status check")
            return "UNKNOWN"

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the campaign block that contains this campaign ID
        campaign_blocks = soup.find_all('div')
        
        for block in campaign_blocks:
            block_text = block.get_text()
            
            # Check if this block contains our campaign ID in any links
            campaign_links = block.find_all('a', href=lambda href: href and f'/adverts/bid/{campaign_id}/' in href)
            if not campaign_links:
                # Also check for other action links with this campaign ID
                campaign_links = block.find_all('a', href=lambda href: href and f'/{campaign_id}/' in href and '/adverts/' in href)
            
            if campaign_links:
                # Found a block with our campaign, now check its status
                block_text_lower = block_text.lower()
                
                if 'complete' in block_text_lower:
                    return "COMPLETE"
                elif 'active' in block_text_lower:
                    return "ACTIVE"
                elif 'paused' in block_text_lower:
                    return "PAUSED"
                elif 'pending' in block_text_lower:
                    return "PENDING"
                else:
                    # If no explicit status found, check for visitor counts
                    if 'visitors' in block_text_lower:
                        return "ACTIVE"  # Assume active if has visitors
                    else:
                        return "UNKNOWN"
        
        return "NOT_FOUND"
        
    except Exception as e:
        print(f"Error getting campaign status for {campaign_id}: {e}")
        return "ERROR"

def get_all_campaigns(session):
    """Dynamically get all campaigns from the adverts page"""
    try:
        response = session.get(f'{BASE_URL}/adverts', timeout=15)
        if response.status_code != 200:
            print("Failed to get adverts page")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all campaign-related links to extract campaign IDs
        all_links = soup.find_all('a', href=True)

        # Also look for non-link elements that might contain campaign data
        all_elements = soup.find_all(['a', 'td', 'tr', 'div'], string=lambda text: text and 'My Advert' in text)
        campaign_ids = set()  # Use set to avoid duplicates

        # Find campaign IDs from action links
        for link in all_links:
            href = link.get('href', '')

            # Look for various campaign-related URL patterns that contain campaign IDs
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
        for element in all_elements:
            parent = element.find_parent()
            if parent:
                parent_text = str(parent)
                campaign_matches = re.findall(r'/adverts/(?:pause|delete|assign|bid)/(\d+)/', parent_text)
                for match in campaign_matches:
                    if match not in campaign_ids:
                        campaign_ids.add(match)
                        print(f"Found campaign {match} from 'My Advert' association")

        # Also check our known campaign that has bid functionality
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
                    'id': campaign_id,
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
    # First, try to find bid links on the main page for this specific campaign ID
    response = session.get(f'{BASE_URL}/adverts', timeout=15)
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
    known_bid_tokens = {
        '2641': '9c11d5c78ca339eee3c02533cae3aaabd292f7711a35ed4575a5e9eacb1100396ec99c4f8c0cd807ac1acac44ab85e847cebbae08b90a3575d3aca99128ad1ec'
    }

    if campaign_id in known_bid_tokens:
        return f"{BASE_URL}/adverts/bid/{campaign_id}/{known_bid_tokens[campaign_id]}"

    # For other campaigns, if we can't find the specific token, return None
    return None

def get_current_bid_info(session, campaign):
    """Get current bid and top bid information for a campaign"""
    try:
        response = session.get(campaign['bid_url'], timeout=15)
        if response.status_code != 200:
            print(f"Failed to get bid info for campaign {campaign['id']}, status code: {response.status_code}")
            return None, None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the bid input field (current bid)
        bid_input = soup.find('input', {'name': 'bid', 'id': 'bid'})
        current_bid = int(bid_input.get('value')) if bid_input else 0

        # Look for top bid information in the page text
        page_text = soup.get_text()
        top_bid = current_bid  # Default to current bid if not found

        # Try multiple patterns to find the top bid in the page
        top_bid_patterns = [
            r'top\s+bid\s+is\s+(\d+)\s+credits?',
            r'bid.*?you.*?(\d+).*?top.*?(\d+)',
            r'top.*?bid.*?(\d+)',
            r'(\d+).*?top.*?bid',
            r'current.*?top.*?(\d+)'
        ]
        
        for pattern in top_bid_patterns:
            top_bid_match = re.search(pattern, page_text, re.IGNORECASE)
            if top_bid_match:
                groups = top_bid_match.groups()
                if len(groups) > 1 and 'you' in pattern.lower():
                    try:
                        top_bid = int(groups[1])
                    except (ValueError, IndexError):
                        for group in groups:
                            if group and group.isdigit():
                                potential_top = int(group)
                                if potential_top != current_bid:
                                    top_bid = potential_top
                                    break
                else:
                    for group in groups:
                        if group and group.isdigit():
                            potential_top = int(group)
                            if potential_top != current_bid:
                                top_bid = potential_top
                                break
                if top_bid != current_bid:
                    break

        print(f"  Parsed bid info: Current Bid={current_bid}, Top Bid={top_bid}")
        return current_bid, top_bid
    except Exception as e:
        print(f"Error getting bid info for campaign {campaign['id']}: {e}")
        return None, None

def adjust_bid(session, campaign, new_bid):
    """Adjust bid to a new value"""
    try:
        bid_data = {
            'bid': str(new_bid),
            'vis': '0'
        }

        response = session.post(campaign['bid_url'], data=bid_data, timeout=15)
        if response.status_code == 200:
            print(f"Successfully adjusted bid for campaign {campaign['id']} to {new_bid}")
            return True
        else:
            print(f"Failed to adjust bid for campaign {campaign['id']}: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error adjusting bid for campaign {campaign['id']}: {e}")
        return False

def run_bid_monitor_once():
    """Main function to run one cycle of the bid monitor."""
    print(f"--- Starting Smart Bid Monitor Cycle at {datetime.now():%Y-%m-%d %H:%M:%S} ---")
    print(f"Using Netscape cookie format: {COOKIE_FILE}")

    # Use adshare_login module to get authenticated session
    session = adshare_login.get_session(USERNAME, PASSWORD)
    
    if not session:
        print("Failed to get authenticated session, exiting")
        return False

    print("Session established successfully")
    print("Waiting 5 seconds for session to stabilize...")
    time.sleep(5)

    # Get all campaigns
    campaigns = get_all_campaigns(session)

    if not campaigns:
        print("No campaigns found, exiting.")
        return True  # Return True as this is not an error, just no campaigns

    successful_adjustments = 0
    skipped_campaigns = 0
    
    for campaign in campaigns:
        print(f"\nChecking campaign {campaign['id']}")

        # Check campaign status before doing anything
        status = get_campaign_status(session, campaign['id'])
        print(f"  Campaign status: {status}")

        # Only adjust bids for ACTIVE campaigns
        if status != "ACTIVE":
            print(f"  ⚠️  Skipping bid adjustment - campaign is {status}")
            skipped_campaigns += 1
            continue

        current_bid, top_bid = get_current_bid_info(session, campaign)
        if current_bid is not None and top_bid is not None:
            print(f"  Current bid: {current_bid}, Top bid: {top_bid}")

            # Calculate desired bid (top bid + buffer)
            desired_bid = top_bid + campaign['bid_buffer']

            if current_bid < desired_bid:
                print(f"  Current bid is below desired ({desired_bid}), adjusting...")
                if adjust_bid(session, campaign, desired_bid):
                    print(f"  ✓ Bid adjusted to {desired_bid}")
                    successful_adjustments += 1
                else:
                    print("  ✗ Failed to adjust bid, continuing...")
            else:
                print(f"  Current bid is sufficient (≥ {desired_bid})")
        else:
            print(f"  Failed to get bid info for campaign {campaign['id']}, skipping...")
            skipped_campaigns += 1

    print(f"\n--- Smart Bid Monitor Cycle Finished ---")
    print(f"Results: {successful_adjustments} bids adjusted, {skipped_campaigns} campaigns skipped")
    
    return successful_adjustments > 0 or len(campaigns) == 0

def main():
    """Command-line interface with support for continuous mode"""
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        print("Running in continuous mode (press Ctrl+C to stop)")
        interval_minutes = 5  # Check every 5 minutes
        
        while True:
            try:
                success = run_bid_monitor_once()
                if not success:
                    print("No successful bid adjustments, waiting longer...")
                    time.sleep(interval_minutes * 60 * 2)  # Wait longer if no adjustments
                else:
                    print(f"Waiting {interval_minutes} minutes until next check...")
                    time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print("\nStopped by user")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                print("Waiting 10 minutes before retry...")
                time.sleep(600)
    else:
        # Single run mode
        run_bid_monitor_once()

if __name__ == "__main__":
    main()
