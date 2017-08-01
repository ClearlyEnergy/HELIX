import datetime
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core import management
from django.utils import timezone
from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.models import Cycle
from seed.models.certification import GreenAssessment
from seed.data_importer.models import ImportRecord


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

        self.user_key = 'ce4cdc28710349a1bbb4b7a047b65837'
        self.building_id = '142543'

    def test_helix_home(self):
        res = self.client.get(reverse('helix:helix_home'))
        self.assertEqual(200, res.status_code)

    # Check that a simple case of helix_hes return the correct status code
    # when completed successfully.
    def test_helix_hes(self):
        data = {'user_key': self.user_key,
                'building_id': self.building_id,
                'dataset':self.record.pk,
                'cycle':self.cycle.pk}
        res = self.client.get(reverse('helix:helix_hes'), data)
        self.assertEqual(200, res.status_code)

    def test_helix_hes_bad_id_400(self):
        data = {'user_key': self.user_key,
                'building_id': 1425434,
                'dataset':self.record.pk,
                'cycle':self.cycle.pk}

        res = self.client.get(reverse('helix:helix_hes'), data)
        self.assertEqual(400, res.status_code)

    def test_helix_hes_bad_hes_key_400(self):
        data = {'user_key': 'ce4cdc28710349a1bbb4b7a047b65827',
                'building_id': 142543,
                'dataset':self.record.pk,
                'cycle':self.cycle.pk}

        res = self.client.get(reverse('helix:helix_hes'), data)
        self.assertEqual(400, res.status_code)

    # Check that the most basic upload case returns the expected status
    # Does not verify the end state of the database is correct
    def test_helix_csv_upload(self):
         with open('../helix_upload_sample.csv') as csv:
             data = {'user_key': self.user_key,
                    'building_id': 1425434,
                    'dataset':self.record.pk,
                    'cycle':self.cycle.pk,
                    'helix_csv':csv}
             res = self.client.post(reverse('helix:helix_csv_upload'), data)
             self.assertEqual(302, res.status_code)


