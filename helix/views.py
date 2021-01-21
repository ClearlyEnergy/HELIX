import os
import csv
import re
import datetime
# from urlparse import urlparse
from urllib.parse import urlparse

from seed.data_importer.tasks import save_raw_data, map_data, match_buildings

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound
from django.shortcuts import render

from django.template.loader import render_to_string
from django.db.models import Q
from rest_framework.decorators import api_view

from seed.models import Cycle, PropertyView, PropertyState, Property

from seed.models.certification import GreenAssessmentPropertyAuditLog, GreenAssessmentURL
from helix.models import HELIXGreenAssessment, HELIXGreenAssessmentProperty, HelixMeasurement, HELIXPropertyMeasure
from seed.models.auditlog import (
    AUDIT_USER_EXPORT,
)
from seed.data_importer.models import ImportRecord
from helix.models import HELIXOrganization as Organization
# from seed.lib.superperms.orgs.models import Organization

from seed.utils.api import api_endpoint

import helix.helix_utils as utils

from label import label

# Return the green assessment front end page. This can be accessed through
# the seed side bar or at /app/assessments
# Parameters:
#   orgs: list of parent organizations


@login_required
def assessment_view(request):
    orgs = Organization.objects.all()
    return render(request, 'helix/green_assessments.html', {'org_list': orgs})


# Returns and html interface for editing an existing green assessment which is
# identified by the parameter id.
# Parameters:
#   assessment: certification id
@login_required
def assessment_edit(request):
    assessment = HELIXGreenAssessment.objects.get(pk=request.GET['id'])
    return render(request, 'helix/assessment_edit.html', {'assessment': assessment})

# Export the GreenAssessmentProperty information for the list of property ids provided
# Parameters:
#   ids: comma separated list of views ids to retrieve
#   file_name: optional parameter that can be set to have the web browser open
#              a save dialog with this as the file name. When not set, raw text
#              is displayed
# Example:
#   GET /helix/helix-csv-export/?view_ids=11,12,13,14
@api_endpoint
@api_view(['GET', 'POST'])
def helix_csv_export(request):
    #    property_ids = map(lambda view_id: int(view_id), request.data.get['ids'].split(','))
    property_ids = request.data.get('ids', [])
    view_ids = PropertyView.objects.filter(property_id__in=property_ids)
    state_ids = view_ids.values_list('state_id', flat=True)

    # retrieve green assessment properties that belong to one of these ids
    today = datetime.datetime.today()
    organizations = Organization.objects.filter(users=request.user)
    reso_certifications = HELIXGreenAssessment.objects.filter(organization_id__in=organizations).filter(is_reso_certification=True)
    assessments = HELIXGreenAssessmentProperty.objects.filter(
        view__pk__in=view_ids).filter(Q(_expiration_date__gte=today) | Q(_expiration_date=None)).filter(opt_out=False).filter(assessment_id__in=reso_certifications)
    #    num_certification = assessments.values_list('assessment_id', flat=True)

    # retrieve measures that belogn to one of these ids
    matching_measures = HELIXPropertyMeasure.objects.filter(property_state__in=state_ids)  # only pv can be exported

    file_name = request.data.get('filename')

    # Handle optional parameter
    if (file_name is not None):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="' + file_name + '"'
    else:
        response = HttpResponse()

    # Dump all fields of all retrieved assessments properties into csv
    addressmap = {'custom_id_1': 'UniversalPropertyId', 'city': 'City', 'postal_code': 'PostalCode', 'state': 'State', 'latitude': 'Latitude', 'longitude': 'Longitude'}
    addressmapxd = {'StreetDirPrefix': 'StreetDirPrefix', 'StreetDirSuffix': 'StreetDirSuffix', 'StreetName': 'StreetName', 'StreetNumber': 'StreetNumber', 'StreetSuffix': 'StreetSuffix', 'UnitNumber': 'UnitNumber'}
    fieldnames = ['GreenVerificationBody',  'GreenBuildingVerificationType', 'GreenVerificationRating', 'GreenVerificationMetric', 'GreenVerificationVersion', 'GreenVerificationYear',  'GreenVerificationSource',  'GreenVerificationStatus', 'GreenVerificationURL']
    measurenames = ['PowerProductionSource', 'PowerProductionOwnership', 'Electric', 'PowerProductionAnnualStatus', 'PowerProductionSize', 'PowerProductionType', 'PowerProductionAnnual', 'PowerProductionYearInstall']

    writer = csv.writer(response)
    arr = [value for key, value in addressmap.items()] + [value for key, value in addressmapxd.items()] + ['Unparsed Address'] + [str(f) for f in fieldnames]
    if matching_measures:
        arr += [str(m) for m in measurenames]
    writer.writerow(arr)
    for a in assessments:
        a_dict = a.to_reso_dict()
        unparsedAddress = a.view.state.address_line_1
        if a.view.state.address_line_2:
            unparsedAddress += ' ' + a.view.state.address_line_2
        writer.writerow([str(getattr(a.view.state, key, '')) for key, value in addressmap.items()] +
                        [str(getattr(a.view.state, key, '')) for key, value in addressmapxd.items()] + [unparsedAddress] +
                        [str(a_dict.get(f, '')) for f in fieldnames])
        # log changes
        a.log(
            user=request.user,
            record_type=AUDIT_USER_EXPORT,
            name='Export log',
            description='Exported via csv')

    for measure in matching_measures:
        matching_measurements = HelixMeasurement.objects.filter(
            measure_property__pk=measure.propertymeasure_ptr_id,
            measurement_type__in=['PROD', 'CAP'],
            measurement_subtype__in=['PV', 'WIND']
        )
        measurement_dict = {}
        for match in matching_measurements:
            measurement_dict.update(match.to_reso_dict())
            measurement_dict.update(measure.to_reso_dict())
        unparsedAddress = measure.property_state.address_line_1
        if measure.property_state.address_line_2:
            unparsedAddress += ' ' + measure.property_state.address_line_2

        writer.writerow([str(getattr(measure.property_state, key, '')) for key, value in addressmap.items()] +
                        [str(getattr(measure.property_state, key, '')) for key, value in addressmapxd.items()] + [unparsedAddress] +
                        [str(getattr({}, f, '')) for f in fieldnames] + [measurement_dict.get(m, '') for m in measurenames])

    return response

