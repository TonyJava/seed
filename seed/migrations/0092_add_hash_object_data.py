# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-07-26 14:17
from __future__ import unicode_literals
from seed.data_importer.tasks import hash_state_object

from itertools import chain

from django.db import migrations


# Go through every property and tax lot and simply save it to create the hash_object
def forwards(apps, schema_editor):
    PropertyState = apps.get_model("seed", "PropertyState")
    TaxLotState = apps.get_model("seed", "TaxLotState")

    # find which columns are not used in column mappings
    property_count = PropertyState.objects.all().count()
    taxlot_count = TaxLotState.objects.all().count()
    print "Thereare %s objects to traverse" % (property_count + taxlot_count)

    print "Iterating over PropertyStates. Count %s" % PropertyState.objects.all().count()
    for idx, obj in enumerate(PropertyState.objects.all().iterator()):
        if idx % 1000 == 0:
            print "... %s / %s ..." % (idx, property_count)
        obj.hash_object = hash_state_object(obj)
        obj.save()

    print "Iterating over TaxLotStates. Count %s" % TaxLotState.objects.all().count()
    for idx, obj in enumerate(TaxLotState.objects.all().iterator()):
        if idx % 1000 == 0:
            print "... %s / %s ..." % (idx, taxlot_count)
        obj.hash_object = hash_state_object(obj)
        obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('seed', '0091_auto_20180725_2039'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]
