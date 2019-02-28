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
    
    def to_label_dict(self):
        ga_dict = {}
        
        ga_dict['green_certification_date_verified'] = self.date.strftime('%m/%d/%y')
        if self.assessment.name == 'NGBS New Construction':
            ga_dict['ngbs_'+self.assesment.rating.lower()] = 'On'
            ga_dict['green_certification_organization_url'] = 'https://www.homeinnovation.com/green'
        elif self.assessment.name == 'LEED for Homes':
            ga_dict['leed_'+self.assesment.rating.lower()] = 'On'
            ga_dict['green_certification_organization_url'] = 'https://new.usgbc.org/cert-guide/homes'
        elif self.assessment.name == 'ENERGY STAR Certified Homes':
            ga_dict['energy_star'] = 'On'
        elif self.assessment.name == 'DOE Zero Energy Ready Home':
            ga_dict['zerh'] = 'On'
        elif self.assessment.name == 'Home Energy Score':
            ga_dict['hes_score'] = str(self.metric)
            ga_dict['hes_official'] = 'On'
            ga_dict['hes_url'] = 'On'
        elif self.assessment.name == 'HERS Index Score':
            ga_dict['hers_rating'] = str(self.metric)
            ga_dict['hers_confirmed_rating'] = 'On'
            ga_dict['resnet_url'] = 'On'
        elif self.assessment.name == 'Efficiency Vermont Residential New Construction Program':
            ga_dict['other_certification'] = self.assessment.name
            ga_dict['gren_certification_organization_url'] = 'https://veic.org'
        if self.version:
            if self.assessment.name in ['NGBS New Construction', 'LEED for Homes']:
                ga_dict['green_certification_version'] = self.version
            if self.assessment.name in ['Home Energy Score', 'HERS Index Score']:
                ga_dict['score_version'] = self.version
                            
        return ga_dict
    
    # verification_reviewed_on_site, verification_attached
    # hers_estimated_savings, hers_rate
    # hes_estimated_savings, hes_rate
    
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
        ("RENEWWIRED", "Pre-Wired for Renewables"),
        ("RENEWREADY", "Ready for Renewables")
    )

    ELECTRIC_CHOICES_REVERSE = {
        "Net Meter":"NETMETER",
        "Energy Storage Device":"STORAGE",
        "Pre-Wired for Renewables":"RENEWWIRED",
        "Ready for Renewables":"RENEWREADY"
    }
    
    OWNERSHIP_CHOICES = (
        ("OWN", "Seller Owned"),
        ("3RD", "Third-Party Owned"),
    )

    OWNERSHIP_CHOICES_REVERSE = {
        "Seller Owned":"OWN",
        "Third-Party Owned":"3RD",
    }
    
    SOURCE_CHOICES = (
        ("ADMIN", "Administrator"),
        ("ASSES", "Assessor"),
        ("BILDR", "Builder"),
        ("CONTR", "Contractor/Installer"),
        ("OTH", "Other"),
        ("OWN", "Owner"),
        ("SPNSR", "Program Sponsor"),
        ("VERIF", "Program Verifier"),
        ("PUBRE", "Public Records")
    )

    SOURCE_CHOICES_REVERSE = {
        "Administrator": "ADMIN",
        "Assessor": "ASSES",
        "Builder": "BILDR",
        "Contractor/Installer": "CONTR",
        "Other": "OTH",
        "Owner": "OWN",
        "Program Sponsor": "SPNSR",
        "Program Verifier": "VERIF",
        "Public Records": "PUBRE"
    }
    
    current_financing = models.CharField(max_length=5, choices=FINANCING_CHOICES, null=True, blank=True)
    ownership = models.CharField(max_length=3, choices=OWNERSHIP_CHOICES,null=True,blank=True)
    electric = models.CharField(max_length=10, choices=ELECTRIC_CHOICES, null=True, blank=True)
    installer = models.CharField(max_length=100, null=True, blank=True)
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    source = models.CharField(max_length=5, choices=SOURCE_CHOICES, null=True, blank=True)
    
    def to_reso_dict(self):
        """
        Return a dict where keys are RESO Power Production Ownership and Electric compatible names.
        """
        reso_dict = {}
        if self.electric:
            reso_dict['Electric'] = dict(self.ELECTRIC_CHOICES)[self.electric]
        if self.ownership:
            reso_dict['PowerProductOwnership'] = dict(self.OWNERSHIP_CHOICES)[self.ownership]
        if self.source:
            reso_dict['PowerProductionSource'] = dict(self.SOURCE_CHOICES)[self.source]
            

        return reso_dict
        
    def to_label_dict(self):
        ga_dict = {}
        if self.measure.name == 'install_photovoltaic_system':
            if self.ownership == 'OWN':
                ga_dict['solar_owned'] = 'On'
            if self.current_financing == 'LEASE':
                ga_dict['solar_lease'] = 'On'
            if self.current_financing == 'PPA':
                ga_dict['solar_ppa'] = 'On'
            if self.application_scale in [7,8,9]:
                ga_dict['solar_location'] = self.get_application_scale_display()
                
        return ga_dict
        

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
        property_measures.PropertyMeasure, on_delete=models.CASCADE, related_name='measurements', blank=True, null=True
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
        
    def to_label_dict(self):
        ga_dict = {}
        if self.measurement_type == 'PROD':
            ga_dict['solar_production'] = str(self.quantity)
            ga_dict['solar_production_type'] = self.status
        if self.measurement_type == 'CAP':
            ga_dict['solar_size'] = str(self.quantity)
            ga_dict['solar_age'] = str(self.year)
        return ga_dict
    
    
    
    
    
    
    
