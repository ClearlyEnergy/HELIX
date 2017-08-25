from django.db import models
from seed.models import certification


class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.TextField(max_length=100)

class HELIXGreenAssessment(certification.GreenAssessment):
    disclosure = models.TextField(max_length=100)

class HelixMeasurement(models.Model):
    HES_FUEL_TYPES = {
        "electric": "ELEC",
        "natural_gas": "NATG",
        "fuel_oil": "FUEL",
        "lpg": "PROP",
        "cord_wood": "CWOOD",
        "pellet_wood": "PWOOD"}
    HES_UNITS = {
        'kwh': "KWH",
        'therms': "THERM",
        'gallons': "GAL",
        'cords': "CORD",
        'pounds': "LB",
        'mmbtu': "MMBTU"}

    MEASUREMENT_TYPE_CHOICES = (
        ("PROD", "Production"),
        ("CONS", "Consumption"),
        ("COST", "Cost"),
        ("EMIT", "Emissions"))
    FUEL_CHOICES = (
        ("ELEC", "Electric"),
        ("NATG", "Natural Gas"),
        ("HEAT", "Heating Oil"),
        ("PROP", "Propane"),
        ("CWOOD", "Cord Wood"),
        ("PWOOD", "Pellet Wood"))
    UNIT_CHOICES = (
        ("KWH", "Kilowatt Hours"),
        ("KW", "Kilowatt"),
        ("GAL", "Gallon"),
        ("MMBTU", "mmbtu"),
        ("TON", "ton"),
        ("LB", "pound"),
        ("CORD", "cord"),
        ("THERM", "therm"))
    STATUS_CHOICES = (
        ("ACTUAL", "Actual"),
        ("ESTIMATE", "Estimated"),
        ("PART_ESTIMATE", "Partially Estimated"))
    assessment_property = models.ForeignKey(certification.GreenAssessmentProperty)
    measurement_type = models.CharField(max_length=4, choices=MEASUREMENT_TYPE_CHOICES)
    measurement_subtype = models.CharField(max_length=100)
    fuel = models.CharField(max_length=5, choices=FUEL_CHOICES)
    quantity = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES)
    status = models.CharField(max_length=13, choices=STATUS_CHOICES)
