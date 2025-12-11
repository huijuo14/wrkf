#!/usr/bin/env python3
"""
AdShare Dynamic Login & Session Manager
Establishes and maintains a logged-in session for AdShare automation scripts.
Uses Netscape cookie format for compatibility with other tools.
"""
import os
import time
import sys
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
            print(f"Session validation failed: {e}. Proceeding to re-login.")
    
    # Perform login
    print("Performing dynamic login...")
    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1} of 3...")
            
            # Get login page
            response = session.get(f"{BASE_URL}/login", timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find login form
            login_form = soup.find('form')
            if not login_form:
                raise ValueError("Could not find login form.")
            
            # Extract form action
            action = login_form.get('action')
            if action:
                login_action_url = f"{BASE_URL}{action}" if action.startswith('/') else action
            else:
                login_action_url = f"{BASE_URL}/login"
            
            # Find form inputs - more flexible approach
            inputs = login_form.find_all('input')
            payload = {}
            
            for inp in inputs:
                name = inp.get('name')
                if name:
                    inp_type = inp.get('type', '').lower()
                    inp_value = inp.get('value', '')
                    
                    # Fill in credentials
                    if inp_type == 'email' or 'email' in name.lower() or inp_value == 'Email Address':
                        payload[name] = username
                    elif inp_type == 'password' or 'password' in name.lower() or inp_value == 'Password':
                        payload[name] = password
                    elif inp_type not in ['submit', 'button']:
                        # Preserve other fields
                        payload[name] = inp_value
            
            # Fallback if we couldn't find fields
            if not payload:
                email_input = login_form.find('input', {'type': 'email'}) or \
                             login_form.find('input', {'name': 'email'}) or \
                             login_form.find('input', {'placeholder': 'Email'})
                password_input = login_form.find('input', {'type': 'password'}) or \
                                login_form.find('input', {'name': 'password'}) or \
                                login_form.find('input', {'placeholder': 'Password'})
                
                if email_input and password_input:
                    payload = {
                        email_input.get('name'): username,
                        password_input.get('name'): password,
                    }
                else:
                    raise ValueError("Could not identify email/password fields.")
            
            print(f"Logging in to: {login_action_url}")
            
            # Submit login form
            login_response = session.post(
                login_action_url, 
                data=payload, 
                timeout=15,
                allow_redirects=True
            )
            login_response.raise_for_status()
            
            # Check if login was successful
            if 'adverts' in login_response.url or 'account' in login_response.url:
                print("✓ Login successful!")
                
                # Save cookies in Netscape format
                save_cookies(session.cookies)
                
                # Verify we can access protected content
                verify_response = session.get(f"{BASE_URL}/account", timeout=10)
                if verify_response.status_code == 200:
                    print("✓ Account page accessible - session confirmed")
                return session
            
            # Check for common error indicators
            soup = BeautifulSoup(login_response.text, 'html.parser')
            error_messages = soup.find_all(class_=['error', 'alert', 'danger', 'warning'])
            if error_messages:
                print(f"Login may have failed. Errors found: {[e.text[:50] for e in error_messages]}")
            
            print(f"Login attempt {attempt + 1} may have failed. Retrying in 2 seconds...")
            time.sleep(2)
            
        except requests.exceptions.RequestException as e:
            print(f"Login attempt {attempt + 1} failed with network error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            import traceback
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
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
