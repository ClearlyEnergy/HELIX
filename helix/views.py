import json
import logging
import os
import subprocess
import csv
import datetime
import string

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse, HttpResponse, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from seed.decorators import (
    ajax_request, get_prog_key
)
from django.template import RequestContext
from django.template.loader import render_to_string
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view

from seed.models import Cycle, PropertyView, Property

from seed.models.certification import GreenAssessmentProperty, GreenAssessmentPropertyAuditLog
from helix.models import HELIXGreenAssessment, HELIXGreenAssessmentProperty, HelixMeasurement
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
from seed.utils.api import api_endpoint

import helix.helix_utils as utils
from zeep.exceptions import Fault

from hes import hes


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
        hes_client = hes.HesHelix(hes.CLIENT_URL, request.POST['user_name'], request.POST['password'], request.POST['user_key'])
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
        
# Retrieve HES records and generate file to use in rest of upload process
# responds with file content and status 200 on success, 400 on fail
# Parameters:
#   dataset: id of import record that data will be uploaded to
#   cycle: id of cycle that data will be uploaded to
@login_required
def hes_upload(request):
    dataset = ImportRecord.objects.get(pk=request.POST.get('dataset', request.GET.get('dataset')))
    cycle = Cycle.objects.get(pk=request.POST.get('cycle', request.GET.get('cycle')))
    org = Organization.objects.get(pk=request.POST.get('organization_id', request.GET.get('organization_id')))
                
    hes_auth = {'user_key': settings.HES_USER_KEY, 
                'user_name': settings.HES_USER_NAME,
                'password': settings.HES_PASSWORD,
                'client_url': settings.HES_CLIENT_URL}

    partner = org.hes
    if org.hes_start_date is None:
        start_date = datetime.date.today() - datetime.timedelta(7)
    else:
        start_date = org.hes_start_date
                
    response = utils.helix_hes_to_file(request.user, dataset, cycle, hes_auth, partner, start_date)
    
    if(response['status'] == 'error'):
        return JsonResponse(response, status=400)
    else:
        org.hes_start_date = datetime.date.today()
        org.save() 
        return JsonResponse(response, status=200)    

# Add certifications to already imported file
# Parameters:
#   import_file_id: id of import file
# Returns:
#   status: 
#   json structure with number of new and updated certifications and measurements
# Example:
#   Get /helix/add_certifications/?import_file_id=1
@login_required
def add_certifications(request, import_file_id):
    response = utils.helix_certification_create(request.user,import_file_id)
    
    if(response['status'] == 'error'):
        return JsonResponse(response, status=400)
    else:
        return JsonResponse(response, status=200)    

# Export the GreenAssessmentProperty information for the list of property view
# ids provided
# Parameters:
#   view_ids: comma separated list of views ids to retrieve
#   file_name: optional parameter that can be set to have the web browser open
#              a save dialog with this as the file name. When not set, raw text
#              is displayed
# Example:
#   GET /helix/helix-csv-export/?view_ids=11,12,13,14
@login_required
def helix_csv_export(request):
    # splitting view_ids parameter string into list of integer view_ids
    property_ids = map(lambda view_id: int(view_id), request.GET['view_ids'].split(','))
    view_ids = PropertyView.objects.filter(property_id__in=property_ids)

    # retrieve green assessment properties that belong to one of these ids
    assessments = HELIXGreenAssessmentProperty.objects.filter(view__pk__in=view_ids).filter(opt_out=False)
    

    file_name = request.GET.get('file_name')

    # Handle optional parameter
    if (file_name is not None):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="' + file_name + '"'
    else:
        response = HttpResponse()

    # Dump all fields of all retrieved assessments properties into csv
    fieldnames = [f.name for f in HELIXGreenAssessmentProperty._meta.get_fields()]
    for l in ['id', 'view', 'assessment', 'urls','measurements','gapauditlog_assessment','greenassessmentproperty_ptr']:
        fieldnames.remove(l) 
    writer = csv.writer(response)

    writer.writerow(['Address1', 'Address1', 'City','State', 'Postal Code', 'Certification'] + [string.capwords(str(f).replace('_',' ')) for f in fieldnames])
    for a in assessments:
        writer.writerow([a.assessment.name] + [str(getattr(a, f)) for f in fieldnames])
        # log changes
        a.log(
            user=request.user,
            record_type=AUDIT_USER_EXPORT,
            name='Export log',
            description='Exported via csv')
    return response


