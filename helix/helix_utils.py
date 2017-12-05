import csv
import StringIO
import re
import datetime

from seed.data_importer.models import (
    ImportFile,
    ImportRecord,
    STATUS_READY_TO_MERGE,
)
from seed.lib.mcm import cleaners, mapper, reader
from seed.models.certification import GreenAssessment
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


# HELIX create file, use preset mappings and save file
def helix_address_create(user, dataset, cycle, csv_file):
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    # upload and save to Property state table
    file_pk = loader.upload(csv_file, dataset, cycle)
    import_file = ImportFile.objects.get(pk=file_pk)
    parser = reader.MCMParser(import_file.local_file)

    mappings = []
    # Hardcoding these because they are known ahead of time but,
    # there's no reason matching can't be automatic
    for col in parser.headers:
        if re.match('state', col.lower()) is not None:
            mappings.append(mapping_entry('state', col))
        if re.match('city', col.lower()) is not None:
            mappings.append(mapping_entry('city', col))
        if re.match(r'[postal,zip].*code', col.lower()) is not None:
            mappings.append(mapping_entry('postal_code', col))
            postal_code = col
        if re.match(r'address.*1', col.lower()) is not None:
            mappings.append(mapping_entry('address_line_1', col))
            address1 = col
        if re.match(r'address.*2', col.lower()) is not None:
            mappings.append(mapping_entry('address_line_2', col))
            address2 = col
        if re.match(r'year.*built', col.lower()) is not None:
            mappings.append(mapping_entry('year_built', col))
        if re.match(r'conditioned_floor_area', col.lower()) is not None:
            mappings.append(mapping_entry('conditioned_floor_area', col))
        if re.match(r'[property|development].*name', col.lower()) is not None:
            mappings.append(mapping_entry('property_name', col))
        if re.match(r'internal.*id', col.lower()) is not None:
            mappings.append(mapping_entry('custom_id_1', col))

# Create address records   
    response = loader.autoload_file(file_pk, mappings) 
    return response
    
# Create certifications
def helix_certification_create(user, file_pk):
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    import_file = ImportFile.objects.get(pk=file_pk)
    parser = reader.MCMParser(import_file.local_file)
    data = {
        'new_assessments': 0,
        'updated_assessments': 0,
        'new_measurements': 0,
        'updated_measurements': 0,
    }
    ga_format = None
    # Green Assessment Mappings and format types or return if no green assessment
    if 'green_assessment_name' in parser.headers:
        ga_format = 'long'
    else:
        for col in parser.headers:
            if re.match(r'HERS|ENERGY.*STAR|LEED|HES|HOME.*ENERGY.*SCORE',col.upper()):
                ga_format = 'short'

    if ga_format is None:
        return {'status': 'success', 'data': data}
    
    mappings = []
    assessment_mappings = []
    date_mapping = ''
    has_opt_out = False
    # Hardcoding these because they are known ahead of time but,
    # there's no reason matching can't be automatic
    # VB Note: switch to using column mappings for address
    for col in parser.headers:
        if re.match(r'[postal,zip].*code', col.lower()) is not None:
            mappings.append(mapping_entry('postal_code', col))
            postal_code = col
        if re.match(r'(address|address.*1)$', col.lower()) is not None:
            mappings.append(mapping_entry('address_line_1', col))
            address1 = col
        if re.match(r'address.*2$', col.lower()) is not None:
            mappings.append(mapping_entry('address_line_2', col))
            address2 = col
        if re.match(r'opt.*out', col.lower()) is not None:
            opt_out = col
            has_opt_out = True
        if re.search(r'hers', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('HERS Index Score',col))
        if re.search(r'energy star', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('ENERGY STAR Certified Homes',col))
        if re.search(r'leed', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('LEED for Homes',col))
        if re.search(r'(ngbs|national green building)', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('NGBS New Construction',col))
        if re.search(r'passive house', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('Passive House',col))
        if re.search(r'efficiency vermont', col.lower()) is not None:
            assessment_mappings.append(mapping_entry('Efficiency Vermont Certified',col))
        if re.search(r'[complete|assessment].*date', col.lower()) is not None:
            date_mapping = col
                                     
    # If a green property assessment is provided for the property
    # parse the data and create the green assessment entry        
    rows = parser.next()
    for row in rows:
        print row
        if row[date_mapping] is not '':
            row[date_mapping] = test_date_format(row[date_mapping])
        if ga_format == 'short':
            for assess in assessment_mappings:
                assessment = GreenAssessment.objects.get(name=assess['to_field'], organization_id=user.default_organization.id)
                score_type = ("metric" if assessment.is_numeric_score else "rating")
                score_value = test_score_value(score_type, row[assess['from_field']])

                if score_value not in ['','FALSE']:
                    green_assessment_data = {
                        "date": row[date_mapping],
                        "assessment": assessment
                    }
                    green_assessment_data.update({score_type: score_value})                    
                    normalized_address = normalize_address_str(row[address1], row[address2])
                    
                    loader.create_green_assessment_property(
                        green_assessment_data, normalized_address, row[postal_code])                     
                
        elif ga_format == 'long':
            # do data base lookup by name for the assessment
            # all assessments must exists in the database before upload
            assessment = GreenAssessment.objects.get(name=row['green_assessment_name'], organization_id=user.default_organization.id)
            print assessment
            green_assessment_data = {
                "source": row["green_assessment_property_source"],
                "version": row["green_assessment_property_version"],
                "date": row["green_assessment_property_date"],
                "status": row["green_assessment_property_status"],
                "extra_data": row["green_assessment_property_extra_data"],
                "urls": [row["green_assessment_property_url"]],
                "assessment": assessment
            }
            if has_opt_out:
                green_assessment_data["opt_out"] = cleaners.bool_cleaner(row[opt_out])
                 
            score_type = ("metric" if assessment.is_numeric_score else "rating") 
            score_value = test_score_value(score_type, row['green_assessment_property_'+score_type])
            address2 = ""
            if address2 in row:
                address2 = row[address2]
            if score_value not in ['','FALSE']:
                green_assessment_data.update({score_type: score_value}) 
                normalized_address = normalize_address_str(row[address1], address2)
                print green_assessment_data
           
                log, prop_assess = loader.create_green_assessment_property(
                    green_assessment_data, normalized_address, row[postal_code])
                print log
                print prop_assess
                data['new_assessments'] += log['created']
                data['updated_assessments'] += log['updated']
                
            log = loader.setup_measurements(parser.headers, row, prop_assess)

            data['new_measurements'] += log['created']
            data['updated_measurements'] += log['updated']
            
    return {'status': 'success', 'data': data}

