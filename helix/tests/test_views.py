from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core import management
from django.utils import timezone

from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.models import Cycle, PropertyView
from seed.data_importer.models import ImportRecord

from helix.models import HelixMeasurement


class TestHelixView(TestCase):

    def setUp(self):
        management.call_command('loaddata', 'doe_org.json', verbosity=0)
        management.call_command('loaddata', 'greenassessments.json', verbosity=0)

        self.user = User.objects.create(username='test_user@demo.com')
        self.user.set_password('test_pass')
        self.user.email = 'test_user@demo.com'
        self.user.save()

        self.org = Organization.objects.create()
        OrganizationUser.objects.create(user=self.user, organization=self.org)

        self.user.default_organization_id = self.org.id
        self.user.save()

        self.client.login(username='test_user@demo.com', password='test_pass')

        self.cycle = Cycle.objects.create(
                organization=self.org,
                user=self.user,
                name="test",
                start=timezone.now(),
                end=timezone.now()
        )
        self.cycle.save()

        self.record = ImportRecord.objects.create(
                name='test',
                app='seed',
                start_time=timezone.now(),
                created_at=timezone.now(),
                last_modified_by=self.user,
                super_organization=self.org,
                owner=self.user
        )

        self.user_name = 'TST-HELIX'
        self.password = 'helix123'
        self.user_key = '520df908c6cb4bea8c14691ee95aff88'
        self.building_id = '142860'

    def test_helix_home(self):
        res = self.client.get(reverse('helix:helix_home'))
        self.assertEqual(200, res.status_code)

    # Check that a simple case of helix_hes return the correct status code
    # when completed successfully.
    def test_helix_hes(self):
        data = {'user_key': self.user_key,
                'user_name': self.user_name,
                'password': self.password,
                'building_id': self.building_id,
                'dataset': self.record.pk,
                'cycle': self.cycle.pk}
        res = self.client.post(reverse('helix:helix_hes'), data)
        self.assertEqual(200, res.status_code)

    def test_helix_hes_bad_id_400(self):
        data = {'user_key': self.user_key,
                'user_name': self.user_name,
                'password': self.password,
                'building_id': '123456',
                'dataset': self.record.pk,
                'cycle': self.cycle.pk}

        res = self.client.post(reverse('helix:helix_hes'), data)
        self.assertEqual(400, res.status_code)

    def test_helix_hes_bad_hes_key_400(self):
        data = {'user_key': 'ce4cdc28710349a1bbb4b7a047b65827',
                'user_name': self.user_name,
                'password': self.password,
                'building_id': self.building_id,
                'dataset': self.record.pk,
                'cycle': self.cycle.pk}

        res = self.client.post(reverse('helix:helix_hes'), data)
        self.assertEqual(400, res.status_code)

    # Check that the most basic upload case returns the expected status
    # Does not verify the end state of the database is correct
    def test_helix_csv_upload(self):
        with open('./helix/helix_upload_sample.csv') as csv:
            data = {'user_key': self.user_key,
                    'user_name': self.user_name,
                    'password': self.password,
                    'dataset': self.record.pk,
                    'cycle': self.cycle.pk,
                    'helix_csv': csv}
            res = self.client.post(reverse('helix:helix_csv_upload'), data)
            self.assertEqual(302, res.status_code)

    def test_helix_csv_upload_create_measurement(self):
        with open('./helix/helix_upload_sample.csv') as csv:
            data = {'user_key': self.user_key,
                    'user_name': self.user_name,
                    'password': self.password,
                    'dataset': self.record.pk,
                    'cycle': self.cycle.pk,
                    'helix_csv': csv}
            res = self.client.post(reverse('helix:helix_csv_upload'), data)
            self.assertEqual(302, res.status_code)

            self.assertTrue(HelixMeasurement.objects.filter(fuel='NATG', quantity=495, unit='THERM').exists())
            self.assertTrue(HelixMeasurement.objects.filter(fuel='ELEC', quantity=12339, unit='KWH').exists())

    def test_reso_export_with_private(self):
        with open('./helix/helix_upload_sample.csv') as csv:
            data = {'user_key': self.user_key,
                    'user_name': self.user_name,
                    'password': self.password,
                    'dataset': self.record.pk,
                    'cycle': self.cycle.pk,
                    'helix_csv': csv}

            res = self.client.post(reverse('helix:helix_csv_upload'), data)
            self.assertEqual(302, res.status_code)

            view_id = PropertyView.objects.get(state__custom_id_1='1234').pk

            data = {'propertyview_pk': view_id,
                    'start_date': '2016-09-14',
                    'end_date': '2016-09-26',
                    'private_data': 'True'}
            res = self.client.get(reverse('helix:helix_reso_export_xml'), data)
            self.assertEqual(200, res.status_code)
            self.assertTrue('NGBS' in res.content)

    def test_reso_export_no_private(self):
        with open('./helix/helix_upload_sample.csv') as csv:
            data = {'user_key': self.user_key,
                    'user_name': self.user_name,
                    'password': self.password,
                    'dataset': self.record.pk,
                    'cycle': self.cycle.pk,
                    'helix_csv': csv}
            res = self.client.post(reverse('helix:helix_csv_upload'), data)
            self.assertEqual(302, res.status_code)
            view_id = PropertyView.objects.get(state__custom_id_1='1234').pk

            data = {'propertyview_pk': view_id,
                    'start_date': '2016-09-14',
                    'end_date': '2016-09-26',
                    'private_data': 'True'}
            res = self.client.get(reverse('helix:helix_reso_export_xml'), data)
            self.assertEqual(200, res.status_code)
            self.assertTrue('NGBS' in res.content)
