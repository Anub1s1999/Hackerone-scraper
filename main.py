import json
import time
import sys
import os
from seleniumbase import sb_cdp
import get_users
import profile_scraper
import export_csv
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # No argument provided → use default 5
        n = 5
        print(f"No argument given. Using default value: {n}")
    else:
        try:
            n = int(sys.argv[1])
            if n <= 0:
                print("\n[!] Error: The number of users must be a positive integer.")
                print(f"    Example: python {os.path.basename(__file__)} 25")
                sys.exit(1)
            elif n>100:
                print("\n[!] Error: Maximum is 100 user")
                sys.exit(1)
        except ValueError:
            print("\n[!] Error: Please provide a valid integer.")
            print(f"    Example: python {os.path.basename(__file__)} 25")
            sys.exit(1)

    top_users = get_users.get_h1_leaderboard_usernames(n)
    each_user=profile_scraper.scrape_h1_profiles(top_users)
    
    export_csv.export_to_csv(each_user, "hackerone")
    output_file = "hackerone_users.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(top_users, f, indent=2, ensure_ascii=False)
    print(f"\n Saved usernames to {output_file}")