# retrieves home energy score records and formats file for rest of upload process
def helix_hes_to_file(user, dataset, cycle, hes_auth, hes_id):
    # instantiate HES client for external API
    hes_client = hes.HesHelix(hes.CLIENT_URL, hes_auth['user_name'], hes_auth['password'], hes_auth['user_key'])
    # find assessment entry for hes by name. Maybe not ideal!
    hes_assessment = GreenAssessment.objects.get(name='Home Energy Score', organization_id=user.default_organization.id)
#    if len(hes_assessment) != 1:
#        return {"status": "error", "message": 'Bad Home Energy Score Assessment match, check spelling or number of entries'}

    buf = StringIO.StringIO()
    #loop through available id's
#    dict_data = csv.DictReader(csv_file.splitlines())
#    for row in dict_data:
    try:
        hes_data = hes_client.query_hes(hes_id)
    except Fault as f:
        return {"status": "error", "message": f.message}
    
    #change a few naming conventions
    hes_data['green_assessment_property_metric']= hes_data.pop('base_score')     
    hes_data['green_assessment_name'] = 'Home Energy Score'
    hes_data['green_assessment_property_source'] = 'Department of Energy'
    hes_data['green_assessment_property_status'] = hes_data.pop('assessment_type')
    hes_data['green_assessment_property_version'] = hes_data.pop('hescore_version')
    hes_data['green_assessment_property_url'] = hes_data.pop('pdf')
    hes_data['green_assessment_property_date'] = hes_data.pop('assessment_date')
    hes_data['green_assessment_property_extra_data'] = ''
            
    # construct a csv string out of the dictionary retrieved by hes
    buf = StringIO.StringIO()
    try:
        writer
    except:
        writer = csv.DictWriter(buf, fieldnames=hes_data.keys())
        writer.writeheader()
        writer.writerow(hes_data) #merge in with green assessment data
    else:
        writer.writerow(hes_data) #merge in with green assessment data

    csv_file = buf.getvalue()
    buf.close()
    
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    # upload and save to Property state table
    file_pk = loader.upload(csv_file, dataset, cycle)
    # save raw data
    resp = loader.save_raw_data(file_pk)
    if (resp['status'] == 'error'):
        return resp
        
    return {'status': 'success', 'file': file_pk}
    
    
