# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2016, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""
import csv
import datetime
import json
import logging
import os.path
from unittest import skip

from dateutil import parser
from mock import patch

from django.core.files import File
from django.test import TestCase

from seed.data_importer import tasks
from seed.data_importer.models import ImportFile, ImportRecord
from seed.data_importer.tasks import save_raw_data, map_data
from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser

from seed.models import (
    ASSESSED_RAW,
    ASSESSED_BS,
    DATA_STATE_IMPORT,
    # DATA_STATE_MAPPING,
    PORTFOLIO_BS,
    POSSIBLE_MATCH,
    SYSTEM_MATCH,
)
from seed.models import (
    Column,
    ColumnMapping,
    Cycle,
    PropertyState,
    PropertyView,
)
from seed.models import (
    get_ancestors,
)
from seed.tests import util
from seed.data_importer.tests.util import (
    FAKE_EXTRA_DATA, FAKE_MAPPINGS, FAKE_ROW, PROPERTIES_MAPPING,
)


logger = logging.getLogger(__name__)


class DataMappingBaseTestCase(TestCase):
    """Base Test Case Class to handle data import"""

    def set_up(self, import_file_source_type):

        # default_values
        import_file_is_espm = getattr(self, 'import_file_is_espm', True)
        import_file_data_state = getattr(
            self, 'import_file_data_state', DATA_STATE_IMPORT
        )

        user = User.objects.create(username='test')
        org = Organization.objects.create()

        # Create an org user
        OrganizationUser.objects.create(
            user=user,
            organization=org
        )

        import_record = ImportRecord.objects.create(
            owner=user, last_modified_by=user, super_organization=org
        )
        import_file = ImportFile.objects.create(import_record=import_record)
        import_file.is_espm = import_file_is_espm
        import_file.source_type = import_file_source_type
        import_file.data_state = import_file_data_state
        import_file.save()
        return user, org, import_file, import_record

    def load_import_file_file(self, filename, import_file):
        f = os.path.join(os.path.dirname(__file__), 'data', filename)
        import_file.file = File(open(f))
        import_file.save()
        return import_file

    def tearDown(self):
        User.objects.all().delete()
        ColumnMapping.objects.all().delete()
        ImportFile.objects.all().delete()
        ImportRecord.objects.all().delete()
        OrganizationUser.objects.all().delete()
        Organization.objects.all().delete()
        User.objects.all().delete()
        Cycle.objects.all().delete()
        PropertyState.objects.all().delete()


