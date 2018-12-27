from django.db import models
from seed.models import certification
from seed.models import property_measures
from seed.lib.superperms.orgs.models import Organization
from django.contrib.auth.models import Group
from tos.models import TermsOfService, UserAgreement, NoActiveTermsOfService
            
class HELIXTermsOfServiceManager(models.Manager):
    def get_current_group_tos(self, group_pk):
        try:
            return self.get(active=True, group_id=group_pk)
        except self.model.DoesNotExist:
            raise NoActiveTermsOfService(
                u'Please create an active Terms-of-Service'
            )

class HELIXTermsOfService(TermsOfService):
    """
    Additional field for Terms of Service
    group Attach to authentication group
    """    
    group = models.ForeignKey(Group, related_name='group') 
    objects = HELIXTermsOfServiceManager()
    
def has_user_agreed_latest_group_tos(user):
    group_id = user.get_group_id()
    return UserAgreement.objects.filter(
        terms_of_service=HELIXTermsOfService.objects.get_current_group_tos(group_id),
        user=user,
    ).exists()
       

class HELIXGreenAssessment(certification.GreenAssessment):
    """
    Additional fields for Green Assessment
    is_reso_certification   True/False, defines what is exported to RESO dictionary
    """
    is_reso_certification = models.BooleanField(default=True)

class HELIXGreenAssessmentProperty(certification.GreenAssessmentProperty):
    """
    Additional fields for Green Assessment Property
    opt_out         True/False
    reference_id    Source Reference ID
    """
    opt_out = models.BooleanField(default=False)
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    
class HELIXOrganization(Organization):
    """
    Additional fields for Organization
    hes             Home Energy Score identifier
    hes_start_date  Start date for home energy score retrieval
    hes_end_date    End date for home energy score retrieval
    hes_partner_name    Home Energy Score Partner User Name
    hes_partner_password    Home Energy Score Partner Password
    """
    hes = models.CharField(max_length=100, null=True, blank=True)
    hes_start_date = models.DateField(null=True, blank=True)
    hes_end_date = models.DateField(null=True, blank=True)
    hes_partner_name = models.CharField(max_length=100, null=True, blank=True)
    hes_partner_password = models.CharField(max_length=100, null=True, blank=True)
    leed_start_date = models.DateField(null=True, blank=True)
    leed_end_date = models.DateField(null=True, blank=True)
    leed_geo_id = models.CharField(max_length=100, null=True, blank=True)
    
    def add_hes(self, hes):
        """Add Home Energy Score ID to organization"""
        for key, value in hes.items():
            setattr(self, key, value)
        return self.save()

    def add_leed(self, leed):
        """Add LEED info to organization"""
        for key, value in leed.items():
            setattr(self, key, value)
        return self.save()

class HELIXPropertyMeasure(property_measures.PropertyMeasure):
    """
    Additional fields for Property Measure
    electric                RESO    Utilities Group -> Electric Field
    current_financing       RESO    Listing Group -> Contract Group -> CurrentFinancing Field
    installer               Name/company of installer of measures
    """

    FINANCING_CHOICES = (
        ("LEASE", "Leased Renewables"),
        ("PPA", "Power Purchase Agreement"),
        ("PACE", "Property-Assessed Clean Energy")
        )

    FINANCING_CHOICES_REVERSE = {
        "Leased Renewables":"LEASE",
        "Power Purchase Agreement":"PPA",
        "Property-Assessed Clean Energy":"PACE"
        }
        
    ELECTRIC_CHOICES = (
        ("NETMETER", "Net Meter"),
        ("STORAGE", "Energy Storage Device"),
        ("PVOWN", "Photovoltaics Seller Owned"),
        ("PV3RD", "Photovoltaics Third-Party Owned"),
        ("WINDOWN", "Wind Turbine Seller Owned"),
        ("WIND3RD", "Wind Turbine Third-Party Owned"),
        ("RENEWWIRED", "Pre-Wired for Renewables"),
        ("RENEWREADY", "Ready for Renewables")
    )

    ELECTRIC_CHOICES_REVERSE = {
        "Net Meter":"NETMETER",
        "Energy Storage Device":"STORAGE",
        "Photovoltaics Seller Owned":"PVOWN",
        "Photovoltaics Third-Party Owned":"PV3RD",
        "Wind Turbine Seller Owned":"WINDOWN",
        "Wind Turbine Third-Party Owned":"WIND3RD",
        "Pre-Wired for Renewables":"RENEWWIRED",
        "Ready for Renewables":"RENEWREADY"
    }
    
    current_financing = models.CharField(max_length=5, choices=FINANCING_CHOICES, null=True, blank=True)
    electric = models.CharField(max_length=10, choices=ELECTRIC_CHOICES, null=True, blank=True)
    installer = models.CharField(max_length=100, null=True, blank=True)

