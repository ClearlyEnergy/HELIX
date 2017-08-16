from django.conf.urls import patterns, url
from helix.views import (
    helix_hes,
    helix_csv_upload,
    helix_csv_export,
    assessment_view,
    assessment_edit,
    helix_reso_export_xml
)


urlpatterns = patterns('',
    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
    url(r'^helix-csv-upload/$', helix_csv_upload, name="helix_csv_upload"),
    url(r'^assessments/$', assessment_view, name="assessment_view"),
    url(r'^assessments/edit/$', assessment_edit, name="assessment_edit"),
    url(r'^helix-csv-export/$', helix_csv_export, name="helix_csv_export"),
    url(r'^helix-reso-export-xml/$', helix_reso_export_xml, name="helix_reso_export_xml")
)
