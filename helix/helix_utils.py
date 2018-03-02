import csv
import StringIO
import re
import datetime
import json

from seed.data_importer.models import (
    ImportFile,
)
from seed.lib.mcm import cleaners
from seed.lib.mcm.utils import batch
from seed.lib.superperms.orgs.models import Organization
from seed.models.certification import GreenAssessment
from seed.models import (
    ASSESSED_RAW,
    ColumnMapping,
    PropertyState,
    DATA_STATE_IMPORT,
    DATA_STATE_UNKNOWN)
from zeep.exceptions import Fault

from helix.models import HelixMeasurement
from helix.utils.address import normalize_address_str

from autoload import autoload
from hes import hes

# Utility to create a dict that will be part of a column mapping list
def mapping_entry(to_field, from_field):
    return {'to_field': to_field,
            'to_table_name': 'PropertyState',
            'from_field': from_field}
    
# Create certifications
def helix_certification_create(user, file_pk):
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    import_file = ImportFile.objects.get(pk=file_pk)

    ### 1. read mappings to find mapped name - largely from seed/data_importer/tasks.py
    org = Organization.objects.get(pk=import_file.import_record.super_organization.pk)
    
    ### 2. read mapped records from file_pk and map
    qs = list(
        PropertyState.objects.filter(import_file=import_file).exclude(
            data_state__in=[DATA_STATE_UNKNOWN, DATA_STATE_IMPORT]).only(
            'id').iterator()
    )

    # to thread it, split into separate method
    id_chunks = [[obj.id for obj in chunk] for chunk in batch(qs, 100)]
    increment = get_cache_increment_value(id_chunks)
#    tasks = [map_row_chunk.s(ids, import_file_id, source_type, prog_key, increment)
#             for ids in id_chunks]
    results = {
            'new_assessments': 0,
            'updated_assessments': 0,
            'new_measurements': 0,
            'updated_measurements': 0,
        }
    for ids in id_chunks:
        data = PropertyState.objects.filter(id__in=ids).only('extra_data').iterator()
    #    data = PropertyState.objects.filter(id__in=id_chunks[0]).only('extra_data').iterator()
        
        for original_row in data:
            extra_data = original_row.extra_data
            normalized_address = original_row.normalized_address
            postal_code = original_row.postal_code;

            # long format
            if 'Green Assessment Name' in extra_data:
                assessment = GreenAssessment.objects.get(name=extra_data['Green Assessment Name'], 
                    organization=org)
                green_assessment_data = {
                    "source": extra_data['Green Assessment Property Source'],
                    "version": extra_data['Green Assessment Property Version'],
                    "date": cleaners.date_cleaner(extra_data['Green Assessment Property Date']),
                    "status": extra_data['Green Assessment Property Status'],
                    "extra_data": extra_data['Green Assessment Property Extra Data'],
                    "urls": [extra_data['Green Assessment Property Url']],
                    "assessment": assessment
                }
            
                if 'Opt Out' in extra_data:
                    green_assessment_data["opt_out"] = cleaners.bool_cleaner(extra_data['Opt Out'])
                 
                score_type = ("Metric" if assessment.is_numeric_score else "Rating") 
                score_value = test_score_value(score_type, extra_data['Green Assessment Property '+score_type])
                if score_value not in ['','FALSE']:
                    green_assessment_data.update({score_type.lower(): score_value}) 
           
                    log, prop_assess = loader.create_green_assessment_property(
                        green_assessment_data, normalized_address, postal_code)
                    results['new_assessments'] += log['created']
                    results['updated_assessments'] += log['updated']

                log = _setup_measurements(extra_data, prop_assess)
                results['new_measurements'] += log['created']
                results['updated_measurements'] += log['updated']
            # short format
            else:
                for assess, value in extra_data.items():
                    try: 
                        assessment = GreenAssessment.objects.get(name=assess, organization=org)
                        print assessment
                        score_type = ("Metric" if assessment.is_numeric_score else "Rating")
                        score_value = test_score_value(score_type, value)
                        if score_value not in ['','FALSE']:
                            green_assessment_data = {
                                "date": cleaners.date_cleaner(extra_data['Date']),
                                "assessment": assessment
                            }
                            green_assessment_data.update({score_type: score_value})                    
                            loader.create_green_assessment_property(
                                green_assessment_data, normalized_address, postal_code)                     
                    except: 
                         print 'assessment not found'   
                     
                     
            
    return {'status': 'success', 'data': results}

