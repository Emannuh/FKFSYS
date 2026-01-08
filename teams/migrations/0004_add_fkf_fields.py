from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('teams', '0003_team_password_hash'),
    ]
    
    operations = [
        migrations.AddField(
            model_name='player',
            name='fkf_license_number',
            field=models.CharField(blank=True, max_length=50, verbose_name='FKF License Number'),
        ),
        migrations.AddField(
            model_name='player',
            name='license_expiry_date',
            field=models.DateField(blank=True, null=True, verbose_name='License Expiry Date'),
        ),
    ]
