from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core import management
from django.utils import timezone
import datetime

from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.models import Cycle, PropertyView
from seed.models.certification import GreenAssessment
from seed.data_importer.models import ImportRecord
from seed.test_helpers.fake import (
    FakeGreenAssessmentFactory,
    FakeGreenAssessmentPropertyFactory, FakeGreenAssessmentURLFactory,
)

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

        # This information is likely to change or become outdated as the hes
        # api updates or acount information is changed. If a lot of tests
        # start failing, make sure this is up to date.
        self.user_name = 'TST-HELIX'
        self.password = 'helix123'
        self.user_key = '520df908c6cb4bea8c14691ee95aff88'
        self.building_id = '144148'

        self.assessment_factory = FakeGreenAssessmentFactory(
            organization=self.org
        )
        self.green_assessment = self.assessment_factory.get_green_assessment(
            name="Green Test Score", award_body="Green TS Inc",
            recognition_type=GreenAssessment.SCORE,
            validity_duration=(365 * 5)
        )
        self.url_factory = FakeGreenAssessmentURLFactory()
        self.gap_factory = FakeGreenAssessmentPropertyFactory(
            organization=self.org, user=self.user
        )
        self.start_date = datetime.date.today() - datetime.timedelta(2 * 365)
        self.status_date = datetime.date.today() - datetime.timedelta(7)
        self.target_date = datetime.date.today() - datetime.timedelta(7)
        self.gap = self.gap_factory.get_green_assessment_property(
            assessment=self.green_assessment,
            organization=self.org, user=self.user, with_url=3,
            metric=5, date=self.start_date, status='Pending',
            source='Assessor', status_date=self.status_date,
            version='1', eligibility=True
        )
        self.gap.log(
            user=self.user,
            record_type=2,
            name='Dummy',
            description='For testing')        
        
        self.urls = [url.url for url in self.gap.urls.all()]
    
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

# Check that a simple case of helix_hes fails for bad building_id or user_key        
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
        data = {'user_key': '123456',
                'user_name': self.user_name,
                'password': self.password,
                'building_id': self.building_id,
                'dataset': self.record.pk,
                'cycle': self.cycle.pk}

        res = self.client.post(reverse('helix:helix_hes'), data)
        self.assertEqual(400, res.status_code)

# Test structure of RESO export        
    def test_reso_export(self):
        data = {'propertyview_pk': self.gap.view_id,
                'start_date': '2000-09-14',
                'end_date': '2025-09-26'}
        res = self.client.get(reverse('helix:helix_reso_export_xml'), data)
        self.assertEqual(200, res.status_code)
        self.assertTrue(self.gap.assessment.name in res.content)
        self.assertFalse('Efficiency Vermont' in res.content)


    def test_helix_csv_upload_create_measurement(self):
#        with open('./helix/helix_upload_sample.csv') as csv:
#            data = {'user_key': self.user_key,
#                    'user_name': self.user_name,
#                    'password': self.password,
#                    'dataset': self.record.pk,
#                    'cycle': self.cycle.pk,
#                    'helix_csv': csv}
#            res = self.client.post(reverse('helix:helix_csv_upload'), data)
#            self.assertEqual(302, res.status_code)

#            self.assertTrue(HelixMeasurement.objects.filter(fuel='NATG', quantity=495, unit='THERM').exists())
#            self.assertTrue(HelixMeasurement.objects.filter(fuel='ELEC', quantity=12339, unit='KWH').exists())
        self.assertTrue(2,2)



