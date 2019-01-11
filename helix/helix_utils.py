import os
import csv
import StringIO
import re
import datetime
import json
import time, calendar

from django.core.files.storage import default_storage, FileSystemStorage
from django.conf import settings

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
    DATA_STATE_UNKNOWN, 
    DATA_STATE_MATCHING,
    MERGE_STATE_MERGED,
    MERGE_STATE_NEW)

from helix.models import HelixMeasurement
from helix.utils.address import normalize_address_str
    
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
    

