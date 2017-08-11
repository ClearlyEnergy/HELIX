from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.template.loader import render_to_string

from seed.models import Cycle, PropertyView
from seed.models.certification import GreenAssessmentProperty, GreenAssessment
from seed.data_importer.models import ImportRecord
from helix.models import HELIXGreenAssessmentProperty

import helix.utils as utils


# Responds with an extremely basic helix home page. At the moment this exists
# as a place to stage testing of our api calls without worrying about
# integrating them into the structure of the main seed site.
# Example:
#   GET http://localhost:8000/helix/
@login_required
def helix_home(request):
    return render(request, 'helix/index.html')


@login_required
def assessment_view(request):
    return render(request, 'helix/green_assessments.html')


@login_required
def assessment_edit(request):
    assessment = GreenAssessment.objects.get(pk=request.GET['id'])
    context = RequestContext(request, {'assessment': assessment})
    return render(request, 'helix/assessment_edit.html', context)


# Retrieve building data for a single building_id from the HES api.
# responds with status 200 on success, 400 on fail
# Parameters:
#   dataset: id of import record that data will be uploaded to
#   cycle: id of cycle that data will be uploaded to
#   user_key: api key to the hes api
#   building_id: building id for a building in the hes database
# Example:
#   GET /helix/helix-hes/?dataset=1&cycle=1&user_key=ce4cdc28710349a1bbb4b7a047b65837&building_id=142543
@login_required
def helix_hes(request):
    dataset = ImportRecord.objects.get(pk=request.GET['dataset'])
    cycle = Cycle.objects.get(pk=request.GET['cycle'])
    building_info = {'user_key': request.GET['user_key'],
                     'building_id': request.GET['building_id']}
    res = utils.helix_hes(request.user, dataset, cycle, building_info)
    if(res['status'] == 'error'):
        return JsonResponse(res, status=400)
    else:
        return JsonResponse(res, status=200)


# Upload a csv file constructed according to the helix csv file format.
# [see helix_upload_sample.csv]
# This file can contain multiple properties that can each have multiple green
# responds with status 200 on success, 400 on fail
# assessments
# Parameters:
#   dataset: id of import record that data will be uploaded to
#   cycle: id of cycle that data will be uploaded to
#   user_key: api key to the hes api
#   helix_csv: data file
@login_required
def helix_csv_upload(request):
    dataset = ImportRecord.objects.get(pk=request.POST['dataset'])
    cycle = Cycle.objects.get(pk=request.POST['cycle'])
    api_key = request.POST['user_key']
    data = request.FILES['helix_csv'].read()

    res = utils.helix_csv_upload(request.user, dataset, cycle, api_key, data)
    if(res['status'] == 'error'):
        return JsonResponse(res, status=400)
    else:
        return redirect('seed:home')


# http://localhost:8000/helix/helix-reso-export-xml/?propertyview_pk=11&start_date=2016-09-14&end_date=2017-07-11&private_data=True
@login_required
def helix_reso_export_xml(request):
    propertyview = PropertyView.objects.get(pk=request.GET['propertyview_pk'])
    start_date = request.GET['start_date']
    end_date = request.GET['end_date']

    # There should be some sort of check here to see if the user has permisino 
    # to see this private data at all. Not sure what the criteria for this would be.
    get_private = request.GET['private_data'] == 'True'

    # select green assessment properties that are in the specified range
    # and associated with the correct property view
    matching_assessments = HELIXGreenAssessmentProperty.objects.filter(
        view=propertyview,
        date__range=(start_date, end_date))

    # filter out any private data if it has not been requested
    if (not get_private):
        matching_assessments = filter(lambda e: e.disclosure,matching_assessments)

    # use this list as part of the context to render an xml response
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'assessment_list': matching_assessments}
    rendered_xml = render_to_string('reso_export_template.xml', context)

    return HttpResponse(rendered_xml, content_type='text/xml')
