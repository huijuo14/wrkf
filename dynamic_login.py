#!/usr/bin/env python3
"""
Dynamic Login Script for AdShare
Handles dynamic form fields and URL changes automatically
"""

import requests
from bs4 import BeautifulSoup
import os
import pickle
from requests.cookies import RequestsCookieJar

def load_cookies():
    """Load cookies from file if it exists"""
    if os.path.exists('session_cookies.pkl'):
        try:
            with open('session_cookies.pkl', 'rb') as f:
                jar = pickle.load(f)
                return jar
        except Exception as e:
            print(f"Error loading cookies: {e}")
    return None

def save_cookies(jar):
    """Save cookies to file"""
    try:
        with open('session_cookies.pkl', 'wb') as f:
            pickle.dump(jar, f)
        print("Cookies saved to session_cookies.pkl")
    except Exception as e:
        print(f"Error saving cookies: {e}")

def dynamic_login(username, password):
    """Perform login with dynamic form field detection"""
    session = requests.Session()
    
    # Try to load existing cookies first
    loaded_cookies = load_cookies()
    if loaded_cookies:
        session.cookies = loaded_cookies
        print("Loaded existing cookies")
        
        # Test if session is still valid
        test_response = session.get("https://adsha.re/adverts")
        if test_response.status_code == 200:
            return session
    
    print("No existing cookies or session invalid, performing fresh login")
    
    # Fetch login page to get dynamic elements
    response = session.get("https://adsha.re/login")
    if response.status_code != 200:
        print("Failed to fetch login page")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the login form
    login_form = soup.find('form')
    if not login_form:
        print("Could not find login form")
        return None
    
    # Get the actual form action URL
    form_action = login_form.get('action')
    if form_action.startswith('/'):
        login_url = "https://adsha.re" + form_action
    elif not form_action.startswith('http'):
        login_url = "https://adsha.re/" + form_action
    else:
        login_url = form_action
    
    # Find email and password fields by analyzing their properties
    email_field = None
    password_field = None
    
    all_inputs = login_form.find_all('input')
    for inp in all_inputs:
        inp_type = inp.get('type', 'text')
        inp_value = inp.get('value', '')
        inp_name = inp.get('name', '')
        
        # Look for email field
        if inp_type == 'text' or inp_type == 'email':
            inp_value_lower = inp_value.lower()
            if 'email' in inp_value_lower or 'mail' in inp_value_lower or 'address' in inp_value_lower or 'email' in inp_name.lower():
                email_field = inp
        # Look for password field (has 'Password' as the value)
        elif inp_value == 'Password':
            password_field = inp

    if not email_field or not password_field:
        print("Could not find email or password fields")
        return None
    
    # Prepare login data with dynamic field names
    login_data = {
        email_field.get('name'): username,
        password_field.get('name'): password,
    }
    
    # Send login request
    login_response = session.post(login_url, data=login_data)
    
    if login_response.status_code == 200:
        print("Login successful")
        save_cookies(session.cookies)
        return session
    else:
        print(f"Login failed with status {login_response.status_code}")
        return None

if __name__ == "__main__":
    # Use your credentials
    USERNAME = "jiocloud90@gmail.com"
    PASSWORD = "@Sd2007123"
    
    session = dynamic_login(USERNAME, PASSWORD)
    if session:
        # Test access to adverts page
        response = session.get("https://adsha.re/adverts")
        if response.status_code == 200:
            print("Successfully accessed adverts page after login")
        else:
            print(f"Failed to access adverts page: {response.status_code}")
    else:
        print("Login failed")