class TestMapping(DataMappingBaseTestCase):
    """Tests for dealing with SEED related tasks for mapping data."""

    def setUp(self):
        # Make sure to delete the old mappings and properties because this
        # tests expects very specific column names and properties in order
        filename = getattr(self, 'filename', 'portfolio-manager-sample.csv')
        import_file_source_type = 'PORTFOLIO_RAW'
        self.fake_mappings = FAKE_MAPPINGS['short']
        self.fake_extra_data = FAKE_EXTRA_DATA
        self.fake_row = FAKE_ROW
        selfvars = self.set_up(import_file_source_type)
        self.user, self.org, self.import_file, self.import_record = selfvars
        self.import_file = self.load_import_file_file(
            filename, self.import_file
        )

    def test_cached_first_row_order(self):
        """Tests to make sure the first row is saved in the correct order.
        It should be the order of the headers in the original file."""
        with patch.object(ImportFile, 'cache_first_rows', return_value=None):
            tasks._save_raw_data(
                self.import_file.pk,
                'fake_cache_key',
                1
            )
        expected_first_row = u"Property Id|#*#|Property Name|#*#|Year Ending|#*#|Property Floor Area (Buildings and Parking) (ft2)|#*#|Address 1|#*#|Address 2|#*#|City|#*#|State/Province|#*#|Postal Code|#*#|Year Built|#*#|ENERGY STAR Score|#*#|Site EUI (kBtu/ft2)|#*#|Total GHG Emissions (MtCO2e)|#*#|Weather Normalized Site EUI (kBtu/ft2)|#*#|National Median Site EUI (kBtu/ft2)|#*#|Source EUI (kBtu/ft2)|#*#|Weather Normalized Source EUI (kBtu/ft2)|#*#|National Median Source EUI (kBtu/ft2)|#*#|Parking - Gross Floor Area (ft2)|#*#|Organization|#*#|Generation Date|#*#|Release Date"    # NOQA

        import_file = ImportFile.objects.get(pk=self.import_file.pk)
        first_row = import_file.cached_first_row
        self.assertEqual(first_row, expected_first_row)

    def test_save_raw_data(self):
        """Save information in extra_data, set other attrs."""
        with patch.object(ImportFile, 'cache_first_rows', return_value=None):
            tasks._save_raw_data(
                self.import_file.pk,
                'fake_cache_key',
                1
            )

        raw_saved = PropertyState.objects.filter(
            import_file=self.import_file,
        ).latest('id')

        self.assertDictEqual(raw_saved.extra_data, self.fake_extra_data)
        self.assertEqual(raw_saved.organization, self.org)

    def test_map_data(self):
        """Save mappings based on user specifications."""
        self.import_file.raw_save = True
        self.import_file.save()
        fake_raw_bs = PropertyState.objects.create(
            import_file=self.import_file,
            extra_data=self.fake_row,
            source_type=ASSESSED_RAW,
            data_state=DATA_STATE_IMPORT,
        )

        util.make_fake_mappings(self.fake_mappings, self.org)

        tasks.map_data(self.import_file.pk)

        mapped_bs = list(PropertyState.objects.filter(
            import_file=self.import_file,
            source_type=ASSESSED_BS,
        ))

        self.assertEqual(len(mapped_bs), 1)

        test_bs = mapped_bs[0]

        self.assertNotEqual(test_bs.pk, fake_raw_bs.pk)
        self.assertEqual(test_bs.property_name, self.fake_row['Name'])
        self.assertEqual(
            test_bs.address_line_1, self.fake_row['Address Line 1']
        )
        self.assertEqual(
            test_bs.year_built,
            parser.parse(self.fake_row['Year Built']).year
        )

        # Make sure that we saved the extra_data column mappings
        data_columns = Column.objects.filter(
            organization=test_bs.organization,
            is_extra_data=True
        )

        # There's only one peice of data that didn't cleanly map
        self.assertListEqual(
            sorted([d.column_name for d in data_columns]), ['Double Tester']
        )

    def test_mapping_w_concat(self):
        """When we have a json encoded list as a column mapping, we concat."""
        fake_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            raw_save_done=True
        )
        self.fake_row['City'] = 'Someplace Nice'
        PropertyState.objects.create(
            import_file=fake_import_file,
            source_type=ASSESSED_RAW,
            extra_data=self.fake_row,
            data_state=DATA_STATE_IMPORT,
        )

        self.fake_mappings['address_line_1'] = ['Address Line 1', 'City']
        util.make_fake_mappings(self.fake_mappings, self.org)

        tasks.map_data(fake_import_file.pk)

        mapped_bs = list(PropertyState.objects.filter(
            import_file=fake_import_file,
            source_type=ASSESSED_BS,
        ))[0]

        self.assertEqual(
            mapped_bs.address_line_1, u'1600 Pennsylvania Ave. Someplace Nice'
        )


