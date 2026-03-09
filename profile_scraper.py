#!/usr/bin/env python3
import json
import time
import sys
from seleniumbase import sb_cdp

def scrape_h1_profiles(usernames):
    """
    Takes a list of HackerOne usernames (or a JSON string),
    scrapes their profile pages, and returns a list of dictionaries.
    Extracts: name, location, joined_date, socials, bio, thanks_count,
              signal, signal_percentile, impact, impact_percentile,
              reputation, rank, streak_months, completed_pentests,
              vulnerabilities_found, contributions.
    """
    if isinstance(usernames, str):
        try:
            usernames = json.loads(usernames)
        except json.JSONDecodeError:
            print("[!] Invalid JSON string provided", file=sys.stderr)
            return []

    if not isinstance(usernames, list):
        print("[!] Input must be a list of usernames", file=sys.stderr)
        return []

    results = []
    total = len(usernames)

    for idx, username in enumerate(usernames):
        print(f"[*] Processing {username} ({idx+1}/{total})", file=sys.stderr)
        url = f"https://hackerone.com/{username}?type=user"
        sb = None
        try:
            sb = sb_cdp.Chrome(url, use_chromium=True)
            sb.sleep(5)
            sb.solve_captcha()

            # Scroll to trigger lazy content
            sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            sb.sleep(2)
            sb.execute_script("window.scrollTo(0, 0);")
            sb.sleep(1)

            js_code = """
                const data = {};

                // ----- Full name (first part before any parenthesis) -----
                const nameElem = document.querySelector('strong.text-center');
                if (nameElem) {
                    let fullText = nameElem.innerText.trim();
                    // Often "Aidan (m0chan)" – take part before '('
                    const parenIndex = fullText.indexOf('(');
                    data.name = parenIndex > 0 ? fullText.substring(0, parenIndex).trim() : fullText;
                } else {
                    data.name = null;
                }

                // ----- Location -----
                const locationElem = document.querySelector('div.daisy-helper-text');
                // The location is the first daisy-helper-text after the follow section
                // We'll search for a div containing a location name (not "Joined")
                const allHelper = document.querySelectorAll('div.daisy-helper-text');
                for (let el of allHelper) {
                    const txt = el.innerText.trim();
                    if (txt && !txt.startsWith('Joined') && !txt.includes('thanks') && !txt.match(/^[0-9]+$/)) {
                        data.location = txt;
                        break;
                    }
                }
                if (!data.location) data.location = null;

                // ----- Joined date -----
                const joinedElem = Array.from(document.querySelectorAll('div.daisy-helper-text')).find(el => el.innerText.trim().startsWith('Joined'));
                data.joined_date = joinedElem ? joinedElem.innerText.trim() : null;

                // ----- Social links -----
                const socialLinks = [];
                const socialContainer = document.querySelector('.Spacing-module_mt-spacing-md__p99vF');
                if (socialContainer) {
                    const anchors = socialContainer.querySelectorAll('a[href]');
                    anchors.forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && !socialLinks.includes(href) && !href.startsWith('/')) {
                            socialLinks.push(href);
                        }
                    });
                }
                data.socials = socialLinks;

                // ----- Bio (from About section) -----
                const aboutCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('About'));
                if (aboutCard) {
                    const bioPara = aboutCard.querySelector('.interactive_markdown__p');
                    data.bio = bioPara ? bioPara.innerText.trim() : null;
                } else {
                    data.bio = null;
                }

                // ----- Thanks count -----
                const thanksElem = document.querySelector('.card__heading span')?.innerText;
                if (thanksElem && thanksElem.includes('thanks received')) {
                    const match = thanksElem.match(/(\\d+)/);
                    data.thanks_count = match ? parseInt(match[0]) : null;
                } else {
                    // fallback
                    const thanksText = document.body.innerText.match(/(\\d+)\\s+thanks received/);
                    data.thanks_count = thanksText ? parseInt(thanksText[1]) : null;
                }

                // ----- Stats (Signal, Impact, Reputation, Rank) -----
                const statsCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('Stats'));
                if (statsCard) {
                    const rows = statsCard.querySelectorAll('.sc-aXZVg.cWletH .sc-aXZVg.ilPZY'); // each stat row
                    const stats = {};
                    rows.forEach(row => {
                        const value = row.querySelector('h4')?.innerText.trim();
                        const label = row.querySelector('.daisy-helper-text')?.innerText.trim() || row.querySelector('span.inline-help')?.innerText.trim();
                        if (value && label) {
                            if (label === 'Signal') stats.signal = value;
                            else if (label === 'Percentile' && stats.signal) stats.signal_percentile = value;
                            else if (label === 'Impact') stats.impact = value;
                            else if (label === 'Percentile' && stats.impact) stats.impact_percentile = value;
                            else if (label === 'Reputation') stats.reputation = parseInt(value.replace(',',''));
                            else if (label === 'Rank') stats.rank = value.replace(/[^0-9]/g, '');
                        }
                    });
                    data.signal = stats.signal || null;
                    data.signal_percentile = stats.signal_percentile || null;
                    data.impact = stats.impact || null;
                    data.impact_percentile = stats.impact_percentile || null;
                    data.reputation = stats.reputation || null;
                    data.rank = stats.rank || null;
                } else {
                    data.signal = data.signal_percentile = data.impact = data.impact_percentile = data.reputation = data.rank = null;
                }

                // ----- Streak -----
                const streakCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('Streak'));
                if (streakCard) {
                    const streakText = streakCard.querySelector('h2.Heading-module_u1-heading--300__FFW9M')?.innerText;
                    const match = streakText ? streakText.match(/(\\d+)/) : null;
                    data.streak_months = match ? parseInt(match[0]) : null;
                } else {
                    data.streak_months = null;
                }

                // ----- Pentest stats -----
                const pentestCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('Pentest stats'));
                if (pentestCard) {
                    const completed = pentestCard.querySelector('.profile-stats-amount span.daisy-h4')?.innerText;
                    data.completed_pentests = completed ? parseInt(completed) : null;
                } else {
                    data.completed_pentests = null;
                }

                // ----- Credits (Vulnerabilities found) -----
                const creditsCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('Credits'));
                if (creditsCard) {
                    const vulns = creditsCard.querySelector('.profile-stats-amount span.daisy-h4')?.innerText;
                    data.vulnerabilities_found = vulns ? parseInt(vulns) : null;
                } else {
                    data.vulnerabilities_found = null;
                }

                // ----- Contributions table -----
                const rows = [];
                const thanksCard = Array.from(document.querySelectorAll('.card')).find(card => card.querySelector('.card__heading')?.innerText.includes('Thanks'));
                if (thanksCard) {
                    const items = thanksCard.querySelectorAll('.spec-thanks-item');
                    items.forEach(item => {
                        const programElem = item.querySelector('.sc-aXZVg.gA-DtUp .sc-aXZVg.kGRXWp');
                        const program = programElem ? programElem.innerText.trim() : null;
                        const validClosed = item.querySelector('.sc-aXZVg.jYAlVg')?.innerText.replace(/\\s+/g, '') || null; // e.g., "418/549"
                        const rep = item.querySelector('.sc-aXZVg.beuQBY')?.innerText.trim() || null;
                        const rank = item.querySelector('.sc-aXZVg.cVXFhP')?.innerText.replace(/[^0-9]/g, '') || null;
                        if (program || validClosed || rep || rank) {
                            rows.push({ program, valid_closed: validClosed, rep, rank });
                        }
                    });
                }
                data.contributions = rows;

                return data;
            """
            profile_data = sb.execute_script(js_code)
            profile_data['username'] = username
            results.append(profile_data)

        except Exception as e:
            print(f"[!] Error processing {username}: {e}", file=sys.stderr)
            results.append({'username': username, 'error': str(e)})

        finally:
            if sb:
                sb.sleep(2)

        time.sleep(3)   # polite delay

    return results