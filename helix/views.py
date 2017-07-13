from django.http import JsonResponse
from django.template.context import RequestContext
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from hes import hes
from autoload import autoload
import csv
import StringIO
from zeep.exceptions import Fault


@login_required
def helix_home(request):
    return render(request,'helix/index.html')

def helix_hes(request):
    building_info={'user_key':request.GET['user_key'],'building_id':request.GET['building_id']}


    hes_res = {}
    try:
        hes_res = hes.hes_helix(building_info)
    except Fault as f:
        print f
        return JsonResponse({"status":"error","message":f.message},status=404)

    col_mappings = [{"from_field":"city","to_field":"city","to_table_name":"PropertyState"},
                    {"from_field":"year_built","to_field":"year_built","to_table_name":"PropertyState"},
                    {"from_field":"conditioned_floor_area","to_field":"conditioned_floor_area","to_table_name":"PropertyState"},
                    {"from_field":"state","to_field":"state","to_table_name":"PropertyState"},
                    {"from_field":"address","to_field":"address_line_1","to_table_name":"PropertyState"},
                    {"from_field":"zip_code","to_field":"postal_code","to_table_name":"PropertyState"}]

    HES_ASSESSMENT_ID = 1 #this values was inserted manulay into the database
    green_assessment_mapping = {
        "source": hes_res["qualified_assessor_id"],
        "status": hes_res["assessment_type"],
        # "satus_date": ?
        "metric": hes_res["base_score"],
        "version": hes_res["hescore_version"],
        "date": hes_res["assessment_date"],
        "assessment": HES_ASSESSMENT_ID
    }

    url_base = "http://localhost:"+request.META["SERVER_PORT"]
    loader = autoload.AutoLoad(url_base,request.user.get_username(),request.user.api_key)

    buf = StringIO.StringIO()

    writer = csv.DictWriter(buf,fieldnames=hes_res.keys())
    writer.writeheader()
    writer.writerow(hes_res)

    csv_file = buf.getvalue()
    buf.close

    buf = StringIO.StringIO(csv_file)

    org_id =  str(request.user.default_organization_id)
    response = loader.autoload_file(buf,"hes-res","2",org_id,col_mappings)

    if(response['status'] == 'error'):
        return JsonResponse(response)

    response = loader.create_green_assessment_property(response['import_file_id'],green_assessment_mapping,'2')

    return JsonResponse(response)
