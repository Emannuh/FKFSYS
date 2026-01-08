from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0011_rename_teams_trans_status_d8e7b4_idx_teams_trans_status_541356_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaguesettings',
            name='team_registration_deadline',
            field=models.DateTimeField(blank=True, null=True, help_text='Automatically close team registration at this date/time'),
        ),
        migrations.AddField(
            model_name='leaguesettings',
            name='player_registration_deadline',
            field=models.DateTimeField(blank=True, null=True, help_text='Automatically close player registration at this date/time'),
        ),
        migrations.AddField(
            model_name='leaguesettings',
            name='transfer_window_deadline',
            field=models.DateTimeField(blank=True, null=True, help_text='Automatically close transfer window at this date/time'),
        ),
    ]
