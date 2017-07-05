from django.http import JsonResponse
from django.template.context import RequestContext
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from hes import hes
from autoload import autoload
import csv
import StringIO


@login_required
def helix_home(request):
    return render(request,'helix/index.html')

def helix_hes(request):
    building_info={'user_key':request.GET['user_key'],'building_id':request.GET['building_id']}

    hes_res = hes.hes_helix(building_info)

    col_mappings = [{"from_field":"city","to_field":"city","to_table_name":"PropertyState"},
                    {"from_field":"year_built","to_field":"year_built","to_table_name":"PropertyState"},
                    {"from_field":"conditioned_floor_area","to_field":"conditioned_floor_area","to_table_name":"PropertyState"},
                    {"from_field":"base_score","to_field":"energy_score","to_table_name":"PropertyState"},
                    {"from_field":"state","to_field":"state","to_table_name":"PropertyState"},
                    {"from_field":"address","to_field":"address_line_1","to_table_name":"PropertyState"},
                    {"from_field":"zip_code","to_field":"postal_code","to_table_name":"PropertyState"}]

    #There should be some way to query django to find what port it's
    #running on. Hardcoded port is no good.
    authorization = {'authorization':request.user.get_username()+':'+request.user.api_key}
    loader = autoload.AutoLoad("http://localhost:8000",authorization)

    buf = StringIO.StringIO()

    writer = csv.DictWriter(buf,fieldnames=hes_res.keys())
    writer.writeheader()
    writer.writerow(hes_res)

    csv_file = buf.getvalue()
    buf.close

    buf = StringIO.StringIO(csv_file)

    org_id =  str(request.user.default_organization_id)
    loader.autoload_file(buf,"hes-res","2",org_id,col_mappings)

    #Should respond with usefull information
    return JsonResponse({'status': 'success'})
