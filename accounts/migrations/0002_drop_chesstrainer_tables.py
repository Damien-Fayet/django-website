"""Supprime les tables de l'app chessTrainer (app retirée du projet).

Irréversible : sauvegarder db.sqlite3 avant de lancer `migrate`.
"""
from django.db import migrations

LEGACY_APP = "chessTrainer"


def drop_legacy(apps, schema_editor):
    connection = schema_editor.connection
    prefix = f"{LEGACY_APP}_".lower()
    with connection.cursor() as cursor:
        tables = [
            t for t in connection.introspection.table_names(cursor)
            if t.lower().startswith(prefix)
        ]
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
        cursor.execute("DELETE FROM django_migrations WHERE app = %s", [LEGACY_APP])

    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label=LEGACY_APP).delete()  # supprime aussi les permissions


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_drop_legacy_avent_tables"),
    ]

    operations = [
        migrations.RunPython(drop_legacy, migrations.RunPython.noop),
    ]
