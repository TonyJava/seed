# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-07-16 21:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orgs', '0006_organization_display_significant_figures'),
        ('data_importer', '0010_importfile_matching_results_data'),
        ('seed', '0090_auto_20180508_1243'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertystate',
            name='hash_object',
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='taxlotstate',
            name='hash_object',
            field=models.CharField(blank=True, default=None, max_length=32, null=True),
        ),
        migrations.AlterField(
            model_name='unit',
            name='unit_type',
            field=models.IntegerField(choices=[(1, b'String'), (6, b'Integer'), (3, b'Float'), (4, b'Date'), (5, b'Datetime')], default=1),
        ),
        migrations.RemoveField(
            model_name='propertystate',
            name='confidence',
        ),
        migrations.AlterIndexTogether(
            name='propertystate',
            index_together=set([('import_file', 'data_state'), ('hash_object',), ('analysis_state', 'organization'), ('import_file', 'data_state', 'merge_state')]),
        ),
        migrations.RemoveField(
            model_name='taxlotstate',
            name='confidence',
        ),
        migrations.AlterIndexTogether(
            name='taxlotstate',
            index_together=set([('import_file', 'data_state'), ('hash_object',), ('import_file', 'data_state', 'merge_state')]),
        ),
    ]