# Export the property address information for the list of property ids provided, matching up likely duplicates
# Parameters:
#   ids: comma separated list of views ids to retrieve
#   file_name: optional parameter that can be set to have the web browser open
#              a save dialog with this as the file name. When not set, raw text
#              is displayed
# Example:
#   GET /helix/helix-dups-export/?view_ids=11,12,13,14
@api_endpoint
@api_view(['GET', 'POST'])
def helix_dups_export(request):
    property_ids = request.data.get('ids', [])
    view_ids = PropertyView.objects.filter(property_id__in=property_ids)
    state_ids = view_ids.values_list('state_id', flat=True)
    # convert to list to facilitate removal later on
    states = [s for s in PropertyState.objects.filter(id__in=state_ids).only("id", "address_line_1", "normalized_address", "postal_code", "extra_data")]

    file_name = request.data.get('filename')
    # Handle optional parameter
    if (file_name is not None):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="' + file_name + '"'
    else:
        response = HttpResponse()

    writer = csv.writer(response)

    addressmap = ['id', 'address_line_1', 'city', 'postal_code']
    writer.writerow(addressmap)

    remaining_states = states
    skip_states = []
    for state in states:
        if state.id in skip_states:
            continue
        for rem_state in remaining_states:
            # likely matches, same zip code
            if state.extra_data['StreetNumber'] == rem_state.extra_data['StreetNumber'] and state.extra_data['StreetName'] == rem_state.extra_data['StreetName'] and state.extra_data['UnitNumber'] == rem_state.extra_data['UnitNumber'] and state.postal_code == rem_state.postal_code and state.id != rem_state.id:
                writer.writerow(['Similar street address, same postal code'])
                writer.writerow([str(getattr(state, elem, '')) for elem in addressmap])
                writer.writerow([str(getattr(rem_state, elem, '')) for elem in addressmap])
