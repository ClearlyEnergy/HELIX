import csv
import StringIO

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from seed.models.certification import GreenAssessment

from zeep.exceptions import Fault

from autoload import autoload
import helix.utils
from hes import hes

@login_required
def helix_home(request):
    return render(request,'helix/index.html')

@login_required
def helix_hes(request):
    building_info={'user_key':request.GET['user_key'],'building_id':request.GET['building_id']}
    res = helix.utils.helix_hes(request.user,building_info)
    if(res['status'] == 'error'):
        return JsonResponse(res,status=400)
    else:
        return JsonResponse(res,status=200)

@login_required
def helix_csv_upload(request):
    api_key = request.POST['user_key']
    data = request.FILES['helix_csv'].read()

    res = helix.utils.helix_csv_upload(request.user,api_key,data)
    if(res['status'] == 'error'):
        return JsonResponse(res,status=400)
    else:
        return JsonResponse(res,status=200)
