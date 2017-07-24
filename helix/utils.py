import csv
import StringIO

from seed.models.certification import GreenAssessment

from zeep.exceptions import Fault

from autoload import autoload
from hes import hes


def mapping_entry(to_field, from_field):
    return {'to_field': to_field,
            'to_table_name': 'PropertyState',
            'from_field': from_field}


def helix_csv_upload(user, hes_api_key, csv_file):
    # load some of the data dirrectly from csv
    loader = autoload.AutoLoad(user, user.default_organization)

    # Hardcoding these because they are known ahead of time but,
    # there's no reason matching can't be automatic
    mappings = [mapping_entry('address_line_1', 'address_line_1'),
                mapping_entry('address_line_2', 'address_line_2'),
                mapping_entry('city', 'city'),
                mapping_entry('state', 'state'),
                mapping_entry('postal_code', 'postal_code'),
                mapping_entry('year_built', 'year_built'),
                mapping_entry('conditioned_floor_area', 'conditioned_floor_area'),
                mapping_entry('custom_id_1', 'Internal ID')]

    response = loader.autoload_file(csv_file, "helix_import", "2", mappings)
    file_id = response['import_file_id']

    if(response['status'] == 'error'):
        return response

    # if a hes building id is provided for a property,
    # get the hes data
    dict_data = csv.DictReader(csv_file.split('\n'))
    for row in dict_data:
        isHES = row['green_assessment_name'] == 'Home Energy Score'
        hesID = row['green_assessment_reference_id']
        if (hesID != '' and isHES):
            building_info = {'user_key': hes_api_key,
                             'building_id': hesID}
            response = helix_hes(user, building_info)
            if(response['status'] == 'error'):
                return response
        elif (hesID == '' and isHES):
            # Hardcoded assessment id. Should be abstracted at least a little
            HES_ASSESSMENT_ID = 1
            HES_ASSESSMENT = GreenAssessment.objects.get(pk=HES_ASSESSMENT_ID)
            green_assessment_data = {
                "source": row["green_assessment_property_source"],
                "status": row["green_assessment_property_status"],
                "metric": row["green_assessment_property_metric"],
                "version": row["green_assessment_property_version"],
                "date": row["green_assessment_property_date"],
                "assessment": HES_ASSESSMENT
            }
            response = loader.create_green_assessment_property(
                file_id,
                green_assessment_data,
                HES_ASSESSMENT.organization.pk,
                row['address_line_1'])
            if(response['status'] == 'error'):
                return response

    return {'status': 'success'}


def helix_hes(user, building_info):
    try:
        hes_res = hes.hes_helix(building_info)
    except Fault as f:
        return {"status": "error", "message": f.message}

    mappings = [mapping_entry('address_line_1', 'address'),
                mapping_entry('city', 'city'),
                mapping_entry('state', 'state'),
                mapping_entry('postal_code', 'zip_code'),
                mapping_entry('year_built', 'year_built'),
                mapping_entry('conditioned_floor_area', 'conditioned_floor_area')]

    # Hardcoded assessment id. Should be abstracted at least a little
    HES_ASSESSMENT_ID = 1
    HES_ASSESSMENT = GreenAssessment.objects.get(pk=HES_ASSESSMENT_ID)
    green_assessment_data = {
        "source": hes_res["qualified_assessor_id"],
        "status": hes_res["assessment_type"],
        "metric": hes_res["base_score"],
        "version": hes_res["hescore_version"],
        "date": hes_res["assessment_date"],
        "assessment": HES_ASSESSMENT
    }

    loader = autoload.AutoLoad(user, user.default_organization)

    buf = StringIO.StringIO()

    writer = csv.DictWriter(buf, fieldnames=hes_res.keys())
    writer.writeheader()
    writer.writerow(hes_res)

    csv_file = buf.getvalue()
    buf.close()

    org_id = str(user.default_organization_id)
    response = loader.autoload_file(csv_file, "hes-res", org_id, mappings)

    if(response['status'] == 'error'):
        return response

    response = loader.create_green_assessment_property(
            response['import_file_id'],  # id of initial import file
            green_assessment_data,  # data retreived from HES API
            HES_ASSESSMENT.organization.pk,
            hes_res['address'])

    return response
