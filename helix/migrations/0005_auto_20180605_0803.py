# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-06-05 15:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('helix', '0004_helixgreenassessment'),
    ]

    operations = [
        migrations.AddField(
            model_name='helixorganization',
            name='hes_partner_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='helixorganization',
            name='hes_partner_password',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]