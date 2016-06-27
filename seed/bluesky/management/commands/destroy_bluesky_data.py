from __future__ import unicode_literals

from django.db import models, migrations
from django.core.management.base import BaseCommand
from django.apps import apps

def delete_based_on_org(apps, org):
#     Things that can be deleted because they have a direct reference to an org:
# 
#     Cycle
#     Property
#     TaxLot
#     
#     Things that can be deleted because they have a reference to something with a direct reference:
#     
#     PropertyView -> Cycle
#     TaxLotView -> Cycle
#     TaxLotProperty -> Cycle
#     
#     Things that are 2 levels removed:
#     PropertyState <- PropertyView
#     TaxLotState <- TaxLotView
#     
#     Order of deletion:
#     
#     Delete PropertyStates and TaxLotStates     
#     Delete PropertyViews, TaxLotViews, and TaxLotProperties
#     Delete Cycles, Properties, TaxLots
    
    apps.get_model("bluesky", "PropertyState").objects.filter(propertyview__cycle__organization__id = org).delete()
    apps.get_model("bluesky", "TaxLotState").objects.filter(taxlotview__cycle__organization__id = org).delete()
    
    apps.get_model("bluesky", "PropertyView").objects.filter(cycle__organization__id = org).delete()
    apps.get_model("bluesky", "TaxLotView").objects.filter(cycle__organization__id = org).delete()
    apps.get_model("bluesky", "TaxLotProperty").objects.filter(cycle__organization__id = org).delete()
    
    apps.get_model("bluesky", "Cycle").objects.filter(organization__id = org).delete()
    apps.get_model("bluesky", "Property").objects.filter(organization__id = org).delete()
    apps.get_model("bluesky", "TaxLot").objects.filter(organization__id = org).delete()
    
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--org', dest='organizations', default=False, type=str)
        return
    
    def handle(self, *args, **options):
        print "Destroying Blue Sky Data"        
        
        if 'organizations' in options:
            orgs_to_delete = options['organizations']
            orgs_to_delete = orgs_to_delete.split(",")
            orgs_to_delete = [int(x) for x in orgs_to_delete]
            for org in orgs_to_delete:
                delete_based_on_org(apps, org)
            
        else:
            apps.get_model("bluesky", "Cycle").objects.all().delete()
            apps.get_model("bluesky", "PropertyState").objects.all().delete()
            apps.get_model("bluesky", "PropertyView").objects.all().delete()
            apps.get_model("bluesky", "Property").objects.all().delete()
            apps.get_model("bluesky", "TaxLotState").objects.all().delete()
            apps.get_model("bluesky", "TaxLotView").objects.all().delete()
            apps.get_model("bluesky", "TaxLot").objects.all().delete()
            apps.get_model("bluesky", "TaxLotProperty").objects.all().delete()

        return