# Export GreenAssessmentProperty information for a property view in an xml
# format using RESO fields
# Parameters:
#    propertyview_pk: primary key into the property view table. Determines
#                     which records are exported. If the key does not exist
#                     in the database, a response code 404 is returned.
#    start_date: A date in the format yyyy-mm-dd specifying the earliest
#                date to export.
#    end_date: A date in the same format specifying the last date to export.
#    private_data: An optional parameter. If equal to True, then all matching
#                  records are returned. If absent or equal to anything other
#                  than true, only records with a disclosure are returned.
#                  At the moment, this can be set by any user. It might be
#                  that case that only owners/admins should be able to retrieve
#                  private data.
# Example:
#    http://localhost:8000/helix/helix-reso-export-xml/?propertyview_pk=11&start_date=2016-09-14&end_date=2017-07-11&private_data=True

#@login_required
@api_endpoint
@api_view(['GET'])
def helix_reso_export_xml(request):
    # Get the relevant property view form its table. If it can't be found,
    # a 404 error is returned.
    # Get properties updated within dates
    # Green Assessment Property Audit Log
    # Property Audit Log
    today = datetime.datetime.today()
    start_date = end_date = None
    ga_pks = GreenAssessmentPropertyAuditLog.objects.none()
    if 'start_date' in request.GET:
        start_date = request.GET['start_date']
    if 'end_date' in request.GET:
        end_date = request.GET['end_date']

    organizations = Organization.objects.filter(users=request.user)
    properties = Property.objects.filter(organization_id__in=organizations)
    reso_certifications = HELIXGreenAssessment.objects.filter(organization_id__in=organizations).filter(is_reso_certification=True)
        
    try:
# select green assessment properties that are in the specified create / update date range
# and associated with the correct property view
        if start_date:
            ga_pks = GreenAssessmentPropertyAuditLog.objects.filter(created__gte=(request.GET['start_date']))
        if end_date:
            ga_pks = ga_pks & GreenAssessmentPropertyAuditLog.objects.filter(created__lte=(request.GET['end_date'])) 
            
        if ga_pks:
            ga_pks = ga_pks.values_list('property_view_id', flat=True)
            if 'propertyview_pk' in request.GET:
                propertyviews = PropertyView.objects.filter(pk=request.GET['propertyview_pk'], property_id__in=properties, pk__in=ga_pks)
            else:
                propertyviews = PropertyView.objects.filter(pk=request.GET['propertyview_pk'], pk__in=ga_pks)
        else:
            if start_date or end_date:
                return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
            else:
                if 'propertyview_pk' in request.GET:
                    propertyviews = PropertyView.objects.filter(pk=request.GET['propertyview_pk'], property_id__in=properties)
                else:
                    return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
    except PropertyView.DoesNotExist:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
    
    if not propertyviews:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')

    content = []
    for propertyview in propertyviews:  
        matching_assessments = HELIXGreenAssessmentProperty.objects.filter(
            view=propertyview).filter(Q(_expiration_date__gte=today)|Q(_expiration_date=None)).filter(opt_out=False)
        
        gis = {}
        if 'Latitude' in propertyview.state.extra_data:
            gis = {
                'Latitude': propertyview.state.extra_data["Latitude"],
                'Longitude': propertyview.state.extra_data["Longitude"]
            }
            
        if matching_assessments:        
            matching_measurements = HelixMeasurement.objects.filter(
                assessment_property__pk__in=matching_assessments.values_list('pk',flat=True),
                measurement_type__in=['PROD','CAP'],
                measurement_subtype__in=['PV','WIND']
            )
    
            measurement_dict = {}
            for measure in matching_measurements:
                measurement_dict.update(measure.to_reso_dict())
            
            property_info = {
                "property": propertyview.state,
                "assessments": matching_assessments.filter(assessment_id__in=reso_certifications),
                "measurements": measurement_dict,
                "gis": gis
            }
            
            content.append(property_info) 

        context = {
            'start_date': start_date,
            'end_date': end_date,
            'content': content
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
