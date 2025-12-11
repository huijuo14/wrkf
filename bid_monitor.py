#!/usr/bin/env python3
"""
AdShare Smart Bid Monitor with Campaign Status Checking
Fixes the credit wasting issue by checking campaign status before bidding
Uses adshare_login module for session management - GitHub compatible
"""
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Import the login module
import adshare_login

# Configuration
BASE_URL = "https://adsha.re"
USERNAME = os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com")
PASSWORD = os.environ.get('ADSHARE_PASSWORD', "@Sd2007123")

def verify_session_active(session):
    """Verify the session is actually logged in by checking account page"""
    try:
        # Try multiple endpoints to confirm login
        endpoints = ['/account', '/adverts', '/dashboard']
        
        for endpoint in endpoints:
            try:
                response = session.get(f'{BASE_URL}{endpoint}', timeout=15)
                
                # Check for login indicators
                response_lower = response.text.lower()
                if ('logout' in response_lower or 
                    'my account' in response_lower or 
                    'welcome' in response_lower or
                    'dashboard' in response_lower):
                    print(f"✓ Session verified as active via {endpoint}")
                    return True
                    
                # Check if we're redirected to login page
                if 'login' in response_lower and 'email' in response_lower:
                    print(f"✗ Redirected to login page on {endpoint}")
                    continue
                    
            except Exception as e:
                print(f"Error checking {endpoint}: {e}")
                continue
        
        print("✗ Could not verify active session on any endpoint")
        return False
        
    except Exception as e:
        print(f"✗ Session verification failed: {e}")
        return False

def get_campaign_status(session, campaign_id):
    """Get the status of a campaign (ACTIVE, COMPLETE, PAUSED, etc.)"""
    try:
        response = session.get(f'{BASE_URL}/adverts', timeout=15)
        
        # Debug info
        if os.getenv('GITHUB_ACTIONS'):
            print(f"DEBUG: Adverts page status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Failed to get adverts page: {response.status_code}")
            return "ERROR"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # First check if we're actually on adverts page
        page_title = soup.find('title')
        if page_title and 'login' in page_title.text.lower():
            print("ERROR: Not logged in - on login page")
            return "NOT_LOGGED_IN"
        
        # More robust search for campaign status
        # Look for campaign in tables
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                row_text = row.get_text()
                if campaign_id in row_text:
                    # Check row for status indicators
                    row_lower = row_text.lower()
                    
                    if 'complete' in row_lower:
                        return "COMPLETE"
                    elif 'active' in row_lower:
                        return "ACTIVE"
                    elif 'paused' in row_lower:
                        return "PAUSED"
                    elif 'pending' in row_lower:
                        return "PENDING"
                    elif 'visitors' in row_lower or 'credits' in row_lower:
                        return "ACTIVE"  # Likely active if showing metrics
                    else:
                        return "UNKNOWN"
        
        # If not found in tables, check divs with campaign cards
        campaign_divs = soup.find_all('div', class_=lambda x: x and ('campaign' in x.lower() or 'advert' in x.lower() or 'card' in x.lower()))
        for div in campaign_divs:
            div_text = div.get_text()
            if campaign_id in div_text:
                div_lower = div_text.lower()
                
                if 'complete' in div_lower:
                    return "COMPLETE"
                elif 'active' in div_lower:
                    return "ACTIVE"
                elif 'paused' in div_lower:
                    return "PAUSED"
                elif 'pending' in div_lower:
                    return "PENDING"
                else:
                    return "UNKNOWN"
        
        # Check for any elements containing campaign ID
        all_elements = soup.find_all(text=re.compile(campaign_id))
        for element in all_elements:
            parent_text = element.parent.get_text().lower() if element.parent else ""
            
            if 'complete' in parent_text:
                return "COMPLETE"
            elif 'active' in parent_text:
                return "ACTIVE"
            elif 'paused' in parent_text:
                return "PAUSED"
            elif 'pending' in parent_text:
                return "PENDING"
        
        return "NOT_FOUND"
        
    except Exception as e:
        print(f"Error getting campaign status for {campaign_id}: {e}")
        return "ERROR"

