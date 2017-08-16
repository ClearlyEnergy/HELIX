from django.db import models
from seed.models import certification

class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.TextField(max_length=100)
