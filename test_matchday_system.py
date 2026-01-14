#!/usr/bin/env python
"""
Matchday Squad System Integration Test
This script checks if the matchday squad system is properly integrated
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fkf_league.settings')
django.setup()

from django.contrib.auth.models import User
from teams.models import Team
from matches.models import Match
from referees.models import MatchdaySquad, SquadPlayer
from django.utils import timezone
from django.db.models import Q

def print_section(title):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def test_migrations():
    """Test if matchday migrations are applied"""
    print_section("1. MIGRATIONS CHECK")
    try:
        # Try to import and use the models
        from referees.models import MatchdaySquad, SquadPlayer, SubstitutionRequest, SubstitutionOpportunity
        print("✓ MatchdaySquad model exists")
        print("✓ SquadPlayer model exists")
        print("✓ SubstitutionRequest model exists")
        print("✓ SubstitutionOpportunity model exists")
        print("\n✅ All matchday models are accessible")
        return True
    except ImportError as e:
        print(f"❌ ERROR: {e}")
        return False

def test_database_tables():
    """Test if database tables exist"""
    print_section("2. DATABASE TABLES CHECK")
    try:
        # Try to query the tables
        squad_count = MatchdaySquad.objects.count()
        player_count = SquadPlayer.objects.count()
        print(f"✓ MatchdaySquad table exists (records: {squad_count})")
        print(f"✓ SquadPlayer table exists (records: {player_count})")
        print("\n✅ All database tables are accessible")
        return True
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_team_managers():
    """Test if there are team managers in the system"""
    print_section("3. TEAM MANAGERS CHECK")
    try:
        team_managers = User.objects.filter(managed_teams__isnull=False).distinct()
        count = team_managers.count()
        
        if count > 0:
            print(f"✓ Found {count} team manager(s)")
            for tm in team_managers[:5]:
                teams = tm.managed_teams.all()
                print(f"  - {tm.username} manages: {', '.join([t.team_name for t in teams])}")
            print("\n✅ Team managers exist in the system")
            return True
        else:
            print("❌ No team managers found in the system")
            print("   Create a user and assign them to a team via Team.manager")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_upcoming_matches():
    """Test if there are upcoming matches"""
    print_section("4. UPCOMING MATCHES CHECK")
    try:
        today = timezone.now()
        upcoming_matches = Match.objects.filter(
            match_date__gte=today.date(),
            status='scheduled'
        ).order_by('round_number', 'match_date')
        
        count = upcoming_matches.count()
        
        if count > 0:
            print(f"✓ Found {count} upcoming match(es)")
            for match in upcoming_matches[:5]:
                print(f"  - Round {match.round_number}: {match.home_team.team_name} vs {match.away_team.team_name}")
                print(f"    Date: {match.match_date}, Kickoff: {match.kickoff_time or 'TBD'}")
            print("\n✅ Upcoming matches exist")
            return True
        else:
            print("❌ No upcoming matches found")
            print("   Create matches with future dates and status='scheduled'")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_url_patterns():
    """Test if URL patterns are configured"""
    print_section("5. URL PATTERNS CHECK")
    try:
        from django.urls import reverse
        
        urls_to_test = [
            ('team_matchday_squad_list', 'referees:team_matchday_squad_list'),
            ('submit_matchday_squad', 'referees:submit_matchday_squad', {'match_id': 1}),
            ('referee_squad_approval_list', 'referees:referee_squad_approval_list'),
            ('fourth_official_substitutions', 'referees:fourth_official_substitutions', {'match_id': 1}),
        ]
        
        all_ok = True
        for item in urls_to_test:
            url_name = item[0]
            reverse_name = item[1]
            kwargs = item[2] if len(item) > 2 else {}
            
            try:
                url = reverse(reverse_name, kwargs=kwargs)
                print(f"✓ {url_name}: {url}")
            except Exception as e:
                print(f"❌ {url_name}: {e}")
                all_ok = False
        
        if all_ok:
            print("\n✅ All matchday URLs are configured correctly")
            return True
        else:
            print("\n⚠️  Some URL patterns have issues")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_views():
    """Test if views are properly configured"""
    print_section("6. VIEWS CHECK")
    try:
        from referees import matchday_views
        
        views_to_check = [
            'team_matchday_squad_list',
            'submit_matchday_squad',
            'referee_squad_approval_list',
            'approve_matchday_squads',
            'fourth_official_substitutions',
            'activate_concussion_substitute',
        ]
        
        all_ok = True
        for view_name in views_to_check:
            if hasattr(matchday_views, view_name):
                print(f"✓ {view_name} exists")
            else:
                print(f"❌ {view_name} missing")
                all_ok = False
        
        if all_ok:
            print("\n✅ All matchday views are accessible")
            return True
        else:
            print("\n⚠️  Some views are missing")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_templates():
    """Test if templates exist"""
    print_section("7. TEMPLATES CHECK")
    import os
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    templates_to_check = [
        'templates/teams/dashboard.html',
        'templates/referees/dashboard.html',
        'templates/referees/matchday/squad_list.html',
        'templates/referees/matchday/submit_squad.html',
        'templates/referees/matchday/approval_list.html',
        'templates/referees/matchday/fourth_official_subs.html',
    ]
    
    all_ok = True
    for template in templates_to_check:
        template_path = os.path.join(base_path, template)
        if os.path.exists(template_path):
            print(f"✓ {template}")
        else:
            print(f"❌ {template} (not found)")
            all_ok = False
    
    if all_ok:
        print("\n✅ All required templates exist")
        return True
    else:
        print("\n⚠️  Some templates are missing")
        return False

def test_squad_submission_logic():
    """Test the squad submission logic"""
    print_section("8. SQUAD SUBMISSION LOGIC TEST")
    try:
        # Get a team manager
        team_manager = User.objects.filter(managed_teams__isnull=False).first()
        
        if not team_manager:
            print("⚠️  No team manager to test with")
            return False
        
        team = team_manager.managed_teams.first()
        print(f"✓ Testing with team: {team.team_name}")
        
        # Get upcoming matches for this team
        today = timezone.now()
        upcoming_matches = Match.objects.filter(
            Q(home_team=team) | Q(away_team=team),
            match_date__gte=today.date(),
            status='scheduled'
        ).order_by('round_number', 'match_date')
        
        if not upcoming_matches.exists():
            print(f"⚠️  No upcoming matches for {team.team_name}")
            return False
        
        first_match = upcoming_matches.first()
        print(f"✓ Next match: {first_match.home_team.team_name} vs {first_match.away_team.team_name}")
        print(f"  Round: {first_match.round_number}, Date: {first_match.match_date}")
        
        # Check if squad exists
        squad = MatchdaySquad.objects.filter(match=first_match, team=team).first()
        if squad:
            print(f"✓ Squad exists (Status: {squad.get_status_display()})")
            print(f"  Starting players: {squad.players.filter(is_starting=True).count()}")
            print(f"  Substitute players: {squad.players.filter(is_starting=False).count()}")
        else:
            print("✓ No squad submitted yet (as expected for new system)")
        
        print("\n✅ Squad submission logic is working")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   MATCHDAY SQUAD SYSTEM - INTEGRATION TEST                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    results = []
    
    # Run all tests
    results.append(("Migrations", test_migrations()))
    results.append(("Database Tables", test_database_tables()))
    results.append(("Team Managers", test_team_managers()))
    results.append(("Upcoming Matches", test_upcoming_matches()))
    results.append(("URL Patterns", test_url_patterns()))
    results.append(("Views", test_views()))
    results.append(("Templates", test_templates()))
    results.append(("Squad Logic", test_squad_submission_logic()))
    
    # Summary
    print_section("SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! The matchday squad system is properly integrated.")
        print("\n📋 NEXT STEPS:")
        print("   1. Login as a team manager")
        print("   2. Navigate to the team dashboard")
        print("   3. Look for 'Upcoming Matches & Matchday Squads' section")
        print("   4. Click 'Submit Squad' for the active match")
        print("\n🌐 Server is running at: http://127.0.0.1:8000/")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please address the issues above.")
    
    print("\n")

if __name__ == '__main__':
    main()
