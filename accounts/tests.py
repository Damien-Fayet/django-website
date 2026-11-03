from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from .models import Profile
from .utils import family_user_ids, is_family


class FamilyFlagTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")

    def test_no_profile_means_not_family(self):
        self.assertFalse(is_family(self.alice))
        self.assertFalse(is_family(AnonymousUser()))
        self.assertFalse(is_family(None))

    def test_flag_makes_a_family_member(self):
        Profile.objects.create(user=self.alice, is_family=True)
        Profile.objects.create(user=self.bob, is_family=False)
        self.assertTrue(is_family(self.alice))
        self.assertFalse(is_family(self.bob))
        self.assertEqual(family_user_ids(), {self.alice.pk})

    def test_profile_is_removed_with_its_user(self):
        Profile.objects.create(user=self.alice, is_family=True)
        self.alice.delete()
        self.assertEqual(Profile.objects.count(), 0)


class FamilyAdminTests(TestCase):
    """La case « Membre de la famille » se coche dans la fiche de l'utilisateur."""

    def setUp(self):
        self.admin = User.objects.create_superuser("chef", password="pw")
        self.alice = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.admin)

    def test_user_list_has_the_family_column_and_filter(self):
        Profile.objects.create(user=self.alice, is_family=True)
        r = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertContains(r, "Famille")
        r = self.client.get(reverse("admin:auth_user_changelist"), {"profile__is_family__exact": "1"})
        self.assertEqual([u.username for u in r.context["cl"].result_list], ["alice"])

    def test_user_form_shows_the_checkbox_and_saves_it(self):
        url = reverse("admin:auth_user_change", args=[self.alice.pk])
        r = self.client.get(url)
        self.assertContains(r, "Membre de la famille")
        data = {
            "username": "alice", "date_joined_0": "2026-11-01", "date_joined_1": "10:00:00", "is_active": "on",
            "profile-TOTAL_FORMS": "1", "profile-INITIAL_FORMS": "0", "profile-MIN_NUM_FORMS": "0",
            "profile-MAX_NUM_FORMS": "1", "profile-0-is_family": "on", "profile-0-user": self.alice.pk,
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(is_family(self.alice))
