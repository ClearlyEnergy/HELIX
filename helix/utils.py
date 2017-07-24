import csv
import StringIO

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from seed.models.certification import GreenAssessment

from zeep.exceptions import Fault

from autoload import autoload
from hes import hes

def helix_csv_upload(user, hes_api_key, csv_file):
    # load some of the data dirrectly from csv
    loader = autoload.AutoLoad(user,user.default_organization)

    # Hardcoding these because they are known ahead of time but,
    # there's no reason matching can't be automatic
    col_mappings = [{'to_field': 'address_line_1', 'to_table_name': 'PropertyState', 'from_field': 'address_line_1'},
                    {'to_field': 'address_line_2', 'to_table_name': 'PropertyState', 'from_field': 'address_line_2'},
                    {'to_field': 'city', 'to_table_name': 'PropertyState', 'from_field': 'city'},
                    {'to_field': 'state', 'to_table_name': 'PropertyState', 'from_field': 'state'},
                    {'to_field': 'postal_code', 'to_table_name': 'PropertyState', 'from_field': 'postal_code'},
                    {'to_field': 'year_built', 'to_table_name': 'PropertyState', 'from_field': 'year_built'},
                    {'to_field': 'conditioned_floor_area', 'to_table_name': 'PropertyState', 'from_field': 'conditioned_floor_area'},
                    {'to_field': 'custom_id_1', 'to_table_name': 'PropertyState', 'from_field': 'Internal ID'}]

    response = loader.autoload_file(csv_file,"helix_csv_import","2",col_mappings)

    if(response['status'] == 'error'):
        return response

    # if a hes building id is provided for a property,
    # get the hes data
    dict_data = csv.DictReader(csv_file.split('\n'))
    for row in dict_data:
        if (row['green_assessment_reference_id'] != '' and row['green_assessment_name']=='Home Energy Score'):
            building_info = {'user_key':hes_api_key,'building_id':row['green_assessment_reference_id']}
            response = helix_hes(user,building_info)
            if(response['status'] == 'error'):
                return response

    return {'status':'success'}

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

    org_id = str(user.default_organization_id)
    response = loader.autoload_file(csv_file,"hes-res","2",col_mappings)

    if(response['status'] == 'error'):
        return response

    response = loader.create_green_assessment_property(response['import_file_id'],green_assessment_mapping,'2',hes_res['address'])

    return response
