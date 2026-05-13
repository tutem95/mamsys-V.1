"""Seed inicial de monedas globales: ARS, USD, EUR."""

from django.db import migrations


SEED = [
    {"code": "ARS", "name": "Peso argentino", "symbol": "$"},
    {"code": "USD", "name": "Dólar estadounidense", "symbol": "US$"},
    {"code": "EUR", "name": "Euro", "symbol": "€"},
]


def forwards(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    for row in SEED:
        Currency.objects.update_or_create(code=row["code"], defaults=row)


def backwards(apps, schema_editor):
    Currency = apps.get_model("currencies", "Currency")
    Currency.objects.filter(code__in=[r["code"] for r in SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [("currencies", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]