# retrieves home energy score records and formats file for rest of upload process
def helix_hes_to_file(user, dataset, cycle, hes_auth, partner, start_date=None):
    # instantiate HES client for external API
    hes_client = hes.HesHelix(hes_auth['client_url'], hes_auth['user_name'], hes_auth['password'], hes_auth['user_key'])
    # find assessment entry for hes by name. Maybe not ideal!
    hes_assessment = GreenAssessment.objects.get(name='Home Energy Score', organization_id=user.default_organization.id)
#    if len(hes_assessment) != 1:
#        return {"status": "error", "message": 'Bad Home Energy Score Assessment match, check spelling or number of entries'}

    hes_ids = hes_client.query_by_partner(partner, start_date=start_date)
    if not hes_ids:
        return {'status': 'error', 'message': 'no data found'}
    print len(hes_ids)
    hes_all = []
    for hes_id in hes_ids:
        print hes_id
        hes_data = hes_client.query_hes(hes_id)
        if hes_data['status'] == 'error':
            continue
            
        #change a few naming conventions
        hes_data['green_assessment_property_metric']= hes_data.pop('base_score')     
        hes_data['green_assessment_name'] = 'Home Energy Score'
        hes_data['green_assessment_property_source'] = 'Department of Energy'
        hes_data['green_assessment_property_status'] = hes_data.pop('assessment_type')
        hes_data['green_assessment_property_version'] = hes_data.pop('hescore_version')
        hes_data['green_assessment_property_url'] = hes_data.pop('pdf')
        hes_data['green_assessment_property_date'] = hes_data.pop('assessment_date')
        hes_data['green_assessment_property_extra_data'] = ''
        
        hes_all.append(hes_data)

        try:
            hes_headers
        except:
            hes_headers = hes_data.keys()
        else:
            hes_headers = list(set(hes_headers + hes_data.keys()))
            
    buf = StringIO.StringIO()
    writer = csv.DictWriter(buf, fieldnames=hes_headers)
    writer.writeheader()
    for dat in hes_all:
        writer.writerow(dat) #merge in with green assessment data

    csv_file = buf.getvalue()
    buf.close()
    
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    # upload and save to Property state table
    file_pk = loader.upload('home_energy_score.csv', csv_file, dataset, cycle)
    # save raw data
    resp = loader.save_raw_data(file_pk)
    if (resp['status'] == 'error'):
        return resp

    # revoke session token created for the hes client
    # if the client was never instantiated, nothing needs to be done
    if(hes_client is not None):
        hes_client.end_session()
        
    return {'status': 'success', 'file': file_pk}

# Test for valid score value
def test_score_value(score_type, value):
    """Uses certification type to normalize score/rating value
    :param score_type metric or other
    :param value    
    """
    if score_type == 'metric': 
        return value
    else:
        if value in [0,1]:
            return str(bool(value)).upper()
        else:
            return value.strip().upper()
                
def _setup_measurements(extra_data, assessment_property):
    data = {
        'created': 0,
        'updated': 0,
    }

    for k, dat in extra_data.items():
        if (k.startswith('CONS') or k.startswith('PROD') or k.startswith('CAP')):
            if not dat:
                continue
                 
            dat = json.loads(dat)
            # find fuel and measurement type
            for fuel in list(HelixMeasurement.HES_FUEL_TYPES.keys()):
                if fuel in k:
                    break
                    
            measurement_data = {
                'measurement_type': k.split(' ')[0],
                'fuel':  HelixMeasurement.HES_FUEL_TYPES[fuel],
                'quantity': dat['quantity'],
                'unit': HelixMeasurement.HES_UNITS[dat['unit']], 
                'status': dat['status']}
            if 'pv' in k:
                measurement_data['measurement_subtype'] = 'PV'
                if k.startswith('CAP'):
                    measurement_data['year'] = dat['year']
                    
            data_log, meas = _create_measurement(assessment_property, **measurement_data)
            data['created'] += data_log['created']
            data['updated'] += data_log['updated']

    return data
        
def _create_measurement(assessment_property, **kwargs):
    data_log = {'created': False, 'updated': False}
    kwargs.update({'assessment_property': assessment_property})
    measurement_record, created = HelixMeasurement.objects.get_or_create(**kwargs)
    if created:
        data_log['created'] = True
    else:
        data_log['updated'] = True
        
    return data_log, measurement_record
    
def get_cache_increment_value(chunk):
    denom = len(chunk) or 1
    return 1.0 / denom * 100

            