#                remaining_states = list(filter(lambda i: i.id != rem_state.id, remaining_states))
                skip_states.append(rem_state.id)
                continue
            # likely matches, no unit number, same zip code
            if state.extra_data['StreetNumber'] == rem_state.extra_data['StreetNumber'] and state.extra_data['StreetName'] == rem_state.extra_data['StreetName'] and state.postal_code == rem_state.postal_code and state.id != rem_state.id:
                writer.writerow(['Similar address, excludes unit #, same postal code'])
                writer.writerow([str(getattr(state, elem, '')) for elem in addressmap])
                writer.writerow([str(getattr(rem_state, elem, '')) for elem in addressmap])
                skip_states.append(rem_state.id)
                continue
            # likely matches, different zip code
            if state.extra_data['StreetNumber'] == rem_state.extra_data['StreetNumber'] and state.extra_data['StreetDirPrefix'] == rem_state.extra_data['StreetDirPrefix'] and state.extra_data['StreetName'] == rem_state.extra_data['StreetName'] and state.extra_data['UnitNumber'] == rem_state.extra_data['UnitNumber'] and state.postal_code != rem_state.postal_code and state.id != rem_state.id:
                writer.writerow(['Same street address, different postal code'])
                writer.writerow([str(getattr(state, elem, '')) for elem in addressmap])
                writer.writerow([str(getattr(rem_state, elem, '')) for elem in addressmap])
                skip_states.append(rem_state.id)
                continue
# { 'StreetSuffix': 'court', 'StreetDirSuffix': '', 'StreetNamePreDirectional': ''}
    return response

# Export List of updated properties in an xml
# format
# Parameters:
#    start_date: A date in the format yyyy-mm-dd specifying the earliest
#                date to export.
#    end_date: A date in the same format specifying the last date to export.
#    private_data: An optional parameter, not included in the official documentation.
#                   If equal to True, then all matching
#                  records are returned. If absent or equal to anything other
#                  than true, only records with a disclosure are returned.
#                  At the moment, this can be set by any user. It might be
#                  that case that only owners/admins should be able to retrieve
#                  private data.
# Example:
#    http://localhost:8000/helix/helix-reso-export-list-xml/?start_date=2016-09-14&end_date=2017-07-11&private_data=True
@api_endpoint
@api_view(['GET'])
def helix_reso_export_list_xml(request):
    content = []
    ga_pks = GreenAssessmentPropertyAuditLog.objects.none()
    property_pks = Property.objects.none()
    start_date = request.GET.get('start_date', None)
    end_date = request.GET.get('end_date', None)
    organization = request.GET.get('organization', None)
    if organization:
        organizations = Organization.objects.filter(users=request.user, name=organization)
        organizations = organizations | Organization.objects.filter(parent_org_id__in=organizations)  # add sub-organizations with same parent
    else:
        organizations = Organization.objects.filter(users=request.user)
        organizations = organizations | Organization.objects.filter(parent_org_id__in=organizations)  # add sub-organizations with same parent
    
#    if propertyview.state.data_quality == 2:
#        return HttpResponse('<errors><error>Property has errors and cannot be exported</error></errors>', content_type='text/xml')

    try:
        # select green assessment properties that are in the specified create / update date range
        # and associated with the correct property view
        if start_date:
            ga_pks = GreenAssessmentPropertyAuditLog.objects.filter(created__gte=start_date)
            property_pks = Property.objects.filter(organization_id__in=organizations, updated__gte=start_date)
        if end_date:
            ga_pks = ga_pks & GreenAssessmentPropertyAuditLog.objects.filter(created__lte=end_date)
            property_pks = property_pks & Property.objects.filter(organization_id__in=organizations, updated__lte=end_date)

        if property_pks:
            property_views = PropertyView.objects.filter(property__in=property_pks)
            content = list(property_views.values_list('id', flat=True))
        if ga_pks:
            content = list(set(content) | set(list(ga_pks.values_list('property_view_id', flat=True))))

        if content:
            context = {
                'content': content
                }
            rendered_xml = render_to_string('reso_export_list_template.xml', context)
            return HttpResponse(rendered_xml, content_type='text/xml')
        else:
            return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
    except PropertyView.DoesNotExist:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')


