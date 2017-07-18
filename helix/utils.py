import csv
import StringIO

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from seed.models.certification import GreenAssessment

from zeep.exceptions import Fault

from autoload import autoload
from hes import hes

def helix_hes(user,building_info):
    try:
        hes_res = hes.hes_helix(building_info)
    except Fault as f:
       return {"status":"error","message":f.message}


    col_mappings = [{"from_field":"city","to_field":"city","to_table_name":"PropertyState"},
                    {"from_field":"year_built","to_field":"year_built","to_table_name":"PropertyState"},
                    {"from_field":"conditioned_floor_area","to_field":"conditioned_floor_area","to_table_name":"PropertyState"},
                    {"from_field":"state","to_field":"state","to_table_name":"PropertyState"},
                    {"from_field":"address","to_field":"address_line_1","to_table_name":"PropertyState"},
                    {"from_field":"zip_code","to_field":"postal_code","to_table_name":"PropertyState"}]

    HES_ASSESSMENT_ID = 1 #this values was inserted into the database ahead of time
    green_assessment_mapping = {
        "source": hes_res["qualified_assessor_id"],
        "status": hes_res["assessment_type"],
        # "satus_date": ?
        "metric": hes_res["base_score"],
        "version": hes_res["hescore_version"],
        "date": hes_res["assessment_date"],
        "assessment": GreenAssessment.objects.get(pk=HES_ASSESSMENT_ID)
    }

    loader = autoload.AutoLoad(user,user.default_organization)

    buf = StringIO.StringIO()

    writer = csv.DictWriter(buf,fieldnames=hes_res.keys())
    writer.writeheader()
    writer.writerow(hes_res)

    csv_file = buf.getvalue()
    buf.close()

    buf = StringIO.StringIO(csv_file)

    org_id = str(user.default_organization_id)
    response = loader.autoload_file(buf,"hes-res","2",col_mappings)

    if(response['status'] == 'error'):
        return response

    response = loader.create_green_assessment_property(response['import_file_id'],green_assessment_mapping,'2',hes_res['address'])

    return response
