import datetime
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils import timezone
from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.models import Cycle
from seed.models.certification import GreenAssessment


class TestHelixView(TestCase):

    def setUp(self):
        user_details = {
            'username': 'test_user@demo.com',
            'password': 'test_pass',
        }
        self.user = User.objects.create(username='test_user@demo.com')
        self.user.set_password('test_pass')
        self.user.email = 'test_user@demo.com'
        self.user.save()

        self.org = Organization.objects.create()
        OrganizationUser.objects.create(user=self.user, organization=self.org)

        self.user.default_organization_id = self.org.id
        self.user.save()

        self.client.login(username='test_user@demo.com',password='test_pass')

        self.cycle = Cycle.objects.create(organization=self.org,user=self.user,name="test",start=timezone.now(),end=timezone.now())
        self.cycle.save()

        GreenAssessment.objects.create(
            name='Home Energy Score',
            award_body='Department of Energy',
            recognition_type='SCR',
            description='Developed by DOE...',
            is_numeric_score=True,
            is_integer_score=True,
            validity_duration=datetime.timedelta(days=365),
            organization=self.org)



    def test_helix_home(self):
        res = self.client.get(reverse('helix:helix_home'))
        self.assertEqual(200,res.status_code)

    def test_helix_hes(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65837','building_id':'142543'})
        self.assertEqual(200,res.status_code)

    def test_helix_hes_bad_id_404(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65837','building_id':1425434})
        self.assertEqual(400,res.status_code)

    def test_helix_hes_bad_hes_key_404(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65827','building_id':142543})
        self.assertEqual(400,res.status_code)
