#!/usr/bin/env python3
"""
AdShare Dynamic Login & Session Manager
Establishes and maintains a logged-in session for AdShare automation scripts.
Uses Netscape cookie format for compatibility with other tools.
"""
import os
import time
import sys
import traceback
from http.cookiejar import MozillaCookieJar
import requests
from bs4 import BeautifulSoup

COOKIE_FILE = "cookies.txt"  # Changed to .txt for Netscape format
BASE_URL = "https://adsha.re"

def load_cookies():
    """Load cookies from Netscape format file."""
    jar = MozillaCookieJar(COOKIE_FILE)
    if os.path.exists(COOKIE_FILE):
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
            print(f"Loaded {len(jar)} cookies from {COOKIE_FILE}")
            return jar
        except Exception as e:
            print(f"Could not load cookies: {e}")
    return None

def save_cookies(jar):
    """Save cookies in Netscape format (compatible with curl, wget, etc.)."""
    try:
        # Convert requests.cookies.RequestsCookieJar to MozillaCookieJar
        if not isinstance(jar, MozillaCookieJar):
            mozilla_jar = MozillaCookieJar(COOKIE_FILE)
            for cookie in jar:
                # Create a cookie with proper attributes
                mozilla_cookie = requests.cookies.create_cookie(
                    name=cookie.name,
                    value=cookie.value,
                    domain=cookie.domain,
                    path=cookie.path
                )
                mozilla_jar.set_cookie(mozilla_cookie)
            jar = mozilla_jar
        
        jar.save(ignore_discard=True, ignore_expires=True)
        print(f"Session cookies saved to {COOKIE_FILE} (Netscape format)")
        print(f"Total cookies saved: {len(jar)}")
        
        # Display saved cookies for verification
        print("\nSaved cookies:")
        for cookie in jar:
            print(f"  - {cookie.name}: {cookie.value[:30]}...")
        return True
    except Exception as e:
        print(f"Error saving cookies: {e}")
        return False