# Export GreenAssessmentProperty and Measures information for a property view in an xml
# format using RESO fields
# Parameters:
#    propertyview_pk: primary key into the property view table. Determines
#                     which records are exported. If the key does not exist
#                     in the database, a response code 404 is returned.
# Example:
#    http://localhost:8000/helix/helix-reso-export-xml/?property_id=11
# @login_required
@api_endpoint
@api_view(['GET'])
def helix_reso_export_xml(request):
    propertyview = utils.propertyview_find(request)

    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')

    today = datetime.datetime.today()

    if 'crsdata' in request.GET:
        propertyview.state.jurisdiction_property_id = propertyview.state.custom_id_1

    organizations = Organization.objects.filter(users=request.user)
    property = propertyview.first().state
    match = re.search(r'.*\d{5}',property.normalized_address)
    if match:
        property.normalized_address = property.normalized_address[0:property.normalized_address.rindex(' ')]

    property_info = {
        "property": property,
    }

#    for pv in propertyview:
#        if pv.state.data_quality == 2: #exclude records with data quality errors
#            propertyview.exclude(pv)
#        return HttpResponse('<errors><error>Property has errors and cannot be exported</error></errors>', content_type='text/xml')

    measurement_dict = {}
    # assessments
    matching_assessments = HELIXGreenAssessmentProperty.objects.filter(
        view__in=propertyview).filter(Q(_expiration_date__gte=today) | Q(_expiration_date=None)).filter(opt_out=False).exclude(status__in=['draft','test','preliminary'])
    if matching_assessments:
        reso_certifications = HELIXGreenAssessment.objects.filter(organization_id__in=organizations).filter(is_reso_certification=True)
        property_info["assessments"] = matching_assessments.filter(assessment_id__in=reso_certifications)
        for assessment in matching_assessments.filter(assessment_id__in=reso_certifications):
            matching_measurements = HelixMeasurement.objects.filter(
                assessment_property__pk=assessment.greenassessmentproperty_ptr_id
            )
            for match in matching_measurements:
                measurement_dict.update(match.to_reso_dict())
        property_info["measurements"] = measurement_dict

    # measures
    for pv in propertyview:
        matching_measures = HELIXPropertyMeasure.objects.filter(property_state=pv.state)  # only pv can be exported
        if matching_measures:
            for measure in matching_measures:
                matching_measurements = HelixMeasurement.objects.filter(
                    measure_property__pk=measure.propertymeasure_ptr_id,
                    measurement_type__in=['PROD', 'CAP'],
                    measurement_subtype__in=['PV', 'WIND']
                )

            for match in matching_measurements:
                measurement_dict.update(match.to_reso_dict())
                measurement_dict.update(measure.to_reso_dict())

            property_info["measurements"] = measurement_dict

    context = {
        'content': property_info
        }

    # log changes
    for a in matching_assessments:
        a.log(
            user=request.user,
            record_type=AUDIT_USER_EXPORT,
            name='Export log',
            description='Exported via xml')
    rendered_xml = render_to_string('reso_export_template.xml', context)

    return HttpResponse(rendered_xml, content_type='text/xml')


@api_endpoint
@api_view(['GET'])
def helix_green_addendum(request, pk=None):
    if 'organization_id' in request.GET:
        org_id = request.GET['organization_id']
        org = Organization.objects.get(pk=org_id)
    elif 'organization_name' in request.GET:
        org = Organization.objects.get(name=request.GET['organization_name'])
        org_id = org.id
    else:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No organization found --!>')
        
    user = request.user
