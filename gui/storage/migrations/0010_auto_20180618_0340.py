# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-06-18 03:40
from __future__ import unicode_literals

from django.db import migrations, models


def create_root_dataset(apps, schema_editor):
    RootDataset = apps.get_model('storage', 'rootdataset')
    rd = RootDataset()
    rd.quota_warning = 0.8
    rd.quota_critical = 0.95
    rd.refquota_warning = 0.8
    rd.refquota_critical = 0.95
    rd.save()


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0009_disk_disk_passwd'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, unique=True)),
                ('quota_warning', models.FloatField(null=True)),
                ('quota_critical', models.FloatField(null=True)),
                ('refquota_warning', models.FloatField(null=True)),
                ('refquota_critical', models.FloatField(null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RootDataset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quota_warning', models.FloatField()),
                ('quota_critical', models.FloatField()),
                ('refquota_warning', models.FloatField()),
                ('refquota_critical', models.FloatField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.DeleteModel(
            name='QuotaExcess',
        ),
        migrations.RunPython(create_root_dataset),
    ]
