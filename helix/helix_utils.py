import csv
import StringIO
import re
import datetime
import json

from celery import chord, shared_task
#from celery.utils.log import get_task_logger

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
from zeep.exceptions import Fault

from helix.models import HelixMeasurement
from helix.utils.address import normalize_address_str

from autoload import autoload
from hes import hes
from leed import leed
    
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
    resp = load_csv_data(user, dataset, cycle, csv_data, file_name)
    return resp    
    
def save_formatted_data(headers, data):
    buf = StringIO.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for dat in data:
        writer.writerow(dat)

    csv_file = buf.getvalue()
    buf.close()
    
    return csv_file

def load_csv_data(user, dataset, cycle, csv_file, file_name):
    # load some of the data directly from csv
    loader = autoload.AutoLoad(user, user.default_organization)
    # upload and save to Property state table
    file_pk = loader.upload(file_name, csv_file, dataset, cycle)
    # save raw data
    resp = loader.save_raw_data(file_pk)
    if (resp['status'] == 'error'):
        return resp

    return {'status': 'success', 'file': file_pk, 'message': 'successful file upload'}
