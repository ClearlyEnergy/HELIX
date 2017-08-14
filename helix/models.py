from django.db import models
from seed.models import certification

class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    # setting default disclosure to true. Worth considering weather this is
    # should be the case.
    disclosure = models.BooleanField(default=True) # null=true, blank=true might need to be set
