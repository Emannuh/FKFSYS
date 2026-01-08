# Generated migration for transfer system and league settings

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('teams', '0009_team_kit_setup_prompt_shown'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeagueSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_registration_open', models.BooleanField(default=True, help_text='Allow new teams to register')),
                ('player_registration_open', models.BooleanField(default=True, help_text='Allow teams to add new players')),
                ('transfer_window_open', models.BooleanField(default=True, help_text='Allow teams to request player transfers')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='league_settings_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'League Settings',
                'verbose_name_plural': 'League Settings',
            },
        ),
        migrations.CreateModel(
            name='TransferRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending_parent', 'Pending Parent Club Decision'), ('approved', 'Approved - Transfer Complete'), ('rejected', 'Rejected by Parent Club'), ('cancelled', 'Cancelled by Requester')], default='pending_parent', max_length=20)),
                ('request_date', models.DateTimeField(auto_now_add=True)),
                ('parent_decision_reason', models.TextField(blank=True)),
                ('parent_decision_date', models.DateTimeField(blank=True, null=True)),
                ('admin_override', models.BooleanField(default=False, help_text='True if admin forced approval after rejection')),
                ('admin_override_reason', models.TextField(blank=True)),
                ('admin_override_date', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('admin_override_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfer_overrides_made', to=settings.AUTH_USER_MODEL)),
                ('from_team', models.ForeignKey(help_text='Current team (parent club)', on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_transfer_requests', to='teams.team')),
                ('parent_decision_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfer_decisions_made', to=settings.AUTH_USER_MODEL)),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_requests', to='teams.player')),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transfer_requests_made', to=settings.AUTH_USER_MODEL)),
                ('to_team', models.ForeignKey(help_text='Requesting team', on_delete=django.db.models.deletion.CASCADE, related_name='incoming_transfer_requests', to='teams.team')),
            ],
            options={
                'ordering': ['-request_date'],
            },
        ),
        migrations.CreateModel(
            name='TransferHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_override', models.BooleanField(default=False)),
                ('transfer_date', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('from_team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players_transferred_out', to='teams.team')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transfer_history', to='teams.player')),
                ('to_team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players_transferred_in', to='teams.team')),
                ('transfer_request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='teams.transferrequest')),
            ],
            options={
                'verbose_name': 'Transfer History',
                'verbose_name_plural': 'Transfer Histories',
                'ordering': ['-transfer_date'],
            },
        ),
        migrations.AddIndex(
            model_name='transferrequest',
            index=models.Index(fields=['status', 'from_team'], name='teams_trans_status_d8e7b4_idx'),
        ),
        migrations.AddIndex(
            model_name='transferrequest',
            index=models.Index(fields=['status', 'to_team'], name='teams_trans_status_c3a3e5_idx'),
        ),
        migrations.AddIndex(
            model_name='transferrequest',
            index=models.Index(fields=['player', 'status'], name='teams_trans_player__5d5b3e_idx'),
        ),
    ]