#    try:
    assessment = HELIXGreenAssessment.objects.get(name='Green Addendum', organization_id=org_id)
    dataset_name = request.GET.get('dataset_name','Green Addendum')
    
    if pk is not None:
        property_state = PropertyState.objects.get(pk=pk)
        property_view = PropertyView.objects.get(state=property_state)
    else:
        property_view = utils.propertyview_find(request, org)
        if not property_view:
            property_view = _create_propertyview(request, org, user, dataset_name)

    if not property_view:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')
    elif pk is None:
        property_view = property_view[0]
        property_state = property_view.state

    assessment_data = {'assessment': assessment, 'view': property_view, 'date': datetime.date.today()}

    data_dict = {
        'street': property_state.address_line_1,
        'street_2': property_state.address_line_1,
        'street_3': property_state.address_line_1,
        'city': property_state.city,
        'state': property_state.state,
        'zip': property_state.postal_code
    }
    if 'Utility' in property_state.extra_data:
        data_dict['utility_name'] = property_state.extra_data['Utility']

    # retrieve green assessment properties
    assessments = HELIXGreenAssessmentProperty.objects.filter(view=property_view).filter(opt_out=False)
    for assess in assessments:
        data_dict.update(assess.to_label_dict())
        measurements = HelixMeasurement.objects.filter(assessment_property=assess)
        for measurement in measurements:
            if assess.name == 'HERS Index Score':
                data_dict.update(measurement.to_label_dict(0, 'hers'))
            elif assess.name == 'Home Energy Score':
                data_dict.update(measurement.to_label_dict(0, 'hes'))

    # retrieve measures
    measures = HELIXPropertyMeasure.objects.filter(property_state=property_state)
    for index, meas in enumerate(measures):
        #    for meas in measures:
        data_dict.update(meas.to_label_dict(index))
        # add _2 for second solar
        measurements = HelixMeasurement.objects.filter(measure_property=meas)
        for measurement in measurements:
            data_dict.update(measurement.to_label_dict(index))

    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
    if dataset_name == "Green Addendum":
        key = lab.green_addendum(data_dict, settings.AWS_BUCKET_NAME)        
    elif dataset_name == "Project Summary":
        data_dict ={'address_line_1': '34 Somerset Rd', 'address_line_2': None, 'city': 'Montpelier', 'state': 'VT', 'postal_code': '05602', 
        'hes_pre': 5, 'hes_post': 10, 'cost_pre': 3000, 'cost_post': 1000, 
        'coach_name': 'Richard Faesy', 'coach_phone': '444-444-4444', 
        'originator_name': 'Joe Banker', 'originator_phone': '555-555-5555',
        'contractor_name': 'Gabrielle Contractor', 'contractor_company': 'Contractor Co.', 'contractor_phone': '123-456-7890', 
        'customer_name': 'Handy Andy', 'customer_phone': '111-111-1111', 'customer_email': 'handy@andy.com', 
        'measures': {'Solar Photovoltaic': 25000, 'Garage Insulation': 2345}, 'mortgage': 100000} 
        key = lab.energy_first_mortgage(data_dict, settings.AWS_BUCKET_NAME)
        
    url = 'https://s3.amazonaws.com/' + settings.AWS_BUCKET_NAME + '/' + key

    priorAssessments = HELIXGreenAssessmentProperty.objects.filter(
            view=property_view,
            assessment=assessment)

    if(not priorAssessments.exists()):
        # If the property does not have an assessment in the database
        # for the specifed assesment type create a new one.
        green_property = HELIXGreenAssessmentProperty.objects.create(**assessment_data)
        green_property.initialize_audit_logs(user=user)
        green_property.save()
    else:
        # find most recently created property and a corresponding audit log
        green_property = priorAssessments.order_by('date').last()
        old_audit_log = GreenAssessmentPropertyAuditLog.objects.filter(greenassessmentproperty=green_property).exclude(record_type=AUDIT_USER_EXPORT).order_by('created').last()

        # log changes
        green_property.log(
                changed_fields=assessment_data,
                ancestor=old_audit_log.ancestor,
                parent=old_audit_log,
                user=user)

    ga_url, _created = GreenAssessmentURL.objects.get_or_create(property_assessment=green_property)
    ga_url.url = url
    ga_url.description = 'Green Addendum Generated on ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ga_url.save()

    return JsonResponse({'status': 'success', 'url': url})
#    except:
#        return JsonResponse({'status': 'error', 'msg': 'Green Addendum generation failed'})


