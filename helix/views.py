import os
import csv
import re
import datetime
import json
# from urlparse import urlparse
from urllib.parse import urlparse

from seed.data_importer.tasks import save_raw_data, map_data, match_buildings

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
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

from hes import hes

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
    print(start_date)
    print(end_date)
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
            ga_pks = GreenAssessmentPropertyAuditLog.objects.filter(organization_id__in=organizations, created__gte=start_date)
            property_pks = Property.objects.filter(organization_id__in=organizations, updated__gte=start_date)
        if end_date:
            ga_pks = ga_pks & GreenAssessmentPropertyAuditLog.objects.filter(organization_id__in=organizations, created__lte=end_date)
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
    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
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

    data_dict = {
        'street': property_state.address_line_1,
        'street_2': property_state.address_line_1,
        'street_3': property_state.address_line_1,
        'city': property_state.city,
        'state': property_state.state,
        'zip': property_state.postal_code
    }
    assessment_data = {'assessment': assessment, 'view': property_view, 'date': datetime.date.today()}
    if dataset_name == "Green Addendum":
        if 'ga_from_ee' in request.GET and request.GET['ga_from_ee'] is not None: #Green Addendum from external data
            txtvars = ['indoor_air_plus', 'water_sense', 'energy_star', 'zerh', 
                'ngbs_bronze', 'ngbs_silver', 'ngbs_gold', 'ngbs_emerald', 
                'living_building_certified', 'petal_certification', 'phi_low_energy', 'energy_phit', 'passive_house', 'phius_2015'
                'leed_certified', 'leed_silver', 'leed_gold', 'leed_platinum', 'green_certification_date_verified', 
                'verification_reviewed_on_site', 'verification_attached', 'green_certification_version', 'green_certification_organization_url',
                'hers_rating', 'hers_sampling_rating', 'hers_projected_rating', 'hers_confirmed_rating', 'hers_estimated_savings', 'hers_rate',
                'hes_score', 'hes_official', 'hes_unofficial', 'hes_estimated_savings', 'hes_rate', 'score_date_verified', 'score_version']
            floatvars = []
            boolvars = []
            intvars = []
            # energy_improvement_description, cost_of_energy_improvement
            # resnet_url, hes_url, other_score_url_check, other_score_url
            # score_reviewed_on_site, score_attached
            # solar_leased, solar_owned, solar_loan_ucc, solar_ppa
            # solar_size, solar_production, solar_production_type, solar_age
            # solar_fixed_mount, solar_tracking_mount
            # same with _2]
    
            source_data_dict = utils.data_dict_from_vars(request, txtvars, floatvars, intvars, boolvars)
            for key in source_data_dict:
                if source_data_dict[key] is None:
                    source_data_dict[key] = ''
            data_dict.update(source_data_dict)
        else: #Green Addendum from HELIX data
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
        key = lab.green_addendum(data_dict, settings.AWS_BUCKET_NAME)        
    elif dataset_name == "Project Summary":
        txtvars = ['address_line_1', 'city', 'state', 'postal_code', 
            'customer_name', 'customer_phone', 'customer_email', 
            'contractor_name', 'contractor_company', 'contractor_phone', 
            'coach_name', 'coach_phone', 
            'originator_name', 'originator_phone',
            'measure_name_1', 'measure_name_2','measure_name_3', 'measure_name_4', 'measure_name_5', 'measure_name_6','measure_name_7', 'measure_name_8',
            'notes']
        floatvars = ['mortgage', 'measure_cost_1', 'measure_cost_2', 'measure_cost_3', 'measure_cost_4', 
            'measure_cost_5', 'measure_cost_6', 'measure_cost_7', 'measure_cost_8',
            'cost_pre', 'cost_post', 'hes_pre', 'hes_post']
        boolvars = []
        intvars = []
        source_data_dict = utils.data_dict_from_vars(request, txtvars, floatvars, intvars, boolvars)
        
        data_dict.update(source_data_dict)
        
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
# Test with /helix-home-energy-score?organization_name=ClearlyEnergy&hes_id=332297
def helix_home_energy_score(request):
    user = request.user
    org = Organization.objects.get(name=request.GET['organization_name'])
    hes_id = request.GET['hes_id']
    # instantiate HES client for external API
    hes_auth = {'user_key': settings.HES_USER_KEY,
                'user_name': org.hes_partner_name,
                'password': org.hes_partner_password,
                'client_url': settings.HES_CLIENT_URL}
    hes_client = hes.HesHelix(hes_auth['client_url'], hes_auth['user_name'], hes_auth['password'], hes_auth['user_key'])
    hes_data = hes_client.query_hes(hes_id)
    if hes_data['status'] == 'error':
        return JsonResponse({'status': 'error', 'message': 'no existing home'})
    else:
        del hes_data['status']
            
    if(hes_client is not None):
        hes_client.end_session()
        
    return JsonResponse({'status': 'success', 'data': hes_data})

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

    txtvars = ['street', 'city', 'state', 'zipcode', 'evt', 'leed', 'ngbs', 'heatingfuel', 'author_name', 'author_company', 'auditor', 'rating', 'low_cost_action', 'heater_type', 'water_type', 'solar_ownership', 'weatherization', 'source', 'third_party', 'bill', 'comments']
    floatvars = ['cons_mmbtu', 'cons_mmbtu_avg', 'cons_mmbtu_max', 'cons_mmbtu_min', 'cons_mmbtu_avg', 'score', 'elec_score', 'ng_score', 'ho_score', 'propane_score', 'wood_cord_score', 'wood_pellet_score', 'solar_score',
                 'finishedsqft', 'yearbuilt', 'hers_score', 'hes_score', 'capacity',
                 'cons_elec', 'cons_ng', 'cons_ho', 'cons_propane', 'cons_wood_cord', 'cons_wood_pellet', 'cons_solar',
                 'rate_elec', 'rate_ng', 'rate_ho', 'rate_propane', 'rate_wood_cord', 'rate_wood_pellet', 'high_cost_action']
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

    data_dict = None 

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

    if request.GET.get('url', None):
        url = request.GET['url']
    else:
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
        utils.add_certification_label_to_property(propertyview, user, assessment, url, data_dict, request.GET.get('status', None), request.GET.get('reference_id', None), org)
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

