"""Supprime les tables des éditions avent2024 et avent2025 (apps retirées du projet).

Irréversible : sauvegarder db.sqlite3 avant de lancer `migrate`.
"""
from django.db import migrations

LEGACY_APPS = ("avent2024", "avent2025")


def drop_legacy(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = [
            t for t in connection.introspection.table_names(cursor)
            if t.startswith(tuple(f"{a}_" for a in LEGACY_APPS))
        ]
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
        for app in LEGACY_APPS:
            cursor.execute("DELETE FROM django_migrations WHERE app = %s", [app])

    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label__in=LEGACY_APPS).delete()  # supprime aussi les permissions


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(drop_legacy, migrations.RunPython.noop),
    ]
