from datetime import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from . import competition, scoring, village
from .models import Attempt, Hint, HintReveal, Puzzle, Submission


def on(month, day, hour=12):
    """Simule l'instant présent (heure de Paris) : par défaut midi, donc après la sortie des deux pistes."""
    return mock.patch("avent2026.scoring.now", return_value=datetime(2026, month, day, hour, tzinfo=scoring.TZ))


def at(day, hour=12):
    """Simule un jour de décembre 2026."""
    return on(12, day, hour)


class ScoringTests(TestCase):
    def test_normalize(self):
        self.assertEqual(scoring.normalize("  Le Père-Noël !! "), "le pere noel")

    def test_points_floor_and_penalties(self):
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        h = Hint.objects.create(puzzle=p, number=1, text="h")
        d = Puzzle.objects.create(kind="devinette", day=1, title="d", text="x", answers="a")
        self.assertEqual(scoring.compute_points(d, 0, []), 50)  # pas de bonus hors des énigmes
        self.assertEqual(scoring.compute_points(d, 2, [h]), 50 - 10 - 15)
        self.assertEqual(scoring.compute_points(p, 2, [h]), 100 - 10 - 15)  # ni sans indice ni sans faute
        # Le plancher s'applique à la pénalité, les bonus s'y ajoutent.
        self.assertEqual(scoring.compute_points(p, 100, [h]), scoring.MIN_POINTS)
        self.assertEqual(scoring.compute_points(p, 100, [h], rank=1), scoring.MIN_POINTS + 50)

    def test_enigme_bonuses(self):
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        h = Hint.objects.create(puzzle=p, number=1, text="h")
        labels = lambda **kw: [b[0] for b in scoring.bonuses(p, **kw)]  # noqa: E731
        self.assertEqual(labels(rank=None, errors=0, hints=[]), ["Sans indice", "Sans faute"])
        self.assertEqual(labels(rank=2, errors=1, hints=[h]), ["Deuxième à briser ce verrou"])
        self.assertEqual(labels(rank=4, errors=1, hints=[h]), [])  # hors podium
        self.assertEqual(scoring.compute_points(p, 0, [], rank=1), 100 + 50 + 25 + 10)
        self.assertEqual(scoring.compute_points(p, 0, [], rank=3), 100 + 20 + 25 + 10)

    def test_no_speed_bonus_beyond_the_podium(self):
        """Pas de bonus de rapidité : seul le rang compte, pas l'heure de résolution."""
        p = Puzzle.objects.create(kind="enigme", day=1, title="t", text="x", answers="a")
        self.assertEqual({label for label, _ in scoring.bonuses(p, 5, 1, [object()])}, set())

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
        self.assertEqual((a.rank, a.points), (1, 100 - 5 - 20 + 50))  # premier au podium, mais ni sans indice ni sans faute

    def test_solved_is_final_and_hints_blocked(self):
        with at(1):
            url = reverse("avent2026:answer", args=[self.enigme.id])
            self.client.post(url, {"answer": "oui"})
            self.client.post(url, {"answer": "faux"})
            self.client.post(reverse("avent2026:hint", args=[self.enigme.id]))
        a = Attempt.objects.get(user=self.user, puzzle=self.enigme)
        self.assertEqual((a.errors, a.points), (0, 100 + 50 + 25 + 10))
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
        self.assertEqual(r.context["total"][0], {"name": "alice", "points": 185 + 50})

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
    def test_thresholds_and_levels(self):
        start = village.village_state(0)
        self.assertEqual((start["level"], start["lit"], start["next_threshold"], start["progress_pct"]), (1, 0, 4, 0))
        self.assertEqual(village.village_state(3)["level"], 1)
        self.assertEqual(village.village_state(4)["level"], 2)
        top = village.village_state(10 ** 6)  # plafonné au nombre d'étapes du jeu
        self.assertEqual((top["lit"], top["level"], top["progress_pct"], top["next_threshold"]),
                         (village.TOTAL, len(village.LEVELS), 100, None))

    def test_last_level_reachable(self):
        """Le dernier palier se franchit sans avoir tout résolu ; 24 devinettes + 8 énigmes = 32 étapes."""
        self.assertEqual(village.TOTAL, 32)
        self.assertLess(village.LEVELS[-1][0], village.TOTAL)
        self.assertEqual(village.LEVELS, sorted(village.LEVELS))


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
        self.assertEqual(first.points, 100 + 50 + 25 + 10)
        self.assertEqual(second.points, 100 - 5 + 30 + 25)  # une faute : pas de « sans faute »
        self.assertEqual(third.points, 100 - 15 + 20 + 10)  # un indice : pas de « sans indice »
        self.assertEqual(fourth.points, 100 + 25 + 10)  # hors podium
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
        self.assertEqual(admin.points, 100 + 25 + 10)  # pas de bonus de podium
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
        self.assertEqual((a.rank, again.pk, again.points, again.errors), (1, a.pk, 100 - 5 + 50 + 25, 1))  # une faute, puis résolue

    def test_puzzle_page_shows_bonuses_then_podium(self):
        url = reverse("avent2026:puzzle", args=[self.e1.id])
        with at(1):
            self.client.force_login(self.users["alice"])
            r = self.client.get(url)
            self.assertEqual(r.context["current_points"], 100 + 50 + 25 + 10)  # si elle résolvait maintenant
            self.assertContains(r, "Sans indice")
            self.assertContains(r, "bonus « sans indice » perdu")  # prévenu avant de prendre un indice
            self.solve("alice")
            r = self.client.get(url)
            self.assertContains(r, "Premier à briser ce verrou")
            self.assertContains(r, "Podium")
            self.client.force_login(self.users["bob"])
            r = self.client.get(url)
        self.assertEqual(r.context["current_points"], 100 + 30 + 25 + 10)  # bob viserait la 2e place
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
