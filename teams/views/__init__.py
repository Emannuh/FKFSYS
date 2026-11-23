"""teams views, split by feature. Re-exported so ``views.<name>`` keeps working."""
from .admin_officials import (
    admin_add_team_official,
    admin_delete_official,
    admin_manage_officials,
    admin_suspend_official,
    admin_unsuspend_official,
)
from .admin_players import (
    admin_delete_player,
    admin_edit_player,
    admin_manage_players,
    admin_suspend_player,
    admin_unsuspend_player,
)
from .dashboards import (
    all_teams,
    edit_team_info,
    league_admin_dashboard,
    team_dashboard,
    team_detail,
    team_manager_dashboard,
)
from .kits import select_kit_colors, update_team_kits
from .officials import delete_official, team_officials
from .players import add_player_action, add_players_to_approved_team
from .registration import registration_success, team_registration
from .squads import view_approved_squad
from .transfers import (
    approve_transfer,
    cancel_transfer,
    my_transfer_requests,
    reject_transfer,
    request_transfer,
    search_players,
)

__all__ = [
    'add_player_action', 'add_players_to_approved_team', 'admin_add_team_official',
    'admin_delete_official', 'admin_delete_player', 'admin_edit_player', 'admin_manage_officials',
    'admin_manage_players', 'admin_suspend_official', 'admin_suspend_player',
    'admin_unsuspend_official', 'admin_unsuspend_player', 'all_teams', 'approve_transfer',
    'cancel_transfer', 'delete_official', 'edit_team_info', 'league_admin_dashboard',
    'my_transfer_requests', 'registration_success', 'reject_transfer', 'request_transfer',
    'search_players', 'select_kit_colors', 'team_dashboard', 'team_detail',
    'team_manager_dashboard', 'team_officials', 'team_registration', 'update_team_kits',
    'view_approved_squad',
]