@csrf_exempt
@api_endpoint
@api_view(['POST'])
def remotely_label(request):
    """
    Generates PDF Label for the Remotely IPC programs.

    Expected JSON request body:
    
    ```json
    {
        "program_display_name": "IPC SMARTE",
        "ce_api_id": "0123456789",
        "street": "77 MASSACHUSETTS AVE",
        "city": "CAMBRIDGE",
        "state": "MA",
        "zipcode": "02139",
        "year_built": 1895,
        "program_name": "SMARTEPV",
        "question_answers": [...]
    }
    ```
    
    The question_answers objects should be like the following.
    (See label.remotely_ipc_pdf for more examples)
    
    ```json
    {
        "question_group": "Installations",
        "question": "Select all systems which have been installed for this home.",
        "options": ["Air Sealing", "Air source heat pump", "Central air conditioning", ...],
        "answer": ["Other hot water heaters", "Window retrofits"]
    }
    ```

    Returns:
    ```json
    {'status': 'success', 'url': <pdf_label_url>}
    ```
    """

    try:
        data = json.loads(request.data.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON body'}, status=400)

    required_keys =  [
        "program_display_name",
        "ce_api_id",
        "street",
        "city",
        "state",
        "zipcode",
        "year_built",
        "program_name",
        "question_answers"
    ]
    missing_keys = set(required_keys) - set(data.keys())
    if missing_keys:
        response = {'status': 'error', 'message': f'Missing keys: {", ".join(missing_keys)}'}
        return JsonResponse(response, status=400)

    lab = label.Label(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
    try:
        file_url = lab.remotely_ipc_pdf(data, settings.AWS_BUCKET_NAME)
        return JsonResponse({'status': 'success', 'url': file_url})
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except KeyError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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
