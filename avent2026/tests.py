from datetime import date, datetime
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile

from . import achievements, competition, scoring, village
from .models import Attempt, Hint, HintReveal, LeaderboardDay, Puzzle, Submission


def on(month, day, hour=12):
    """Simule l'instant présent (heure de Paris) : par défaut midi, donc après la sortie des deux pistes."""
    return mock.patch("avent2026.scoring.now", return_value=datetime(2026, month, day, hour, tzinfo=scoring.TZ))


def at(day, hour=12):
    """Simule un jour de décembre 2026."""
    return on(12, day, hour)


class ScoringTests(TestCase):
    def test_normalize(self):
        self.assertEqual(scoring.normalize("  Le Père-Noël !! "), "le pere noel")

    def test_points_hint_cost_and_floor(self):
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        h = Hint.objects.create(puzzle=p, number=1, text="h")
        d = Puzzle.objects.create(kind="devinette", day=1, title="d", text="x", answers="a")
        self.assertEqual(scoring.compute_points(d, []), 50)  # pas de bonus hors des énigmes
        self.assertEqual(scoring.compute_points(d, [h]), 50 - scoring.DEFAULT_HINT_COST)
        self.assertEqual(scoring.compute_points(p, [h]), 100 - scoring.DEFAULT_HINT_COST)  # pas de « sans indice »
        # Le plancher s'applique au coût des indices, les bonus s'y ajoutent.
        costly = Hint.objects.create(puzzle=p, number=2, text="h2", cost=500)
        self.assertEqual(scoring.compute_points(p, [costly]), scoring.MIN_POINTS)
        self.assertEqual(scoring.compute_points(p, [costly], rank=1), scoring.MIN_POINTS + scoring.PODIUM_BONUS[0])

    def test_wrong_answers_cost_nothing_and_hints_are_cheap(self):
        """Se tromper ne coûte rien (il n'y a plus de paramètre d'erreurs) ; un indice coûte quelques points."""
        self.assertNotIn("errors", scoring.compute_points.__code__.co_varnames[:scoring.compute_points.__code__.co_argcount])
        self.assertLessEqual(scoring.DEFAULT_HINT_COST, 5)
        self.assertLessEqual(max(scoring.PODIUM_BONUS), 10)  # bonus de podium symbolique
        self.assertLessEqual(scoring.NO_HINT_BONUS, 10)

    def test_enigme_bonuses(self):
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        h = Hint.objects.create(puzzle=p, number=1, text="h")
        labels = lambda **kw: [b[0] for b in scoring.bonuses(p, **kw)]  # noqa: E731
        self.assertEqual(labels(rank=None, hints=[]), ["Sans indice"])
        self.assertEqual(labels(rank=2, hints=[h]), ["Deuxième à briser ce verrou"])
        self.assertEqual(labels(rank=4, hints=[h]), [])  # hors podium
        podium, no_hint = scoring.PODIUM_BONUS, scoring.NO_HINT_BONUS
        self.assertEqual(scoring.compute_points(p, [], rank=1), 100 + podium[0] + no_hint)
        self.assertEqual(scoring.compute_points(p, [], rank=3), 100 + podium[2] + no_hint)

    def test_no_speed_bonus_beyond_the_podium(self):
        """Pas de bonus de rapidité : seul le rang compte, pas l'heure de résolution."""
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        self.assertEqual({label for label, _ in scoring.bonuses(p, 5, [object()])}, set())

    def test_release_hours(self):
        e = Puzzle.objects.create(kind="enigme", day=5, title="e", text="x", answers="a")
        d = Puzzle.objects.create(kind="devinette", day=5, title="d", text="x", answers="a")
        with at(5, hour=5):
            self.assertFalse(scoring.is_unlocked(e))
            self.assertTrue(scoring.is_unlocked(d))
        with at(5, hour=6):
            self.assertTrue(scoring.is_unlocked(e))
        with at(4, hour=23):
            self.assertFalse(scoring.is_unlocked(d))
        self.assertEqual(scoring.unlock_at(e), datetime(2026, 12, 5, 6, tzinfo=scoring.TZ))

    def test_unlock_date_override_keeps_the_release_hour(self):
        e = Puzzle.objects.create(kind="enigme", day=5, title="e", text="x", answers="a",
                                  unlock_date=datetime(2026, 12, 7).date())
        with at(7, hour=5):
            self.assertFalse(scoring.is_unlocked(e))
        with at(7, hour=6):
            self.assertTrue(scoring.is_unlocked(e))

    def test_enigme_days_are_tuesday_first_then_wednesdays_and_saturdays(self):
        weekdays = [datetime(2026, 12, d).weekday() for d in village.ENIGME_DAYS]  # 1 mardi, 2 mercredi, 5 samedi
        self.assertEqual(village.ENIGME_DAYS[0], 1)
        self.assertEqual(weekdays[0], 1)
        self.assertTrue(all(w in (2, 5) for w in weekdays[1:]))
        self.assertEqual(len(village.ENIGME_DAYS), 8)
        self.assertEqual(village.ENIGME_DAYS[-1], 23)

    def test_base_points_depend_on_kind_only(self):
        e = Puzzle.objects.create(kind="enigme", day=1, title="e", text="x", answers="a")
        d = Puzzle.objects.create(kind="devinette", day=1, title="d", text="x", answers="a")
        self.assertEqual((scoring.puzzle_base_points(e), scoring.puzzle_base_points(d)), (100, 50))


class FlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.enigme = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="Oui")
        self.devinette = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="Non")
        Hint.objects.create(puzzle=self.enigme, number=1, text="h1", cost=20)
        Hint.objects.create(puzzle=self.enigme, number=2, text="h2")

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("avent2026:home")).status_code, 302)

    def test_locked_before_date(self):
        with on(11, 30):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 403)
            r = self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(Attempt.objects.exists())

    def test_staff_bypasses_lock(self):
        self.user.is_staff = True
        self.user.save()
        with on(11, 1):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)

    def test_superuser_bypasses_lock_even_without_staff_flag(self):
        self.user.is_superuser = True
        self.user.save()
        with on(11, 1):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
            self.assertEqual(self.client.post(reverse("avent2026:answer", args=[self.enigme.id]),
                                              {"answer": "oui"}).status_code, 302)

    def test_staff_nav_links_to_the_admin(self):
        admin_url = reverse("admin:avent2026_puzzle_changelist")
        with on(11, 1):
            self.assertNotContains(self.client.get(reverse("avent2026:home")), admin_url)
            self.user.is_staff = True
            self.user.save()
            self.assertContains(self.client.get(reverse("avent2026:home")), admin_url)

    def test_unlocked_day_one(self):
        day2 = Puzzle.objects.create(kind="enigme", day=2, title="E2", text="?", answers="x")
        with at(1):
            self.assertEqual(self.client.get(reverse("avent2026:home")).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[day2.id])).status_code, 403)

    def test_enigmes_come_out_at_6am_devinettes_at_midnight(self):
        with at(1, hour=0):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.devinette.id])).status_code, 200)
            r = self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id]))
            self.assertEqual(r.status_code, 403)
            self.assertContains(r, "à 6 h", status_code=403)
            self.assertEqual(self.client.post(reverse("avent2026:answer", args=[self.enigme.id]),
                                              {"answer": "oui"}).status_code, 403)
            self.assertEqual(self.client.post(reverse("avent2026:hint", args=[self.enigme.id])).status_code, 403)
        with at(1, hour=5):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 403)
        # Les accès refusés (page, réponse, indice) ne laissent aucune trace, pas même un « premier affichage ».
        self.assertFalse(Attempt.objects.filter(puzzle=self.enigme).exists())
        with at(1, hour=6):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
        self.assertIsNotNone(Attempt.objects.get(puzzle=self.enigme).first_seen_at)

    def test_wrong_then_right_with_hint(self):
        with at(1):
            url = reverse("avent2026:answer", args=[self.enigme.id])
            self.client.post(url, {"answer": "peut-être"})
            self.client.post(reverse("avent2026:hint", args=[self.enigme.id]))
            self.client.post(url, {"answer": " OUI "})
        a = Attempt.objects.get(user=self.user, puzzle=self.enigme)
        self.assertTrue(a.solved)
        self.assertEqual(a.errors, 1)
        self.assertEqual((a.rank, a.points), (1, 100 - 20 + scoring.PODIUM_BONUS[0]))  # premier au podium, mais l'indice coûte 20 et fait perdre « sans indice »
        self.assertEqual(a.errors, 1)  # la faute, elle, n'a rien coûté

    def test_solved_is_final_and_hints_blocked(self):
        with at(1):
            url = reverse("avent2026:answer", args=[self.enigme.id])
            self.client.post(url, {"answer": "oui"})
            self.client.post(url, {"answer": "faux"})
            self.client.post(reverse("avent2026:hint", args=[self.enigme.id]))
        a = Attempt.objects.get(user=self.user, puzzle=self.enigme)
        self.assertEqual((a.errors, a.points), (0, 100 + scoring.PODIUM_BONUS[0] + scoring.NO_HINT_BONUS))
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
        first = r.context["total"][0]
        self.assertEqual((first["name"], first["points"], first["solved"], first["place"]),
                         ("alice", 100 + scoring.PODIUM_BONUS[0] + scoring.NO_HINT_BONUS + 50, 2, 1))

    @override_settings(AVENT2026_UNLOCK_ALL=True)
    def test_unlock_all_setting(self):
        with on(1, 1):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
            cartes = self.client.get(reverse("avent2026:home")).context["cartes"]
        states = {step["state"] for c in cartes for step in c["steps"]}
        self.assertNotIn("locked", states)

    def test_one_puzzle_per_kind_and_day(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Puzzle.objects.create(kind="enigme", day=1, title="Doublon", text="?", answers="x")
        Puzzle.objects.create(kind="enigme", day=2, title="Autre jour", text="?", answers="x")

    def test_old_day_url_redirects_to_scene(self):
        r = self.client.get("/avent2026/jour/3/")
        self.assertRedirects(r, reverse("avent2026:home"), fetch_redirect_response=False)

    def test_puzzle_links_to_other_track_same_day(self):
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id]))
        self.assertEqual(r.context["other"], self.devinette)
        self.assertContains(r, reverse("avent2026:puzzle", args=[self.devinette.id]))
        self.assertContains(r, "Devinette du jour")
        self.assertNotContains(r, 'class="etat etat--done"')

    def test_other_track_link_shows_check_when_solved(self):
        Attempt.objects.create(user=self.user, puzzle=self.devinette, solved_at=timezone.now())
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id]))
        self.assertContains(r, 'class="etat etat--done"')


class CartesPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dora", password="pw")
        self.client.force_login(self.user)
        self.enigme = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="oui")
        self.devinette = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="non")

    def home(self):
        return self.client.get(reverse("avent2026:home"))

    def steps(self, response):
        return {(c["kind"], s["day"]): s for c in response.context["cartes"] for s in c["steps"]}

    def carte(self, response, kind="devinette"):
        return next(c for c in response.context["cartes"] if c["kind"] == kind)["carte"]

    def test_two_cartes_with_8_and_24_steps_and_states(self):
        Puzzle.objects.create(kind="enigme", day=9, title="E9", text="?", answers="x")
        with at(2):
            r = self.home()
        self.assertEqual([c["kind"] for c in r.context["cartes"]], ["enigme", "devinette"])
        self.assertEqual([len(c["steps"]) for c in r.context["cartes"]], [8, 24])
        steps = self.steps(r)
        self.assertEqual([d for k, d in steps if k == "enigme"], list(village.ENIGME_DAYS))
        self.assertEqual(steps[("enigme", 1)]["state"], "open")
        self.assertEqual(steps[("devinette", 1)]["state"], "open")
        self.assertEqual(steps[("enigme", 2)]["state"], "empty")  # jour débloqué mais rien de publié
        self.assertEqual(steps[("enigme", 5)]["state"], "locked")
        self.assertEqual(steps[("enigme", 9)]["state"], "locked")  # publiée mais pas encore sortie
        self.assertEqual(steps[("devinette", 3)]["state"], "locked")

    def test_cellule_step_released_at_6am(self):
        with at(1, hour=5):
            self.assertEqual(self.steps(self.home())[("enigme", 1)]["state"], "locked")
            self.assertEqual(self.steps(self.home())[("devinette", 1)]["state"], "open")
        with at(1, hour=6):
            self.assertEqual(self.steps(self.home())[("enigme", 1)]["state"], "open")

    def test_solving_moves_only_its_own_carte(self):
        with at(1):
            self.assertEqual(self.home().context["village"]["lit"], 0)
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            r = self.home()
        steps = self.steps(r)
        self.assertEqual(steps[("devinette", 1)]["state"], "done")
        self.assertEqual(steps[("enigme", 1)]["state"], "open")
        self.assertEqual({c["kind"]: c["solved"] for c in r.context["cartes"]}, {"enigme": 0, "devinette": 1})
        self.assertEqual(r.context["village"]["lit"], 1)
        self.assertEqual(r.context["village"]["total"], 32)
        self.assertEqual(r.context["scores"]["devinette"], 50)
        self.assertEqual(r.context["scores"]["devinette_solved"], 1)

    def test_locked_puzzle_title_not_exposed(self):
        Puzzle.objects.create(kind="enigme", day=5, title="TITRE-SECRET", text="?", answers="x")
        with at(1):
            self.assertNotContains(self.home(), "TITRE-SECRET")
        with at(5):
            self.assertContains(self.home(), "TITRE-SECRET")

    def test_cellule_shows_dates(self):
        with at(1):
            r = self.home()
        self.assertContains(r, "Verrou 1")
        self.assertContains(r, "sam 5")  # le 5 décembre 2026 est un samedi (mis en majuscule par le CSS)

    def test_all_images_of_the_devinette_map_are_present(self):
        for step in range(len(village.CARTES["devinette"].days) + 1):
            self.assertIsNotNone(village.carte_image_path("devinette", step), f"étape {step} manquante")

    def test_cellule_map_follows_solved_count_and_has_9_steps(self):
        with at(1):
            carte = self.carte(self.home(), "enigme")
            self.assertEqual(carte["step"], 0)
            self.assertTrue(carte["missing"].endswith("carte-enigmes/cellule-etape-00.webp"))
            self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            carte = self.carte(self.home(), "enigme")
        self.assertEqual(carte["step"], 1)
        self.assertTrue(carte["missing"].endswith("carte-enigmes/cellule-etape-01.webp"))

    def test_cellule_image_used_when_present(self):
        with mock.patch("avent2026.village.finders.find", side_effect=lambda path: path.endswith("etape-03.webp")):
            self.assertEqual(village.carte_image_path("enigme", 3), "avent2026/img/carte-enigmes/cellule-etape-03.webp")
            self.assertIsNone(village.carte_image_path("enigme", 4))
            # étape hors bornes : ramenée à l'étape finale (8), pas d'exception
            self.assertIsNone(village.carte_image_path("enigme", 99))

    def test_devinette_map_follows_solved_count(self):
        with at(1):
            self.assertEqual(self.carte(self.home())["image"], "avent2026/img/carte-devinettes/village-iso-etape-00.webp")
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            carte = self.carte(self.home())
        self.assertEqual((carte["step"], carte["image"]),
                         (1, "avent2026/img/carte-devinettes/village-iso-etape-01.webp"))

    def test_devinette_map_only_counts_devinettes(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            self.assertEqual(self.carte(self.home())["step"], 0)

    def seen_url(self, kind="devinette"):
        return reverse("avent2026:carte_seen", args=[kind])

    def test_devinette_map_reveals_new_step_until_browser_confirms(self):
        with at(1):
            self.assertIsNone(self.carte(self.home())["previous"])  # première visite : rien à animer
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            r = self.home()
            self.assertEqual(self.carte(r)["previous"], "avent2026/img/carte-devinettes/village-iso-etape-00.webp")
            self.assertContains(r, "carte__img carte__img--reveal")  # la classe sur l'<img>, pas le sélecteur du script
            self.assertContains(r, self.seen_url())
            # Un rendu qui n'a pas été affiché (préchargement, connexion coupée) ne consomme pas le fondu.
            self.assertIsNotNone(self.carte(self.home())["previous"])
            self.assertEqual(self.client.post(self.seen_url(), {"step": "1"}).status_code, 204)
            r = self.home()
        self.assertIsNone(self.carte(r)["previous"])  # vu, plus d'animation
        self.assertNotContains(r, "carte__img carte__img--reveal")

    def test_carte_seen_validates_input(self):
        self.assertEqual(self.client.get(self.seen_url()).status_code, 405)
        self.assertEqual(self.client.post(self.seen_url(), {"step": "abc"}).status_code, 400)
        self.assertEqual(self.client.post(self.seen_url(), {"step": "25"}).status_code, 400)
        self.assertEqual(self.client.post(self.seen_url(), {"step": "-1"}).status_code, 400)
        self.assertEqual(self.client.post(self.seen_url("inconnue"), {"step": "1"}).status_code, 404)

    def test_cellule_seen_is_capped_at_8_steps(self):
        self.assertEqual(self.client.post(self.seen_url("enigme"), {"step": "8"}).status_code, 204)
        self.assertEqual(self.client.post(self.seen_url("enigme"), {"step": "9"}).status_code, 400)

    def test_carte_seen_never_goes_backwards(self):
        with at(1):
            self.home()  # étape 0 enregistrée
            self.client.post(self.seen_url(), {"step": "5"})
            self.client.post(self.seen_url(), {"step": "2"})
        self.assertEqual(self.client.session["avent2026_carte_devinette"], 5)

    def test_counters_are_singular_for_zero_and_one(self):
        with at(1):
            self.assertContains(self.home(), "0 bâtiment allumé sur 24")
            self.assertContains(self.home(), "0 verrou brisé sur 8")
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            r = self.home()
        self.assertContains(r, "1 bâtiment allumé sur 24")
        self.assertContains(r, "1 verrou brisé sur 8")
        self.assertEqual(village.counter("enigme", 3), "3 verrous brisés")

    def test_maps_without_image_fall_back(self):
        with at(1), mock.patch("avent2026.village.finders.find", return_value=None):
            r = self.home()
        self.assertIsNone(self.carte(r)["image"])
        self.assertIsNone(self.carte(r, "enigme")["image"])
        self.assertContains(r, "carte__frame--placeholder")
        self.assertContains(r, "Verrou 1")  # les étapes restent jouables
        self.assertContains(r, 'aria-label="Jour 1')

    def test_calibration_page_is_gone(self):
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get("/avent2026/calibrage/enigme/").status_code, 404)


class VillageTests(TestCase):
    def test_progression_is_capped_to_the_number_of_steps(self):
        self.assertEqual(village.TOTAL, 32)  # 24 devinettes + 8 énigmes
        self.assertEqual(village.progression(0), {"lit": 0, "total": 32, "pct": 0})
        self.assertEqual(village.progression(8)["pct"], 25)
        self.assertEqual(village.progression(10 ** 6), {"lit": 32, "total": 32, "pct": 100})
        self.assertEqual(village.progression(None)["lit"], 0)


class StoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carl", password="pw")
        self.client.force_login(self.user)
        self.p = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="oui",
                                       story="<p>SECRET-FRAGMENT</p>")

    def test_story_hidden_until_solved(self):
        with at(1):
            url = reverse("avent2026:puzzle", args=[self.p.id])
            self.assertNotContains(self.client.get(url), "SECRET-FRAGMENT")
            self.assertNotContains(self.client.get(reverse("avent2026:journal")), "SECRET-FRAGMENT")
            self.client.post(reverse("avent2026:answer", args=[self.p.id]), {"answer": "oui"})
            self.assertContains(self.client.get(url), "SECRET-FRAGMENT")
            self.assertContains(self.client.get(reverse("avent2026:journal")), "SECRET-FRAGMENT")

    def test_prologue_shown_once(self):
        with at(1):
            self.assertTrue(self.client.get(reverse("avent2026:home")).context["prologue"])
            self.assertFalse(self.client.get(reverse("avent2026:home")).context["prologue"])

    def test_epilogue_needs_the_last_puzzle_of_both_tracks(self):
        """Dernière énigme (jour 23, verrou 8) et dernière devinette (jour 24)."""
        e23 = Puzzle.objects.create(kind="enigme", day=23, title="Fin E", text="?", answers="x")
        d24 = Puzzle.objects.create(kind="devinette", day=24, title="Fin D", text="?", answers="x")
        with at(24):
            self.assertFalse(self.client.get(reverse("avent2026:home")).context["epilogue"])
            self.client.post(reverse("avent2026:answer", args=[d24.id]), {"answer": "x"})
            self.assertFalse(self.client.get(reverse("avent2026:home")).context["epilogue"])
            self.client.post(reverse("avent2026:answer", args=[e23.id]), {"answer": "x"})
            r = self.client.get(reverse("avent2026:home"))
            self.assertTrue(r.context["epilogue"])
            self.assertTrue(r.context["finale"])  # l'étoile du grand sapin s'allume, la porte s'ouvre


class CompetitionTests(TestCase):
    """La course aux verrous : podium, bonus, titres. Seules les énigmes comptent, le staff est hors course."""

    def setUp(self):
        self.users = {n: User.objects.create_user(n, password="pw") for n in ("alice", "bob", "carl", "dora")}
        self.e1 = Puzzle.objects.create(kind="enigme", day=1, title="E1", text="?", answers="oui")
        Hint.objects.create(puzzle=self.e1, number=1, text="h")

    def solve(self, name, puzzle=None, answer="oui", wrong=0, hint=False):
        puzzle = puzzle or self.e1
        self.client.force_login(self.users[name])
        for _ in range(wrong):
            self.client.post(reverse("avent2026:answer", args=[puzzle.id]), {"answer": "faux"})
        if hint:
            self.client.post(reverse("avent2026:hint", args=[puzzle.id]))
        self.client.post(reverse("avent2026:answer", args=[puzzle.id]), {"answer": answer})
        return Attempt.objects.get(user=self.users[name], puzzle=puzzle)

    def test_podium_ranks_and_bonuses(self):
        with at(1):
            first = self.solve("alice")
            second = self.solve("bob", wrong=1)
            third = self.solve("carl", hint=True)
            fourth = self.solve("dora")
        self.assertEqual([a.rank for a in (first, second, third, fourth)], [1, 2, 3, 4])
        pb, nh, hc = scoring.PODIUM_BONUS, scoring.NO_HINT_BONUS, scoring.DEFAULT_HINT_COST
        self.assertEqual(first.points, 100 + pb[0] + nh)
        self.assertEqual(second.points, 100 + pb[1] + nh)  # une faute : aucune conséquence sur les points
        self.assertEqual(third.points, 100 - hc + pb[2])  # un indice : coût, et pas de « sans indice »
        self.assertEqual(fourth.points, 100 + nh)  # hors podium
        self.assertEqual([(p, n) for p, n, _ in competition.podium(self.e1)], [(1, "alice"), (2, "bob"), (3, "carl")])

    def test_rank_depends_on_resolution_time_not_on_when_the_player_started(self):
        with at(1):
            self.client.force_login(self.users["alice"])
            self.client.post(reverse("avent2026:answer", args=[self.e1.id]), {"answer": "faux"})  # alice commence
            bob = self.solve("bob")
            alice = self.solve("alice")
        self.assertEqual((bob.rank, alice.rank), (1, 2))

    def test_staff_is_out_of_the_race(self):
        staff = User.objects.create_user("zed", password="pw", is_staff=True)
        self.users["zed"] = staff
        with at(1):
            admin = self.solve("zed")
            alice = self.solve("alice")
        self.assertIsNone(admin.rank)
        self.assertEqual(admin.points, 100 + scoring.NO_HINT_BONUS)  # pas de bonus de podium
        self.assertEqual(alice.rank, 1)
        self.assertEqual([n for _, n, _ in competition.podium(self.e1)], ["alice"])

    def test_devinettes_have_no_bonus_and_no_rank(self):
        d = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="non")
        with at(1):
            a = self.solve("alice", d, answer="non")
        self.assertEqual((a.rank, a.points), (None, 50))

    def test_wrong_answer_gives_nothing_and_resolved_stays_final(self):
        with at(1):
            self.solve("alice", answer="faux")
            a = self.solve("alice")
            again = self.solve("alice")
        self.assertEqual((a.rank, again.pk, again.points, again.errors),
                         (1, a.pk, 100 + scoring.PODIUM_BONUS[0] + scoring.NO_HINT_BONUS, 1))  # une faute sans effet, puis résolue

    def test_puzzle_page_shows_bonuses_then_podium(self):
        url = reverse("avent2026:puzzle", args=[self.e1.id])
        with at(1):
            self.client.force_login(self.users["alice"])
            r = self.client.get(url)
            self.assertEqual(r.context["current_points"], 100 + scoring.PODIUM_BONUS[0] + scoring.NO_HINT_BONUS)  # si elle résolvait maintenant
            self.assertContains(r, "Sans indice")
            self.assertContains(r, "bonus « sans indice » perdu")  # prévenu avant de prendre un indice
            self.solve("alice")
            r = self.client.get(url)
            self.assertContains(r, "Premier à briser ce verrou")
            self.assertContains(r, "Podium")
            self.client.force_login(self.users["bob"])
            r = self.client.get(url)
        self.assertEqual(r.context["current_points"], 100 + scoring.PODIUM_BONUS[1] + scoring.NO_HINT_BONUS)  # bob viserait la 2e place
        self.assertContains(r, "alice")

    def test_hint_reveal_warns_about_the_lost_bonus(self):
        with at(1):
            self.client.force_login(self.users["alice"])
            r = self.client.post(reverse("avent2026:hint", args=[self.e1.id]), follow=True)
        self.assertContains(r, "bonus « sans indice »")

    def test_leaderboard_lists_podiums_and_titles(self):
        with at(1):
            self.solve("alice")
            self.client.force_login(self.users["bob"])
            r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual([v["step"] for v in r.context["verrous"]], [1])
        self.assertContains(r, "Verrou 1, E1")
        self.assertContains(r, "alice")
        self.assertIsNone(r.context["titles"]["liberateur"])

    def test_leaderboard_hides_verrous_not_yet_released(self):
        with at(1, hour=5):
            self.client.force_login(self.users["alice"])
            r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual(r.context["verrous"], [])

    def make_cellule(self):
        return [self.e1] + [Puzzle.objects.create(kind="enigme", day=d, title=f"E{d}", text="?", answers="oui")
                            for d in village.ENIGME_DAYS[1:]]

    def test_liberateur_and_sans_filet(self):
        puzzles = self.make_cellule()
        # alice finit les 8 sans indice ; bob finit après elle, avec un indice ; carl n'a pas fini.
        with on(12, 24):
            for p in puzzles:
                self.solve("alice", p)
            for p in puzzles:
                self.solve("bob", p, hint=(p is puzzles[0]))
            for p in puzzles[:7]:
                self.solve("carl", p)
        titles = competition.titles()
        self.assertEqual(titles["liberateur"]["user__username"], "alice")
        self.assertEqual(titles["sans_filet"], ["alice"])

    def test_liberateur_is_whoever_finishes_first_not_who_started_first(self):
        puzzles = self.make_cellule()
        with on(12, 24):
            for p in puzzles[:7]:
                self.solve("alice", p)  # alice a une longueur d'avance...
            for p in puzzles:
                self.solve("bob", p)
            self.solve("alice", puzzles[7])  # ...mais bob termine le premier
        self.assertEqual(competition.titles()["liberateur"]["user__username"], "bob")

    def test_staff_never_wins_a_title(self):
        staff = User.objects.create_user("zed", password="pw", is_staff=True)
        self.users["zed"] = staff
        with on(12, 24):
            for p in self.make_cellule():
                self.solve("zed", p)
        self.assertEqual(competition.titles(), {"liberateur": None, "sans_filet": []})

    def test_enigme_day_must_be_a_cellule_day(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            Puzzle(kind="enigme", day=3, title="x", text="?", answers="x").full_clean()
        Puzzle(kind="enigme", day=5, title="x", text="?", answers="x").full_clean()
        Puzzle(kind="devinette", day=3, title="x", text="?", answers="x").full_clean()


class TwoTracksMigrationTests(TransactionTestCase):
    """La migration 0003 garde un puzzle par (type, jour) : le « facile » en priorité."""

    before = [("avent2026", "0002_puzzle_story")]
    after = [("avent2026", "0003_two_tracks")]

    def tearDown(self):
        # Remet la base à jour pour les tests suivants.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_duplicates_collapsed_keeping_facile(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        OldPuzzle, OldHint = old.get_model("avent2026", "Puzzle"), old.get_model("avent2026", "Hint")
        hard = OldPuzzle.objects.create(kind="enigme", day=1, difficulty="difficile", title="Dur", text="?", answers="a")
        easy = OldPuzzle.objects.create(kind="enigme", day=1, difficulty="facile", title="Facile", text="?", answers="a")
        other = OldPuzzle.objects.create(kind="devinette", day=1, difficulty="facile", title="Devinette", text="?", answers="a")
        OldHint.objects.create(puzzle=hard, number=1, text="h")

        executor = MigrationExecutor(connection)
        executor.migrate(self.after)
        new = executor.loader.project_state(self.after).apps
        NewPuzzle, NewHint = new.get_model("avent2026", "Puzzle"), new.get_model("avent2026", "Hint")
        self.assertEqual(sorted(NewPuzzle.objects.values_list("title", flat=True)), ["Devinette", "Facile"])
        self.assertEqual(NewPuzzle.objects.get(kind="enigme").pk, easy.pk)
        self.assertEqual(NewPuzzle.objects.get(kind="devinette").pk, other.pk)
        self.assertEqual(NewHint.objects.count(), 0)  # indice du puzzle supprimé parti en cascade


class TrackingTests(TestCase):
    """Suivi staff : connexions, réponses envoyées, premier affichage et temps de réponse."""

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.boss = User.objects.create_user("boss", password="pw", is_staff=True)
        self.puzzle = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="Oui")
        self.url = reverse("avent2026:tracking")

    def test_login_is_recorded(self):
        from accounts.models import LoginEvent
        self.assertTrue(self.client.login(username="alice", password="pw"))
        self.assertEqual(LoginEvent.objects.filter(user=self.alice).count(), 1)

    def test_first_display_recorded_once(self):
        self.client.force_login(self.alice)
        with at(1):
            self.client.get(reverse("avent2026:puzzle", args=[self.puzzle.id]))
            first = Attempt.objects.get().first_seen_at
            self.assertIsNotNone(first)
            self.client.get(reverse("avent2026:puzzle", args=[self.puzzle.id]))
        self.assertEqual(Attempt.objects.get().first_seen_at, first)

    def test_answers_are_logged(self):
        self.client.force_login(self.alice)
        with at(1):
            url = reverse("avent2026:answer", args=[self.puzzle.id])
            self.client.post(url, {"answer": "  Non  "})
            self.client.post(url, {"answer": "oui"})
            self.client.post(url, {"answer": "encore"})  # déjà résolu : non journalisé
        rows = list(Submission.objects.order_by("id").values_list("answer", "correct"))
        self.assertEqual(rows, [("Non", False), ("oui", True)])
        # Répondre sans avoir ouvert la page : pas de premier affichage.
        self.assertIsNone(Attempt.objects.get().first_seen_at)

    def test_staff_only(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)  # anonyme → connexion
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_login(self.boss)
        for vue in ("temps", "reponses", "connexions", "inconnue"):
            self.assertEqual(self.client.get(self.url, {"vue": vue}).status_code, 200)

    def test_response_time_and_flags(self):
        from datetime import datetime, timedelta, timezone as tz
        t0 = datetime(2026, 12, 1, 10, 0, 0, tzinfo=tz.utc)
        bob = User.objects.create_user("bob", password="pw")
        Attempt.objects.create(user=self.alice, puzzle=self.puzzle, first_seen_at=t0,
                               solved_at=t0 + timedelta(seconds=20), points=100)
        Attempt.objects.create(user=bob, puzzle=self.puzzle, first_seen_at=t0,
                               solved_at=t0 + timedelta(minutes=5), points=100)
        Submission.objects.create(user=self.alice, puzzle=self.puzzle, answer="oui", correct=True)
        self.client.force_login(self.boss)
        resp = self.client.get(self.url, {"vue": "temps", "seuil": 60})
        rows = resp.context["page"].object_list
        self.assertEqual([r["user"].username for r in rows], ["alice", "bob"])  # plus rapide d'abord
        self.assertEqual([r["duration_text"] for r in rows], ["20 s", "5 min 00 s"])
        self.assertEqual(len(rows[0]["flags"]), 1)
        self.assertEqual(rows[1]["flags"], [])
        self.assertContains(resp, "Résolu en moins de 60 s")

    def test_answer_without_display_is_flagged(self):
        Attempt.objects.create(user=self.alice, puzzle=self.puzzle)
        Submission.objects.create(user=self.alice, puzzle=self.puzzle, answer="x", correct=False)
        self.client.force_login(self.boss)
        row = self.client.get(self.url, {"vue": "temps"}).context["page"].object_list[0]
        self.assertEqual(row["flags"], ["Réponse envoyée sans avoir ouvert la page"])

    def test_staff_hidden_unless_requested(self):
        Submission.objects.create(user=self.boss, puzzle=self.puzzle, answer="test", correct=False)
        Submission.objects.create(user=self.alice, puzzle=self.puzzle, answer="x", correct=False)
        self.client.force_login(self.boss)
        self.assertEqual(len(self.client.get(self.url, {"vue": "reponses"}).context["page"].object_list), 1)
        self.assertEqual(len(self.client.get(self.url, {"vue": "reponses", "staff": "1"}).context["page"].object_list), 2)

    def test_chosen_staff_player_is_shown(self):
        # Choisir explicitement un compte staff dans le filtre « Joueur » l'affiche sans cocher « Inclure le staff ».
        Submission.objects.create(user=self.boss, puzzle=self.puzzle, answer="test", correct=False)
        Submission.objects.create(user=self.alice, puzzle=self.puzzle, answer="x", correct=False)
        self.client.force_login(self.boss)
        rows = self.client.get(self.url, {"vue": "reponses", "joueur": self.boss.id}).context["page"].object_list
        self.assertEqual([s.user.username for s in rows], ["boss"])

    def test_answer_is_escaped(self):
        Submission.objects.create(user=self.alice, puzzle=self.puzzle, answer="<script>alert(1)</script>", correct=False)
        self.client.force_login(self.boss)
        self.assertNotContains(self.client.get(self.url, {"vue": "reponses"}), "<script>alert(1)</script>")

    def test_bad_params_do_not_crash(self):
        self.client.force_login(self.boss)
        r = self.client.get(self.url, {"vue": "temps", "joueur": "x", "puzzle": "y", "seuil": "abc", "page": "zzz"})
        self.assertEqual(r.status_code, 200)


