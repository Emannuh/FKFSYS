#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fkf_league.settings')
django.setup()

from teams.models import Team
from django.db.models import Count

print("=== Checking for duplicate emails ===")
# Check for duplicate emails (excluding blank/null emails)
duplicate_emails = Team.objects.values('email').annotate(
    count=Count('email')
).filter(count__gt=1).exclude(email='')

if duplicate_emails:
    print(f"Found {len(duplicate_emails)} duplicate email(s):")
    for item in duplicate_emails:
        email = item['email']
        count = item['count']
        print(f"\nEmail '{email}' appears {count} times")
        
        # Get all teams with this email
        teams = Team.objects.filter(email=email).order_by('id')
        for i, team in enumerate(teams):
            if i == 0:
                # Keep the first one as is
                print(f"  ✓ Keeping team '{team.team_name}' (ID: {team.id}) with email: {team.email}")
            else:
                # Make email unique by adding team ID
                if email:  # Only if email is not empty
                    if '@' in email:
                        username, domain = email.split('@')
                        new_email = f"{username}.team{team.id}@{domain}"
                    else:
                        new_email = f"{email}.team{team.id}"
                    
                    old_email = team.email
                    team.email = new_email
                    team.save()
                    print(f"  → Changed team '{team.team_name}' (ID: {team.id}) email from '{old_email}' to '{new_email}'")
else:
    print("No duplicate emails found.")

print("\n=== Checking for duplicate phone numbers ===")
# Check for duplicate phone numbers
duplicate_phones = Team.objects.values('phone_number').annotate(
    count=Count('phone_number')
).filter(count__gt=1)

if duplicate_phones:
    print(f"Found {len(duplicate_phones)} duplicate phone number(s):")
    for item in duplicate_phones:
        phone = item['phone_number']
        count = item['count']
        print(f"\nPhone '{phone}' appears {count} times")
        
        # Get all teams with this phone
        teams = Team.objects.filter(phone_number=phone).order_by('id')
        for i, team in enumerate(teams):
            if i == 0:
                # Keep the first one as is
                print(f"  ✓ Keeping team '{team.team_name}' (ID: {team.id}) with phone: {team.phone_number}")
            else:
                # Make phone unique by adding team ID
                new_phone = f"{phone}-{team.id}"
                old_phone = team.phone_number
                team.phone_number = new_phone
                team.save()
                print(f"  → Changed team '{team.team_name}' (ID: {team.id}) phone from '{old_phone}' to '{new_phone}'")
else:
    print("No duplicate phone numbers found.")

print("\n=== Checking for duplicate team names ===")
# Check for duplicate team names
duplicate_names = Team.objects.values('team_name').annotate(
    count=Count('team_name')
).filter(count__gt=1)

if duplicate_names:
    print(f"Found {len(duplicate_names)} duplicate team name(s):")
    for item in duplicate_names:
        name = item['team_name']
        count = item['count']
        print(f"\nTeam name '{name}' appears {count} times")
        
        # Get all teams with this name
        teams = Team.objects.filter(team_name=name).order_by('id')
        for i, team in enumerate(teams):
            if i == 0:
                # Keep the first one as is
                print(f"  ✓ Keeping team '{team.team_name}' (ID: {team.id})")
            else:
                # Make name unique by adding location or ID
                new_name = f"{name} ({team.location or team.id})"
                old_name = team.team_name
                team.team_name = new_name
                team.save()
                print(f"  → Changed team '{old_name}' (ID: {team.id}) to '{new_name}'")
else:
    print("No duplicate team names found.")

print("\n=== Summary ===")
total_teams = Team.objects.count()
print(f"Total teams in database: {total_teams}")

# Verify all are now unique
emails = list(Team.objects.exclude(email='').values_list('email', flat=True))
unique_emails = set(emails)
print(f"Unique emails: {len(unique_emails)} out of {len(emails)}")

phones = list(Team.objects.values_list('phone_number', flat=True))
unique_phones = set(phones)
print(f"Unique phones: {len(unique_phones)} out of {len(phones)}")

names = list(Team.objects.values_list('team_name', flat=True))
unique_names = set(names)
print(f"Unique names: {len(unique_names)} out of {len(names)}")

if len(emails) == len(unique_emails) and len(phones) == len(unique_phones) and len(names) == len(unique_names):
    print("\n✅ All duplicates fixed! You can now run migrations.")
else:
    print("\n⚠️  Some duplicates may still exist. Please check manually.")
