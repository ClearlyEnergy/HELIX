import json
import logging
import os
import subprocess
import csv
import datetime
import string

from seed.data_importer.tasks import helix_hes_to_file, helix_leed_to_file, helix_certification_create

from django.conf import settings
from django.core import serializers
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound, HttpResponseRedirect, FileResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from seed.decorators import ajax_request, ajax_request_class
from seed.decorators import get_prog_key

from django.template import RequestContext
from django.template.loader import render_to_string
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, detail_route, list_route, parser_classes, \
    permission_classes

from seed.models import Cycle, PropertyView, PropertyState, Property
from seed.models.data_quality import DataQualityCheck

from seed.models.certification import GreenAssessmentProperty, GreenAssessmentPropertyAuditLog, GreenAssessmentURL
from seed.lib.superperms.orgs.decorators import has_perm_class
from seed.lib.progress_data.progress_data import ProgressData
from seed.lib.mcm.utils import batch
from helix.models import HELIXGreenAssessment, HELIXGreenAssessmentProperty, HelixMeasurement, HELIXPropertyMeasure
from seed.models.auditlog import (
    AUDIT_USER_EDIT,
    AUDIT_USER_CREATE,
    AUDIT_USER_EXPORT,
    DATA_UPDATE_TYPE
)
from seed.data_importer.models import ImportRecord
from helix.models import HELIXOrganization as Organization
#from seed.lib.superperms.orgs.models import Organization

from seed.lib.mcm import cleaners, mapper, reader
from seed.utils.api import api_endpoint, api_endpoint_class

import helix.helix_utils as utils
from zeep.exceptions import Fault

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


# Tests HES connectivity. 
# Retrieve building data for a single building_id from the HES api.
# responds with status 200 on success, 400 on fail
# Parameters:
#   dataset: id of import record that data will be uploaded to
#   cycle: id of cycle that data will be uploaded to
#   building_id: building id for a building in the hes database
#   user_key: hes api key
#   user_name: hes username
#   password: hes password
#@login_required
def helix_hes(request):
    dataset = ImportRecord.objects.get(pk=request.POST['dataset'])
    cycle = Cycle.objects.get(pk=request.POST['cycle'])

    try: 
        hes_client = hes.HesHelix(request.POST['client_url'], request.POST['user_name'], request.POST['password'], request.POST['user_key'])
        try:
            res = hes_client.query_hes(request.POST['building_id'])
            res["status"] = "success"
        except Fault as f:
            res = {"status": "error", "message": f.message}
    except Fault as f: 
        res = {"status": "error", "message": f.message}
    
    if(res['status'] == 'error'):
        return JsonResponse(res, status=400)
    else:
        return JsonResponse(res, status=200)
 

