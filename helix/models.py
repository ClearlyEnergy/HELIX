from django.db import models
from seed.models import certification


class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.TextField(max_length=100)


class HelixMeasurement(models.Model):
    MEASUREMENT_TYPE_CHOICES = (
        ("PROD", "Production"),
        ("CONS", "Consumption"),
        ("COST", "Cost"),
        ("EMIT", "Emissions"))
    FUEL_CHOICES = (
        ("ELEC", "Electric"),
        ("NATG", "Natural Gas"),
        ("HEAT", "Heating Oil"),
        ("PROP", "Propane"))
    UNIT_CHOICES = (
        ("KWH", "Kilowatt Hours"),
        ("KW", "Kilowatt"),
        ("GAL", "Gallon"),
        ("MMBTU", "mmbtu"),
        ("TON", "ton co2 equivalents"),
        ("LB", "pound co2 equivalents"))
    STATUS_CHOICES = (
        ("ACTUAL", "Actual"),
        ("ESTIMATE", "Estimated"),
        ("PART_ESTIMATE", "Partially Estimated"))
    view = models.ForeignKey(certification.GreenAssessmentProperty)
    measurement_type = models.CharField(max_length=4, choices=MEASUREMENT_TYPE_CHOICES)
    measurement_subtype = models.CharField(max_length=100)
    fuel = models.CharField(max_length=4, choices=FUEL_CHOICES)
    quantity = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=4, choices=UNIT_CHOICES)
    status = models.CharField(max_length=4, choices=STATUS_CHOICES)
