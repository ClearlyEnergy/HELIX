from django.test import TestCase
from django.core.urlresolvers import reverse
from django.core import management
from django.utils import timezone
import datetime
import json

from seed.landing.models import SEEDUser as User
#from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.lib.superperms.orgs.models import OrganizationUser
from helix.models import HELIXOrganization as Organization
from seed.models import Cycle, PropertyView

#from seed.models.certification import GreenAssessmentProperty, GreenAssessmentPropertyAuditLog
from seed.models.certification import GreenAssessmentPropertyAuditLog
#from seed.models.certification import GreenAssessment
from seed.data_importer.models import ImportRecord
from seed.test_helpers.fake import (
    FakeGreenAssessmentFactory,
    FakeGreenAssessmentPropertyFactory, FakeGreenAssessmentURLFactory,
)

from helix.models import HELIXGreenAssessment as GreenAssessment
from helix.models import HELIXGreenAssessmentProperty as GreenAssessmentProperty
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

