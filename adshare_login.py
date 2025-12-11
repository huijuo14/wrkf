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
import zlib
import gzip
import io
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

def decode_compressed_response(response):
    """Handle various types of compressed responses."""
    content = response.content
    
    # Check if it's gzipped
    if response.headers.get('Content-Encoding') == 'gzip':
        try:
            return gzip.decompress(content).decode('utf-8')
        except:
            pass
    
    # Try to decode as UTF-8 first
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # Try other common encodings
    encodings = ['latin-1', 'iso-8859-1', 'cp1252']
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    
    # If all else fails, return as is (will likely fail but at least we tried)
    return content.decode('utf-8', errors='ignore')

def get_session(username, password):
    """Get authenticated session with AdShare."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",  # Tell server we accept compression
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
            
            # Get login page with proper headers
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }
            
            response = session.get(f"{BASE_URL}/login", timeout=15, headers=headers)
            response.raise_for_status()
            
            # Debug: Print response info
            print(f"Response status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            print(f"Content-Encoding: {response.headers.get('Content-Encoding', 'none')}")
            print(f"Content length: {len(response.content)} bytes")
            
            # Handle compressed response
            html_content = decode_compressed_response(response)
            
            # Check if we got valid HTML
            if len(html_content) < 100 or '<html' not in html_content.lower():
                print(f"Warning: Response doesn't look like HTML. First 200 chars: {html_content[:200]}")
                # Try without compression
                headers['Accept-Encoding'] = 'identity'
                response = session.get(f"{BASE_URL}/login", timeout=15, headers=headers)
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find login form - simple approach first
            login_form = soup.find('form')
            
            if not login_form:
                # Try to find any form
                all_forms = soup.find_all('form')
                if all_forms:
                    login_form = all_forms[0]
                    print(f"Using first form found (total forms: {len(all_forms)})")
            
            if not login_form:
                # Save the HTML to file for debugging
                debug_file = f"login_debug_{attempt}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"Saved response to {debug_file} for debugging")
                print(f"Page title: {soup.title}")
                raise ValueError("Could not find login form.")
            
            print(f"Found login form")
            
            # Extract form action
            action = login_form.get('action')
            if action:
                if action.startswith('/'):
                    login_action_url = f"{BASE_URL}{action}"
                elif action.startswith('http'):
                    login_action_url = action
                else:
                    login_action_url = f"{BASE_URL}/{action}"
            else:
                login_action_url = f"{BASE_URL}/login"
            
            print(f"Login action URL: {login_action_url}")
            
            # Find email and password inputs - use original logic
            email_input = login_form.find('input', {'value': 'Email Address'})
            if not email_input:
                email_input = login_form.find('input', {'placeholder': 'Email Address'})
            if not email_input:
                email_input = login_form.find('input', {'type': 'email'})
            if not email_input:
                # Find any input that looks like email
                for inp in login_form.find_all('input'):
                    if inp.get('name', '').lower() in ['email', 'username', 'user']:
                        email_input = inp
                        break
            
            password_input = login_form.find('input', {'value': 'Password'})
            if not password_input:
                password_input = login_form.find('input', {'placeholder': 'Password'})
            if not password_input:
                password_input = login_form.find('input', {'type': 'password'})
            if not password_input:
                # Find any input that looks like password
                for inp in login_form.find_all('input'):
                    if inp.get('name', '').lower() in ['password', 'pass', 'pwd']:
                        password_input = inp
                        break

            if not email_input or not password_input:
                raise ValueError("Could not find email or password fields.")
            
            print(f"Found email field: name='{email_input.get('name')}'")
            print(f"Found password field: name='{password_input.get('name')}'")
            
            # Prepare payload - ORIGINAL LOGIC
            payload = {
                email_input.get('name'): username,
                password_input.get('name'): password,
            }
            
            # Include any hidden fields
            for inp in login_form.find_all('input', {'type': 'hidden'}):
                name = inp.get('name')
                value = inp.get('value', '')
                if name and name not in payload:
                    payload[name] = value
            
            print(f"Submitting login with payload keys: {list(payload.keys())}")
            
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
            
            # Check if login was successful by checking final URL
            final_url = login_response.url.lower()
            success_indicators = ['adverts', 'account', 'dashboard', 'home', 'index']
            failed_indicators = ['login', 'signin', 'auth']
            
            success = any(indicator in final_url for indicator in success_indicators)
            failed = any(indicator in final_url for indicator in failed_indicators)
            
            # Also check response text
            response_text = login_response.text.lower()
            if 'logout' in response_text or 'welcome' in response_text:
                success = True
            if 'invalid' in response_text or 'incorrect' in response_text:
                failed = True
            
            if success and not failed:
                print("✓ Login successful!")
                
                # Save cookies in Netscape format
                save_cookies(session.cookies)
                
                # Quick verification
                try:
                    verify_response = session.get(f"{BASE_URL}/adverts", timeout=10)
                    if verify_response.status_code == 200:
                        print("✓ Adverts page accessible - session confirmed")
                except:
                    print("⚠ Could not verify adverts page, but session seems OK")
                
                return session
            else:
                print(f"Login may have failed. Final URL: {login_response.url}")
                if failed:
                    print("Login page detected in response")
                
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
        print("1. Check if https://adsha.re is accessible from your location")
        print("2. Verify your username and password")
        print("3. Try logging in manually first in a browser")
        print("4. Check if there's a CAPTCHA or 2FA enabled")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()
