#!/usr/bin/env python3
"""
AdShare Daily Visitor Assigner
Runs once daily to find completed campaigns and assign new visitors.
"""
import os
import re
import time
import random
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
    'campaign_speed': '2',  # 'Faster - Revisit in 12 hours'
    'text_ads': '0',
    'url_ads': '0',
    'bid_amount': '0',
    'request_timeout': 15,
    'campaign_status': 'COMPLETE',  # Status to look for
}

def load_config():
    """Load configuration from environment variables with defaults."""
    config = DEFAULT_CONFIG.copy()
    
    # Override with environment variables if they exist
    config['username'] = os.environ.get('ADSHARE_USERNAME', config['username'])
    config['password'] = os.environ.get('ADSHARE_PASSWORD', config['password'])
    config['adverts_url'] = os.environ.get('ADSHARE_ADVERTS_URL', config['adverts_url'])
    config['visitors_per_campaign'] = int(os.environ.get('ADSHARE_VISITORS_PER_CAMPAIGN', config['visitors_per_campaign']))
    config['max_campaigns_per_run'] = int(os.environ.get('ADSHARE_MAX_CAMPAIGNS', config['max_campaigns_per_run']))
    config['campaign_speed'] = os.environ.get('ADSHARE_CAMPAIGN_SPEED', config['campaign_speed'])
    config['request_timeout'] = int(os.environ.get('ADSHARE_REQUEST_TIMEOUT', config['request_timeout']))
    config['campaign_status'] = os.environ.get('ADSHARE_CAMPAIGN_STATUS', config['campaign_status'])
    
    return config

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='AdShare Daily Visitor Assigner')
    parser.add_argument('--username', help='AdShare username')
    parser.add_argument('--password', help='AdShare password')
    parser.add_argument('--visitors', type=int, help='Number of visitors to assign per campaign')
    parser.add_argument('--max-campaigns', type=int, help='Maximum number of campaigns to process')
    parser.add_argument('--speed', choices=['1', '2', '3'], help='Campaign speed (1=Slow, 2=Faster, 3=Fastest)')
    parser.add_argument('--timeout', type=int, help='Request timeout in seconds')
    parser.add_argument('--status', help='Campaign status to look for (default: COMPLETE)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without making changes')
    
    return parser.parse_args()

def get_completed_campaigns(session, config):
    """Finds campaigns marked with specified status that can have visitors assigned."""
    try:
        response = session.get(config['adverts_url'], timeout=config['request_timeout'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        completed_campaigns = []

        # A campaign block is a div with a border style
        campaign_blocks = soup.find_all('div', style=lambda s: s and 'border' in s)

        for block in campaign_blocks:
            # Look for campaigns with the specified status
            if config['campaign_status'].lower() in block.get_text().lower():
                assign_link = block.find('a', href=lambda href: href and '/adverts/assign/' in href)
                if assign_link:
                    campaign_id_match = re.search(r'/assign/(\d+)/', assign_link['href'])
                    if campaign_id_match:
                        completed_campaigns.append({
                            'id': campaign_id_match.group(1),
                            'assign_url': f"https://adsha.re{assign_link['href']}",
                        })
                        print(f"Found {config['campaign_status']} campaign {campaign_id_match.group(1)} to reactivate.")
        return completed_campaigns
    except requests.exceptions.RequestException as e:
        print(f"Network error getting campaigns: {e}")
    except Exception as e:
        print(f"An error occurred while getting campaigns: {e}")
    return []

def assign_visitors(session, assign_url, config, dry_run=False):
    """Submits the form to assign more visitors to a campaign."""
    try:
        if dry_run:
            print(f"  [DRY RUN] Would assign {config['visitors_per_campaign']} visitors to campaign")
            return True

        response = session.get(assign_url, timeout=config['request_timeout'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        form = soup.find('form')
        if not form:
            print("  Could not find assignment form.")
            return False

        action_url = form.get('action')
        campaign_id = assign_url.split('/')[4]
        
        payload = {
            'vis': str(config['visitors_per_campaign']),
            'bid': config['bid_amount'],
            'spe': config['campaign_speed'],
            'txt': config['text_ads'],
            'url': config['url_ads'],
            'aid': campaign_id,
        }

        submit_response = session.post(action_url, data=payload, timeout=config['request_timeout'])
        submit_response.raise_for_status()
        print(f"  Successfully submitted assignment of {config['visitors_per_campaign']} visitors.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  Failed to assign visitors: {e}")
        return False

def run_daily_assignment():
    """Main function to find and reactivate completed campaigns."""
    # Load configuration
    config = load_config()
    args = parse_arguments()
    
    # Override config with command line arguments
    if args.username:
        config['username'] = args.username
    if args.password:
        config['password'] = args.password
    if args.visitors:
        config['visitors_per_campaign'] = args.visitors
    if args.max_campaigns:
        config['max_campaigns_per_run'] = args.max_campaigns
    if args.speed:
        config['campaign_speed'] = args.speed
    if args.timeout:
        config['request_timeout'] = args.timeout
    if args.status:
        config['campaign_status'] = args.status

    # Display current time in IST for verification
    ist = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist)
    print(f"--- Starting Daily Visitor Assignment at {current_time_ist:%Y-%m-%d %H:%M:%S} IST ---")
    print(f"Configuration: {config['visitors_per_campaign']} visitors, {config['max_campaigns_per_run']} max campaigns, status: {config['campaign_status']}")

    # Login
    session = get_session(config['username'], config['password'])
    if not session:
        print("Could not establish a session. Exiting.")
        return

    # Find campaigns
    completed_campaigns = get_completed_campaigns(session, config)

    if not completed_campaigns:
        print(f"No {config['campaign_status']} campaigns found to reactivate. Nothing to do.")
        return
        
    # Process campaigns (up to max limit)
    campaigns_to_process = completed_campaigns[:config['max_campaigns_per_run']]
    successful_assignments = 0
    
    for campaign in campaigns_to_process:
        print(f"\nAttempting to reactivate campaign {campaign['id']}...")
        
        if assign_visitors(session, campaign['assign_url'], config, dry_run=args.dry_run):
            successful_assignments += 1
            print(f"Successfully assigned {config['visitors_per_campaign']} visitors to campaign {campaign['id']}.")
        else:
            print(f"Failed to assign visitors to campaign {campaign['id']}.")

    print(f"\n--- Daily Visitor Assignment Finished ---")
    print(f"Processed: {len(campaigns_to_process)} campaigns")
    print(f"Successful: {successful_assignments} assignments")

if __name__ == "__main__":
    run_daily_assignment()