class ClientIpTests(TestCase):
    """IP enregistrée avec les connexions et réponses, et IP partagées entre comptes."""

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.boss = User.objects.create_user("boss", password="pw", is_staff=True)
        self.puzzle = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="Oui")

    def test_cloudflare_header_trusted_only_from_loopback(self):
        from accounts.utils import client_ip
        from django.test import RequestFactory
        rf = RequestFactory()
        behind_tunnel = rf.get("/", REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(client_ip(behind_tunnel), "203.0.113.7")
        spoofed = rf.get("/", REMOTE_ADDR="198.51.100.2", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(client_ip(spoofed), "198.51.100.2")
        self.assertEqual(client_ip(rf.get("/", REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="n'importe quoi")), None)
        self.assertIsNone(client_ip(None))

    def test_login_and_answer_record_ip(self):
        from accounts.models import LoginEvent
        self.client.post(reverse("login"), {"username": "alice", "password": "pw"},
                         REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(LoginEvent.objects.get(user=self.alice).ip, "203.0.113.7")
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.puzzle.id]), {"answer": "non"},
                             REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.7")
        self.assertEqual(Submission.objects.get().ip, "203.0.113.7")

    def test_shared_ips(self):
        from accounts.models import LoginEvent
        LoginEvent.objects.create(user=self.alice, ip="203.0.113.7")
        Submission.objects.create(user=self.bob, puzzle=self.puzzle, answer="x", correct=False, ip="203.0.113.7")
        LoginEvent.objects.create(user=self.alice, ip="203.0.113.8")
        LoginEvent.objects.create(user=self.boss, ip="203.0.113.8")  # staff : ignoré par défaut
        self.client.force_login(self.boss)
        resp = self.client.get(reverse("avent2026:tracking"), {"vue": "connexions"})
        self.assertEqual(resp.context["shared_ips"], [{"ip": "203.0.113.7", "users": ["alice", "bob"]}])
        self.assertContains(resp, "203.0.113.7")


class MediaServingTests(TestCase):
    """Les images téléversées pour un énoncé doivent s'afficher aussi en production (DEBUG=False)."""

    @override_settings(DEBUG=False)
    def test_uploaded_image_is_served_without_debug(self):
        from pathlib import Path
        from django.conf import settings
        folder = Path(settings.MEDIA_ROOT) / "avent2026_test"
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / "x.webp"
        f.write_bytes(b"RIFFdata")
        try:
            r = self.client.get("/media/avent2026_test/x.webp")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), b"RIFFdata")
        finally:
            f.unlink()
            folder.rmdir()

    @override_settings(DEBUG=False)
    def test_range_requests_get_partial_content(self):
        """Safari / iOS ne lisent une vidéo que si le serveur répond 206 aux requêtes Range."""
        from pathlib import Path
        from django.conf import settings
        folder = Path(settings.MEDIA_ROOT) / "avent2026_test"
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / "v.mp4"
        f.write_bytes(b"0123456789")
        try:
            r = self.client.get("/media/avent2026_test/v.mp4")
            self.assertEqual((r.status_code, r["Accept-Ranges"], r["Content-Type"]), (200, "bytes", "video/mp4"))
            r.close()  # sous Windows, un fichier resté ouvert ne peut pas être supprimé ensuite
            cases = [("bytes=0-3", b"0123", "bytes 0-3/10"), ("bytes=4-", b"456789", "bytes 4-9/10"),
                     ("bytes=-3", b"789", "bytes 7-9/10"), ("bytes=8-99", b"89", "bytes 8-9/10")]
            for header, body, content_range in cases:
                with self.subTest(header):
                    r = self.client.get("/media/avent2026_test/v.mp4", HTTP_RANGE=header)
                    self.assertEqual(r.status_code, 206)
                    self.assertEqual(b"".join(r.streaming_content), body)
                    self.assertEqual((r["Content-Range"], r["Content-Length"]), (content_range, str(len(body))))
                    self.assertEqual(r["Content-Type"], "video/mp4")
            r = self.client.get("/media/avent2026_test/v.mp4", HTTP_RANGE="bytes=50-")
            self.assertEqual((r.status_code, r["Content-Range"]), (416, "bytes */10"))
            # Un en-tête illisible est ignoré : fichier entier.
            r = self.client.get("/media/avent2026_test/v.mp4", HTTP_RANGE="octets=1-2")
            self.assertEqual(r.status_code, 200)
            r.close()
            self.assertEqual(self.client.get("/media/avent2026_test/nope.mp4", HTTP_RANGE="bytes=0-1").status_code, 404)
            self.assertEqual(self.client.get("/media/../manage.py", HTTP_RANGE="bytes=0-1").status_code, 404)
        finally:
            f.unlink()
            folder.rmdir()


