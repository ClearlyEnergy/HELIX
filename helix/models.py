from django.db import models
from seed.models import certification
from seed.models.properties import PropertyView

class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.TextField(max_length=100)


# A table to keep track of energy production and consumption
# for a property. Schema based on the draft measurement
# excell sheet.
class HelixEnergyMeasurement(models.Model):
    MEASUREMENT_TYPE_CHOICES = (
        ("PROD", "Production"),
        ("CONS", "Consumption"),
        ("COST", "Cost"),
        ("EMIT", "Emissions")
    )
    # Associating this model with a PropertyView to be consistant with
    # GreenAssessmentProperty. Maybe should be PropertyState or
    # Property?
    view = models.ForeignKey(PropertyView)
    measurement_type = models.CharField(max_length=4, choices=MEASUREMENT_TYPE_CHOICES)
    # Source of energy/emissions
    # If there's a finite list of possible sources this could make use
    # of an enumeration like measurement type
    source = models.CharField(max_length=100)
    annual_quantity = models.FloatField(null=True, blank=True)
    # This could also be taken from an enumeration
    unit = models.CharField(max_length=100)