@api_endpoint
@api_view(['GET'])
def helix_vermont_profile(request):
    org = Organization.objects.get(name=request.GET['organization_name'])
    user = request.user
    propertyview = utils.propertyview_find(request, org)
    dataset_name = request.GET['dataset_name']
    if not propertyview:
        propertyview = _create_propertyview(request, org, user, dataset_name)

    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')

    assessment = HELIXGreenAssessment.objects.get(name=dataset_name, organization=org)

    txtvars = ['street', 'city', 'state', 'zipcode', 'evt', 'leed', 'ngbs', 'heatingfuel', 'author_name', 'author_company', 'auditor', 'rating', 'low_cost_action', 'heater_type', 'water_type', 'solar_ownership', 'weatherization', 'source', 'third_party']
    floatvars = ['cons_mmbtu', 'cons_mmbtu_avg', 'cons_mmbtu_max', 'cons_mmbtu_min', 'cons_mmbtu_avg', 'score', 'elec_score', 'ng_score', 'ho_score', 'propane_score', 'wood_cord_score', 'wood_pellet_score', 'solar_score',
                 'finishedsqft', 'yearbuilt', 'hers_score', 'hes_score', 'capacity',
                 'cons_elec', 'cons_ng', 'cons_ho', 'cons_propane', 'cons_wood_cord', 'cons_wood_pellet', 'cons_solar',
                 'rate_elec', 'rate_ng', 'rate_ho', 'rate_propane', 'rate_wood_cord', 'rate_wood_pellet', 'high_cost_action', 'bill']
    boolvars = ['estar_wh', 'iap', 'zerh', 'phius', 'heater_estar', 'water_estar', 'water_solar', 'ac_estar', 'fridge_estar', 'washer_estar', 'dishwasher_estar', 'lighting_estar', 'has_audit', 'has_solar', 'has_storage', 'evcharger', 'has_cert', 'certified_bill', 'opt_out']
    intvars = []
    data_dict = utils.data_dict_from_vars(request, txtvars, floatvars, intvars, boolvars)

    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
    if request.GET['state'] == 'VT':
        key = lab.vermont_energy_profile(data_dict, settings.AWS_BUCKET_NAME)
    else:
        key = lab.generic_energy_profile(data_dict, settings.AWS_BUCKET_NAME)
    url = 'https://s3.amazonaws.com/' + settings.AWS_BUCKET_NAME + '/' + key
    
    if propertyview is not None:
        utils.add_certification_label_to_property(propertyview, user, assessment, url, data_dict)
        return JsonResponse({'status': 'success', 'url': url})
    else:
        return JsonResponse({'status': 'error', 'message': 'no existing home'})


@api_endpoint
@api_view(['GET'])
def helix_massachusetts_scorecard(request, pk=None):
    org_id = request.GET['organization_id']
    user = request.user
    property_state = PropertyState.objects.get(pk=pk)
    propertyview = PropertyView.objects.filter(state=property_state)

    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')

    assessment = HELIXGreenAssessment.objects.get(name='Massachusetts Scorecard', organization_id=org_id)
    data_dict = {
        'address_line_1': property_state.address_line_1,
        'address_line_2': property_state.address_line_2,
        'city': property_state.city,
        'state': property_state.state,
        'postal_code': property_state.postal_code,
    }

    floatvars = ['Utility Price > Fuel Oil', 'Utility Price > Electricity', 'Utility Price > Natural Gas', 'Utility Price > Wood', 'Utility Price > Pellets', 'Utility Price > Propane',
                 'Utilities > Primary Heating Fuel Type', 'Metrics > Fuel Energy Usage Base (therms/yr)',
                 'Metrics > Total Energy Cost Improved ($/yr)', 'Metrics > Total Energy Cost Base ($/yr)',
                 'Metrics > Total Energy Usage Improved (MMBtu/yr)', 'Metrics > Total Energy Usage Base (MMBtu/yr)',
                 'Metrics > Electric Energy Usage Base (kWh/yr)',
                 'Metrics > CO2 Production Improved (Tons/yr)', 'Metrics > CO2 Production Base (Tons/yr)',
                 'Building > Conditioned Area', 'Building > Year Built', 'Building > Number Of Bedrooms', 'Contractor > Name',
                 'Green Assessment Property Date', 'HES > Final > Base Score', 'HES > Final > Improved Score']

    for var in floatvars:
        if var in property_state.extra_data:
            part1 = var.split('>')[-1].lstrip()
    #        part2 = part1.replace('/yr)','')
    #        part2 = part2.replace('(','')
            part2 = part1.split('(')[0].rstrip()
            part3 = part2.replace(' ', '_').lower()
            data_dict[part3] = property_state.extra_data[var]
    data_dict['assessment_date'] = data_dict['green_assessment_property_date']
    if 'year_built' not in data_dict:
        data_dict['year_built'] = property_state.year_built
    if 'conditioned_area' not in data_dict:
        data_dict['conditioned_area'] = property_state.conditioned_floor_area

    # to_btu = {'electric': 0.003412, 'fuel_oil': 0.1, 'propane': 0.1, 'natural_gas': 0.1, 'wood': 0.1, 'pellets': 0.1}
    to_co2 = {'electric': 0.00061}

    if data_dict['fuel_energy_usage_base'] is not None:
        data_dict['fuel_percentage'] = 100.0 * data_dict['fuel_energy_usage_base']*0.1 / (data_dict['fuel_energy_usage_base']*0.1 + data_dict['electric_energy_usage_base']*0.003412)
        data_dict['fuel_percentage_co2'] = 100.0 * (data_dict['co2_production_base'] - to_co2['electric'] * data_dict['electric_energy_usage_base']) / data_dict['co2_production_base']
    else:
        data_dict['fuel_percentage'] = 0.0
        data_dict['fuel_percentage_co2'] = 0.0

    data_dict['electric_percentage'] = 100.0 - data_dict['fuel_percentage']
    data_dict['electric_percentage_co2'] = 100.0 - data_dict['fuel_percentage_co2']

    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
    key = lab.massachusetts_energy_scorecard(data_dict, settings.AWS_BUCKET_NAME)
    url = 'https://s3.amazonaws.com/' + settings.AWS_BUCKET_NAME + '/' + key

    if propertyview is not None:
        utils.add_certification_label_to_property(propertyview, user, assessment, url, data_dict, request.GET.get('status', None), request.GET.get('reference_id', None))
        return JsonResponse({'status': 'success', 'url': url})
    else:
        return JsonResponse({'status': 'error', 'message': 'no existing home'})
    return None