# Export the GreenAssessmentProperty information for the list of property ids provided
# Parameters:
#   ids: comma separated list of views ids to retrieve
#   file_name: optional parameter that can be set to have the web browser open
#              a save dialog with this as the file name. When not set, raw text
#              is displayed
# Example:
#   GET /helix/helix-csv-export/?view_ids=11,12,13,14
@api_endpoint
@api_view(['GET','POST'])
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
        view__pk__in=view_ids).filter(Q(_expiration_date__gte=today)|Q(_expiration_date=None)).filter(opt_out=False).filter(assessment_id__in=reso_certifications)
    
    #retrieve measures that belogn to one of these ids
    matching_measures = HELIXPropertyMeasure.objects.filter(property_state__in=state_ids) #only pv can be exported

    file_name = request.data.get('filename')

    # Handle optional parameter
    if (file_name is not None):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="' + file_name + '"'
    else:
        response = HttpResponse()
        
    # Dump all fields of all retrieved assessments properties into csv
    addressmap = {'custom_id_1': 'UniversalPropertyId', 'city': 'City', 'postal_code': 'PostalCode', 'state': 'State', 'latitude': 'Latitude', 'longitude': 'Longitude'}
    addressmapxd = {'StreetDirPrefix': 'StreetDirPrefix', 'StreetDirSuffix': 'StreetDirSuffix', 'StreetName': 'StreetName', 'StreetNumber': 'StreetNumber', 'StreetSuffix':'StreetSuffix', 'UnitNumber': 'UnitNumber'}
    fieldnames = ['GreenVerificationRating', 'GreenVerificationVersion', 'GreenVerificationYear', 'GreenVerificationBody',  'GreenBuildingVerificationType', 'GreenVerificationSource', 'GreenVerificationMetric', 'GreenVerificationStatus', 'GreenVerificationURL']
    measurenames = ['PowerProductionSource', 'PowerProductionOwnership', 'Electric', 'PowerProductionAnnualStatus', 'PowerProductionSize', 'PowerProductionType', 'PowerProductionAnnual', 'YearInstall']

    writer = csv.writer(response)
    writer.writerow([value for key, value in addressmap.iteritems()] + 
        [value for key, value in addressmapxd.iteritems()] + ['Unparsed Address'] + 
        [str(f) for f in fieldnames] + [str(m) for m in measurenames])
    for a in assessments:
        a_dict = a.to_reso_dict()
        unparsedAddress = a.view.state.address_line_1
        if a.view.state.address_line_2:
            unparsedAddress += ' ' + a.view.state.address_line_2
        writer.writerow([str(getattr(a.view.state, key, '')) for key, value in addressmap.iteritems()] + 
            [str(getattr(a.view.state, key, '')) for key, value in addressmapxd.iteritems()] + [unparsedAddress] +
            [str(a_dict.get(f,'')) for f in fieldnames])
        # log changes
        a.log(
            user=request.user,
            record_type=AUDIT_USER_EXPORT,
            name='Export log',
            description='Exported via csv')

    for measure in matching_measures:
        matching_measurements = HelixMeasurement.objects.filter(
            measure_property__pk=measure.propertymeasure_ptr_id,
            measurement_type__in=['PROD','CAP'],
            measurement_subtype__in=['PV','WIND']
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
            [str(getattr({}, f, '')) for f in fieldnames ] + [measurement_dict.get( m, '') for m in measurenames])
    
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
    start_date = end_date = None
    content = []
    ga_pks = GreenAssessmentPropertyAuditLog.objects.none()
    property_pks = Property.objects.none()
    if 'start_date' in request.GET:
        start_date = request.GET['start_date']
    if 'end_date' in request.GET:
        end_date = request.GET['end_date']
    organizations = Organization.objects.filter(users=request.user)
    organizations = organizations | Organization.objects.filter(parent_org_id__in=organizations) #add sub-organizations with same parent
    
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
#@login_required
@api_endpoint
@api_view(['GET'])
def helix_reso_export_xml(request):
    if 'property_id' in request.GET:
        propertyview_pk = request.GET['property_id']
        propertyview = PropertyView.objects.get(pk=propertyview_pk)
    elif 'property_uid' in request.GET:
        property_uid = request.GET['property_uid']        
        state_ids = PropertyState.objects.filter(ubid=property_uid)
        propertyview = PropertyView.objects.filter(state_id__in=state_ids).first()
    else:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property specified --!>')
        
    if not propertyview:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property found --!>')        

    today = datetime.datetime.today()
    content = []
    
    if 'crsdata' in request.GET:
        propertyview.state.jurisdiction_property_id = propertyview.state.custom_id_1
        
    property_info = {
        "property": propertyview.state,
    }
    
    organizations = Organization.objects.filter(users=request.user)
    if propertyview.state.data_quality == 2:
        return HttpResponse('<errors><error>Property has errors and cannot be exported</error></errors>', content_type='text/xml')
    
    matching_assessments = HELIXGreenAssessmentProperty.objects.filter(
        view=propertyview).filter(Q(_expiration_date__gte=today)|Q(_expiration_date=None)).filter(opt_out=False)
    matching_measures = HELIXPropertyMeasure.objects.filter(property_state=propertyview.state) #only pv can be exported

    if matching_assessments:        
        reso_certifications = HELIXGreenAssessment.objects.filter(organization_id__in=organizations).filter(is_reso_certification=True)        
        property_info["assessments"] = matching_assessments.filter(assessment_id__in=reso_certifications)
        measurement_dict = {}
        for assessment in matching_assessments.filter(assessment_id__in=reso_certifications):
            matching_measurements = HelixMeasurement.objects.filter(
                assessment_property__pk=assessment.greenassessmentproperty_ptr_id
            )
            for match in matching_measurements:
                measurement_dict.update(match.to_reso_dict())
        property_info["measurements"] = measurement_dict
        print(property_info)
        
        
    if matching_measures:    
        for measure in matching_measures:
            matching_measurements = HelixMeasurement.objects.filter(
                measure_property__pk=measure.propertymeasure_ptr_id,
                measurement_type__in=['PROD','CAP'],
                measurement_subtype__in=['PV','WIND']
            )

        measurement_dict = {}
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
    org_id = request.GET['organization_id']
    user = request.user
