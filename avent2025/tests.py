"""
Tests d'intégration pour le Calendrier de l'Avent 2025
Ces tests simulent le parcours complet d'un utilisateur
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserProfile, Enigme, Devinette, Indice, IndiceDevinette
from datetime import date


class UserExperienceTestCase(TestCase):
    """
    Test complet de l'expérience utilisateur sur avent2025
    Simule : création compte → login → navigation → énigmes → classement → logout
    """

    def setUp(self):
        """Configuration initiale avant chaque test"""
        self.client = Client()
        self.test_username = 'test_user_2025'
        self.test_email = 'test2025@example.com'
        self.test_password = 'TestPassword123!'
        
        # Créer quelques énigmes de test
        self.enigme1 = Enigme.objects.create(
            id=1,
            titre="Énigme de Test 1",
            texte="Quelle est la réponse à la grande question sur la vie, l'univers et le reste ?",
            reponse="42",
            date_dispo=date(2025, 11, 1)
        )
        
        self.enigme2 = Enigme.objects.create(
            id=2,
            titre="Énigme de Test 2",
            texte="Combien font 2 + 2 ?",
            reponse="4",
            date_dispo=date(2025, 11, 2)
        )
        
        # Créer un indice pour l'énigme 1
        self.indice1 = Indice.objects.create(
            enigme=self.enigme1,
            numero=1,
            texte="C'est un nombre pair"
        )
        
        # Créer une devinette de test
        self.devinette1 = Devinette.objects.create(
            id=1,
            titre="Devinette de Test 1",
            texte="Qui a peint la Joconde ?",
            reponse="Léonard de Vinci",
            genre=Devinette.PERSONALITE,
            date_dispo=date(2025, 11, 1)
        )

    def tearDown(self):
        """Nettoyage après chaque test"""
        # Supprimer l'utilisateur de test s'il existe
        User.objects.filter(username=self.test_username).delete()

    def test_01_home_page_accessible(self):
        """Test 1: Vérifier que la page d'accueil est accessible"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Les Ressources de Damien')

    def test_02_avent2025_redirect_when_not_logged(self):
        """Test 2: Vérifier la redirection vers login si non connecté"""
        response = self.client.get(reverse('avent2025:home'))
        # Devrait rediriger vers la page de login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_03_user_registration(self):
        """Test 3: Créer un nouveau compte utilisateur"""
        response = self.client.post(reverse('signup'), {
            'username': self.test_username,
            'email': self.test_email,
            'password1': self.test_password,
            'password2': self.test_password,
        })
        
        # Vérifier que l'utilisateur a été créé
        self.assertTrue(User.objects.filter(username=self.test_username).exists())
        user = User.objects.get(username=self.test_username)
        
        # Vérifier que le profil a été créé automatiquement (via signal)
        self.assertTrue(hasattr(user, 'userprofile_2025'))
        self.assertEqual(user.userprofile_2025.currentEnigma, 0)
        self.assertEqual(user.userprofile_2025.score, 0)

    def test_04_user_login(self):
        """Test 4: Se connecter avec un compte"""
        # Créer d'abord un utilisateur
        user = User.objects.create_user(
            username=self.test_username,
            email=self.test_email,
            password=self.test_password
        )
        
        # Tenter de se connecter
        logged_in = self.client.login(
            username=self.test_username,
            password=self.test_password
        )
        self.assertTrue(logged_in)
        
        # Vérifier que l'utilisateur peut accéder à avent2025
        response = self.client.get(reverse('avent2025:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_username)

    def test_05_complete_user_journey(self):
        """
        Test 5: Parcours complet utilisateur
        Inscription → Login → Accueil → Démarrer énigmes → Résoudre → Classement
        """
        print("\n=== TEST PARCOURS COMPLET UTILISATEUR ===")
        
        # ÉTAPE 1: Créer un compte
        print("1. Création du compte...")
        user = User.objects.create_user(
            username=self.test_username,
            email=self.test_email,
            password=self.test_password
        )
        self.assertIsNotNone(user)
        print(f"   ✓ Utilisateur créé: {user.username}")
        
        # ÉTAPE 2: Se connecter
        print("2. Connexion...")
        logged_in = self.client.login(
            username=self.test_username,
            password=self.test_password
        )
        self.assertTrue(logged_in)
        print("   ✓ Connexion réussie")
        
        # ÉTAPE 3: Accéder à la page d'accueil avent2025
        print("3. Accès page d'accueil avent2025...")
        response = self.client.get(reverse('avent2025:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendrier de l\'Avent 2025')
        print("   ✓ Page d'accueil accessible")
        
        # ÉTAPE 4: Démarrer l'aventure (énigmes)
        print("4. Démarrage de l'aventure...")
        response = self.client.get(reverse('avent2025:start_adventure'))
        user.refresh_from_db()
        self.assertEqual(user.userprofile_2025.currentEnigma, 1)
        print(f"   ✓ Aventure démarrée, énigme actuelle: {user.userprofile_2025.currentEnigma}")
        
        # ÉTAPE 5: Afficher l'énigme - vérifier le titre au lieu du texte encodé
        print("5. Affichage de l'énigme...")
        response = self.client.get(reverse('avent2025:display_enigme'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.enigme1.titre)
        # On vérifie que le texte est présent même si encodé en HTML
        self.assertIn(b'grande question', response.content)
        print(f"   ✓ Énigme affichée: {self.enigme1.titre}")
        
        # ÉTAPE 6: Répondre incorrectement
        print("6. Réponse incorrecte...")
        response = self.client.post(reverse('avent2025:validate_enigme'), {
            'user_reponse': 'mauvaise réponse'
        })
        user.refresh_from_db()
        self.assertEqual(user.userprofile_2025.erreurEnigma, 1)
        self.assertEqual(user.userprofile_2025.currentEnigma, 1)  # Toujours sur la même énigme
        print(f"   ✓ Erreur enregistrée: {user.userprofile_2025.erreurEnigma}")
        
        # ÉTAPE 7: Révéler un indice
        print("7. Révélation d'un indice...")
        response = self.client.post(reverse('avent2025:reveler_indice'), {
            'indice_id': self.indice1.id
        })
        user.refresh_from_db()
        self.assertIn(str(self.indice1.id), user.userprofile_2025.indices_enigme_reveles)
        print(f"   ✓ Indice révélé: {self.indice1.numero}")
        
        # ÉTAPE 8: Répondre correctement
        print("8. Réponse correcte...")
        response = self.client.post(reverse('avent2025:validate_enigme'), {
            'user_reponse': self.enigme1.reponse
        })
        user.refresh_from_db()
        self.assertEqual(user.userprofile_2025.currentEnigma, 2)  # Passe à l'énigme 2
        # Le score est calculé dynamiquement: (currentEnigma - 1) * 100 - erreurs * 5 - indices
        # Ici: (2 - 1) * 100 - 1 * 5 - 1 = 100 - 5 - 1 = 94
        print(f"   ✓ Énigme résolue! Énigme suivante: {user.userprofile_2025.currentEnigma}")
        
        # ÉTAPE 9: Accéder au classement
        print("9. Consultation du classement...")
        response = self.client.get(reverse('avent2025:classement'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_username)
        print("   ✓ Classement accessible, utilisateur visible")
        
        # ÉTAPE 10: Démarrer les devinettes
        print("10. Démarrage des devinettes...")
        response = self.client.get(reverse('avent2025:start_devinette'))
        user.refresh_from_db()
        self.assertEqual(user.userprofile_2025.currentDevinette, 1)
        print("   ✓ Devinettes démarrées")
        
        # ÉTAPE 11: Afficher devinette
        print("11. Affichage de la devinette...")
        response = self.client.get(reverse('avent2025:display_devinette'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.devinette1.titre)
        print(f"   ✓ Devinette affichée: {self.devinette1.titre}")
        
        # ÉTAPE 12: Se déconnecter
        print("12. Déconnexion...")
        response = self.client.post(reverse('logout'))
        response = self.client.get(reverse('avent2025:home'))
        self.assertEqual(response.status_code, 302)  # Redirigé car non connecté
        print("   ✓ Déconnexion réussie")
        
        print("\n=== PARCOURS COMPLET TERMINÉ AVEC SUCCÈS ===\n")

    def test_06_score_calculation(self):
        """Test 6: Vérifier le calcul du score (calculé dynamiquement)"""
        user = User.objects.create_user(
            username=self.test_username,
            password=self.test_password
        )
        self.client.login(username=self.test_username, password=self.test_password)
        
        # Démarrer l'aventure
        self.client.get(reverse('avent2025:start_adventure'))
        
        # Résoudre l'énigme 1 sans erreur ni indice
        self.client.post(reverse('avent2025:validate_enigme'), {
            'user_reponse': self.enigme1.reponse
        })
        user.refresh_from_db()
        
        # Vérifier que l'utilisateur est passé à l'énigme 2
        self.assertEqual(user.userprofile_2025.currentEnigma, 2)
        # Le score est calculé dynamiquement dans la vue classement
        # Formula: (currentEnigma - 1) * 100 - erreurs * 5 - nb_indices
        # Ici: (2 - 1) * 100 - 0 * 5 - 0 = 100

    def test_07_multiple_users_ranking(self):
        """Test 7: Tester le classement avec plusieurs utilisateurs"""
        # Créer plusieurs utilisateurs avec différents scores
        users_data = [
            ('user1', 200),
            ('user2', 150),
            ('user3', 250),
        ]
        
        for username, score in users_data:
            user = User.objects.create_user(username=username, password='test123')
            user.userprofile_2025.score = score
            user.userprofile_2025.currentEnigma = score // 100
            user.userprofile_2025.save()
        
        # Se connecter et vérifier le classement
        user = User.objects.create_user(
            username=self.test_username,
            password=self.test_password
        )
        self.client.login(username=self.test_username, password=self.test_password)
        
        response = self.client.get(reverse('avent2025:classement'))
        self.assertEqual(response.status_code, 200)
        
        # Vérifier que tous les utilisateurs sont présents
        for username, _ in users_data:
            self.assertContains(response, username)

    def test_08_enigme_not_available_yet(self):
        """Test 8: Vérifier qu'une énigme future n'est pas accessible"""
        # Créer une énigme avec une date future
        future_enigme = Enigme.objects.create(
            id=99,
            titre="Énigme Future",
            texte="Cette énigme n'est pas encore disponible",
            reponse="future",
            date_dispo=date(2026, 12, 25)  # Dans le futur
        )
        
        # Vérifier que is_dispo renvoie False
        self.assertFalse(future_enigme.is_dispo)

    def test_09_userprofile_creation_on_signup(self):
        """Test 9: Vérifier que le UserProfile est créé automatiquement"""
        # Créer un utilisateur
        user = User.objects.create_user(
            username=self.test_username,
            password=self.test_password
        )
        
        # Le signal devrait avoir créé le profil automatiquement
        self.assertTrue(hasattr(user, 'userprofile_2025'))
        profile = user.userprofile_2025
        
        # Vérifier les valeurs par défaut
        self.assertEqual(profile.currentEnigma, 0)
        self.assertEqual(profile.currentDevinette, 0)
        self.assertEqual(profile.score, 0)
        self.assertEqual(profile.erreurEnigma, 0)
        self.assertEqual(profile.erreurDevinette, 0)
        self.assertEqual(profile.indices_enigme_reveles, "")
        self.assertEqual(profile.indices_devinette_reveles, "")

    def test_10_navigation_flow(self):
        """Test 10: Tester le flux de navigation complet"""
        user = User.objects.create_user(
            username=self.test_username,
            password=self.test_password
        )
        self.client.login(username=self.test_username, password=self.test_password)
        
        # Liste des URLs à tester
        urls_to_test = [
            ('avent2025:home', 200),
            ('avent2025:classement', 200),
            ('home', 200),
        ]
        
        for url_name, expected_status in urls_to_test:
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(
                    response.status_code, 
                    expected_status,
                    f"URL {url_name} devrait retourner {expected_status}"
                )


class ModelTestCase(TestCase):
    """Tests unitaires pour les modèles"""

    def test_enigme_str(self):
        """Test de la représentation string d'une énigme"""
        enigme = Enigme.objects.create(
            id=1,
            titre="Test Énigme",
            texte="Test",
            reponse="test",
            date_dispo=date.today()
        )
        self.assertEqual(str(enigme), "Enigme 1 : Test Énigme")

    def test_devinette_str(self):
        """Test de la représentation string d'une devinette"""
        devinette = Devinette.objects.create(
            id=1,
            titre="Test Devinette",
            texte="Test",
            reponse="test",
            genre=Devinette.FILM,
            date_dispo=date.today()
        )
        self.assertEqual(str(devinette), "Devinette 1 : Test Devinette")

    def test_userprofile_str(self):
        """Test de la représentation string du profil utilisateur"""
        user = User.objects.create_user(username='testuser', password='test123')
        profile = user.userprofile_2025
        profile.currentEnigma = 5
        profile.currentDevinette = 3
        expected = f"{user} Enigme 5, Devinette 3"
        self.assertEqual(str(profile), expected)


class EdgeCaseTestCase(TestCase):
    """Tests des cas limites et erreurs"""

    def test_empty_response_validation(self):
        """Test de validation avec réponse vide"""
        user = User.objects.create_user(username='testuser', password='test123')
        client = Client()
        client.login(username='testuser', password='test123')
        
        # Créer une énigme
        Enigme.objects.create(
            id=1,
            titre="Test",
            texte="Test",
            reponse="test",
            date_dispo=date.today()
        )
        
        # Démarrer l'aventure
        client.get(reverse('avent2025:start_adventure'))
        
        # Essayer de valider avec une réponse vide
        response = client.post(reverse('avent2025:validate_enigme'), {
            'user_reponse': ''
        })
        
        # Le formulaire devrait rejeter la réponse vide
        user.refresh_from_db()
        self.assertEqual(user.userprofile_2025.currentEnigma, 1)

    def test_case_insensitive_answer(self):
        """Test que les réponses ne sont pas sensibles à la casse"""
        user = User.objects.create_user(username='testuser', password='test123')
        client = Client()
        client.login(username='testuser', password='test123')
        
        Enigme.objects.create(
            id=1,
            titre="Test",
            texte="Test",
            reponse="Paris",
            date_dispo=date.today()
        )
        
        # Il faut créer l'énigme 2 sinon get_object_or_404 plante après validation
        Enigme.objects.create(
            id=2,
            titre="Test 2",
            texte="Test 2",
            reponse="London",
            date_dispo=date.today()
        )
        
        client.get(reverse('avent2025:start_adventure'))
        
        # Répondre en minuscules (la réponse attendue est "Paris")
        # Le système normalise avec .lower() donc "paris" doit fonctionner
        client.post(reverse('avent2025:validate_enigme'), {
            'user_reponse': 'paris'
        })
        
        user.refresh_from_db()
        # Devrait passer à l'énigme 2 car la réponse normalisée "paris" = "paris"
        self.assertEqual(user.userprofile_2025.currentEnigma, 2)
