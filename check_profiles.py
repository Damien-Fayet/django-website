import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth.models import User
from avent2025.models import UserProfile

users = User.objects.all()
profiles = UserProfile.objects.all()

print(f'✅ {users.count()} utilisateurs, {profiles.count()} profils\n')

for u in users:
    status = "✅ Profil OK" if hasattr(u, "userprofile_2025") else "❌ MANQUANT"
    print(f'  - {u.username}: {status}')
