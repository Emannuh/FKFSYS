# matches/utils/fixture_generator.py
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from teams.models import Team, Zone
from matches.models import Match
import random

def generate_fixtures_for_zone(zone_id, start_date=None):
    """
    Generate SINGLE round-robin fixtures with alternating home/away
    Teams alternate home/away matches each round when possible
    """
    try:
        zone = Zone.objects.get(id=zone_id)
    except Zone.DoesNotExist:
        return False, "Zone not found"
    
    if zone.fixtures_generated:
        return False, f"Fixtures already generated for {zone.name}"
    
    teams = Team.objects.filter(zone=zone, status='approved')
    team_list = list(teams)
    
    if len(team_list) < 2:
        return False, f"Need at least 2 approved teams in zone (has {len(team_list)})"
    
    # Determine start date (next SUNDAY)
    if not start_date:
        today = timezone.now().date()
        days_to_sunday = (0 - today.weekday()) % 7
        if days_to_sunday == 0:
            days_to_sunday = 7
        start_date = today + timedelta(days=days_to_sunday)
    
    match_day_of_week = getattr(zone, 'match_day_of_week', 0)
    days_to_match_day = (match_day_of_week - start_date.weekday()) % 7
    start_date = start_date + timedelta(days=days_to_match_day)
    
    # Shuffle teams for random fixture order
    random.shuffle(team_list)
    n = len(team_list)
    
    # Track home/away balance for each team
    home_away_balance = {team.id: {'home': 0, 'away': 0} for team in team_list}
    
    # If odd number of teams, add a BYE
    if n % 2 == 1:
        team_list.append(None)
        n = len(team_list)
    
    total_rounds = n - 1 if team_list[-1] is None else n - 1
    match_dates = []
    current_date = start_date
    
    # Generate match dates
    for round_num in range(total_rounds):
        match_date = current_date
        while match_date.weekday() != match_day_of_week:
            match_date += timedelta(days=1)
        match_dates.append(match_date)
        current_date = match_date + timedelta(days=7)
    
    fixtures = []
    
    # Generate initial round-robin pairings
    for round_num in range(total_rounds):
        round_date = match_dates[round_num] if round_num < len(match_dates) else match_dates[-1]
        
        # Create pairs for this round
        for i in range(n // 2):
            team1 = team_list[i]
            team2 = team_list[n - 1 - i]
            
            if team1 is None or team2 is None:
                continue  # Skip BYE
            
            # Decide home/away based on balance
            team1_home = home_away_balance[team1.id]['home']
            team1_away = home_away_balance[team1.id]['away']
            team2_home = home_away_balance[team2.id]['home']
            team2_away = home_away_balance[team2.id]['away']
            
            # Team with fewer home games gets to be home
            if team1_home < team2_home or (team1_home == team2_home and team1_away > team2_away):
                home_team = team1
                away_team = team2
            else:
                home_team = team2
                away_team = team1
            
            # Update balance
            home_away_balance[home_team.id]['home'] += 1
            home_away_balance[away_team.id]['away'] += 1
            
            # RANDOM KICKOFF TIMES: 1 PM (13:00), 3 PM (15:00), or 5 PM (17:00)
            kickoff_times = ['13:00', '15:00', '17:00']
            random_time = random.choice(kickoff_times)
            
            # FIX: Use timezone-aware datetime
            match_datetime = timezone.make_aware(
                datetime.combine(round_date, datetime.strptime(random_time, '%H:%M').time())
            )
            
            fixtures.append({
                'zone': zone,
                'home_team': home_team,
                'away_team': away_team,
                'round_number': round_num + 1,
                'match_date': match_datetime,
                'kickoff_time': random_time,
                'venue': getattr(home_team, 'home_ground', None) or f"{home_team.team_name} Home Ground",
                'status': 'scheduled'
            })
        
        # Rotate teams for next round
        team_list.insert(1, team_list.pop())
    
    # Check and fix home/away balance
    fixtures = balance_home_away_sequence(fixtures)
    
    # Save fixtures
    with transaction.atomic():
        match_objects = []
        for fixture_data in fixtures:
            match = Match(**fixture_data)
            match_objects.append(match)
        
        Match.objects.bulk_create(match_objects)
        
        zone.fixtures_generated = True
        zone.fixture_generation_date = timezone.now()
        zone.season_start_date = start_date
        zone.save()
    
    # Create summary of home/away distribution
    summary = create_home_away_summary(fixtures)
    
    return True, f"✅ Generated {len(fixtures)} fixtures for {zone.name}\n{summary}"

def balance_home_away_sequence(fixtures):
    """
    Ensure no team has too many home or away matches in sequence
    """
    # Group fixtures by team and check sequences
    team_fixtures = {}
    for fixture in fixtures:
        for team_field in ['home_team', 'away_team']:
            team = fixture[team_field]
            if team.id not in team_fixtures:
                team_fixtures[team.id] = []
            team_fixtures[team.id].append({
                'round': fixture['round_number'],
                'is_home': (team_field == 'home_team'),
                'fixture': fixture
            })
    
    # Check for problematic sequences (3+ home/away in a row)
    for team_id, matches in team_fixtures.items():
        matches.sort(key=lambda x: x['round'])
        
        current_streak = 0
        last_status = None
        
        for i, match in enumerate(matches):
            if match['is_home'] == last_status:
                current_streak += 1
            else:
                current_streak = 1
                last_status = match['is_home']
            
            # If 3 in a row, try to swap home/away with another fixture
            if current_streak >= 3 and i > 0:
                # Try to swap with a previous match
                for swap_match in matches[:i]:
                    if (swap_match['fixture'] != match['fixture'] and 
                        swap_match['fixture']['home_team'].id != match['fixture']['away_team'].id and
                        swap_match['fixture']['away_team'].id != match['fixture']['home_team'].id):
                        
                        # Swap home/away for this match
                        temp = match['fixture']['home_team']
                        match['fixture']['home_team'] = match['fixture']['away_team']
                        match['fixture']['away_team'] = temp
                        match['fixture']['venue'] = f"{match['fixture']['home_team'].team_name} Home Ground"
                        
                        # Update streak
                        match['is_home'] = not match['is_home']
                        break
    
    return fixtures

def create_home_away_summary(fixtures):
    """Create a summary of home/away distribution"""
    team_stats = {}
    
    for fixture in fixtures:
        home_id = fixture['home_team'].id
        away_id = fixture['away_team'].id
        
        if home_id not in team_stats:
            team_stats[home_id] = {'name': fixture['home_team'].team_name, 'home': 0, 'away': 0}
        if away_id not in team_stats:
            team_stats[away_id] = {'name': fixture['away_team'].team_name, 'home': 0, 'away': 0}
        
        team_stats[home_id]['home'] += 1
        team_stats[away_id]['away'] += 1
    
    summary_lines = ["Home/Away Distribution:"]
    for team_id, stats in team_stats.items():
        total = stats['home'] + stats['away']
        summary_lines.append(f"  {stats['name']}: {stats['home']}H/{stats['away']}A (total: {total})")
    
    return "\n".join(summary_lines)

def regenerate_fixtures_for_zone(zone_id):
    """
    Delete existing fixtures and regenerate them
    Super Admin can use this to reset fixtures
    """
    try:
        zone = Zone.objects.get(id=zone_id)
    except Zone.DoesNotExist:
        return False, "Zone not found"
    
    # Delete existing fixtures
    Match.objects.filter(zone=zone).delete()
    
    # Reset zone status
    zone.fixtures_generated = False
    zone.fixture_generation_date = None
    zone.season_start_date = None
    zone.save()
    
    # Generate new fixtures
    return generate_fixtures_for_zone(zone_id)

def update_match_date(match_id, new_date, new_time=None, new_kickoff_time=None):
    """
    Update a single match date/time
    Super Admin can reschedule individual matches
    """
    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return False, "Match not found"
    
    # Update date
    if isinstance(new_date, str):
        new_date = datetime.strptime(new_date, '%Y-%m-%d').date()
    
    # Update time if provided
    if new_time:
        if isinstance(new_time, str):
            new_time = datetime.strptime(new_time, '%H:%M').time()
        match.match_date = timezone.make_aware(
            datetime.combine(new_date, new_time)
        )
        match.kickoff_time = new_time.strftime('%H:%M')
    else:
        # Keep original time, just change date
        old_time = match.match_date.time()
        match.match_date = timezone.make_aware(
            datetime.combine(new_date, old_time)
        )
    # Update kickoff_time if provided
    if new_kickoff_time:
        match.kickoff_time = new_kickoff_time
    match.save()
    return True, f"✅ Match rescheduled to {match.match_date} (Kickoff: {match.kickoff_time})"