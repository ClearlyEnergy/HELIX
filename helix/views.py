from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from seed.models import Cycle
from seed.data_importer.models import ImportRecord

import helix.utils as utils


# Responds with an extremely basic helix home page. At the moment this exists
# as a place to stage testing of our api calls without worrying about
# integrating them into the structure of the main seed site.
# Example:
#   GET http://localhost:8000/helix/
@login_required
def helix_home(request):
    return render(request, 'helix/index.html')


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
