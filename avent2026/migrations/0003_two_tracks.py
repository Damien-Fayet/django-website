from django.db import migrations, models


def keep_one_per_kind_and_day(apps, schema_editor):
    """Avant la contrainte (kind, day) : garde un seul puzzle par type et par jour (le « facile » en priorité).

    Les indices, tentatives et révélations des puzzles supprimés partent en cascade. Seul du contenu de test
    existe avant décembre 2026.
    """
    Puzzle = apps.get_model("avent2026", "Puzzle")
    seen = set()
    candidates = sorted(Puzzle.objects.all(), key=lambda p: (p.kind, p.day, p.difficulty != "facile", p.id))
    for puzzle in candidates:
        key = (puzzle.kind, puzzle.day)
        if key in seen:
            puzzle.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ("avent2026", "0002_puzzle_story"),
    ]

    operations = [
        migrations.RunPython(keep_one_per_kind_and_day, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="puzzle", name="uniq_avent2026_puzzle"),
        migrations.RemoveField(model_name="puzzle", name="difficulty"),
        migrations.AlterModelOptions(name="puzzle", options={"ordering": ["day", "kind"]}),
        migrations.AddConstraint(
            model_name="puzzle",
            constraint=models.UniqueConstraint(fields=("kind", "day"), name="uniq_avent2026_puzzle"),
        ),
    ]