# Similar to the above function, this abstracts logic away from the view in a
# way that should facilitate code reuse.
def helix_hes_upload(user, dataset, cycle, hes_auth, csv_file):
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    
    # instantiate HES client for external APi
    hes_client = hes.HesHelix(hes.CLIENT_URL, hes_auth['user_name'], hes_auth['password'], hes_auth['user_key'])
    # These mappings are hardcoded because they are known ahead of time
    mappings = [mapping_entry('address_line_1', 'address'),
                mapping_entry('city', 'city'),
                mapping_entry('state', 'state'),
                mapping_entry('postal_code', 'zip_code'),
                mapping_entry('year_built', 'year_built'),
                mapping_entry('conditioned_floor_area', 'conditioned_floor_area')]
    # find assessment entry for hes by name. Maybe not the ideal!
    hes_assessment = GreenAssessment.objects.get(name='Home Energy Score', organization_id=user.default_organization.id)
#    if len(hes_assessment) != 1:
#        return {"status": "error", "message": 'Bad Home Energy Score Assessment match, check spelling or number of entries'}
    
    # determine file format from headers
    dict_data = csv.DictReader(csv_file.splitlines())
    for row in dict_data:
        is_hes = row['green_assessment_name'] == 'Home Energy Score'
        hes_id = row['green_assessment_reference_id']    
        if is_hes and hes_id:
            try:
                hes_data = hes_client.query_hes(hes_id)
            except Fault as f:
                return {"status": "error", "message": f.message}

            green_assessment_data = {
                "source": hes_data["qualified_assessor_id"],
                "status": hes_data["assessment_type"],
                "metric": hes_data["base_score"],
                "version": hes_data["hescore_version"],
                "date": hes_data["assessment_date"],
                "urls": [hes_data["pdf"]],
                "assessment": hes_assessment
            }

            # construct a csv string out of the dictionary retrieved by hes
            buf = StringIO.StringIO()

            writer = csv.DictWriter(buf, fieldnames=hes_data.keys())
            writer.writeheader()

            writer.writerow(hes_data)

            csv_file = buf.getvalue()
            buf.close()

            # upload and save to Property state table
            file_pk = loader.upload(csv_file, dataset, cycle)
            #match and merge
            response = loader.autoload_file(file_pk, mappings)    
            if(response['status'] == 'error'):
                return response
            # unique address field
            normalized_address = normalize_address_str(hes_data['address'],'')
            log_data, prop_assess = loader.create_green_assessment_property(
                green_assessment_data,  # data retrieved from HES API
                normalized_address, hes_data['zip_code'])

            for k in hes_data:
                if (k.startswith('CONS') or k.startswith('PROD') or k.startswith('CAP')):
                    consumption = hes_data[k][0]
                    unit = hes_data[k][1]
                    # find fuel and measurement type
                    for fuel in list(HelixMeasurement.HES_FUEL_TYPES.keys()):
                        if fuel in k:
                            break
        
                    measurement_data = {
                        'measurement_type': k.split('_')[0],
                        'fuel':  HelixMeasurement.HES_FUEL_TYPES[fuel],
                        'quantity': consumption,
                        'unit': HelixMeasurement.HES_UNITS[unit], 
                        'status': 'ESTIMATE'}
                    if 'pv' in k:
                        measurement_data['measurement_subtype'] = 'PV'
                        if k.startswith('CAP'):
                            measurement_data['year'] = hes_data[k][2]
                            
                    loader.create_measurement(prop_assess, **measurement_data)

    # revoke session token created for the hes client
    # if the client was never instantiated, nothing needs to be done
    if(hes_client is not None):
        hes_client.end_session()

    return {'status': 'success'}
    
    
# Test for valid date formats
def test_date_format(value):
        #TODO: use seed.lib.mcm.cleaner date_cleaner instead
    try: 
        datetime.datetime.strptime(value, '%Y-%m-%d')
        return value
    except ValueError:
        try:
            value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return value
        except ValueError:
            try: 
                value = datetime.datetime.strptime(value, '%m/%d/%y')
                return value
            except ValueError:
                raise ValueError("Incorrect data format, should be YYYY-MM-DD, MM/DD/YY or Excel date")

# Test for valid score value
def test_score_value(score_type, value):
    if score_type == 'metric': 
        return value
    else:
        #TODO: use seed.lib.mcm.cleaner bool_cleaner instead
        if value in [0,1]:
            return str(bool(value)).upper()
        else:
            return value.strip().upper()
                

    
