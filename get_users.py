import json
import time
import sys
import os
from seleniumbase import sb_cdp
from selenium.webdriver.chrome.options import Options

def get_h1_leaderboard_usernames(num_users):
    url = "https://hackerone.com/leaderboard/reputation?year=2026&quarter=1&owasp=a1&country=US&assetType=WEB_APP&tab=all&userTypeTab=individual"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    # Initialize SeleniumBase with UC Mode
    sb = sb_cdp.Chrome(url, use_chromium=True)
    
    try:
        print(f"[*] Navigating to HackerOne...")
        sb.sleep(5) # Initial wait for page load
        
        # Handle CAPTCHA if it exists
        sb.solve_captcha()
        
        print("[*] Page loaded. Scrolling to bottom to trigger table rendering...")
        # Force the virtualized table to load all rows by scrolling
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sb.sleep(3)
        sb.execute_script("window.scrollTo(0, 0);") # Scroll back up
        sb.sleep(2)

        print("[*] Extracting usernames via JavaScript...")
        
        # We use JavaScript to grab the handles directly. 
        # This bypasses the 'visibility' requirement that caused your error.
        js_code = """
            const elements = document.querySelectorAll('a.daisy-link.routerlink.daisy-link--black');
            return Array.from(elements).map(el => el.innerText.trim());
        """
        
        raw_names = sb.execute_script(js_code)
        
        # Filter duplicates and navigational noise
        usernames = []
        junk = ["Log in", "Sign up", "View profile", "HackerOne"]
        
        for name in raw_names:
            if name and name not in junk and name not in usernames:
                usernames.append(name)
            if len(usernames) >= num_users:
                break
        
        return usernames
    finally:
        sb.sleep(3)