import json
import logging
import os
import subprocess
import csv
import datetime
import string
import boto3

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


from seed.models import Cycle, PropertyView, PropertyState
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

#from hes import hes
#from leed import leed
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
#    http://localhost:8000/helix/helix-reso-export-list-xml/?11&start_date=2016-09-14&end_date=2017-07-11&private_data=True
@api_endpoint
@api_view(['GET'])
def helix_reso_export_list_xml(request):
    start_date = end_date = None
    ga_pks = GreenAssessmentPropertyAuditLog.objects.none()
    if 'start_date' in request.GET:
        start_date = request.GET['start_date']
    if 'end_date' in request.GET:
        end_date = request.GET['end_date']
    organizations = Organization.objects.filter(users=request.user)
    organizations = organizations | Organization.objects.filter(parent_org_id__in=organizations) #add sub-organizations with same parent
    properties = Property.objects.filter(organization_id__in=organizations)
    try:
# select green assessment properties that are in the specified create / update date range
# and associated with the correct property view

        if start_date:
            ga_pks = GreenAssessmentPropertyAuditLog.objects.filter(created__gte=(request.GET['start_date']))
        if end_date:
            ga_pks = ga_pks & GreenAssessmentPropertyAuditLog.objects.filter(created__lte=(request.GET['end_date'])) 
        
        if ga_pks:
            content = ga_pks.values_list('property_view_id', flat=True)
            content = list(content)
        else:
            return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
    except PropertyView.DoesNotExist:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No properties found --!>')
        
        content.append(property_info) 

    context = {
        'content': content
        }
    rendered_xml = render_to_string('reso_export_list_template.xml', context)
    return HttpResponse(rendered_xml, content_type='text/xml')

# Export GreenAssessmentProperty information for a property view in an xml
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
    else:
        return HttpResponseNotFound('<?xml version="1.0"?>\n<!--No property specified --!>')

    today = datetime.datetime.today()
    content = []
    propertyview = PropertyView.objects.get(pk=propertyview_pk)
    property_info = {
        "property": propertyview.state,
    }
    
    organizations = Organization.objects.filter(users=request.user)
    matching_assessments = HELIXGreenAssessmentProperty.objects.filter(
        view=propertyview).filter(Q(_expiration_date__gte=today)|Q(_expiration_date=None)).filter(opt_out=False)
    matching_measures = HELIXPropertyMeasure.objects.filter(property_state=propertyview.state) #only pv can be exported

    if matching_assessments:        
        reso_certifications = HELIXGreenAssessment.objects.filter(organization_id__in=organizations).filter(is_reso_certification=True)        
        property_info["assessments"] = matching_assessments.filter(assessment_id__in=reso_certifications)
        
    if matching_measures:    
        for measure in matching_measures:
            print measure
            print measure.to_reso_dict()
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
    
    print context

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
    for meas in measures:
        data_dict.update(meas.to_label_dict())
        #add _2 for second solar
        measurements = HelixMeasurement.objects.filter(measure_property=meas)
        for measurement in measurements:
            data_dict.update(measurement.to_label_dict())
        
    lab = label.Label()
    key = lab.green_addendum(data_dict)
#    key = 'labels/28d0d1f7-8009-4a6c-8d57-a0c563074061.pdf'
#        s3 = boto3.client('s3')
#        url = s3.generate_presigned_url(ClientMethod='get_object', Params={'Bucket': settings.AWS_BUCKET_NAME, 'Key': key}, ExpiresIn=3600)
#    https://s3.amazonaws.com/ce-seed/labels/28d0d1f7-8009-4a6c-8d57-a0c563074061.pdf
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
    
    
    