def get_all_campaigns(session):
    """Dynamically get all campaigns from the adverts page"""
    try:
        response = session.get(f'{BASE_URL}/adverts', timeout=15)
        if response.status_code != 200:
            print(f"Failed to get adverts page: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Check page content
        if os.getenv('GITHUB_ACTIONS'):
            print(f"DEBUG: Adverts page length: {len(response.text)} chars")
            # Save first 1000 chars for debugging
            with open('adverts_debug.txt', 'w') as f:
                f.write(response.text[:1000])

        campaign_ids = set()
        final_campaigns = []

        # Find all links that might be campaign actions
        all_links = soup.find_all('a', href=True)
        
        # Extract campaign IDs from various URL patterns
        patterns = [
            r'/adverts/pause/(\d+)/',
            r'/adverts/delete/(\d+)/',
            r'/adverts/assign/(\d+)/',
            r'/adverts/bid/(\d+)/',
            r'/adverts/speed/(\d+)/',
            r'/adverts/edit/(\d+)/',
            r'/adverts/view/(\d+)/'
        ]
        
        for link in all_links:
            href = link.get('href', '')
            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    campaign_id = match.group(1)
                    if campaign_id not in campaign_ids:
                        campaign_ids.add(campaign_id)
                        print(f"Found campaign {campaign_id}")

        # Also look for campaign IDs in text
        text_elements = soup.find_all(text=re.compile(r'[Cc]ampaign\s*[#:]?\s*(\d+)'))
        for element in text_elements:
            match = re.search(r'(\d{3,})', element)
            if match and len(match.group(1)) >= 3:  # Campaign IDs are usually 3+ digits
                campaign_id = match.group(1)
                if campaign_id not in campaign_ids:
                    campaign_ids.add(campaign_id)
                    print(f"Found campaign {campaign_id} in text")

        # If no campaigns found, use known campaigns
        if not campaign_ids:
            print("No campaigns found dynamically, using known campaigns")
            known_campaigns = ['2641']  # Add more if discovered
            campaign_ids.update(known_campaigns)

        # Find bid URLs for each campaign
        for campaign_id in campaign_ids:
            bid_url = find_bid_url_for_campaign_id(session, campaign_id, all_links)
            if bid_url:
                campaign_info = {
                    'id': campaign_id,
                    'bid_url': bid_url,
                    'bid_buffer': 2  # Bid this amount above the top bid
                }
                final_campaigns.append(campaign_info)
                print(f"✓ Bid URL found for campaign {campaign_id}")
            else:
                print(f"✗ No bid functionality found for campaign {campaign_id}")

        return final_campaigns
        
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        return []

def find_bid_url_for_campaign_id(session, campaign_id, all_links=None):
    """Find bid URL for a specific campaign"""
    # First check in provided links
    if all_links:
        for link in all_links:
            href = link.get('href', '')
            if f'/adverts/bid/{campaign_id}/' in href:
                full_url = href if href.startswith('http') else f'{BASE_URL}{href}'
                return full_url
    
    # If not found, check known bid tokens
    known_bid_tokens = {
        '2641': '9c11d5c78ca339eee3c02533cae3aaabd292f7711a35ed4575a5e9eacb1100396ec99c4f8c0cd807ac1acac44ab85e847cebbae08b90a3575d3aca99128ad1ec'
    }
    
    if campaign_id in known_bid_tokens:
        return f"{BASE_URL}/adverts/bid/{campaign_id}/{known_bid_tokens[campaign_id]}"
    
    # Try to construct bid URL with common patterns
    common_patterns = [
        f'{BASE_URL}/adverts/bid/{campaign_id}/',
        f'{BASE_URL}/bid/{campaign_id}/',
        f'{BASE_URL}/campaigns/{campaign_id}/bid/'
    ]
    
    # Try each pattern
    for pattern in common_patterns:
        try:
            response = session.get(pattern, timeout=10, allow_redirects=False)
            if response.status_code == 200:
                return pattern
        except:
            continue
    
    return None

def get_current_bid_info(session, campaign):
    """Get current bid and top bid information for a campaign"""
    try:
        response = session.get(campaign['bid_url'], timeout=15)
        
        if response.status_code != 200:
            print(f"Failed to get bid page for campaign {campaign['id']}: {response.status_code}")
            return None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Save bid page for debugging
        if os.getenv('GITHUB_ACTIONS'):
            with open(f'bid_page_{campaign["id"]}.html', 'w') as f:
                f.write(soup.prettify())

        # Find bid input field
        bid_input = soup.find('input', {'name': 'bid'})
        if not bid_input:
            # Try other input names
            bid_input = soup.find('input', {'id': 'bid'}) or \
                       soup.find('input', {'type': 'number'}) or \
                       soup.find('input', {'value': re.compile(r'\d+')})
        
        current_bid = 0
        if bid_input and bid_input.get('value'):
            try:
                current_bid = int(bid_input.get('value'))
            except:
                current_bid = 0

        # Look for top bid in the page
        page_text = soup.get_text()
        top_bid = current_bid  # Default
        
        # Multiple patterns to find top bid
        patterns = [
            r'top\s*bid.*?(\d+)',
            r'highest\s*bid.*?(\d+)',
            r'current\s*top.*?(\d+)',
            r'bid.*?(\d+).*?top',
            r'top.*?:.*?(\d+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if match.isdigit():
                    potential_top = int(match)
                    if potential_top > current_bid:
                        top_bid = potential_top
                        break
            if top_bid != current_bid:
                break

        print(f"  Campaign {campaign['id']}: Current={current_bid}, Top={top_bid}")
        return current_bid, top_bid
        
    except Exception as e:
        print(f"Error getting bid info for campaign {campaign['id']}: {e}")
        return None, None

def adjust_bid(session, campaign, new_bid):
    """Adjust bid to a new value"""
    try:
        # First, get the bid page to find any CSRF tokens
        response = session.get(campaign['bid_url'], timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find CSRF token if exists
        csrf_token = None
        csrf_input = soup.find('input', {'name': 'csrf_token'}) or \
                    soup.find('input', {'name': 'csrfmiddlewaretoken'}) or \
                    soup.find('input', {'name': 'token'})
        
        if csrf_input:
            csrf_token = csrf_input.get('value')
        
        # Prepare data for POST
        bid_data = {
            'bid': str(new_bid),
            'vis': '0'
        }
        
        if csrf_token:
            bid_data['csrf_token'] = csrf_token
            bid_data['csrfmiddlewaretoken'] = csrf_token

        # Submit bid adjustment
        headers = {
            'Referer': campaign['bid_url'],
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        response = session.post(campaign['bid_url'], data=bid_data, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Check if bid was successful
            if 'success' in response.text.lower() or 'updated' in response.text.lower():
                print(f"✓ Bid adjusted to {new_bid} for campaign {campaign['id']}")
                return True
            else:
                print(f"✗ Bid adjustment may have failed for campaign {campaign['id']}")
                return False
        else:
            print(f"✗ Failed to adjust bid: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Error adjusting bid for campaign {campaign['id']}: {e}")
        return False

def run_bid_monitor_once():
    """Main function to run one cycle of the bid monitor."""
    print(f"\n{'='*60}")
    print(f"AdShare Smart Bid Monitor - {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}")
    
    if os.getenv('GITHUB_ACTIONS'):
        print("🔧 Running on GitHub Actions")
    else:
        print("💻 Running locally")
    
    # Get authenticated session
    print("\n🔑 Authenticating...")
    session = adshare_login.get_session(USERNAME, PASSWORD)
    
    if not session:
        print("❌ Failed to get authenticated session")
        return
    
    print("✅ Session obtained")
    
    # Verify session is actually logged in
    print("\n🔍 Verifying session...")
    if not verify_session_active(session):
        print("❌ Session is not properly authenticated")
        print("Possible issues:")
        print("  1. Invalid credentials")
        print("  2. Website changes")
        print("  3. IP blocked")
        return
    
    print("✅ Session verified as active")
    print("⏳ Waiting 3 seconds...")
    time.sleep(3)
    
    # Get all campaigns
    print("\n📋 Finding campaigns...")
    campaigns = get_all_campaigns(session)
    
    if not campaigns:
        print("❌ No campaigns with bid functionality found")
        return
    
    print(f"✅ Found {len(campaigns)} campaign(s) with bid functionality")
    
    # Process each campaign
    for idx, campaign in enumerate(campaigns, 1):
        print(f"\n{'─'*40}")
        print(f"📊 Campaign {idx}/{len(campaigns)}: ID {campaign['id']}")
        
        # Check campaign status
        status = get_campaign_status(session, campaign['id'])
        print(f"   Status: {status}")
        
        # Only adjust bids for ACTIVE campaigns
        if status != "ACTIVE":
            print(f"   ⏸️  Skipping - campaign is {status}")
            continue
        
        # Get current bid info
        print("   📈 Getting bid information...")
        current_bid, top_bid = get_current_bid_info(session, campaign)
        
        if current_bid is None or top_bid is None:
            print("   ❌ Failed to get bid information")
            continue
        
        # Calculate desired bid
        desired_bid = top_bid + campaign['bid_buffer']
        print(f"   💡 Desired bid: {desired_bid} (Top: {top_bid} + Buffer: {campaign['bid_buffer']})")
        
        # Check if bid adjustment is needed
        if current_bid < desired_bid:
            print(f"   ⬆️  Current bid ({current_bid}) is below desired ({desired_bid})")
            print("   🔄 Adjusting bid...")
            
            if adjust_bid(session, campaign, desired_bid):
                print(f"   ✅ Bid adjusted to {desired_bid}")
            else:
                print("   ❌ Failed to adjust bid")
        else:
            print(f"   ✅ Current bid ({current_bid}) is sufficient")
        
        # Small delay between campaigns
        if idx < len(campaigns):
            time.sleep(2)
    
    print(f"\n{'='*60}")
    print("🎉 Bid monitor cycle completed successfully!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    try:
        run_bid_monitor_once()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
