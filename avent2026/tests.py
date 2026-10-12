from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from . import scoring, village
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
        with mock.patch("avent2026.scoring.today", return_value=date(2026, 11, 30)):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 403)
            r = self.client.post(reverse("avent2026:answer", args=[self.enigme.id]), {"answer": "oui"})
            self.assertEqual(r.status_code, 403)
            self.assertFalse(Attempt.objects.exists())

    def test_staff_bypasses_lock(self):
        self.user.is_staff = True
        self.user.save()
        with mock.patch("avent2026.scoring.today", return_value=date(2026, 11, 1)):
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)

    def test_unlocked_day_one(self):
        day2 = Puzzle.objects.create(kind="enigme", day=2, title="E2", text="?", answers="x")
        with at(1):
            self.assertEqual(self.client.get(reverse("avent2026:home")).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[day2.id])).status_code, 403)

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
            self.assertEqual(self.client.get(reverse("avent2026:puzzle", args=[self.enigme.id])).status_code, 200)
            villages = self.client.get(reverse("avent2026:home")).context["villages"]
        states = {light["state"] for v in villages for light in v["lights"]}
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


class VillagesPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dora", password="pw")
        self.client.force_login(self.user)
        self.enigme = Puzzle.objects.create(kind="enigme", day=1, title="E", text="?", answers="oui")
        self.devinette = Puzzle.objects.create(kind="devinette", day=1, title="D", text="?", answers="non")

    def home(self):
        return self.client.get(reverse("avent2026:home"))

    def lights(self, response):
        return {(v["kind"], light["day"]): light for v in response.context["villages"] for light in v["lights"]}

    def test_two_villages_with_24_lights_each_and_states(self):
        with at(2):
            r = self.home()
        self.assertEqual([v["kind"] for v in r.context["villages"]], ["enigme", "devinette"])
        lights = self.lights(r)
        self.assertEqual(len(lights), 48)
        self.assertEqual(lights[("enigme", 1)]["state"], "open")
        self.assertEqual(lights[("devinette", 1)]["state"], "open")
        self.assertEqual(lights[("enigme", 2)]["state"], "empty")  # jour débloqué mais rien de publié
        self.assertEqual(lights[("enigme", 3)]["state"], "locked")

    def test_solving_lights_only_its_own_village(self):
        with at(1):
            self.assertEqual(self.home().context["village"]["lit"], 0)
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            r = self.home()
        lights = self.lights(r)
        self.assertEqual(lights[("devinette", 1)]["state"], "done")
        self.assertEqual(lights[("enigme", 1)]["state"], "open")
        self.assertEqual({v["kind"]: v["lit"] for v in r.context["villages"]}, {"enigme": 0, "devinette": 1})
        self.assertEqual(r.context["village"]["lit"], 1)
        self.assertEqual(r.context["scores"]["devinette"], 50)
        self.assertEqual(r.context["scores"]["devinette_solved"], 1)

    def test_locked_puzzle_title_not_exposed(self):
        Puzzle.objects.create(kind="enigme", day=5, title="TITRE-SECRET", text="?", answers="x")
        with at(1):
            self.assertNotContains(self.home(), "TITRE-SECRET")
        with at(5):
            self.assertContains(self.home(), "TITRE-SECRET")

    def test_light_positions_cover_every_day_inside_the_image(self):
        for kind in village.KINDS:
            positions = [village.light_position(kind, day) for day in range(1, village.DAYS + 1)]
            self.assertEqual(len(set(positions)), village.DAYS)  # deux lumières ne se superposent pas
            for x, y in positions:
                self.assertTrue(0 <= x <= 100 and 0 <= y <= 100)

    def test_page_works_without_illustration(self):
        with at(1):
            r = self.home()
        self.assertTrue(all(v["image"] is None for v in r.context["villages"]))  # aucune image déposée dans le dépôt
        self.assertContains(r, "village--placeholder")

    def test_illustration_is_used_when_present(self):
        with mock.patch("avent2026.village.finders.find", return_value="/x/village-enigmes.webp"):
            self.assertEqual(village.image_path("enigme"), "avent2026/img/village-enigmes.webp")

    def carte(self, response):
        return next(v for v in response.context["villages"] if v["kind"] == "devinette")["carte"]

    def test_all_25_steps_of_the_devinette_map_are_present(self):
        for step in range(village.DAYS + 1):
            self.assertIsNotNone(village.carte_image_path("devinette", step), f"étape {step} manquante")

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

    def seen_url(self):
        return reverse("avent2026:carte_seen", args=["devinette"])

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
        self.assertEqual(self.client.post(reverse("avent2026:carte_seen", args=["enigme"]), {"step": "1"}).status_code, 404)

    def test_carte_seen_never_goes_backwards(self):
        with at(1):
            self.home()  # étape 0 enregistrée
            self.client.post(self.seen_url(), {"step": "5"})
            self.client.post(self.seen_url(), {"step": "2"})
        self.assertEqual(self.client.session["avent2026_carte_devinette"], 5)

    def test_counter_is_singular_for_zero_and_one(self):
        with at(1):
            self.assertContains(self.home(), "0 bâtiment allumé sur 24")
            self.client.post(reverse("avent2026:answer", args=[self.devinette.id]), {"answer": "non"})
            self.assertContains(self.home(), "1 bâtiment allumé sur 24")

    def test_devinette_map_without_image_falls_back(self):
        with at(1), mock.patch("avent2026.village.finders.find", return_value=None):
            r = self.home()
        self.assertIsNone(self.carte(r)["image"])
        self.assertContains(r, "carte__frame--placeholder")
        self.assertContains(r, "Jour 1")  # les 24 jours restent jouables

    def test_calibration_not_available_for_step_map(self):
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.get(reverse("avent2026:calibration", args=["devinette"])).status_code, 404)

    def test_calibration_is_staff_only(self):
        url = reverse("avent2026:calibration", args=["enigme"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.user.is_staff = True
        self.user.save()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "lights-data")
        self.assertEqual(self.client.get(reverse("avent2026:calibration", args=["inconnu"])).status_code, 404)


class VillageTests(TestCase):
    def test_thresholds_and_levels(self):
        from . import village
        start = village.village_state(0)
        self.assertEqual((start["level"], start["lit"], start["next_threshold"], start["progress_pct"]), (1, 0, 6, 0))
        self.assertEqual(village.village_state(5)["level"], 1)
        self.assertEqual(village.village_state(6)["level"], 2)
        top = village.village_state(10 ** 6)  # plafonné au nombre de lumières du village
        self.assertEqual((top["lit"], top["level"], top["progress_pct"], top["next_threshold"]),
                         (village.TOTAL, len(village.LEVELS), 100, None))

    def test_each_light_makes_the_village_calmer(self):
        from . import village
        calms = [village.village_state(n)["calm"] for n in range(village.TOTAL + 1)]
        self.assertEqual(calms, sorted(calms))
        self.assertEqual((calms[0], calms[-1]), (0, 1))

    def test_last_level_reachable(self):
        """Le dernier palier se franchit sans avoir tout résolu, et le village a bien 24 jours × 2 pistes."""
        from . import village
        self.assertEqual(village.TOTAL, village.DAYS * len(village.KINDS))
        self.assertLess(village.LEVELS[-1][0], village.TOTAL)


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

    def test_epilogue_needs_both_tracks_of_day_24(self):
        e24 = Puzzle.objects.create(kind="enigme", day=24, title="Fin E", text="?", answers="x")
        d24 = Puzzle.objects.create(kind="devinette", day=24, title="Fin D", text="?", answers="x")
        with at(24):
            self.assertFalse(self.client.get(reverse("avent2026:home")).context["epilogue"])
            self.client.post(reverse("avent2026:answer", args=[d24.id]), {"answer": "x"})
            self.assertFalse(self.client.get(reverse("avent2026:home")).context["epilogue"])
            self.client.post(reverse("avent2026:answer", args=[e24.id]), {"answer": "x"})
            r = self.client.get(reverse("avent2026:home"))
            self.assertTrue(r.context["epilogue"])
            self.assertTrue(r.context["finale"])  # l'étoile du grand sapin s'allume


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