def get_session(username, password):
    """Get authenticated session with AdShare."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    
    # Try to load existing cookies
    cookies = load_cookies()
    if cookies:
        session.cookies.update(cookies)
        print("Loaded cookies. Verifying session...")
        try:
            response = session.get(f"{BASE_URL}/adverts", timeout=15)
            response.raise_for_status()
            
            # Check if we're logged in
            if 'logout' in response.text.lower() or 'account' in response.text.lower():
                print("✓ Session is valid (already logged in).")
                return session
            else:
                print("Session expired or invalid. Re-logging in...")
        except requests.exceptions.RequestException as e:
            print(f"Session validation failed: {e}. Proceeding to re-loggin.")
    
    # Perform login - using the original form parsing logic
    print("Performing dynamic login...")
    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1} of 3...")
            
            # Get login page
            response = session.get(f"{BASE_URL}/login", timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find login form - using multiple methods to find it
            login_form = soup.find('form')
            
            # If no form found with simple find, try more specific searches
            if not login_form:
                # Try to find form by common attributes
                login_form = soup.find('form', {'method': 'post'})
            
            if not login_form:
                # Try to find form by action attribute containing 'login'
                login_form = soup.find('form', action=lambda x: x and 'login' in x.lower())
            
            if not login_form:
                # Try to find any form that has email and password fields
                all_forms = soup.find_all('form')
                for form in all_forms:
                    # Check if form has input fields that look like login fields
                    inputs = form.find_all('input')
                    has_email = False
                    has_password = False
                    for inp in inputs:
                        inp_type = inp.get('type', '').lower()
                        inp_name = inp.get('name', '').lower()
                        if inp_type == 'email' or 'email' in inp_name:
                            has_email = True
                        if inp_type == 'password' or 'password' in inp_name:
                            has_password = True
                    if has_email and has_password:
                        login_form = form
                        break
            
            if not login_form:
                # Debug: print page to see what we're working with
                print("DEBUG: Could not find login form. Page snippet:")
                print(soup.prettify()[:1000])
                raise ValueError("Could not find login form.")
            
            print(f"Found login form with method: {login_form.get('method', 'POST')}")
            
            # Extract form action - using original logic
            action = login_form.get('action')
            if action:
                # Handle relative and absolute URLs
                if action.startswith('/'):
                    login_action_url = f"{BASE_URL}{action}"
                elif action.startswith('http'):
                    login_action_url = action
                else:
                    login_action_url = f"{BASE_URL}/{action}"
            else:
                login_action_url = f"{BASE_URL}/login"
            
            print(f"Login action URL: {login_action_url}")
            
            # Find email and password inputs - using original logic but more robust
            email_input = None
            password_input = None
            
            # Try multiple ways to find the email field
            email_candidates = [
                login_form.find('input', {'value': 'Email Address'}),
                login_form.find('input', {'placeholder': 'Email Address'}),
                login_form.find('input', {'placeholder': 'Email'}),
                login_form.find('input', {'type': 'email'}),
                login_form.find('input', {'name': 'email'}),
                login_form.find('input', {'id': 'email'}),
                login_form.find('input', {'name': 'username'}),
                login_form.find('input', {'id': 'username'})
            ]
            
            for candidate in email_candidates:
                if candidate:
                    email_input = candidate
                    break
            
            # Try multiple ways to find the password field
            password_candidates = [
                login_form.find('input', {'value': 'Password'}),
                login_form.find('input', {'placeholder': 'Password'}),
                login_form.find('input', {'type': 'password'}),
                login_form.find('input', {'name': 'password'}),
                login_form.find('input', {'id': 'password'}),
                login_form.find('input', {'name': 'pass'}),
                login_form.find('input', {'id': 'pass'})
            ]
            
            for candidate in password_candidates:
                if candidate:
                    password_input = candidate
                    break
            
            # If still not found, try to find by scanning all inputs
            if not email_input or not password_input:
                all_inputs = login_form.find_all('input')
                for inp in all_inputs:
                    inp_type = inp.get('type', '').lower()
                    inp_name = inp.get('name', '').lower()
                    inp_value = inp.get('value', '').lower()
                    inp_placeholder = inp.get('placeholder', '').lower()
                    
                    if not email_input:
                        if (inp_type == 'email' or 
                            'email' in inp_name or 
                            'email' in inp_value or 
                            'email' in inp_placeholder or
                            inp_name == 'username'):
                            email_input = inp
                    
                    if not password_input:
                        if (inp_type == 'password' or 
                            'password' in inp_name or 
                            'password' in inp_value or 
                            'password' in inp_placeholder):
                            password_input = inp
            
            if not email_input:
                raise ValueError("Could not find email field.")
            if not password_input:
                raise ValueError("Could not find password field.")
            
            print(f"Found email field: name='{email_input.get('name')}'")
            print(f"Found password field: name='{password_input.get('name')}'")
            
            # Prepare payload - include all form fields to be safe
            payload = {}
            all_form_inputs = login_form.find_all('input')
            for inp in all_form_inputs:
                inp_name = inp.get('name')
                inp_type = inp.get('type', '').lower()
                inp_value = inp.get('value', '')
                
                if inp_name and inp_type not in ['submit', 'button', 'image']:
                    # Fill in credentials for our fields
                    if inp is email_input:
                        payload[inp_name] = username
                    elif inp is password_input:
                        payload[inp_name] = password
                    else:
                        # Preserve other fields
                        payload[inp_name] = inp_value
            
            # Make sure we have the credentials in the payload
            email_field_name = email_input.get('name')
            password_field_name = password_input.get('name')
            
            if email_field_name not in payload:
                payload[email_field_name] = username
            if password_field_name not in payload:
                payload[password_field_name] = password
            
            print(f"Submitting login with {len(payload)} fields...")
            
            # Submit login form
            login_response = session.post(
                login_action_url, 
                data=payload, 
                timeout=15,
                allow_redirects=True,
                headers={
                    'Referer': f'{BASE_URL}/login',
                    'Origin': BASE_URL,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            login_response.raise_for_status()
            
            print(f"Login response status: {login_response.status_code}")
            print(f"Login response URL: {login_response.url}")
            
            # Check if login was successful
            if ('adverts' in login_response.url or 
                'account' in login_response.url or
                'dashboard' in login_response.url):
                print("✓ Login successful!")
                
                # Save cookies in Netscape format
                save_cookies(session.cookies)
                
                # Verify we can access protected content
                try:
                    verify_response = session.get(f"{BASE_URL}/account", timeout=10)
                    if verify_response.status_code == 200:
                        print("✓ Account page accessible - session confirmed")
                    else:
                        print(f"⚠ Account page returned status {verify_response.status_code}")
                except Exception as e:
                    print(f"⚠ Could not verify account page: {e}")
                
                return session
            
            # Check for error messages in response
            soup = BeautifulSoup(login_response.text, 'html.parser')
            
            # Look for common error indicators
            error_selectors = [
                '.error', '.alert-danger', '.alert-error', 
                '.text-danger', '.login-error', '.error-message',
                'div[class*="error"]', 'div[class*="alert"]'
            ]
            
            error_messages = []
            for selector in error_selectors:
                errors = soup.select(selector)
                if errors:
                    for error in errors:
                        error_text = error.get_text(strip=True)
                        if error_text and len(error_text) > 3:
                            error_messages.append(error_text)
            
            if error_messages:
                print(f"Login failed with errors: {error_messages[:3]}")
            else:
                # Check for success messages too
                success_selectors = ['.success', '.alert-success', '.text-success']
                for selector in success_selectors:
                    successes = soup.select(selector)
                    if successes:
                        print(f"Found success messages: {[s.get_text(strip=True)[:50] for s in successes[:2]]}")
            
            print(f"Login attempt {attempt + 1} may have failed. Retrying in 2 seconds...")
            time.sleep(2)
            
        except requests.exceptions.RequestException as e:
            print(f"Login attempt {attempt + 1} failed with network error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            traceback.print_exc()
            time.sleep(5)
    
    print("✗ All login attempts failed.")
    return None

def main():
    """Command-line interface."""
    if len(sys.argv) != 3:
        print("Usage: python adshare_login.py <username> <password>")
        print("Example: python adshare_login.py user@example.com mypassword123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    print("=" * 50)
    print("AdShare Login Script")
    print("=" * 50)
    print(f"URL: {BASE_URL}")
    print(f"Username: {username}")
    print(f"Cookie file: {COOKIE_FILE}")
    print("-" * 50)
    
    session = get_session(username, password)
    
    if session:
        print("\n" + "=" * 50)
        print("✓ SUCCESS: Session established!")
        print(f"Cookies saved in Netscape format to: {COOKIE_FILE}")
        print("\nYou can use these cookies with other tools:")
        print(f"  curl -b {COOKIE_FILE} {BASE_URL}/account")
        print(f"  wget --load-cookies {COOKIE_FILE} {BASE_URL}/account")
        print("=" * 50)
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("✗ FAILED: Could not establish session")
        print("\nTroubleshooting tips:")
        print("1. Check if the website is accessible")
        print("2. Verify your username and password")
        print("3. Check if there's a CAPTCHA on the login page")
        print("4. Try logging in manually first")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
