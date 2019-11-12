import os
import csv
import StringIO
import re
import datetime
import json
import time, calendar

from django.core.files.storage import default_storage, FileSystemStorage
from django.conf import settings
from django.db.models import Q

from seed.data_importer.models import (
    ImportFile,
    ImportRecord
)

from seed.lib.mcm import cleaners
from seed.lib.mcm.utils import batch
from seed.lib.superperms.orgs.models import Organization
from seed.models.certification import GreenAssessment, GreenAssessmentPropertyAuditLog, GreenAssessmentURL 
from seed.models import (
    ASSESSED_RAW,
    ColumnMapping,
    PropertyState,
    PropertyView,
    Cycle,
    DATA_STATE_IMPORT,
    DATA_STATE_UNKNOWN, 
    DATA_STATE_MATCHING,
    MERGE_STATE_MERGED,
    MERGE_STATE_NEW)
    
from seed.models.auditlog import (
    AUDIT_USER_EDIT,
    AUDIT_USER_CREATE,
    AUDIT_USER_EXPORT,
    DATA_UPDATE_TYPE
)    

from helix.models import HelixMeasurement, HELIXGreenAssessmentProperty
from helix.utils.address import normalize_address_str
from seed.utils.cache import get_cache
    
"""Create csv output format"""
def save_and_load(user, dataset, cycle, data, file_name):
    # write output file headers
    for elem in data:
        try:
            headers
        except:
            headers = elem.keys()
        else:
            headers = list(set(headers + elem.keys()))

    csv_data = save_formatted_data(headers, data)
    resp = upload(file_name, csv_data, dataset, cycle)
    return resp    
    
"""Create csv record"""
def save_formatted_data(headers, data):
    buf = StringIO.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for dat in data:
        writer.writerow(dat)

    csv_file = buf.getvalue()
    buf.close()
    
    return csv_file
    
"""Upload a file to the specified import record"""
def upload(filename, data, dataset, cycle):
    if 'S3' in settings.DEFAULT_FILE_STORAGE:
        path = 'data_imports/' + filename + '.'+ str(calendar.timegm(time.gmtime())/1000)
        temp_file = default_storage.open(path, 'w')
        temp_file.write(data)
        temp_file.close()
    else:        
        path = settings.MEDIA_ROOT + "/uploads/" + filename
        path = FileSystemStorage().get_available_name(path)

        # verify the directory exists
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        # save the file
        with open(path, 'wb+') as temp_file:
            temp_file.write(data)

    f = ImportFile.objects.create(
            import_record=dataset,
            uploaded_filename=filename,
            file=path,
            cycle=cycle,
            source_type="Assessed Raw")
    return f.pk
    
""" wait for a celery task to finish running"""
def wait_for_task(key):
    prog = 0
    while prog < 100:
        prog = int(get_cache(key)['progress'])
        # Call to sleep is required otherwise this method will hang.
        time.sleep(0.5)

""" find propertyview by id, uid or address, create if propertyview does not exist"""
def propertyview_find_or_create(request, org, user):
    create = False
    if 'property_id' in request.GET:
        propertyview_pk = request.GET['property_id']
        propertyview = PropertyView.objects.filter(pk=propertyview_pk)
    elif 'property_uid' in request.GET:
        property_uid = request.GET['property_uid']
        state_ids = PropertyState.objects.filter(Q(ubid__icontains=property_uid) | Q(custom_id_1__icontains=property_uid))
        if state_ids:
            propertyview = PropertyView.objects.filter(state_id__in=state_ids)
            if not propertyview:
                create = True
        else:
            create = True
    if create:
        cycle = Cycle.objects.filter(organization=org).last() #might need to hardcode this        
        dataset = ImportRecord.objects.get(name="Vermont Profile", super_organization = org)
        result = [{'Address Line 1': request.GET['street'], #fix that into line 1 & 2
            'City': request.GET['city'], 
            'Postal Code': request.GET['zipcode'], 
            'State': request.GET['state'],
            'Custom ID 1': request.GET['property_uid']}]
        file_pk = utils.save_and_load(user, dataset, cycle, result, "vt_profile.csv")
        #save data
        resp = save_raw_data(file_pk)            
        save_prog_key = resp['progress_key']
        utils.wait_for_task(save_prog_key)
        #map data
#        save_column_mappings(file_id, col_mappings) #perform column mapping
        resp = map_data(file_pk)
        map_prog_key = resp['progress_key']
        utils.wait_for_task(map_prog_key)
#       attempt to match with existing records
        resp = match_buildings(file_pk)
#            if (resp['status'] == 'error'):
#                return resp
        match_prog_key = resp['progress_key']
        utils.wait_for_task(match_prog_key)
#       retrieve property        
        state_ids = PropertyState.objects.filter(Q(ubid__icontains=property_uid) | Q(custom_id_1__icontains=property_uid))
        if state_ids:
            propertyview = PropertyView.objects.filter(state_id__in=state_ids)

    return propertyview
    
""" Create data dictionary from request variables """
def data_dict_from_vars(request, txtvars, floatvars, boolvars):
    data_dict = {}
    for var in txtvars:
        data_dict[var] = request.GET[var]
    for var in floatvars:
        if request.GET[var]:
            data_dict[var] = float(request.GET[var])
        else:
            data_dict[var] = request.GET[var]
    for var in boolvars:
        if request.GET[var] == "true":
            data_dict[var] = True
        else:
            data_dict[var] = False
    return data_dict
    
    
""" Add profile or scorecard URL to property """
def add_certification_label_to_property(propertyview, user, assessment, url):
    for pv in propertyview:
        assessment_data = {'assessment': assessment, 'view': pv, 'date': datetime.date.today()}
        #consolidate with green addendum
        priorAssessments = HELIXGreenAssessmentProperty.objects.filter(
                view=pv,
                assessment=assessment)
                
        if(not priorAssessments.exists()):
            # If the property does not have an assessment in the database
            # for the specifed assesment type create a new one.
            green_property = HELIXGreenAssessmentProperty.objects.create(**assessment_data)
            green_property.initialize_audit_logs(user=user)
            green_property.save()
        else:
            # find most recently created property and a corresponding audit log
            green_property = priorAssessments.order_by('date').last()
            old_audit_log = GreenAssessmentPropertyAuditLog.objects.filter(greenassessmentproperty=green_property).exclude(record_type=AUDIT_USER_EXPORT).order_by('created').last()
            if old_audit_log is not None:
                # log changes
                green_property.log(
                        changed_fields=assessment_data,
                        ancestor=old_audit_log.ancestor,
                        parent=old_audit_log,
                        user=user)   
            else:
                green_property.initialize_audit_logs(user=user)
                green_property.save()                    
    
        ga_url, _created = GreenAssessmentURL.objects.get_or_create(property_assessment=green_property)
        ga_url.url = url
        ga_url.description = 'Vermont profile generated on ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ga_url.save()
    
        