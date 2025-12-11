#!/usr/bin/env python3
"""
AdShare Dynamic Login & Session Manager
Establishes and maintains a logged-in session for AdShare automation scripts.
Loads cookies from session-cookies.zip for security.
"""
import os
import pickle
import time
import zipfile
import tempfile
import shutil
import requests
from bs4 import BeautifulSoup

COOKIE_ZIP_FILE = "session-cookies.zip"
COOKIE_FILE_NAME = "session_cookies.pkl"  # File inside the zip
BASE_URL = "https://adsha.re"

def load_cookies():
    """Load cookies from the zip file if it exists."""
    if os.path.exists(COOKIE_ZIP_FILE):
        try:
            # Extract the cookie file from zip
            with zipfile.ZipFile(COOKIE_ZIP_FILE, 'r') as zip_ref:
                # Create a temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extract the cookie file
                    zip_ref.extract(COOKIE_FILE_NAME, temp_dir)
                    cookie_path = os.path.join(temp_dir, COOKIE_FILE_NAME)
                    
                    # Load the cookies
                    with open(cookie_path, 'rb') as f:
                        cookies = pickle.load(f)
                    
                    print("Cookies loaded from zip archive.")
                    return cookies
        except (zipfile.BadZipFile, KeyError, FileNotFoundError) as e:
            print(f"Could not extract cookies from zip: {e}")
        except Exception as e:
            print(f"Error loading cookies: {e}")
    else:
        print(f"Cookie zip file '{COOKIE_ZIP_FILE}' not found.")
    return None

def save_cookies(jar):
    """Save cookies to a zip file for security."""
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as tmp:
            temp_cookie_path = tmp.name
            pickle.dump(jar, tmp)
        
        # Create or update the zip file
        with zipfile.ZipFile(COOKIE_ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            zip_ref.write(temp_cookie_path, COOKIE_FILE_NAME)
        
        # Clean up temporary file
        os.unlink(temp_cookie_path)
        
        print(f"Session cookies saved to '{COOKIE_ZIP_FILE}'.")
    except Exception as e:
        print(f"Error saving cookies to zip: {e}")

def get_session(username, password):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    cookies = load_cookies()
    if cookies:
        session.cookies.update(cookies)
        print("Loaded cookies from zip. Verifying session...")
        try:
            response = session.get(f"{BASE_URL}/adverts", timeout=15)
            response.raise_for_status()
            if 'logout' in response.text.lower() or 'account' in response.text.lower():
                print("Session is valid.")
                return session
        except requests.exceptions.RequestException as e:
            print(f"Session validation failed: {e}. Proceeding to re-login.")
    
    print("Performing dynamic login...")
    for attempt in range(3):
        try:
            response = session.get(f"{BASE_URL}/login", timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            login_form = soup.find('form')
            if not login_form: 
                raise ValueError("Could not find login form.")

            action = login_form.get('action')
            login_action_url = f"{BASE_URL}{action}" if action and action.startswith('/') else action

            # Alternative: Look for input fields by type or name
            email_input = login_form.find('input', {'type': 'email'}) or \
                         login_form.find('input', {'name': 'email'}) or \
                         login_form.find('input', {'value': 'Email Address'})
            
            password_input = login_form.find('input', {'type': 'password'}) or \
                            login_form.find('input', {'name': 'password'}) or \
                            login_form.find('input', {'value': 'Password'})

            if not email_input or not password_input:
                # Try to find by placeholder or other attributes
                for inp in login_form.find_all('input'):
                    if 'email' in str(inp).lower():
                        email_input = inp
                    if 'password' in str(inp).lower():
                        password_input = inp
            
            if not email_input or not password_input:
                raise ValueError("Could not find email or password fields.")
            
            payload = {
                email_input.get('name'): username,
                password_input.get('name'): password,
            }

            # Add any hidden inputs
            for hidden in login_form.find_all('input', {'type': 'hidden'}):
                name = hidden.get('name')
                value = hidden.get('value', '')
                if name and name not in payload:
                    payload[name] = value

            login_response = session.post(login_action_url, data=payload, timeout=15)
            login_response.raise_for_status()

            if 'adverts' in login_response.url or 'account' in login_response.url:
                print("Login successful.")
                save_cookies(session.cookies)
                return session
            
            # Check for error messages
            error_soup = BeautifulSoup(login_response.text, 'html.parser')
            error_div = error_soup.find('div', class_='error') or error_soup.find('div', class_='alert')
            if error_div:
                print(f"Login error: {error_div.get_text(strip=True)}")
            
            print(f"Login attempt {attempt+1} may have failed. Retrying...")
            time.sleep(2)

        except requests.exceptions.RequestException as e:
            print(f"Login attempt {attempt + 1} failed with a network error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            time.sleep(5)
            
    print("All login attempts failed.")
    return None

# Helper function to create initial zip file
def create_zip_from_cookies(cookie_file_path="session_cookies.pkl"):
    """Convert existing cookie file to zip format."""
    if os.path.exists(cookie_file_path):
        try:
            save_cookies(pickle.load(open(cookie_file_path, 'rb')))
            print(f"Converted {cookie_file_path} to {COOKIE_ZIP_FILE}")
        except Exception as e:
            print(f"Conversion failed: {e}")
    else:
        print(f"No existing cookie file at {cookie_file_path}")

# For backward compatibility
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--convert":
        create_zip_from_cookies()
    else:
        print("AdShare Session Manager")
        print("Usage: python script.py --convert  # Convert old cookie file to zip")
        print("Or use get_session(username, password) function in your code.")