class TestMatching(DataMappingBaseTestCase):
    def setUp(self):
        assert len(PropertyState.objects.all()) == 0
        filename = getattr(self, 'filename', 'example-data-properties.xlsx')
        import_file_source_type = ASSESSED_RAW
        self.fake_mappings = FAKE_MAPPINGS['short']
        self.fake_extra_data = FAKE_EXTRA_DATA
        self.fake_row = FAKE_ROW
        selfvars = self.set_up(import_file_source_type)
        self.user, self.org, self.import_file, self.import_record = selfvars
        assert self.org is not None
        self.import_file = self.load_import_file_file(
            filename, self.import_file
        )
        save_raw_data(self.import_file.id)
        Column.create_mappings(PROPERTIES_MAPPING,
                               self.org, self.user)
        map_data(self.import_file.id)
        self.import_record.save()  # May not be needed here
        self.psn = len(PropertyState.objects.all())

    def test_is_same_snapshot(self):
        """Test to check if two snapshots are duplicates"""

        # TODO: Fix the PM, tax lot id, and custom ID fields in PropertyState
        bs_data = {
            'pm_property_id': 1243,
            # 'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 12,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        s1 = util.make_fake_property(
            self.import_file, bs_data, ASSESSED_BS, is_canon=True,
            org=self.org
        )

        self.assertTrue(tasks.is_same_snapshot(s1, s1),
                        "Matching a snapshot to itself should return True")

        # Making a different snapshot
        # now Garfield complex rather than Greenfield complex
        bs_data_2 = {
            'pm_property_id': 1243,
            # 'tax_lot_id': '435/422',
            'property_name': 'Garfield Complex',
            'custom_id_1': 12,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        s2 = util.make_fake_property(
            self.import_file, bs_data_2, ASSESSED_BS, is_canon=True,
            org=self.org
        )

        self.assertFalse(
            tasks.is_same_snapshot(s1, s2),
            "Matching a snapshot to a different snapshot should return False"
        )

    def test_match_buildings(self):
        """Good case for testing our matching system."""

        cycle, _ = Cycle.objects.get_or_create(
            name=u'Test Hack Cycle 2015',
            organization=self.org,
            start=datetime.datetime(2015, 1, 1),
            end=datetime.datetime(2015, 12, 31),
        )

        # Was:
        # ps = PropertyState.objects.filter(
        #     data_state=DATA_STATE_MAPPING, organization=self.org
        # )
        # Should be ?
        ps = PropertyState.objects.filter(
            data_state=DATA_STATE_IMPORT, organization=self.org
        )
        assert len(ps) != 0
        print len(ps), self.psn
        psx = len(PropertyState.objects.filter(organization=self.org))
        assert psx == len(ps)
        has_org = []
        no_org = []
        for p in PropertyState.objects.all():
            if p.organization is None:
                no_org.append(p)
            else:
                has_org.append(p)
        print '>>>', len(no_org), len(has_org)
        hol = [p.pm_property_id for p in has_org]
        nol = [p.pm_property_id for p in no_org]
        print ':::', hol, nol
        for i in hol:
            if i in nol:
                print i, '<<<'

        # Promote case A (one property <-> one tax lot)
        psa = PropertyState.objects.filter(pm_property_id=2264).first()
        # psa = ps.filter(pm_property_id=2264)
        # assert len(psa) != 0
        assert psa is not None
        print type(psa)
        # for f in psa._meta.get_fields():
        #     print f, getattr(psa, f.name, 'blank')
        assert psa.organization is not None
        psa.promote(cycle)

        ps = tasks.get_canonical_snapshots(self.org)
        from django.db.models.query import QuerySet
        self.assertTrue(isinstance(ps, QuerySet))
        logger.debug("There are %s properties" % len(ps))
        for p in ps:
            from seed.utils.generic import pp
            pp(p)

        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0].address_line_1, '50 Willow Ave SE')

        # # Promote 5 of these to views to test the remaining code
        # promote_mes = PropertyState.objects.filter(
        #     data_state=DATA_STATE_MAPPING,
        #     organization=self.org)[:5]
        # for promote_me in promote_mes:
        #     promote_me.promote(cycle)
        #
        # ps = tasks.get_canonical_snapshots(self.org)
        # from django.db.models.query import QuerySet
        # self.assertTrue(isinstance(ps, QuerySet))
        # logger.debug("There are %s properties" % len(ps))
        # for p in ps:
        #     print p
        #
        # self.assertEqual(len(ps), 5)
        # self.assertEqual(ps[0].address_line_1, '1211 Bryant Street')
        # self.assertEqual(ps[4].address_line_1, '1031 Ellis Lane')

        # tasks.match_buildings(self.import_file.pk, self.user.pk)

        # self.assertEqual(result.property_name, snapshot.property_name)
        # self.assertEqual(result.property_name, new_snapshot.property_name)
        # # Since these two buildings share a common ID, we match that way.
        # # self.assertEqual(result.confidence, 0.9)
        # self.assertEqual(
        #     sorted([r.pk for r in result.parents.all()]),
        #     sorted([new_snapshot.pk, snapshot.pk])
        # )
        # self.assertGreater(AuditLog.objects.count(), 0)
        # self.assertEqual(
        #     AuditLog.objects.first().action_note,
        #     'System matched building ID.'
        # )

    @skip("Fix for new data model")
    def test_match_duplicate_buildings(self):
        """
        Test for behavior when trying to match duplicate building data
        """
        # TODO: Fix the PM, tax lot id, and custom ID fields in PropertyState
        bs_data = {
            # 'pm_property_id': "8450",
            # 'tax_lot_id': '143/292',
            'property_name': 'Greenfield Complex',
            # 'custom_id_1': "99",
            'address_line_1': '93754 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': "8999",
        }

        import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )

        # Setup mapped PM snapshot.
        util.make_fake_property(
            import_file, bs_data, PORTFOLIO_BS, is_canon=True,
            org=self.org
        )
        # Different file, but same ImportRecord.
        # Setup mapped PM snapshot.
        # Should be a duplicate.
        new_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )

        util.make_fake_property(
            new_import_file, bs_data, PORTFOLIO_BS, org=self.org
        )

        tasks.match_buildings(import_file.pk, self.user.pk)
        tasks.match_buildings(new_import_file.pk, self.user.pk)

        self.assertEqual(len(PropertyState.objects.all()), 2)

    @skip("Fix for new data model")
    def test_handle_id_matches_duplicate_data(self):
        """
        Test for handle_id_matches behavior when matching duplicate data
        """
        # TODO: Fix the PM, tax lot id, and custom ID fields in PropertyState
        bs_data = {
            # 'pm_property_id': "2360",
            # 'tax_lot_id': '476/460',
            'property_name': 'Garfield Complex',
            # 'custom_id_1': "89",
            'address_line_1': '12975 Database LN.',
            'address_line_2': '',
            'city': 'Cartoon City',
            'postal_code': "54321",
        }

        # Setup mapped AS snapshot.
        util.make_fake_property(
            self.import_file, bs_data, ASSESSED_BS, is_canon=True,
            org=self.org
        )

        # Different file, but same ImportRecord.
        # Setup mapped PM snapshot.
        # Should be an identical match.
        new_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )

        tasks.match_buildings(new_import_file.pk, self.user.pk)

        duplicate_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )

        new_snapshot = util.make_fake_property(
            duplicate_import_file, bs_data, PORTFOLIO_BS, org=self.org
        )

        self.assertRaises(tasks.DuplicateDataError, tasks.handle_id_matches,
                          new_snapshot, duplicate_import_file,
                          self.user.pk)

    @skip("Fix for new data model")
    def test_match_no_matches(self):
        """When a canonical exists, but doesn't match, we create a new one."""
        # TODO: Fix the PM, tax lot id, and custom ID fields in PropertyState
        bs1_data = {
            # 'pm_property_id': 1243,
            # 'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            # 'custom_id_1': 1243,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        bs2_data = {
            # 'pm_property_id': 9999,
            # 'tax_lot_id': '1231',
            'property_name': 'A Place',
            # 'custom_id_1': 0o000111000,
            'address_line_1': '44444 Hmmm Ave.',
            'address_line_2': 'Apt 4',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        snapshot = util.make_fake_property(
            self.import_file, bs1_data, ASSESSED_BS, is_canon=True
        )
        new_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )
        new_snapshot = util.make_fake_property(
            new_import_file, bs2_data, PORTFOLIO_BS, org=self.org
        )

        self.assertEqual(PropertyState.objects.all().count(), 2)

        tasks.match_buildings(new_import_file.pk, self.user.pk)

        # E.g. we didn't create a match
        self.assertEqual(PropertyState.objects.all().count(), 2)
        latest_snapshot = PropertyState.objects.get(pk=new_snapshot.pk)

        # But we did create another canonical building for the unmatched bs.
        self.assertNotEqual(latest_snapshot.canonical_building, None)
        self.assertNotEqual(
            latest_snapshot.canonical_building.pk,
            snapshot.canonical_building.pk
        )

        self.assertEqual(latest_snapshot.confidence, None)

    @skip("Fix for new data model")
    def test_match_no_canonical_buildings(self):
        """If no canonicals exist, create, but no new PropertyStates."""
        bs1_data = {
            'pm_property_id': 1243,
            'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 1243,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        # Note: no Canonical Building is created for this snapshot.
        snapshot = util.make_fake_property(
            self.import_file, bs1_data, ASSESSED_BS, is_canon=False,
            org=self.org
        )

        self.import_file.mapping_done = True
        self.import_file.save()

        self.assertEqual(snapshot.canonical_building, None)
        self.assertEqual(PropertyState.objects.all().count(), 1)

        tasks.match_buildings(self.import_file.pk, self.user.pk)

        refreshed_snapshot = PropertyState.objects.get(pk=snapshot.pk)
        self.assertNotEqual(refreshed_snapshot.canonical_building, None)
        self.assertEqual(PropertyState.objects.all().count(), 1)

    @skip("Fix for new data model")
    def test_no_unmatched_buildings(self):
        """Make sure we shortcut out if there isn't unmatched data."""
        bs1_data = {
            'pm_property_id': 1243,
            'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 1243,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        self.import_file.mapping_done = True
        self.import_file.save()
        util.make_fake_property(
            self.import_file, bs1_data, ASSESSED_BS, is_canon=True
        )

        self.assertEqual(PropertyState.objects.all().count(), 1)

        tasks.match_buildings(self.import_file.pk, self.user.pk)

        self.assertEqual(PropertyState.objects.all().count(), 1)

    @skip("Fix for new data model")
    def test_separates_system_and_possible_match_types(self):
        """We save possible matches separately."""
        bs1_data = {
            'pm_property_id': 123,
            'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 1243,
            'address_line_1': '555 NorthWest Databaseer Lane.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }
        # This building will have a lot less data to identify it.
        bs2_data = {
            'pm_property_id': 1243,
            'custom_id_1': 1243,
            'address_line_1': '555 Database LN.',
            'city': 'Gotham City',
            'postal_code': 8999,
        }
        new_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            mapping_done=True
        )

        util.make_fake_property(
            self.import_file, bs1_data, ASSESSED_BS, is_canon=True,
            org=self.org
        )

        util.make_fake_property(
            new_import_file, bs2_data, PORTFOLIO_BS, org=self.org
        )

        tasks.match_buildings(new_import_file.pk, self.user.pk)

        self.assertEqual(
            PropertyState.objects.filter(match_type=POSSIBLE_MATCH).count(),
            0
        )
        self.assertEqual(
            PropertyState.objects.filter(match_type=SYSTEM_MATCH).count(),
            1
        )

    # Will be obsolete
    @skip("Fix for new data model")
    def test_get_ancestors(self):
        """Tests get_ancestors(building), returns all non-composite, non-raw
            PropertyState instances.
        """
        bs_data = {
            'pm_property_id': 1243,
            'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 1243,
            'address_line_1': '555 Database LN.',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        # Since we changed to not match duplicate data make a second record
        # that matches with something slighty changed
        # In this case appended a 'A' to the end of address_line_1
        bs_data_2 = {
            'pm_property_id': 1243,
            'tax_lot_id': '435/422',
            'property_name': 'Greenfield Complex',
            'custom_id_1': 1243,
            'address_line_1': '555 Database LN. A',
            'address_line_2': '',
            'city': 'Gotham City',
            'postal_code': 8999,
        }

        # Setup mapped AS snapshot.
        util.make_fake_property(
            self.import_file, bs_data, ASSESSED_BS, is_canon=True,
            org=self.org
        )
        # Different file, but same ImportRecord.
        # Setup mapped PM snapshot.
        # Should be an identical match.
        new_import_file = ImportFile.objects.create(
            import_record=self.import_record,
            raw_save_done=True,
            mapping_done=True
        )

        util.make_fake_property(
            new_import_file, bs_data_2, PORTFOLIO_BS, org=self.org
        )

        tasks.match_buildings(new_import_file.pk, self.user.pk)

        result = PropertyState.objects.filter(source_type=4)[0]
        ancestor_pks = set([b.pk for b in get_ancestors(result)])
        buildings = PropertyState.objects.filter(
            source_type__in=[2, 3]
        ).exclude(
            pk=result.pk
        )
        building_pks = set([b.pk for b in buildings])

        self.assertEqual(ancestor_pks, building_pks)

    @skip("Fix for new data model")
    def test_save_raw_data_batch_iterator(self):
        """Ensure split_csv completes"""
        tasks.save_raw_data(self.import_file.pk)

        self.assertEqual(PropertyState.objects.filter(
            import_file=self.import_file
        ).count(), 512)


class TestPromotingProperties(DataMappingBaseTestCase):

    def setUp(self):
        filename = 'propertystates-one-cycle.csv'
        import_file_source_type = ASSESSED_RAW,
        fake_mappings = FAKE_MAPPINGS['full']
        super(TestPromotingProperties, self).setUp(
            import_file_source_type, fake_mappings
        )
        self.import_exported_data(filename)

    def import_exported_data(self, filename):
        """
        Import test files from Stephen for many-to-many testing. This imports
        and maps the data accordingly. Presently these files are missing a
        couple of attributes to make them valid:
            1) the master campus record to define the pm_property_id
            2) the joins between propertystate and taxlotstate
        """

        # Do a bunch of work to flatten out this temp file that has extra_data
        # asa string representation of a dict
        data = []
        keys = None
        new_keys = set()

        f = os.path.join(os.path.dirname(__file__), 'data', filename)
        with open(f, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            keys = reader.fieldnames
            for row in reader:
                ed = json.loads(row.pop('extra_data'))
                for k, v in ed.iteritems():
                    new_keys.add(k)
                    row[k] = v
                data.append(row)

        # remove the extra_data column and add in the new columns
        keys.remove('extra_data')
        for k in new_keys:
            keys.append(k)

        # save the new file
        new_file_name = 'tmp_{}_flat.csv'.format(
            os.path.splitext(os.path.basename(filename))[0]
        )
        f_new = os.path.join(os.path.dirname(__file__), 'data', new_file_name)
        with open(f_new, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=keys)
            writer.writeheader()
            for d in data:
                writer.writerow(d)

        # save the keys         This doesn't appear to be used anywhere
        new_file_name = 'tmp_{}_keys.csv'.format(
            os.path.splitext(os.path.basename(filename))[0]
        )
        f_new = os.path.join(os.path.dirname(__file__), 'data', new_file_name)
        with open(f_new, 'w') as outfile:
            outfile.writelines([str(key) + '\n' for key in keys])

        # Continue saving the raw data
        new_file_name = "tmp_{}_flat.csv".format(
            os.path.splitext(os.path.basename(filename))[0]
        )
        f_new = os.path.join(os.path.dirname(__file__), 'data', new_file_name)
        self.import_file.file = File(open(f_new))
        self.import_file.save()

        save_raw_data(self.import_file.id)

        # the mapping is just the 'keys' repeated since the file
        # was created as a database dump
        mapping = []
        for k in keys:
            if k == 'id':
                continue
            mapping.append(
                {
                    "from_field": k,
                    "to_table_name": "PropertyState",
                    "to_field": k
                }
            )

        Column.create_mappings(mapping, self.org, self.user)

        # call the mapping function from the tasks file
        map_data(self.import_file.id)

#     def test_promote_properties(self):
#         """Good case for testing our matching system."""

#         cycle, _ = Cycle.objects.get_or_create(
#             name=u'Hack Cycle 2015',
#             organization=self.org,
#             start=datetime.datetime(2015, 1, 1),
#             end=datetime.datetime(2015, 12, 31),
#         )

#         cycle2, _ = Cycle.objects.get_or_create(
#             name=u'Hack Cycle 2016',
#             organization=self.org,
#             start=datetime.datetime(2016, 1, 1),
#             end=datetime.datetime(2016, 12, 31),
#         )

#         # make sure that the new data was loaded correctly
#         ps = PropertyState.objects.filter(
#             address_line_1='1181 Douglas Street')[0]
#         self.assertEqual(ps.site_eui, 439.9)
#         self.assertEqual(ps.extra_data['CoStar Property ID'], '1575599')

#         # Promote the PropertyState to a PropertyView
#         pv1 = ps.promote(cycle)
#         pv2 = ps.promote(cycle)  # should just return the same object
#         self.assertEqual(pv1, pv2)

#         # promote the same state for a new cycle, same data
#         pv3 = ps.promote(cycle2)
#         self.assertNotEqual(pv3, pv1)

#         props = PropertyView.objects.all()
#         self.assertEqual(len(props), 2)


# # TODO: inherit from TestMatching once this is fixed
# class TestTasksXLS(TestMappingBase):
#     """Runs the TestTasks tests with an XLS file"""

#     def setUp(self):
#         filename = 'portfolio-manager-sample.xls'
#         import_file_source_type = 'PORTFOLIO_RAW'
#         fake_mappings = FAKE_MAPPINGS['short']
#         super(TestTasksXLS, self).setUp(
#             filename, import_file_source_type, fake_mappings
#         )
#         # Make the field match on an integer because XLS mapping handles casting
#         self.fake_extra_data['Property Id'] = 101125


# class TestTasksXLSX(TestMappingBase):
#     """Runs the TestsTasks tests with an XLSX file."""
#     def setUp(self):
#         filename = 'portfolio-manager-sample.xlsx'
#         import_file_source_type = 'PORTFOLIO_RAW'
#         fake_mappings = FAKE_MAPPINGS['short']
#         super(TestTasksXLSX, self).setUp(
#             filename, import_file_source_type, fake_mappings
#         )
#         # Make the field match on an integer because XLS mapping handles casting
#         self.fake_extra_data['Property Id'] = 101125
