from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import scoring
from .models import Attempt, Hint, Puzzle


def at(day):
    """Simule la date du jour en décembre 2026."""
    return mock.patch("avent2026.scoring.today", return_value=date(2026, 12, day))


class ScoringTests(TestCase):
    def test_normalize(self):
        self.assertEqual(scoring.normalize("  Le Père-Noël !! "), "le pere noel")

    def test_points_floor_and_penalties(self):
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        h = Hint.objects.create(puzzle=p, number=1, text="h")
        self.assertEqual(scoring.compute_points(p, 0, []), 100)
        self.assertEqual(scoring.compute_points(p, 2, [h]), 100 - 10 - 15)
        self.assertEqual(scoring.compute_points(p, 100, [h]), scoring.MIN_POINTS)


class FlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.enigme = Puzzle.objects.create(kind="enigme", day=1, difficulty="facile", title="E", text="?", answers="Oui")
        self.devinette = Puzzle.objects.create(kind="devinette", day=1, difficulty="facile", title="D", text="?", answers="Non")
        Hint.objects.create(puzzle=self.enigme, number=1, text="h1", cost=20)
        Hint.objects.create(puzzle=self.enigme, number=2, text="h2")

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("avent2026:home")).status_code, 302)

    def test_locked_before_date(self):
        with mock.patch("avent2026.scoring.today", return_value=date(2026, 11, 30)):
            self.assertEqual(self.client.get(reverse("avent2026:day", args=[1])).status_code, 403)
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 403)
            r = self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(Attempt.objects.exists())

    def test_staff_bypasses_lock(self):
        self.user.is_staff = True
        self.user.save()
        with mock.patch("avent2026.scoring.today", return_value=date(2026, 11, 1)):
            self.assertEqual(self.client.get(reverse("avent2026:day", args=[1])).status_code, 200)

    def test_unlocked_day_one(self):
        with at(1):
            self.assertEqual(self.client.get(reverse("avent2026:home")).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:day", args=[1])).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:day", args=[2])).status_code, 403)

    def test_wrong_then_right_with_hint(self):
        with at(1):
            url = reverse("avent2026:answer", args=[self.enigme.id])
            self.client.post(url, {"answer": "peut-être"})
            self.client.post(reverse("avent2026:hint", args=[self.enigme.id]))
            self.client.post(url, {"answer": " OUI "})
        a = Attempt.objects.get(user=self.user, puzzle=self.enigme)
        self.assertTrue(a.solved)
        self.assertEqual(a.errors, 1)
        self.assertEqual(a.points, 100 - 5 - 20)

    def test_solved_is_final_and_hints_blocked(self):
        with at(1):
            url = reverse("avent2026:answer", args=[self.enigme.id])
            self.client.post(url, {"answer": "oui"})
            self.client.post(url, {"answer": "faux"})
            self.client.post(reverse("avent2026:hint", args=[self.enigme.id]))
        a = Attempt.objects.get(user=self.user, puzzle=self.enigme)
        self.assertEqual((a.errors, a.points), (0, 100))
        self.assertEqual(self.user.avent2026_hints.count(), 0)

    def test_hints_revealed_in_order_and_capped(self):
        with at(1):
            url = reverse("avent2026:hint", args=[self.enigme.id])
            for _ in range(4):
                self.client.post(url)
        self.assertEqual(self.user.avent2026_hints.count(), 2)

    def test_leaderboard_per_category(self):
        bob = User.objects.create_user("bob", password="pw")
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            self.client.force_login(bob)
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual([x["name"] for x in r.context["enigmes"]], ["alice"])
        self.assertEqual(len(r.context["devinettes"]), 2)
        self.assertEqual(r.context["total"][0], {"name": "alice", "points": 150})

    @override_settings(AVENT2026_UNLOCK_ALL=True)
    def test_unlock_all_setting(self):
        with mock.patch("avent2026.scoring.today", return_value=date(2026, 1, 1)):
            self.assertEqual(self.client.get(reverse("avent2026:day", args=[24])).status_code, 200)
