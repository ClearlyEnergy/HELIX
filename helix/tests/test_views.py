from django.test import TestCase
from django.core import management
from django.utils import timezone

from seed.landing.models import SEEDUser as User
# from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.lib.superperms.orgs.models import OrganizationUser
from helix.models import HELIXOrganization as Organization
from seed.models import Cycle

# from seed.models.certification import GreenAssessmentProperty, GreenAssessmentPropertyAuditLog
# from seed.models.certification import GreenAssessment
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
