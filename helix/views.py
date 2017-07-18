import csv
import StringIO

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from seed.models.certification import GreenAssessment

from zeep.exceptions import Fault

from autoload import autoload
from helix.utils import helix_hes as helix_hes_util
from hes import hes

@login_required
def helix_home(request):
    return render(request,'helix/index.html')

def helix_hes(request):
    building_info={'user_key':request.GET['user_key'],'building_id':request.GET['building_id']}
    res = helix_hes_util(request.user,building_info)
    if(res['status'] == 'error'):
        return JsonResponse(res,status=400)
    else:
        return JsonResponse(res,status=200)
