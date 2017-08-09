from django.db import models
from seed.models import certification

class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.CharField(max_length=100) # null=true, blank=true might need to be set
