#!/usr/bin/env python3
import json
import csv
import sys

def export_to_csv(data, base_filename="hackerone"):
    """
    Writes the scraped data to CSV files for Neo4j import.
    Generates:
        {base_filename}_hackers.csv
        {base_filename}_contributions.csv
    """
    hackers_file = f"{base_filename}_hackers.csv"
    contributions_file = f"{base_filename}_contributions.csv"

    # --- Hackers CSV ---
    hunter_fieldnames = [
        'username', 'name', 'location', 'joined_date', 'socials', 'bio',
        'thanks_count', 'signal', 'signal_percentile', 'impact', 'impact_percentile',
        'reputation', 'rank', 'streak_months', 'completed_pentests',
        'vulnerabilities_found', 'contributions_count'
    ]
    with open(hackers_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=hunter_fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for hunter in data:
            if 'error' in hunter:
                continue
            row = {
                'username': hunter['username'],
                'name': hunter.get('name'),
                'location': hunter.get('location'),
                'joined_date': hunter.get('joined_date'),
                'socials': json.dumps(hunter.get('socials', []), ensure_ascii=False),
                'bio': hunter.get('bio'),
                'thanks_count': hunter.get('thanks_count'),
                'signal': hunter.get('signal'),
                'signal_percentile': hunter.get('signal_percentile'),
                'impact': hunter.get('impact'),
                'impact_percentile': hunter.get('impact_percentile'),
                'reputation': hunter.get('reputation'),
                'rank': hunter.get('rank'),
                'streak_months': hunter.get('streak_months'),
                'completed_pentests': hunter.get('completed_pentests'),
                'vulnerabilities_found': hunter.get('vulnerabilities_found'),
                'contributions_count': len(hunter.get('contributions', []))
            }
            writer.writerow(row)

    # --- Contributions CSV ---
    contrib_fieldnames = ['username', 'program', 'valid_closed', 'rep', 'rank']
    with open(contributions_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=contrib_fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for hunter in data:
            if 'error' in hunter:
                continue
            for contrib in hunter.get('contributions', []):
                row = {
                    'username': hunter['username'],
                    'program': contrib.get('program'),
                    'valid_closed': contrib.get('valid_closed'),
                    'rep': contrib.get('rep'),
                    'rank': contrib.get('rank')
                }
                writer.writerow(row)

    print(f"[+] CSV files saved: {hackers_file}, {contributions_file}", file=sys.stderr)
    print("    Load them into Neo4j using LOAD CSV with the following commands:", file=sys.stderr)
    print("""
    // Load hackers
    LOAD CSV WITH HEADERS FROM 'file:///hackerone_hackers.csv' AS row
    MERGE (h:Hunter {username: row.username})
    SET h.name = row.name,
        h.location = row.location,
        h.joined_date = row.joined_date,
        h.socials = row.socials,
        h.bio = row.bio,
        h.thanks_count = toInteger(row.thanks_count),
        h.signal = row.signal,
        h.signal_percentile = row.signal_percentile,
        h.impact = row.impact,
        h.impact_percentile = row.impact_percentile,
        h.reputation = toInteger(row.reputation),
        h.rank = row.rank,
        h.streak_months = toInteger(row.streak_months),
        h.completed_pentests = toInteger(row.completed_pentests),
        h.vulnerabilities_found = toInteger(row.vulnerabilities_found),
        h.contributions_count = toInteger(row.contributions_count);

    // Load contributions and link to hunters
    LOAD CSV WITH HEADERS FROM 'file:///hackerone_contributions.csv' AS row
    MATCH (h:Hunter {username: row.username})
    CREATE (c:Contribution {
        program: row.program,
        valid_closed: row.valid_closed,
        rep: row.rep,
        rank: row.rank
    })
    CREATE (h)-[:MADE]->(c);
    """, file=sys.stderr)