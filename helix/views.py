from django.http import HttpResponse
from django.template.context import RequestContext
from django.shortcuts import render_to_response
from hes import hes
from autoload import autoload


def helix_home(request):
    return render_to_response('helix/index.html',locals(),context_instance=RequestContext(request))

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

    res = HttpResponse(str(hes_res))
    res.status_code = 200
    return res
