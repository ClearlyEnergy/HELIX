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
        self.user = User.objects.create_superuser(
            email='test_user@demo.com', **user_details)
        self.org = Organization.objects.create()
        OrganizationUser.objects.create(user=self.user, organization=self.org)
        self.client.login(**user_details)

    def test_helix_home(self):
        res = self.client.get(reverse('helix:helix_home'))
        self.assertEqual(200,res.status_code)

    def test_bad_id_404(self):
        res = self.client.get('/helix/helix-hes/',{'user_key':'ce4cdc28710ff9a12bb4b7a047b6583','building_id':1425434})
        self.assertEqual(404,res.status_code)
