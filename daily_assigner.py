#!/usr/bin/env python3
"""
AdShare Daily Visitor Assigner - Debug Version
"""
import os
import re
import time
import argparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from adshare_login import get_session

# Default configuration
DEFAULT_CONFIG = {
    'adverts_url': "https://adsha.re/adverts",
    'username': os.environ.get('ADSHARE_USERNAME', "jiocloud90@gmail.com"),
    'password': os.environ.get('ADSHARE_PASSWORD', "@Sd2007123"),
    'visitors_per_campaign': 50,
    'max_campaigns_per_run': 1,
    'campaign_speed': '2',
    'text_ads': '0',
    'url_ads': '0',
    'bid_amount': '0',
    'request_timeout': 15,
    'campaign_status': 'COMPLETE',
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    config['username'] = os.environ.get('ADSHARE_USERNAME', config['username'])
    config['password'] = os.environ.get('ADSHARE_PASSWORD', config['password'])
    config['visitors_per_campaign'] = int(os.environ.get('ADSHARE_VISITORS_PER_CAMPAIGN', config['visitors_per_campaign']))
    config['max_campaigns_per_run'] = int(os.environ.get('ADSHARE_MAX_CAMPAIGNS', config['max_campaigns_per_run']))
    return config

def debug_page_content(soup):
    """Print debug information about the page content"""
    print("\n" + "="*80)
    print("DEBUG: PAGE CONTENT ANALYSIS")
    print("="*80)
    
    # Print page title
    title = soup.find('title')
    print(f"Page Title: {title.get_text() if title else 'No title found'}")
    
    # Print all text content to see what's actually on the page
    all_text = soup.get_text()
    lines = [line.strip() for line in all_text.split('\n') if line.strip()]
    
    print(f"\nTop 20 text lines on page:")
    for i, line in enumerate(lines[:20]):
        print(f"{i+1:2d}: {line}")
    
    # Look for any divs that might be campaigns
    all_divs = soup.find_all('div')
    print(f"\nTotal div elements found: {len(all_divs)}")
    
    # Look for campaign indicators
    campaign_indicators = []
    for i, div in enumerate(all_divs):
        div_text = div.get_text().strip()
        if any(keyword in div_text.lower() for keyword in ['complete', 'active', 'visitors', 'my advert', 'campaign']):
            campaign_indicators.append((i, div_text[:100]))
    
    print(f"\nDivs with campaign keywords: {len(campaign_indicators)}")
    for idx, text in campaign_indicators[:10]:  # Show first 10
        print(f"  Div {idx}: {text}...")
    
    # Look for all links
    all_links = soup.find_all('a', href=True)
    assign_links = [link for link in all_links if '/adverts/assign/' in link['href']]
    
    print(f"\nAll links containing '/adverts/assign/': {len(assign_links)}")
    for link in assign_links:
        print(f"  Assign link: {link['href']}")
        # Check parent elements for campaign info
        parent = link.find_parent('div')
        if parent:
            parent_text = parent.get_text().strip()
            print(f"    Parent text: {parent_text[:100]}...")
    
    print("="*80 + "\n")

def get_completed_campaigns(session, config):
    """Finds campaigns marked with specified status that can have visitors assigned."""
    try:
        response = session.get(config['adverts_url'], timeout=config['request_timeout'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        completed_campaigns = []

        # First, debug the page content
        debug_page_content(soup)
        
        # METHOD 1: Direct search for assign links and check their context
        print("METHOD 1: Searching for assignment links directly...")
        assign_links = soup.find_all('a', href=lambda href: href and '/adverts/assign/' in href)
        print(f"Found {len(assign_links)} assignment links")
        
        for link in assign_links:
            print(f"Checking assignment link: {link['href']}")
            
            # Get the parent context to check status
            parent = link.find_parent('div')
            if parent:
                parent_text = parent.get_text()
                print(f"Parent context: {parent_text[:200]}...")
                
                if config['campaign_status'].lower() in parent_text.lower():
                    # Extract campaign ID
                    campaign_id_match = re.search(r'/adverts/assign/(\d+)/', link['href'])
                    if campaign_id_match:
                        campaign_id = campaign_id_match.group(1)
                        completed_campaigns.append({
                            'id': campaign_id,
                            'assign_url': f"https://adsha.re{link['href']}",
                        })
                        print(f"✓ Found {config['campaign_status']} campaign {campaign_id}")
                    else:
                        print("✗ Could not extract campaign ID")
                else:
                    print(f"✗ Parent context does not contain '{config['campaign_status']}'")
            else:
                print("✗ No parent div found for this link")
        
        # METHOD 2: Search for any element containing COMPLETE and visitors
        if not completed_campaigns:
            print("\nMETHOD 2: Searching for elements with COMPLETE status...")
            elements_with_complete = soup.find_all(string=re.compile(config['campaign_status'], re.IGNORECASE))
            print(f"Found {len(elements_with_complete)} elements containing '{config['campaign_status']}'")
            
            for element in elements_with_complete:
                parent = element.find_parent()
                if parent:
                    parent_text = parent.get_text()
                    if 'visitors' in parent_text.lower():
                        print(f"Found element with COMPLETE and visitors: {parent_text[:200]}...")
                        
                        # Look for assign link in this context
                        assign_link = parent.find('a', href=lambda href: href and '/adverts/assign/' in href)
                        if assign_link:
                            campaign_id_match = re.search(r'/adverts/assign/(\d+)/', assign_link['href'])
                            if campaign_id_match:
                                campaign_id = campaign_id_match.group(1)
                                completed_campaigns.append({
                                    'id': campaign_id,
                                    'assign_url': f"https://adsha.re{assign_link['href']}",
                                })
                                print(f"✓ Found {config['campaign_status']} campaign {campaign_id}")
                                break
        
        return completed_campaigns
        
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        import traceback
        traceback.print_exc()
        return []

def assign_visitors(session, assign_url, config, dry_run=False):
    """Submits the form to assign more visitors to a campaign."""
    try:
        if dry_run:
            print(f"  [DRY RUN] Would assign {config['visitors_per_campaign']} visitors")
            return True

        print(f"  Navigating to: {assign_url}")
        response = session.get(assign_url, timeout=config['request_timeout'])
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find form
        form = soup.find('form')
        if not form:
            print("  ✗ Could not find assignment form")
            return False

        # Get form action
        action_url = form.get('action', '')
        if not action_url.startswith('http'):
            action_url = f"https://adsha.re{action_url}"
            
        print(f"  Form action: {action_url}")

        # Extract campaign ID
        campaign_id_match = re.search(r'/assign/(\d+)/', assign_url)
        campaign_id = campaign_id_match.group(1) if campaign_id_match else "unknown"
        
        # Prepare payload
        payload = {
            'vis': str(config['visitors_per_campaign']),
            'bid': config['bid_amount'],
            'spe': config['campaign_speed'],
            'txt': config['text_ads'],
            'url': config['url_ads'],
            'aid': campaign_id,
        }

        print(f"  Submitting form for campaign {campaign_id}...")
        
        submit_response = session.post(action_url, data=payload, timeout=config['request_timeout'])
        submit_response.raise_for_status()
        
        print(f"  ✓ Successfully assigned {config['visitors_per_campaign']} visitors to campaign {campaign_id}")
        return True
            
    except Exception as e:
        print(f"  ✗ Failed to assign visitors: {e}")
        return False

def run_daily_assignment():
    """Main function to find and reactivate completed campaigns."""
    config = load_config()
    
    # Display current time
    ist = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist)
    print(f"--- Starting Daily Visitor Assignment at {current_time_ist:%Y-%m-%d %H:%M:%S} IST ---")
    print(f"Configuration: {config['visitors_per_campaign']} visitors, {config['max_campaigns_per_run']} max campaigns, status: {config['campaign_status']}")

    # Login
    session = get_session(config['username'], config['password'])
    if not session:
        print("✗ Could not establish session")
        return

    # Find campaigns
    print("Searching for campaigns...")
    completed_campaigns = get_completed_campaigns(session, config)

    if not completed_campaigns:
        print(f"✗ No {config['campaign_status']} campaigns found to reactivate")
        return
        
    # Process campaigns
    campaigns_to_process = completed_campaigns[:config['max_campaigns_per_run']]
    successful_assignments = 0
    
    print(f"✓ Found {len(completed_campaigns)} campaigns, processing {len(campaigns_to_process)}")
    
    for campaign in campaigns_to_process:
        print(f"\nAttempting to reactivate campaign {campaign['id']}...")
        
        if assign_visitors(session, campaign['assign_url'], config):
            successful_assignments += 1
            print(f"✓ Successfully reactivated campaign {campaign['id']}")
        else:
            print(f"✗ Failed to reactivate campaign {campaign['id']}")

    print(f"\n--- Daily Visitor Assignment Complete ---")
    print(f"Processed: {len(campaigns_to_process)} campaigns")
    print(f"Successful: {successful_assignments} assignments")

if __name__ == "__main__":
    run_daily_assignment()