class PuzzleMediaTests(TestCase):
    """Énoncé facultatif, image ou vidéo téléversée depuis l'admin."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)

    def make(self, media=None, text="", day=3):
        p = Puzzle(kind="devinette", day=day, title="D", text=text, answers="x")
        if media is not None:
            p.image.name = media  # pas besoin d'un vrai fichier pour tester l'affichage
        return p

    def page(self, puzzle):
        puzzle.save()
        with at(24):
            return self.client.get(reverse("avent2026:puzzle", args=[puzzle.id]))

    def test_text_alone_still_valid(self):
        self.make(text="Quel est ce mot ?").full_clean()

    def test_media_alone_is_valid(self):
        self.make(media="avent2026/a.webp").full_clean()
        self.make(media="avent2026/a.mp4").full_clean()

    def test_neither_text_nor_media_is_refused(self):
        from django.core.exceptions import ValidationError
        for text in ("", "  \n"):
            with self.assertRaises(ValidationError) as ctx:
                self.make(text=text).full_clean()
            self.assertIn("text", ctx.exception.message_dict)

    def test_video_is_played_with_controls_and_never_autoplays(self):
        p = self.make(media="avent2026/clip.MP4")
        self.assertTrue(p.is_video)
        r = self.page(p)
        self.assertContains(r, "<video controls playsinline")
        self.assertContains(r, 'src="/media/avent2026/clip.MP4"')
        self.assertNotContains(r, "autoplay")
        self.assertNotContains(r, "statement__figure")

    def test_image_still_uses_the_zoomable_figure(self):
        p = self.make(media="avent2026/a.webp", text="Qui suis-je ?")
        self.assertFalse(p.is_video)
        r = self.page(p)
        self.assertContains(r, "statement__figure")
        self.assertContains(r, "Qui suis-je ?")
        self.assertNotContains(r, "<video")

    def test_text_only_page_has_no_media(self):
        r = self.page(self.make(text="Juste du texte"))
        self.assertContains(r, "Juste du texte")
        self.assertNotContains(r, "<video")
        self.assertNotContains(r, "statement__figure")

    def test_upload_validation(self):
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import IMAGE_MAX_BYTES, VIDEO_MAX_BYTES, validate_media
        validate_media(SimpleUploadedFile("a.mp4", b"x"))
        validate_media(SimpleUploadedFile("a.JPG", b"x"))
        for name in ("a.mov", "a.exe", "noext"):
            with self.assertRaises(ValidationError):
                validate_media(SimpleUploadedFile(name, b"x"))
        big_image = SimpleUploadedFile("a.png", b"x")
        big_image.size = IMAGE_MAX_BYTES + 1
        with self.assertRaises(ValidationError):
            validate_media(big_image)
        video = SimpleUploadedFile("a.webm", b"x")
        video.size = IMAGE_MAX_BYTES + 1  # une vidéo de cette taille est acceptée…
        validate_media(video)
        video.size = VIDEO_MAX_BYTES + 1  # …mais pas au-delà de 200 Mo
        with self.assertRaises(ValidationError):
            validate_media(video)


class NavigationTests(TestCase):
    """Parcours du joueur : à jouer maintenant, voisins d'un puzzle, retour au bloc réponse, page verrouillée."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.d1 = Puzzle.objects.create(kind="devinette", day=1, title="Premiere", text="?", answers="a")
        self.d2 = Puzzle.objects.create(kind="devinette", day=2, title="Deuxieme", text="?", answers="b")
        self.d3 = Puzzle.objects.create(kind="devinette", day=3, title="Troisieme", text="?", answers="c")
        self.e1 = Puzzle.objects.create(kind="enigme", day=1, title="Verrou un", text="?", answers="d")

    def test_home_lists_what_is_playable_and_the_next_unlock(self):
        with at(1):
            r = self.client.get(reverse("avent2026:home"))
        self.assertEqual({item["puzzle"].title for item in r.context["to_play"]}, {"Premiere", "Verrou un"})
        self.assertEqual(r.context["next_unlock"]["label"], "Jour 2")  # minuit avant l'énigme de 6 h
        self.assertContains(r, "À jouer maintenant")
        self.assertContains(r, reverse("avent2026:puzzle", args=[self.d1.id]))

    def test_home_drops_solved_puzzles_from_the_list(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "a"})
            r = self.client.get(reverse("avent2026:home"))
        self.assertEqual([item["puzzle"].title for item in r.context["to_play"]], ["Verrou un"])

    def test_home_caps_the_list_for_staff(self):
        self.user.is_staff = True
        self.user.save()
        for day in village.ENIGME_DAYS[1:]:
            Puzzle.objects.create(kind="enigme", day=day, title=f"E{day}", text="?", answers="x")
        with at(1):
            r = self.client.get(reverse("avent2026:home"))
        self.assertEqual(len(r.context["to_play"]), 6)
        self.assertEqual(r.context["to_play_more"], 11 - 6)  # 3 devinettes + 8 énigmes, aucune résolue

    def test_home_without_anything_to_play_still_announces_the_next_unlock(self):
        with at(1, hour=12):
            self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "a"})
            self.client.post(reverse("avent2026:answer", args=[self.e1.id]), {"answer": "d"})
            r = self.client.get(reverse("avent2026:home"))
        self.assertEqual(r.context["to_play"], [])
        self.assertContains(r, "Prochain déblocage")

    def test_home_is_called_accueil_and_hides_empty_legend_for_players(self):
        with at(1):
            r = self.client.get(reverse("avent2026:home"))
        self.assertContains(r, ">Accueil</a>")
        self.assertNotContains(r, ">Scène<")
        self.assertFalse(r.context["has_empty"])
        self.assertNotContains(r, "Rien de publié")
        with at(2):  # jour 2 de l'énigme : débloqué mais rien de publié
            r = self.client.get(reverse("avent2026:home"))
        self.assertTrue(r.context["has_empty"])
        self.assertContains(r, "Rien de publié")

    def test_locked_steps_are_not_announced_as_images(self):
        with at(1):
            r = self.client.get(reverse("avent2026:home"))
        self.assertNotContains(r, 'role="img"')
        self.assertContains(r, 'aria-disabled="true"')

    def test_puzzle_links_to_previous_and_next_in_its_own_track(self):
        with at(2):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.d2.id]))
        self.assertContains(r, reverse("avent2026:puzzle", args=[self.d1.id]))
        self.assertNotContains(r, reverse("avent2026:puzzle", args=[self.e1.id]) + '" rel')
        # Le suivant n'est pas encore sorti : on donne sa date, pas son titre.
        self.assertContains(r, "Suivant : le jeudi 3 décembre à 0 h")
        self.assertNotContains(r, "Troisieme")

    def test_next_link_appears_once_unlocked(self):
        with at(3):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.d2.id]))
        self.assertContains(r, "Suivant : Troisieme")

    def test_first_puzzle_has_no_previous_link(self):
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.d1.id]))
        self.assertNotContains(r, 'rel="prev"')

    def test_solving_points_to_the_next_puzzle(self):
        with at(2):
            self.client.post(reverse("avent2026:answer", args=[self.d2.id]), {"answer": "b"})
            r = self.client.get(reverse("avent2026:puzzle", args=[self.d2.id]))
        self.assertContains(r, "Résolue")
        self.assertContains(r, "le jeudi 3 décembre à 0 h")

    def test_answer_returns_to_the_result_block(self):
        with at(1):
            wrong = self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "zzz"})
            right = self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "a"})
            hint = self.client.post(reverse("avent2026:hint", args=[self.e1.id]))
        for r, puzzle in ((wrong, self.d1), (right, self.d1), (hint, self.e1)):
            self.assertEqual(r["Location"], reverse("avent2026:puzzle", args=[puzzle.id]) + "#resultat")

    def test_wrong_answer_message_is_an_alert_inside_the_answer_block(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "zzz"})
            r = self.client.get(reverse("avent2026:puzzle", args=[self.d1.id]))
        html = r.content.decode()
        self.assertEqual(html.count("essaie encore"), 1)  # une seule fois, pas aussi en haut de page
        self.assertIn('role="alert"', html)
        self.assertGreater(html.index("essaie encore"), html.index('id="resultat"'))

    def test_other_pages_still_show_messages_on_top(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "zzz"})
            r = self.client.get(reverse("avent2026:home"))
        self.assertContains(r, "essaie encore")

    def test_hint_asks_for_confirmation_and_shows_its_cost(self):
        Hint.objects.create(puzzle=self.e1, number=1, text="h", cost=20)
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
        self.assertContains(r, "data-confirm=")
        self.assertContains(r, "Coût : −20 pts, bonus « sans indice » perdu")
        self.assertNotContains(r, "autofocus")

    def test_locked_page_names_the_step_without_the_title(self):
        with on(11, 30):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Verrou 1 sur 8", status_code=403)
        self.assertContains(r, 'data-at="2026-12-01T06:00:00+01:00"', status_code=403)
        self.assertNotContains(r, "Verrou un", status_code=403)
        self.assertContains(r, "mardi 1 décembre 2026 à 6 h", status_code=403)


class LeaderboardTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="a")
        self.alice = User.objects.create_user("alice", password="pw")
        self.tester = User.objects.create_user("testeur", password="pw", is_staff=True)

    def solve(self, user):
        self.client.force_login(user)
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.puzzle.id]), {"answer": "a"})

    def test_staff_accounts_are_not_ranked(self):
        self.solve(self.tester)
        self.solve(self.alice)
        with at(1):
            r = self.client.get(reverse("avent2026:leaderboard"))
        for board in ("total", "devinettes", "enigmes"):
            self.assertNotIn("testeur", [row["name"] for row in r.context[board]])
        self.assertEqual(r.context["players"], 1)

    def test_rows_show_how_many_were_solved_and_my_place(self):
        self.solve(self.alice)
        with at(1):
            r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual(r.context["total"][0]["solved"], 1)
        self.assertEqual(r.context["my_rank"], 1)
        self.assertContains(r, "1 résolu")
        self.assertContains(r, 'id="moi"')
        self.assertContains(r, "Tu es <b>1er</b> sur 1 joueur")

    def test_staff_sees_a_note_instead_of_a_place(self):
        self.solve(self.alice)
        self.client.force_login(self.tester)
        with at(1):
            r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertIsNone(r.context["my_rank"])
        self.assertContains(r, "Les comptes staff n'apparaissent dans aucun classement")


class AuthPagesTests(TestCase):
    def test_login_keeps_the_username_after_a_failure(self):
        r = self.client.post(reverse("login"), {"username": "alice", "password": "mauvais"})
        self.assertContains(r, 'value="alice"')
        self.assertContains(r, "Demande à Damien")

    def test_password_fields_have_a_show_button(self):
        self.assertContains(self.client.get(reverse("login")), 'data-peek="id_password"')
        self.assertContains(self.client.get(reverse("signup")), 'data-peek="id_password2"')

    def test_welcome_countdown_uses_paris_time(self):
        self.assertContains(self.client.get("/"), "2026-12-01T00:00:00+01:00")

    def test_welcome_page_has_the_festive_countdown_and_its_assets(self):
        from django.contrib.staticfiles import finders
        r = self.client.get("/")
        self.assertContains(r, 'id="countdown" data-open-at="2026-12-01T00:00:00+01:00"')
        self.assertContains(r, "css/accueil.css")
        self.assertContains(r, "js/accueil.js")
        self.assertContains(r, 'id="neige-toggle"')
        for path in ("css/accueil.css", "js/accueil.js"):
            self.assertIsNotNone(finders.find(path), path)

    def test_game_pages_do_not_load_the_festive_assets(self):
        user = User.objects.create_user("alice", password="pw")
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("avent2026:home")), "accueil.css")

    def test_contact_address_is_in_every_footer(self):
        mail = 'href="mailto:contact-avent@damienfayet.com"'
        for url in ("/", reverse("login"), reverse("signup")):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), mail)
        self.client.force_login(User.objects.create_user("alice", password="pw"))
        self.assertContains(self.client.get(reverse("avent2026:home")), mail)
        self.assertContains(self.client.get(reverse("avent2026:leaderboard")), mail)

    def test_festive_assets_exist(self):
        from django.contrib.staticfiles import finders
        for path in ("css/ciel.css", "js/etincelles.js", "avent2026/js/fete.js"):
            self.assertIsNotNone(finders.find(path), path)

    def test_pages_have_a_description_and_an_icon(self):
        r = self.client.get("/")
        self.assertContains(r, '<meta name="description"')
        self.assertContains(r, 'rel="icon"')


