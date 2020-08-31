# SPDX-License-Identifier: EUPL-1.2
# Copyright (C) 2019 - 2020 Dimpact
# Generated by Django 2.2.10 on 2020-08-17 12:12

from django.db import migrations, models

import django_better_admin_arrayfield.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ("selectielijst", "0005_auto_20200807_1410"),
    ]

    operations = [
        migrations.AlterField(
            model_name="referentielijstconfig",
            name="allowed_years",
            field=django_better_admin_arrayfield.models.fields.ArrayField(
                base_field=models.PositiveIntegerField(),
                default=list,
                help_text="De jaartallen waarvan er procestypen gebruikt mogen worden.",
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="referentielijstconfig",
            name="default_year",
            field=models.PositiveIntegerField(
                help_text="Het jaartal dat standaard geselecteerd is bij het kiezen van een procestype bij een zaaktype.",
                null=True,
            ),
        ),
    ]