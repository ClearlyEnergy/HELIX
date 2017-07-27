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


def helix_csv_upload(user, dataset, cycle, hes_api_key, csv_file):
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

    response = loader.autoload_file(csv_file, dataset, cycle, mappings)

    if(response['status'] == 'error'):
        return response

    file_id = response['import_file_id']

    # If a green property assessment is provided for the propery
    # parse the data and create the green assessment entry
    dict_data = csv.DictReader(csv_file.split('\n'))
    for row in dict_data:
        isHES = row['green_assessment_name'] == 'Home Energy Score'
        hesID = row['green_assessment_reference_id']
        # HES data is handled seperatly because it is the only
        # assessment for wich an external api is required
        if (hesID != '' and isHES):
            building_info = {'user_key': hes_api_key,
                             'building_id': hesID}
            response = helix_hes(user, dataset, cycle, building_info)
            if(response['status'] == 'error'):
                return response
        elif (hesID == ''):
            # do data base lookup by name for the assessment
            # all assessments must exists in the database before upload
            assessment = GreenAssessment.objects.get(name=row['green_assessment_name'])
            green_assessment_data = {
                "source": row["green_assessment_property_source"],
                "version": row["green_assessment_property_version"],
                "date": row["green_assessment_property_date"],
                "extra_data": row["green_assessment_property_extra_data"],
                "urls": [row["green_assessment_property_url"]],
                "assessment": assessment
            }

            # seed requires exactly one of metric or rating
            isMetric = row["green_assessment_property_metric"] != ''
            isRating = row["green_assessment_property_rating"] != ''
            if (isMetric and not isRating):
                green_assessment_data.update({"metric": row["green_assessment_property_metric"]})
            elif (isRating and not isMetric):
                green_assessment_data.update({"rating": row["green_assessment_property_rating"]})
            elif (isRating and isMetric):
                return {'status': 'error', 'message': 'assessment should only have one of metric and rating'}

            response = loader.create_green_assessment_property(
                file_id,
                green_assessment_data,
                assessment.organization.pk,
                row['address_line_1'])

            if(response['status'] == 'error'):
                return response

    return {'status': 'success'}


def helix_hes(user, dataset, cycle, building_info):
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

    # find assessment entry for hes by name maybe not the ideal way of getting
    # it but, better than hardcoding the pk
    hes_assessment = GreenAssessment.objects.get(name='Home Energy Score')
    green_assessment_data = {
        "source": hes_res["qualified_assessor_id"],
        "status": hes_res["assessment_type"],
        "metric": hes_res["base_score"],
        "version": hes_res["hescore_version"],
        "date": hes_res["assessment_date"],
        "assessment": hes_assessment
    }

    loader = autoload.AutoLoad(user, user.default_organization)

    # construct a csv string out of the dictionaty retrieved by hes
    buf = StringIO.StringIO()

    writer = csv.DictWriter(buf, fieldnames=hes_res.keys())
    writer.writeheader()
    writer.writerow(hes_res)

    csv_file = buf.getvalue()
    buf.close()

    response = loader.autoload_file(csv_file, dataset, cycle, mappings)

    if(response['status'] == 'error'):
        return response

    response = loader.create_green_assessment_property(
            response['import_file_id'],  # id of initial import file
            green_assessment_data,  # data retreived from HES API
            hes_assessment.organization.pk,
            hes_res['address'])

    return response