class FesteTests(TestCase):
    """Progression de l'accueil, réponse et indices : les dessins et les données dont les scripts ont besoin."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.e1 = Puzzle.objects.create(kind="enigme", day=1, title="E1", text="?", answers="a")
        Hint.objects.create(puzzle=self.e1, number=1, text="un indice")
        self.d1 = Puzzle.objects.create(kind="devinette", day=1, title="D1", text="?", answers="b")

    def test_home_progress_panel_has_counters_gauge_and_icons(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.d1.id]), {"answer": "b"})
            r = self.client.get(reverse("avent2026:home"))
        self.assertContains(r, 'data-compte="1"')
        self.assertContains(r, 'aria-valuemax="32" aria-valuenow="1"')
        self.assertContains(r, "3 %")  # 1 étape sur 32
        self.assertNotContains(r, "alier")  # plus de paliers
        self.assertContains(r, 'class="status nuit avec-guirlande"')
        self.assertContains(r, 'id="ic-cadenas"')  # le sprite est dans la page
        self.assertContains(r, 'src="/static/avent2026/js/fete.js"')

    def test_puzzle_blocks_have_icons_and_the_ciel(self):
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
        for icon in ("#ic-etoile", "#ic-ampoule", "#ic-medaille"):
            self.assertContains(r, f'href="{icon}"')
        self.assertContains(r, 'class="ciel"')

    def test_bonus_icons_follow_the_bonus(self):
        with at(1):
            r = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
        self.assertContains(r, 'href="#ic-medaille"/></svg>Premier à briser ce verrou')
        self.assertContains(r, 'href="#ic-ampoule"/></svg>Sans indice')
        self.assertNotContains(r, "Sans faute")  # se tromper ne coûte plus rien, donc plus de bonus « sans faute »

    def test_messages_keep_their_type_for_the_script(self):
        with at(1):
            self.client.post(reverse("avent2026:answer", args=[self.e1.id]), {"answer": "zzz"})
            wrong = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
            self.client.post(reverse("avent2026:hint", args=[self.e1.id]))
            hinted = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
            self.client.post(reverse("avent2026:answer", args=[self.e1.id]), {"answer": "a"})
            solved = self.client.get(reverse("avent2026:puzzle", args=[self.e1.id]))
        self.assertContains(wrong, "notice--error")
        self.assertContains(hinted, "notice--info")
        self.assertContains(hinted, "un indice")
        self.assertContains(solved, "notice--success")
        self.assertContains(solved, "aside-block--resolu")


class AchievementTests(TestCase):
    """Hauts-faits : chacun se juge sur ce que le joueur a fait (résolutions, essais, indices)."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.counter = 0

    def puzzle(self, kind="devinette", day=None):
        self.counter += 1
        day = day or self.counter
        return Puzzle.objects.create(kind=kind, day=day, title=f"{kind}{day}", text="?", answers="ok")

    def solve(self, puzzle, when=None, errors=0, rank=None, user=None):
        when = when or datetime(2026, 12, 1, 12, tzinfo=scoring.TZ)
        return Attempt.objects.create(user=user or self.user, puzzle=puzzle, errors=errors, solved_at=when, rank=rank)

    def send(self, puzzle, answer, correct=False, times=1):
        for _ in range(times):
            Submission.objects.create(user=self.user, puzzle=puzzle, answer=answer, correct=correct)

    def keys(self):
        return achievements.keys_for(self.user)

    def test_try_harder_needs_more_than_five_tries_on_one_puzzle(self):
        p = self.puzzle()
        self.send(p, "a", times=5)
        self.assertNotIn("try_harder", self.keys())
        self.send(p, "b")
        self.assertIn("try_harder", self.keys())

    def test_try_harder_is_per_puzzle(self):
        for _ in range(3):
            self.send(self.puzzle(), "x", times=2)  # 6 essais au total, mais jamais plus de 2 sur la même énigme ou devinette
        self.assertNotIn("try_harder", self.keys())

    def test_disque_raye_is_ten_wrong_answers_in_total(self):
        """10 mauvaises réponses au total, quelles qu'elles soient et où qu'elles soient envoyées."""
        self.assertEqual(achievements.DISQUE_RAYE_ERRORS, 10)
        for i in range(9):
            self.send(self.puzzle("enigme" if i % 2 else "devinette", i // 2 + 1), f"faux{i}")
        self.assertNotIn("disque_raye", self.keys())
        self.send(self.puzzle("devinette", 20), "encore faux")
        self.assertIn("disque_raye", self.keys())

    def test_disque_raye_ignores_correct_and_blank_answers(self):
        p = self.puzzle()
        self.send(p, "ok", correct=True, times=10)
        self.send(p, "  ", times=10)  # une réponse vide n'est pas une erreur
        self.assertNotIn("disque_raye", self.keys())

    def test_disque_raye_counts_the_same_wrong_answer_every_time(self):
        self.send(self.puzzle(), "faux", times=10)
        self.assertIn("disque_raye", self.keys())

    def test_descriptions_never_say_puzzle(self):
        """« Puzzle » est ambigu pour les joueurs : on dit énigme ou devinette."""
        for h in achievements.HAUTS_FAITS:
            self.assertNotIn("puzzle", (h.name + " " + h.description).lower(), h.key)

    def test_brise_chaine_and_podium_come_from_the_rank_on_enigmes(self):
        self.solve(self.puzzle("enigme", 1), rank=3)
        self.assertEqual({"podium"}, self.keys() & {"podium", "brise_chaine"})
        self.solve(self.puzzle("enigme", 2), rank=1)
        self.assertEqual({"podium", "brise_chaine"}, self.keys() & {"podium", "brise_chaine"})

    def test_rank_on_a_devinette_does_not_count(self):
        self.solve(self.puzzle("devinette"), rank=1)
        self.assertFalse(self.keys() & {"podium", "brise_chaine"})

    def solve_many(self, kind, count, **kwargs):
        """Résout `count` puzzles de la piste (jours 1 à `count`, sans erreur ni indice sauf précision)."""
        puzzles = [self.puzzle(kind, day) for day in range(1, count + 1)]
        for p in puzzles:
            self.solve(p, **kwargs)
        return puzzles

    def test_premier_coup_has_a_tier_per_track_and_count(self):
        """1/5/8 énigmes et 1/5/10/20 devinettes : chaque palier se décroche à son seuil exact, piste par piste."""
        for kind, tiers in achievements.FIRST_TRY_TIERS.items():
            self.assertEqual(tiers, {"enigme": (1, 5, 8), "devinette": (1, 5, 10, 20)}[kind])
            for count in tiers:
                with self.subTest(kind=kind, count=count):
                    Puzzle.objects.all().delete()
                    self.solve_many(kind, count - 1)
                    self.assertNotIn(f"premier_coup_{kind}_{count}", self.keys())
                    self.solve(self.puzzle(kind, count))
                    self.assertIn(f"premier_coup_{kind}_{count}", self.keys())

    def test_premier_coup_ignores_the_other_track_and_mistakes(self):
        self.solve_many("devinette", 10)
        self.assertFalse({k for k in self.keys() if k.startswith("premier_coup_enigme")})
        Attempt.objects.all().delete()
        self.solve_many("enigme", 1, errors=1)  # une erreur avant la bonne réponse : pas du premier coup
        self.assertNotIn("premier_coup_enigme_1", self.keys())

    def test_sans_indice_has_a_tier_per_track_and_count(self):
        for kind, tiers in achievements.NO_HINT_TIERS.items():
            self.assertEqual(tiers, {"enigme": (1, 3, 5, 8), "devinette": (1, 5, 10, 20)}[kind])
            for count in tiers:
                with self.subTest(kind=kind, count=count):
                    Puzzle.objects.all().delete()
                    self.solve_many(kind, count - 1)
                    self.assertNotIn(f"sans_indice_{kind}_{count}", self.keys())
                    self.solve(self.puzzle(kind, count))
                    self.assertIn(f"sans_indice_{kind}_{count}", self.keys())

    def test_a_hint_breaks_sans_indice_but_not_premier_coup(self):
        puzzles = self.solve_many("enigme", 3)
        HintReveal.objects.create(user=self.user, hint=Hint.objects.create(puzzle=puzzles[0], number=1, text="h"))
        keys = self.keys()
        self.assertNotIn("sans_indice_enigme_3", keys)  # 2 énigmes sans indice seulement
        self.assertIn("sans_indice_enigme_1", keys)
        self.assertNotIn("premier_coup_enigme_5", keys)
        self.assertIn("premier_coup_enigme_1", keys)

    def test_accro_aux_indices_has_two_tiers_across_both_tracks(self):
        def take_hint(kind, day):
            HintReveal.objects.create(user=self.user, hint=Hint.objects.create(puzzle=self.puzzle(kind, day), number=1, text="h"))
        for day in range(1, 5):
            take_hint("devinette", day)
        self.assertFalse(self.keys() & {"accro_5", "accro_10"})
        take_hint("enigme", 1)  # le 5e puzzle, d'une autre piste
        self.assertEqual(self.keys() & {"accro_5", "accro_10"}, {"accro_5"})
        for day in range(5, 10):
            take_hint("devinette", day)
        self.assertEqual(self.keys() & {"accro_5", "accro_10"}, {"accro_5", "accro_10"})

    def test_two_hints_on_one_puzzle_count_once(self):
        p = self.puzzle()
        for number in range(1, 7):
            HintReveal.objects.create(user=self.user, hint=Hint.objects.create(puzzle=p, number=number, text="h"))
        self.assertNotIn("accro_5", self.keys())

    def test_serrurier_needs_all_eight_enigmes(self):
        days = list(village.ENIGME_DAYS)
        self.assertEqual(len(days), 8)
        for day in days[:-1]:
            self.solve(self.puzzle("enigme", day))
        self.assertNotIn("serrurier", self.keys())
        for day in range(1, 25):  # 24 devinettes ne comptent pas pour les énigmes
            self.solve(self.puzzle("devinette", day))
        self.assertNotIn("serrurier", self.keys())
        self.solve(self.puzzle("enigme", days[-1]))
        self.assertIn("serrurier", self.keys())

    def board(self, day, views):
        LeaderboardDay.objects.create(user=self.user, day=day, views=views)

    def test_fana_du_classement_needs_more_than_three_views_in_one_day(self):
        self.board(date(2026, 12, 1), 3)
        self.board(date(2026, 12, 2), 3)  # 6 au total mais jamais plus de 3 le même jour
        self.assertNotIn("fana_du_jour", self.keys())
        self.board(date(2026, 12, 3), 4)
        self.assertIn("fana_du_jour", self.keys())

    def test_abonne_au_classement_needs_more_than_a_hundred_views(self):
        for day in range(1, 26):
            self.board(date(2026, 12, day), 4)  # exactement 100 visites au total
        self.assertNotIn("abonne", self.keys())
        LeaderboardDay.objects.filter(day=date(2026, 12, 1)).update(views=5)
        self.assertIn("abonne", self.keys())

    def test_leve_tot_and_noctambule_use_paris_time(self):
        early = self.puzzle("enigme", 1)
        self.solve(early, when=datetime(2026, 12, 1, 7, 30, tzinfo=scoring.TZ))
        self.assertIn("leve_tot", self.keys())
        self.assertNotIn("noctambule", self.keys())
        self.solve(self.puzzle("devinette", 5), when=datetime(2026, 12, 5, 2, 0, tzinfo=scoring.TZ))
        self.assertIn("noctambule", self.keys())

    def test_noctambule_covers_midnight_to_five(self):
        self.solve(self.puzzle("devinette", 1), when=datetime(2026, 12, 1, 5, 0, tzinfo=scoring.TZ))
        self.assertNotIn("noctambule", self.keys())  # 5 h pile : trop tard
        self.solve(self.puzzle("devinette", 2), when=datetime(2026, 12, 2, 0, 0, tzinfo=scoring.TZ))
        self.assertIn("noctambule", self.keys())  # minuit pile : c'est bon

    def test_leve_tot_needs_an_enigme_in_the_morning(self):
        self.solve(self.puzzle("enigme", 1), when=datetime(2026, 12, 1, 9, 0, tzinfo=scoring.TZ))
        self.solve(self.puzzle("devinette", 1), when=datetime(2026, 12, 1, 7, 0, tzinfo=scoring.TZ))
        self.assertFalse(self.keys() & {"leve_tot", "noctambule"})

    def test_double_needs_both_tracks_of_the_same_day(self):
        self.solve(self.puzzle("enigme", 2))
        self.solve(self.puzzle("devinette", 3))
        self.assertNotIn("double", self.keys())
        self.solve(self.puzzle("devinette", 2))
        self.assertIn("double", self.keys())

    def test_assidu_needs_seven_days_in_a_row(self):
        for day in (1, 2, 3, 4, 5, 6, 8):  # le 7 manque
            self.solve(self.puzzle("devinette", day), when=datetime(2026, 12, day, 12, tzinfo=scoring.TZ))
        self.assertNotIn("assidu", self.keys())
        self.solve(self.puzzle("devinette", 7), when=datetime(2026, 12, 7, 12, tzinfo=scoring.TZ))
        self.assertIn("assidu", self.keys())

    def test_grand_allumeur_needs_all_devinettes(self):
        days = village.CARTES["devinette"].days
        for day in days[:-1]:
            self.solve(self.puzzle("devinette", day))
        self.assertNotIn("allumeur", self.keys())
        self.solve(self.puzzle("devinette", days[-1]))
        self.assertIn("allumeur", self.keys())

    def test_badges_keep_only_the_highest_tier_of_a_series(self):
        keys = {"premier_coup_devinette_1", "premier_coup_devinette_5", "premier_coup_devinette_10",
                "premier_coup_enigme_1", "sans_indice_devinette_1", "sans_indice_devinette_5", "try_harder"}
        self.assertEqual([h.key for h in achievements.badges(keys)],
                         ["try_harder", "premier_coup_enigme_1", "premier_coup_devinette_10", "sans_indice_devinette_5"])

    def test_public_list_leaves_out_staff(self):
        tester = User.objects.create_user("testeur", password="pw", is_staff=True)
        for user in (self.user, tester):
            p = self.puzzle()
            self.solve(p, rank=1, user=user)
            self.solve(self.puzzle("enigme", 1 + self.counter), rank=1, user=user)
        won = achievements.by_user()
        self.assertIn(self.user.pk, won)
        self.assertNotIn(tester.pk, won)
        self.assertTrue(achievements.keys_for(tester))  # le staff peut quand même les décrocher

    def test_every_achievement_has_an_icon_in_the_sprite(self):
        sprite = open("templates/avent2026/_sprite.html", encoding="utf-8").read()
        for h in achievements.HAUTS_FAITS:
            self.assertIn(f'id="ic-{h.icon}"', sprite, h.key)
        self.assertEqual(len({h.key for h in achievements.HAUTS_FAITS}), len(achievements.HAUTS_FAITS))


class AchievementMessageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.client.force_login(self.user)
        self.puzzle = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="oui")

    def test_try_harder_is_announced_once_on_the_sixth_try(self):
        url = reverse("avent2026:answer", args=[self.puzzle.id])
        with at(1):
            for i in range(5):
                r = self.client.post(url, {"answer": f"non{i}"}, follow=True)
                self.assertNotContains(r, "Haut-fait débloqué")
            r = self.client.post(url, {"answer": "encore non"}, follow=True)
            self.assertContains(r, "Haut-fait débloqué : Try-Harder")
            self.assertContains(r, "notice--success")  # le script en fait une fête
            r = self.client.post(url, {"answer": "toujours non"}, follow=True)
        self.assertNotContains(r, "Haut-fait débloqué")  # une seule fois

    def test_no_announcement_when_nothing_is_unlocked(self):
        with at(1):
            r = self.client.post(reverse("avent2026:answer", args=[self.puzzle.id]), {"answer": "non"}, follow=True)
        self.assertNotContains(r, "Haut-fait débloqué")

    def test_first_solve_announces_the_first_try_and_no_hint_tiers(self):
        with at(1):
            r = self.client.post(reverse("avent2026:answer", args=[self.puzzle.id]), {"answer": "oui"}, follow=True)
        self.assertContains(r, "Haut-fait débloqué : Du premier coup : 1 devinette")
        self.assertContains(r, "Haut-fait débloqué : Sans indice : 1 devinette")


class FamilyLeaderboardTests(TestCase):
    """Le classement « Famille » : réservé aux membres de la famille, et ne les classe qu'entre eux."""

    def setUp(self):
        self.puzzle = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="oui")
        self.alice = User.objects.create_user("alice", password="pw")   # famille
        self.bob = User.objects.create_user("bob", password="pw")       # pas de la famille
        self.carl = User.objects.create_user("carl", password="pw")     # famille
        Profile.objects.create(user=self.alice, is_family=True)
        Profile.objects.create(user=self.carl, is_family=True)
        Profile.objects.create(user=self.bob, is_family=False)
        for user in (self.alice, self.bob, self.carl):
            Attempt.objects.create(user=user, puzzle=self.puzzle, solved_at=datetime(2026, 12, 1, 12, tzinfo=scoring.TZ),
                                   points=50)

    def get(self, user, vue=None):
        self.client.force_login(user)
        return self.client.get(reverse("avent2026:leaderboard"), {"vue": vue} if vue else {})

    def test_family_members_see_the_tab_and_only_family_in_it(self):
        r = self.get(self.alice, "famille")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([row["name"] for row in r.context["board"]], ["alice", "carl"])
        self.assertContains(r, 'href="?vue=famille"')
        self.assertContains(r, "Classement réservé à la famille")

    def test_others_get_a_404_and_no_tab(self):
        self.assertEqual(self.get(self.bob, "famille").status_code, 404)
        r = self.get(self.bob)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "vue=famille")
        self.assertNotIn("famille", [key for key, _ in r.context["vues"]])
        self.assertIsNone(r.context["famille"])

    def test_a_player_without_profile_is_not_family(self):
        dora = User.objects.create_user("dora", password="pw")
        self.assertEqual(self.get(dora, "famille").status_code, 404)

    def test_the_general_board_still_has_everybody(self):
        names = [row["name"] for row in self.get(self.alice).context["total"]]
        self.assertEqual(sorted(names), ["alice", "bob", "carl"])

    def test_staff_can_look_but_is_never_listed(self):
        staff = User.objects.create_user("zed", password="pw", is_staff=True)
        Profile.objects.create(user=staff, is_family=True)
        Attempt.objects.create(user=staff, puzzle=self.puzzle, solved_at=datetime(2026, 12, 1, 12, tzinfo=scoring.TZ), points=50)
        r = self.get(staff, "famille")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([row["name"] for row in r.context["board"]], ["alice", "carl"])

    def test_places_inside_the_family_board_ignore_outsiders(self):
        Attempt.objects.filter(user=self.bob).update(points=500)  # bob est premier au général
        self.assertEqual(self.get(self.alice).context["my_rank"], 2)
        r = self.get(self.alice, "famille")
        self.assertEqual(r.context["my_place"], 1)


