"""Tournament views, split by feature. Re-exported for ``urls.py``."""
from .manage import (
    admin_tournament_dashboard,
    appoint_officials,
    change_tournament_status,
    create_match,
    create_tournament,
    delete_tournament,
    edit_tournament,
    edit_tournament_match,
    generate_fixtures,
    import_league_teams,
    manage_registrations,
    matches_needing_officials,
    record_result,
    review_registration,
)
from .public import tournament_detail, tournament_fixtures, tournament_list, tournament_standings
from .registration import register_external_players, register_external_team, register_players, register_team
from .squads import (
    tournament_approve_squad,
    tournament_referee_squad_list,
    tournament_submit_squad,
    tournament_team_matches,
)

__all__ = [
    'admin_tournament_dashboard', 'appoint_officials', 'change_tournament_status', 'create_match',
    'create_tournament', 'delete_tournament', 'edit_tournament', 'edit_tournament_match',
    'generate_fixtures', 'import_league_teams', 'manage_registrations', 'matches_needing_officials',
    'record_result', 'review_registration',
    'tournament_detail', 'tournament_fixtures', 'tournament_list', 'tournament_standings',
    'register_external_players', 'register_external_team', 'register_players', 'register_team',
    'tournament_approve_squad', 'tournament_referee_squad_list', 'tournament_submit_squad',
    'tournament_team_matches',
]
