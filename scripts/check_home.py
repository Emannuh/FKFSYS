import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fkf_league.settings')
django.setup()
from django.test import Client
c = Client()
r = c.get('/')
html = r.content.decode()
print('STATUS', r.status_code)
print('FOUND_CLASS_HOME_HERO', 'class="home-hero"' in html)
print('FOUND_CSS_HOME_HERO', '.home-hero' in html)
print('LENGTH', len(html))
for marker in ['<!-- Hero Banner -->', '<!-- Feature Cards -->', 'feature-card', 'sidebar-card', 'Latest News', 'Quick Links', 'home-hero']:
    idx = html.find(marker)
    print(marker, 'FOUND=', idx!=-1, 'INDEX=', idx)
    if idx!=-1:
        start = max(0, idx-200)
        end = idx+800
        print('---SNIPPET---')
        print(html[start:end])
        print('---END SNIPPET---')
