"""User & role management — superuser only, every change audit-logged.

These views never touch ``is_staff``/``is_superuser``, only role groups, so they
cannot be used to grant Django-admin or superuser rights. Superuser accounts
cannot be deactivated or deleted here, and an admin cannot lock themselves out.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..activity_logger import Action, log_activity
from ..email import send_account_setup_email, send_password_reset_email
from .common import superuser_required

User = get_user_model()

USERS_PAGE = 'admin_dashboard:manage_league_admins'


@superuser_required
def manage_league_admins(request):
    """List / filter / search all users (Super Admin only)."""
    role_filter = request.GET.get('role', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()

    users = User.objects.prefetch_related('groups')
    if role_filter != 'all':
        users = users.filter(groups__name=role_filter)
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
        )
    users = users.distinct().order_by('-date_joined')

    user_stats = User.objects.aggregate(
        total=Count('id', distinct=True),
        active=Count('id', filter=Q(is_active=True), distinct=True),
        inactive=Count('id', filter=Q(is_active=False), distinct=True),
        team_managers=Count('id', filter=Q(groups__name='Team Managers'), distinct=True),
        league_admins=Count('id', filter=Q(groups__name='League Admin'), distinct=True),
        referees=Count('id', filter=Q(groups__name='Referee'), distinct=True),
        referee_managers=Count('id', filter=Q(groups__name='Referees Manager'), distinct=True),
    )
    page_obj = Paginator(users, 50).get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/manage_league_admins.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'all_groups': Group.objects.order_by('name'),
        'user_stats': user_stats,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    })


@require_POST
@superuser_required
def create_league_admin(request):
    """Create a user in an existing role group and email a set-password link."""
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', '').strip()

    if not username or not email:
        messages.error(request, "Username and email are required.")
        return redirect(USERS_PAGE)
    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, f"Username '{username}' already exists.")
        return redirect(USERS_PAGE)
    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "That email address is already registered.")
        return redirect(USERS_PAGE)
    group = Group.objects.filter(name=role).first() if role else None
    if role and group is None:
        messages.error(request, f"Unknown role '{role}'.")
        return redirect(USERS_PAGE)

    user = User(
        username=username,
        email=email,
        first_name=request.POST.get('first_name', '').strip(),
        last_name=request.POST.get('last_name', '').strip(),
        is_active=True,
    )
    user.set_unusable_password()
    try:
        user.full_clean(exclude=['password'])
    except ValidationError as exc:
        messages.error(request, "Invalid user details: " + "; ".join(exc.messages))
        return redirect(USERS_PAGE)

    with transaction.atomic():
        user.save()
        if group:
            user.groups.add(group)
        log_activity(request.user, Action.USER_CREATE, f"Created user {user.username} with role {role or 'none'}",
                     obj=user, request=request, extra_data={'role': role})

    if send_account_setup_email(user, role):
        messages.success(request, f"User {username} created ({role or 'no role'}). "
                                  f"A set-password link was emailed to them.")
    else:
        messages.warning(request, f"User {username} created, but the set-password email could not be sent. "
                                  f"Use 'Reset password' to resend it.")
    return redirect(USERS_PAGE)


@require_POST
@superuser_required
def toggle_league_admin_status(request, user_id):
    """Activate / deactivate a user (not yourself, not a superuser)."""
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect(USERS_PAGE)
    if target.is_superuser:
        messages.error(request, "Superuser accounts cannot be deactivated here.")
        return redirect(USERS_PAGE)

    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    action = Action.USER_ACTIVATE if target.is_active else Action.USER_DEACTIVATE
    state = 'activated' if target.is_active else 'deactivated'
    log_activity(request.user, action, f"{state.capitalize()} user {target.username}", obj=target, request=request)
    messages.success(request, f"{target.username} has been {state}.")
    return redirect(USERS_PAGE)


@require_POST
@superuser_required
def reset_league_admin_password(request, user_id):
    """Invalidate a user's password and email them a set-password link."""
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "Use 'Change password' to change your own password.")
        return redirect(USERS_PAGE)

    target.set_unusable_password()
    target.save(update_fields=['password'])
    log_activity(request.user, Action.PASSWORD_RESET, f"Reset password for {target.username}",
                 obj=target, request=request)
    if send_password_reset_email(target):
        messages.success(request, f"Password reset for {target.username}; a set-password link was emailed.")
    else:
        messages.warning(request, f"Password reset for {target.username}, but the email could not be sent.")
    return redirect(USERS_PAGE)


@superuser_required
def edit_user_roles(request, user_id):
    """Show (GET) and replace (POST) a user's role groups."""
    target = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        requested = set(request.POST.getlist('groups'))
        groups = list(Group.objects.filter(name__in=requested))
        unknown = requested - {g.name for g in groups}
        if unknown:
            messages.error(request, f"Unknown role(s): {', '.join(sorted(unknown))}")
            return redirect('admin_dashboard:edit_user_roles', user_id=target.id)

        before = sorted(target.groups.values_list('name', flat=True))
        after = sorted(g.name for g in groups)
        with transaction.atomic():
            target.groups.set(groups)
            log_activity(request.user, Action.USER_ROLE_CHANGE, f"Changed roles for {target.username}",
                         obj=target, request=request, extra_data={'before': before, 'after': after})
        messages.success(request, f"Roles updated for {target.username}")
        return redirect(USERS_PAGE)

    return render(request, 'admin_dashboard/edit_user_roles.html', {
        'edit_user': target,
        'all_groups': Group.objects.order_by('name'),
        'user_groups': target.groups.all(),
    })


@require_POST
@superuser_required
def delete_user(request, user_id):
    """Permanently delete a user (not yourself, not a superuser)."""
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect(USERS_PAGE)
    if target.is_superuser:
        messages.error(request, "Superuser accounts cannot be deleted.")
        return redirect(USERS_PAGE)

    username = target.username
    with transaction.atomic():
        log_activity(request.user, Action.USER_DELETE, f"Deleted user {username}", obj=target, request=request,
                     extra_data={'deleted_user_id': target.pk})
        target.delete()
    messages.success(request, f"User '{username}' has been deleted.")
    return redirect(USERS_PAGE)
