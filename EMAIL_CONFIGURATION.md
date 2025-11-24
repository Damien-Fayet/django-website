# 📧 Configuration Email pour le Formulaire de Contact

## Fonctionnement Actuel (Développement)

En développement, les emails sont affichés dans la **console** au lieu d'être envoyés réellement.

Quand quelqu'un soumet le formulaire de contact :
- Le message s'affiche dans le terminal où Django tourne
- Aucun email n'est réellement envoyé
- Pratique pour tester sans configuration SMTP

## Configuration pour la Production

Pour recevoir les emails sur `fayet.damien63@gmail.com`, vous devez configurer un serveur SMTP.

### Option 1 : Utiliser Gmail (Recommandé pour débuter)

1. **Activer l'authentification à 2 facteurs sur Gmail**
   - Aller sur https://myaccount.google.com/security
   - Activer la validation en 2 étapes

2. **Créer un mot de passe d'application**
   - Aller sur https://myaccount.google.com/apppasswords
   - Sélectionner "Courrier" et "Autre (nom personnalisé)"
   - Nommer "Django Calendrier Avent"
   - Copier le mot de passe généré (16 caractères) 

3. **Modifier `mysite/settings.py`**

Remplacer :
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@calendrieravent2025.fr'
```

Par :
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'mon.mail@gmail.com'
EMAIL_HOST_PASSWORD = 'xxxx xxxx xxxx xxxx'  # Le mot de passe d'application
DEFAULT_FROM_EMAIL = 'mon.mail@gmail.com'
```

⚠️ **IMPORTANT** : Ne committez JAMAIS ce mot de passe dans Git !

### Option 2 : Utiliser des variables d'environnement (Production recommandée)

1. **Installer python-decouple**
```bash
pip install python-decouple
```

2. **Créer un fichier `.env` à la racine du projet**
```env
EMAIL_HOST_USER=mon.mail@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

3. **Ajouter `.env` dans `.gitignore`**
```
.env
```

4. **Modifier `mysite/settings.py`**
```python
from decouple import config

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER')
```

### Option 3 : Utiliser un service tiers (Production professionnelle)

Services recommandés :
- **SendGrid** : 100 emails/jour gratuits
- **Mailgun** : 5000 emails/mois gratuits (3 premiers mois)
- **Amazon SES** : Très bon marché, 62 000 emails/mois gratuits si hébergé sur AWS

Configuration similaire à Gmail mais avec leurs serveurs SMTP.

## Tester l'envoi d'email

1. Démarrer le serveur : `python manage.py runserver`
2. Aller sur : http://localhost:8000/avent2025/contact/
3. Remplir et envoyer le formulaire
4. **En développement** : Voir l'email dans la console
5. **En production** : Vérifier votre boîte mail

## Sécurité

✅ **Votre email est protégé** :
- L'adresse `mon.mail@gmail.com` n'apparaît JAMAIS dans le code HTML
- Elle est uniquement dans `views.py` côté serveur
- Les robots ne peuvent pas la scanner
- Le formulaire utilise un CSRF token Django

✅ **Protection anti-spam** intégrée :
- Message minimum 10 caractères
- Validation email côté serveur
- CSRF protection Django

## Fonctionnalités du formulaire

- ✉️ Nom de l'expéditeur
- 📧 Email de réponse (automatiquement configuré avec `reply_to`)
- 📝 Sujet personnalisé
- 💬 Message avec validation
- ✅ Messages de confirmation/erreur
- 🎨 Design moderne responsive

## Messages d'erreur possibles

### "Bad header error"
- Caractères interdits dans l'en-tête
- Solution : Le formulaire valide déjà les données

### "SMTP Authentication Error"
- Mauvais mot de passe d'application
- Solution : Régénérer un mot de passe d'application Gmail

### "Connection refused"
- Serveur SMTP inaccessible
- Solution : Vérifier les paramètres EMAIL_HOST et EMAIL_PORT

## URL du formulaire

- Développement : `http://localhost:8000/avent2025/contact/`
- Production : `https://votre-domaine.com/avent2025/contact/`
- Lien dans le footer : Automatiquement ajouté sur toutes les pages

## Structure des emails reçus

```
De: Django Calendrier Avent <fayet.damien63@gmail.com>
À: fayet.damien63@gmail.com
Répondre à: email-utilisateur@exemple.com
Sujet: [Calendrier Avent 2025] Sujet du message

Nouveau message de contact depuis le Calendrier de l'Avent 2025

Nom: Jean Dupont
Email: jean.dupont@exemple.com
Sujet: Question sur l'énigme 3

Message:
Bonjour, j'ai une question concernant...

---
Ce message a été envoyé depuis le formulaire de contact du site.
Pour répondre, utilisez l'adresse: jean.dupont@exemple.com
```

## Prochaines étapes

1. ✅ Formulaire créé et fonctionnel
2. ⏳ Configurer SMTP pour production (voir options ci-dessus)
3. ⏳ Tester l'envoi réel d'emails
4. ⏳ (Optionnel) Ajouter un système de captcha anti-spam
5. ⏳ (Optionnel) Ajouter une copie de confirmation à l'expéditeur
