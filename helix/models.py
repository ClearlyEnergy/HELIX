from django.db import models
from seed.models import certification


class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    disclosure = models.TextField(max_length=100, null=True, blank=True)

class HELIXGreenAssessment(certification.GreenAssessment):
<<<<<<< HEAD
    disclosure_default = models.TextField(max_length=100)
=======
    disclosure = models.TextField(max_length=100, null=True, blank=True)
>>>>>>> 6921507a0847cad246da9457c3761b0d5ddc6b68

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
        'kw': "KW",
        'therms': "THERM",
        'gallons': "GAL",
        'cords': "CORD",
        'pounds': "LB",
        'mmbtu': "MMBTU",
        'dollars': "",
        'greenhouse_gas': "GHG",
        'carbon_dioxide': "CO2",
        'carbon_dioxide_equivalent': "CO2e"}

    MEASUREMENT_TYPE_CHOICES = (
        ("PROD", "Production"),
        ("CONS", "Consumption"),
        ("COST", "Cost"),
        ("EMIT", "Emissions"))

    MEASUREMENT_SUBTYPE_CHOICES = (
        ("PV", "Solar Photovoltaic"),
        ("WIND", "Wind"))

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
        ("THERM", "therm"),
        ("DOLLAR","dollar"),
        ("GHG","Greenhouse Gas"),
        ("CO2","Carbon Dioxide"),
        ("CO2e","Carbon Dioxide Equivalent"))
    STATUS_CHOICES = (
        ("ACTUAL", "Actual"),
        ("ESTIMATE", "Estimated"),
        ("PART_ESTIMATE", "Partially Estimated"))
    assessment_property = models.ForeignKey(
        certification.GreenAssessmentProperty, on_delete=models.CASCADE, related_name='measurements'
        )
    measurement_type = models.CharField(max_length=4, choices=MEASUREMENT_TYPE_CHOICES)
    measurement_subtype = models.CharField(max_length=15, choices=MEASUREMENT_SUBTYPE_CHOICES, null=True, blank=True)
    fuel = models.CharField(max_length=5, choices=FUEL_CHOICES)
    quantity = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES)
    status = models.CharField(max_length=13, choices=STATUS_CHOICES)