# Create Massachusetts Scorecard (external service)
# Parameters:
#    property attributes
# Example: http://localhost:8000/helix/massachusetts-scorecard/?address_line_1=298%20Highland%20Ave&city=Cambridge&postal_code=02139&state=MA&propane=2.3&fuel_oil=2.4&natural_gas=0.1&electricity=0.1&wood=200&pellets=0.5&conditioned_area=2000&year_built=1945&number_of_bedrooms=3&primary_heating_fuel_type=propane&name=JoeContractor&assessment_date=2019-06-07&fuel_energy_usage_base=120&total_energy_cost_base=2500&total_energy_cost_improved=1500&total_energy_usage_base=150&total_energy_usage_improved=120&electric_energy_usage_base=12000&co2_production_base=12.1&co2_production_improved=9.9&base_score=7&improved_score=9&incentive_1=5000&status=draft&organization=Snugg%20Pro&reference_id=myref124&url=https://mysnuggurl.com&organization=ClearlyEnergy

# @login_required
@api_endpoint
@api_view(['GET'])
def massachusetts_scorecard(request, pk=None):
    user = request.user
    try:
        org = Organization.objects.get(users=user, name=request.GET['organization'])
    except:
        return JsonResponse({'status': 'error', 'message': 'organization does not exist'})
    
    try:
        assessment = HELIXGreenAssessment.objects.get(name='Massachusetts Scorecard', organization=org)
    except:
        return JsonResponse({'status': 'error', 'message': 'Please create certification with name: Massachusetts Scorecard'})