class HelixMeasurement(models.Model):
    """
    Measurementsattached to a certification.
    Compatible with RESO v1.5/BEDES
    Max lengths for Charfields set to 2 x RESO recommendation.
    Model       RESO                            
    quantity    PowerProduction[Type]Annual, PowerProduction[Type]Size   
    status      PowerProduction[Type]Status   
    ??          PowerProduction[Type]YearInstall
    measurement_type & measurement_subtype  PowerProduction Type
    """
    # pylint:disable=no-member
    
    PV_PROD_MAPPING = {
        # attribute: RESO field
        'measurement_subtype': 'PowerProductionType',
        'quantity': 'PowerProductionAnnual',
        'status': 'PowerProductionAnnualStatus',
    }
    
    PV_CAP_MAPPING = {
        # attribute: RESO field, need to add YearInstall
        'quantity': 'PowerProductionSize',
        'year': 'YearInstall'
    }

    HES_FUEL_TYPES = {
        "Electric": "ELEC",
        "Natural Gas": "NATG",
        "Fuel Oil": "FUEL",
        "Lpg": "PROP",
        "Cord Wood": "CWOOD",
        "Pellet Wood": "PWOOD",
        "Total": "TOTAL"}
        
    HES_TYPES = {
        "Production": "PROD",
        "Consumption": "CONS",
        "Cost": "COST",
        "Emissions": "EMIT",
        "Capacity": "CAP"}
        
    HES_UNITS = {
        'kwh': "KWH",
        'kw': "KW",
        'therms': "THERM",
        'therm': "THERM",
        'gallons': "GAL",
        'cords': "CORD",
        'pounds': "LB",
        'mmbtu': "MMBTU",
        'dollars': "$",
        'dollar': "$",
        'tons_ghg': "TGHG",
        'tons_CO2': "TCO2",
        'tons_CO2e': "TCO2E"}

    MEASUREMENT_TYPE_CHOICES = (
        ("PROD", "Production"),
        ("CONS", "Consumption"),
        ("COST", "Cost"),
        ("EMIT", "Emissions"),
        ("CAP", "Capacity"))

    MEASUREMENT_SUBTYPE_CHOICES = (
        ("PV", "Photovoltaics"),
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
        
    def __unicode__(self):
        return u"{}, {}, {}: {} {}, {}".format(
            self.measurement_type, self.measurement_subtype, self.fuel, self.quantity, self.unit, self.status 
        )
        
    assessment_property = models.ForeignKey(
        certification.GreenAssessmentProperty, on_delete=models.CASCADE, related_name='measurements', blank=True, null=True
        )
    measure_property = models.ForeignKey(
        HELIXPropertyMeasure, on_delete=models.CASCADE, related_name='measurements', blank=True, null=True
        )
    measurement_type = models.CharField(max_length=4, choices=MEASUREMENT_TYPE_CHOICES)
    measurement_subtype = models.CharField(max_length=15, choices=MEASUREMENT_SUBTYPE_CHOICES, null=True, blank=True)
    fuel = models.CharField(max_length=5, choices=FUEL_CHOICES)
    quantity = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=5, choices=UNIT_CHOICES)
    status = models.CharField(max_length=13, choices=STATUS_CHOICES)
    year = models.IntegerField(null=True, blank=True)
    
    def to_reso_dict(self):
        """
        Return a dict where keys are RESO Power Production compatible names.
        RESO Power Production field names may optionally contain the type
        (i.e. name). e.g. Powerproduction[Type]Annual
        """
        reso_dict = {}
        if self.measurement_type == 'PROD':
            for key, val in self.PV_PROD_MAPPING.iteritems():
                attr = getattr(self, key)
                if attr in dict(self.STATUS_CHOICES).keys():
                    attr = dict(self.STATUS_CHOICES)[attr]
                if attr in dict(self.MEASUREMENT_SUBTYPE_CHOICES).keys():
                    attr = dict(self.MEASUREMENT_SUBTYPE_CHOICES)[attr]
                reso_dict[val] = attr

        if self.measurement_type == 'CAP':
            for key, val in self.PV_CAP_MAPPING.iteritems():
                reso_dict[val] = getattr(self, key)

        return reso_dict
        
    
    
    
    
    
    
    