class LeaderboardPageTests(TestCase):
    def setUp(self):
        self.puzzle = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="oui")
        self.users = {n: User.objects.create_user(n, password="pw") for n in ("alice", "bob", "carl", "dora")}
        self.client.force_login(self.users["alice"])

    def give(self, name, points):
        Attempt.objects.create(user=self.users[name], puzzle=self.puzzle, points=points,
                               solved_at=datetime(2026, 12, 1, 12, tzinfo=scoring.TZ))

    def test_ties_share_a_place(self):
        for name, points in (("alice", 60), ("bob", 60), ("carl", 50), ("dora", 40)):
            self.give(name, points)
        r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual([(row["name"], row["place"]) for row in r.context["board"]],
                         [("alice", 1), ("bob", 1), ("carl", 3), ("dora", 4)])

    def test_tabs_show_the_chosen_board(self):
        self.give("alice", 50)
        Attempt.objects.create(user=self.users["bob"], puzzle=Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="x"),
                               points=100, solved_at=datetime(2026, 12, 1, 12, tzinfo=scoring.TZ))
        names = lambda vue: [row["name"] for row in self.client.get(reverse("avent2026:leaderboard"), {"vue": vue}).context["board"]]  # noqa: E731
        self.assertEqual(names("devinettes"), ["alice"])
        self.assertEqual(names("enigmes"), ["bob"])
        self.assertEqual(names("total"), ["bob", "alice"])
        self.assertEqual(names("n'importe quoi"), ["bob", "alice"])  # vue inconnue : le général

    def test_podium_shows_the_top_three(self):
        for name, points in (("alice", 60), ("bob", 50), ("carl", 40), ("dora", 30)):
            self.give(name, points)
        r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual([row["name"] for row in r.context["podium"]], ["alice", "bob", "carl"])
        self.assertContains(r, "podium__place--1")

    def test_badges_appear_next_to_the_name(self):
        self.give("alice", 50)
        p = Puzzle.objects.create(kind="devinette", day=2, title="D2", text="?", answers="x")
        for i in range(6):
            Submission.objects.create(user=self.users["alice"], puzzle=p, answer=f"non{i}", correct=False)
        r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertContains(r, 'aria-label="Try-Harder"')
        self.assertEqual([h.key for h in r.context["board"][0]["badges"]],
                         ["try_harder", "premier_coup_devinette_1", "sans_indice_devinette_1"])

    def test_each_visit_of_the_board_is_counted_per_day_and_user(self):
        url = reverse("avent2026:leaderboard")
        with mock.patch.object(scoring, "now", return_value=datetime(2026, 12, 5, 23, 30, tzinfo=scoring.TZ)):
            for _ in range(4):
                self.client.get(url)
        with mock.patch.object(scoring, "now", return_value=datetime(2026, 12, 6, 0, 10, tzinfo=scoring.TZ)):
            self.client.get(url + "?vue=enigmes")  # l'onglet compte aussi : c'est une visite de la page
        counts = dict(LeaderboardDay.objects.filter(user=self.users["alice"]).values_list("day", "views"))
        self.assertEqual(counts, {date(2026, 12, 5): 4, date(2026, 12, 6): 1})
        self.assertNotIn("fana_du_jour", achievements.keys_for(self.users["bob"]))
        self.assertIn("fana_du_jour", achievements.keys_for(self.users["alice"]))
        r = self.client.get(url)  # la visite qui débloque s'affiche dans la liste dès la page suivante
        self.assertEqual(next(h for h in r.context["hauts_faits"] if h["key"] == "fana_du_jour")["mine"], True)

    def test_hauts_faits_section_lists_everything_and_who_got_it(self):
        self.give("alice", 50)
        p = Puzzle.objects.create(kind="devinette", day=2, title="D2", text="?", answers="x")
        for i in range(6):
            Submission.objects.create(user=self.users["alice"], puzzle=p, answer=f"non{i}", correct=False)
        r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual(len(r.context["hauts_faits"]), len(achievements.HAUTS_FAITS))
        self.assertContains(r, "Plus de 5 essais sur une même énigme ou devinette")
        try_harder = next(h for h in r.context["hauts_faits"] if h["key"] == "try_harder")
        self.assertEqual((try_harder["mine"], try_harder["earners"], try_harder["count"]), (True, ["alice"], 1))
        self.assertContains(r, "Personne pour l'instant")  # les autres n'ont encore rien décroché

    def test_empty_game_still_renders(self):
        r = self.client.get(reverse("avent2026:leaderboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Personne encore")
