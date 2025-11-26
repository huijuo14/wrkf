#!/usr/bin/env python3
"""
AdShare Daily Visitor Assigner - Fixed Campaign Detection
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

def get_completed_campaigns(session, config):
    """Finds campaigns marked with specified status that can have visitors assigned."""
    try:
        response = session.get(config['adverts_url'], timeout=config['request_timeout'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        completed_campaigns = []

        print("DEBUG: Searching for campaigns...")
        
        # METHOD 1: Look for divs containing "My Advert" text (more reliable)
        all_divs = soup.find_all('div')
        campaign_blocks = []
        
        for div in all_divs:
            div_text = div.get_text()
            if 'My Advert' in div_text and config['campaign_status'].lower() in div_text.lower():
                campaign_blocks.append(div)
                print(f"DEBUG: Found campaign block with 'My Advert' and '{config['campaign_status']}'")
        
        print(f"DEBUG: Found {len(campaign_blocks)} campaign blocks using 'My Advert' method")
        
        # If METHOD 1 fails, try METHOD 2: Look for any div with border
        if not campaign_blocks:
            campaign_blocks = soup.find_all('div', style=lambda s: s and 'border' in str(s))
            print(f"DEBUG: Found {len(campaign_blocks)} campaign blocks using border method")
        
        # If METHOD 2 fails, try METHOD 3: Look for divs with specific classes or structure
        if not campaign_blocks:
            # Look for any div that might contain campaign info
            potential_blocks = soup.find_all('div')
            for block in potential_blocks:
                block_text = block.get_text()
                if config['campaign_status'].lower() in block_text.lower() and 'visitors' in block_text.lower():
                    campaign_blocks.append(block)
                    print(f"DEBUG: Found potential campaign block with status and visitors")
            
            print(f"DEBUG: Found {len(campaign_blocks)} campaign blocks using fallback method")

        for block in campaign_blocks:
            block_text = block.get_text()
            print(f"DEBUG: Block text preview: {block_text[:200]}...")
            
            # Verify this is actually a campaign block with COMPLETE status
            if config['campaign_status'].lower() in block_text.lower():
                print(f"DEBUG: Confirmed {config['campaign_status']} status in block")
                
                # Find the "Assign More Visitors" link
                assign_link = block.find('a', href=lambda href: href and '/adverts/assign/' in href)
                if assign_link:
                    print(f"DEBUG: Found assign link: {assign_link['href']}")
                    
                    # Extract campaign ID
                    campaign_id_match = re.search(r'/adverts/assign/(\d+)/', assign_link['href'])
                    if campaign_id_match:
                        campaign_id = campaign_id_match.group(1)
                        completed_campaigns.append({
                            'id': campaign_id,
                            'assign_url': f"https://adsha.re{assign_link['href']}",
                        })
                        print(f"✓ Found {config['campaign_status']} campaign {campaign_id} to reactivate.")
                    else:
                        print("✗ Could not extract campaign ID from link")
                else:
                    print("✗ No assign link found in this block")
                    
                    # Debug: print all links in this block
                    all_links = block.find_all('a')
                    print(f"DEBUG: All links in block: {[link.get('href', '') for link in all_links]}")
            else:
                print(f"✗ Block does not contain '{config['campaign_status']}' status")
                
        return completed_campaigns
        
    except Exception as e:
        print(f"Error getting campaigns: {e}")
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
        
        # Find form - try multiple selectors
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
        print(f"✗ No {config['campaign_status']} campaigns found")
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
