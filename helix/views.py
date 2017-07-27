from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from seed.models import Cycle
from seed.data_importer.models import ImportRecord

import helix.utils as utils


@login_required
def helix_home(request):
    return render(request, 'helix/index.html')


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
