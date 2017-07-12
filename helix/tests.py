from django.test import TestCase
from django.core.urlresolvers import reverse
from seed.landing.models import SEEDUser as User
from seed.lib.superperms.orgs.models import Organization, OrganizationUser


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

    def test_helix_home(self):
        res = self.client.get(reverse('helix:helix_home'))
        self.assertEqual(200,res.status_code)

    def test_helix_hes(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65837','building_id':'142543'})
        self.assertEqual(200,res.status_code)

    def test_helix_hes_bad_id_404(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65837','building_id':1425434})
        self.assertEqual(404,res.status_code)

    def test_helix_hes_bad_hes_key_404(self):
        res = self.client.get(reverse('helix:helix_hes'),{'user_key':'ce4cdc28710349a1bbb4b7a047b65827','building_id':142543})
        self.assertEqual(404,res.status_code)