# test if property exists
    propertyview = utils.propertyview_find(request, org)
    if not propertyview:
        dataset_name = 'MA API'
        propertyview = _create_propertyview(request, org, user, dataset_name)
    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')

    if request.GET.get('url', None):
        url = request.GET['url']
        data_dict = None
    else:
        txtvars = ['address_line_1', 'address_line_2', 'city', 'state', 'postal_code', 'primary_heating_fuel_type', 'name', 'assessment_date']
        floatvars = ['fuel_oil', 'electricity', 'natural_gas', 'wood', 'pellets', 'propane',
                     'conditioned_area', 'year_built', 'number_of_bedrooms',
                     'fuel_energy_usage_base',
                     'total_energy_cost_base', 'total_energy_cost_improved',
                     'total_energy_usage_base', 'total_energy_usage_improved',
                     'electric_energy_usage_base',
                     'co2_production_base', 'co2_production_improved',
                     'base_score', 'improved_score']
        intvars = ['base_score', 'improved_score']
        boolvars = []

        data_dict = utils.data_dict_from_vars(request, txtvars, floatvars, intvars, boolvars)
        # to_btu = {'electric': 0.003412, 'fuel_oil': 0.1, 'propane': 0.1, 'natural_gas': 0.1, 'wood': 0.1, 'pellets': 0.1}
        to_co2 = {'electric': 0.00061}

        if data_dict['fuel_energy_usage_base'] is not None and data_dict['electric_energy_usage_base'] is not None:
            data_dict['fuel_percentage'] = 100.0 * data_dict['fuel_energy_usage_base']*0.1 / (data_dict['fuel_energy_usage_base']*0.1 + data_dict['electric_energy_usage_base']*0.003412)
            data_dict['fuel_percentage_co2'] = 100.0 * (data_dict['co2_production_base'] - to_co2['electric'] * data_dict['electric_energy_usage_base']) / data_dict['co2_production_base']
        else:
            data_dict['fuel_percentage'] = 0.0
            data_dict['fuel_percentage_co2'] = 0.0

        data_dict['electric_percentage'] = 100.0 - data_dict['fuel_percentage']
        data_dict['electric_percentage_co2'] = 100.0 - data_dict['fuel_percentage_co2']


        lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        key = lab.massachusetts_energy_scorecard(data_dict, settings.AWS_BUCKET_NAME)
        url = 'https://s3.amazonaws.com/' + settings.AWS_BUCKET_NAME + '/' + key

    if propertyview is not None:
        # need to save data_dict to extra data
        utils.add_certification_label_to_property(propertyview, user, assessment, url, data_dict, request.GET.get('status', None), request.GET.get('reference_id', None))
        return JsonResponse({'status': 'success', 'url': url, 'property_id': propertyview.first().id})
    else:
        return JsonResponse({'status': 'error', 'message': 'no existing home'})


@api_endpoint
@api_view(['GET'])
def helix_remove_profile(request):
    org = Organization.objects.get(name=request.GET['organization_name'])
    propertyview = utils.propertyview_find(request, org=None)

    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')

    certification_name = request.GET['certification_name']
    assessment = HELIXGreenAssessment.objects.get(name=certification_name, organization=org)
    
    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)

    if propertyview is not None:
        for pv in propertyview:
            # consolidate with green addendum
            priorAssessments = HELIXGreenAssessmentProperty.objects.filter(
                    view=pv,
                    assessment=assessment)

            if priorAssessments:
                # find most recently created property and a corresponding audit log
                green_property = priorAssessments.order_by('date').last()
                ga_urls = GreenAssessmentURL.objects.filter(property_assessment=green_property)
                for ga_url in ga_urls:
                    label_link = ga_url.url
                    o = urlparse(label_link)
                    if o:
                        link_parts = os.path.split(o.path)
                        label_link = link_parts[1]
                        lab.remove_label(label_link, settings.AWS_BUCKET_NAME)
                        ga_url.delete()  # delete URL entry in DB
                    else:
                        JsonResponse({'status': 'success', 'message': 'no existing profile'})
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'no existing home'})


def _create_propertyview(request, org, user, dataset_name):
    cycle = Cycle.objects.filter(organization=org).last()  # might need to hardcode this
    dataset = ImportRecord.objects.get(name=dataset_name, super_organization=org)
    result = [{'City': request.GET['city'],
              'State': request.GET['state']}]
    if 'street' in request.GET:
        result[0]['Address Line 1'] = request.GET['street']
    else:
        result[0]['Address Line 1'] = request.GET['address_line_1']
    if 'zipcode' in request.GET:
        result[0]['Postal Code'] = request.GET['zipcode']
    else:
        result[0]['Postal Code'] = request.GET['postal_code']
    if 'property_uid' in request.GET:
        result[0]['Custom ID 1'] = request.GET['property_uid']
    file_pk = utils.save_and_load(user, dataset, cycle, result, "profile_data.csv")
    # save data
    resp = save_raw_data(file_pk)
    save_prog_key = resp['progress_key']
    utils.wait_for_task(save_prog_key)
    # map data
#        save_column_mappings(file_id, col_mappings) #perform column mapping
    resp = map_data(file_pk)
    map_prog_key = resp['progress_key']
    utils.wait_for_task(map_prog_key)
    resp = match_buildings(file_pk)
#        resp = geocode_buildings_task(file_pk)
    if (resp['status'] == 'error'):
        return resp
    match_prog_key = resp['progress_key']
    utils.wait_for_task(match_prog_key)
    propertyview = utils.propertyview_find(request, org)
    return propertyview
