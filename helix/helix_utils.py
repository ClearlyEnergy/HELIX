import os
import requests
import csv
from io import StringIO
import datetime
import time

from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.db.models import Q

from seed.data_importer.models import (
    ImportFile,
)

from seed.models.certification import GreenAssessmentPropertyAuditLog, GreenAssessmentURL
from seed.models import (
    PropertyState,
    PropertyView
)

from seed.models.auditlog import (
    AUDIT_USER_EXPORT,
)

from helix.models import HELIXGreenAssessmentProperty
from helix.utils.address import normalize_address_str
from seed.utils.cache import get_cache


def save_and_load(user, dataset, cycle, data, file_name):
    """
    Create csv output format
    """
    for elem in data:
        try:
            headers
        except:
            headers = list(elem.keys())
        else:
            headers = list(headers | elem.keys())

    csv_data = save_formatted_data(headers, data)
    resp = upload(file_name, csv_data, dataset, cycle)
    return resp


def save_formatted_data(headers, data):
    """
    Create csv output format
    """
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for dat in data:
        writer.writerow(dat)

    csv_file = buf.getvalue()
    buf.close()

    return csv_file


def upload(filename, data, dataset, cycle):
    """
    Upload a file to the specified import record
    """
    #    if 'S3' in settings.DEFAULT_FILE_STORAGE:
    #        path = 'data_imports/' + filename + '.'+ str(calendar.timegm(time.gmtime())/1000)
    #        temp_file = default_storage.open(path, 'w')
    #        temp_file.write(data)
    #        temp_file.close()
    #    else:
    path = settings.MEDIA_ROOT + "/uploads/" + filename
    path = FileSystemStorage().get_available_name(path)

    # verify the directory exists
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    # save the file
    with open(path, 'w+') as temp_file:
        temp_file.write(data)

    f = ImportFile.objects.create(
            import_record=dataset,
            uploaded_filename=filename,
            file=path,
            cycle=cycle,
            source_type="Assessed Raw")
    return f.pk


def wait_for_task(key):
    """
    wait for a celery task to finish running
    """
    prog = 0
    while prog < 100:
        prog = int(get_cache(key)['progress'])
        # Call to sleep is required otherwise this method will hang.
        time.sleep(0.5)


def propertyview_find(request):
    """
    find propertyview by id, uid or address
    """
    propertyview = None
    if 'property_id' in request.GET and request.GET['property_id']:
        propertyview_pk = request.GET['property_id']
        propertyview = PropertyView.objects.filter(pk=propertyview_pk)

    if propertyview is None:
        if 'property_uid' in request.GET and request.GET['property_uid']:
            property_uid = request.GET['property_uid']
    #        property_uid = request.GET['property_uid'].translate({ord(i): None for i in '-_()'})
            state_ids = PropertyState.objects.filter(Q(ubid__icontains=property_uid) | Q(custom_id_1__icontains=property_uid)).filter(postal_code=request.GET['postal_code'])
            propertyview = PropertyView.objects.filter(state_id__in=state_ids)

    if propertyview is None:
        if ('street' in request.GET or 'address_line_1' in request.GET) and ('postal_code' in request.GET or 'zipcode' in request.GET):
            if 'postal_code' in request.GET:
                zip = request.GET['postal_code']
            else:
                zip = request.GET['zipcode']
            if 'address_line_1' in request.GET:
                street = request.GET['address_line_1']
            else:
                street = request.GET['street']
            normalized_address, extra_data = normalize_address_str(street, '', zip, {})
            state_ids = PropertyState.objects.filter(normalized_address=normalized_address)
            propertyview = PropertyView.objects.filter(state_id__in=state_ids)

    return propertyview


def data_dict_from_vars(request, txtvars, floatvars, intvars, boolvars):
    """
    Create data dictionary from request variables
    """
    data_dict = {}
    for var in txtvars:
        if var in request.GET and request.GET[var] is not None:
            data_dict[var] = request.GET[var]
        else:
            data_dict[var] = None
    for var in floatvars:
        if var in request.GET and request.GET[var] is not None:
            data_dict[var] = float(request.GET[var])
    for var in intvars:
        if var in request.GET and request.GET[var] is not None:
            data_dict[var] = int(request.GET[var])
    for var in boolvars:
        if var in request.GET and request.GET[var] == "true":
            data_dict[var] = True
        else:
            data_dict[var] = False
    return data_dict


def add_certification_label_to_property(propertyview, user, assessment, url, status=None):
    """
    Add profile or scorecard URL to property
    """
    for pv in propertyview:
        assessment_data = {'assessment': assessment, 'view': pv, 'date': datetime.date.today()}
        # consolidate with green addendum
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
        if status is not None:
            green_property.status = status
            green_property.status_date = datetime.date.today()
            green_property.save()

        ga_url, _created = GreenAssessmentURL.objects.get_or_create(property_assessment=green_property)
        ga_url.url = url
        ga_url.description = 'Vermont profile generated on ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ga_url.save()

def get_pvwatts_production(latitude, longitude, capacity, module_type=1, losses=5,
                           array_type=1, tilt=5, azimuth=180):
    params = {
        'api_key': settings.PVWATTS_API_KEY,
        'system_capacity': capacity,
        'losses': losses,
        'array_type': array_type,
        'tilt': tilt,
        'azimuth': azimuth,
        'module_type': module_type,
        'lat': latitude,
        'lon': longitude,
    }
    response = requests.get('https://developer.nrel.gov/api/pvwatts/v6.json', params=params)
    if response.status_code == requests.codes.ok:
        return {'success': True, 'production': response.json()['outputs']['ac_annual']}
    return {'success': False, 'code': response.status_code, 'body': response.json()['errors']}