#    try:
    assessment = HELIXGreenAssessment.objects.get(name='Green Addendum', organization_id=org_id)
    property_state = PropertyState.objects.get(pk=pk)
    property_view = PropertyView.objects.get(state=property_state) 
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

    #retrieve measures
    measures = HELIXPropertyMeasure.objects.filter(property_state=property_state)
    for index, meas in enumerate(measures):
        print(index)
#    for meas in measures:
        data_dict.update(meas.to_label_dict(index))
        #add _2 for second solar
        measurements = HelixMeasurement.objects.filter(measure_property=meas)
        for measurement in measurements:
            data_dict.update(measurement.to_label_dict(index))
        
    lab = label.Label()
    key = lab.green_addendum(data_dict)
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
def helix_vermont_profile(request, pk=None):
    print(request.GET)
    org_id = request.GET['organization_id']
    if 'property_uid' in request.GET:
        property_uid = request.GET['property_uid']        
    
    user = request.user
    
    assessment_name = 'Vermont Profile'
    assessment = HELIXGreenAssessment.objects.get(name=assessment_name, organization_id=org_id)
    
    data_dict = {}
    txtvars = ['street', 'city', 'state', 'zipcode','evt','heatingfuel','estar_wh','owner_name']
    floatvars = ['cons_mmbtu', 'cons_mmbtu_max', 'cons_mmbtu_min', 'score', 'elec_score', 'ng_score', 'ho_score', 'propane_score', 'wood_cord_score', 'wood_pellet_score', 'solar_score',
        'finishedsqft','yearbuilt','hers_score',
        'cons_elec', 'cons_ng', 'cons_ho', 'cons_propane', 'cons_wood_cord', 'cons_wood_pellet', 'cons_solar',
        'rate_elec', 'rate_ng', 'rate_ho', 'rate_propane', 'rate_wood_cord', 'rate_wood_pellet']
    for var in txtvars:
        data_dict[var] = request.GET[var]
    for var in floatvars:
        if request.GET[var]:
            data_dict[var] = float(request.GET[var])
        else:
            data_dict[var] = request.GET[var]
        
    lab = label.Label()
    key = lab.vermont_energy_profile(data_dict)
    url = 'https://s3.amazonaws.com/' + settings.AWS_BUCKET_NAME + '/' + key
    print(url)

    try:
        if property_uid:
            property_state = PropertyState.objects.get(custom_id_1=property_uid)
        else:
            property_state = PropertyState.objects.get(pk=pk)
        property_view = PropertyView.objects.get(state=property_state) 
        assessment_data = {'assessment': assessment, 'view': property_view, 'date': datetime.date.today()}
        #consolidate with green addendum
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
        ga_url.description =  assessment_name + 'Generated on ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ga_url.save()
    except:
        print('no existing home')

    return JsonResponse({'status': 'success', 'url': url})       
    
