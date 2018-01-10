from django.conf.urls import url
from helix.views import (
    hes_upload,
#    helix_hes_upload,
    helix_hes,
    helix_csv_upload,
    helix_csv_export,
    assessment_view,
    assessment_edit,
    helix_reso_export_xml
)

urlpatterns = [
    url(r'^certifications/$', assessment_view, name="assessment_view"),
    url(r'^certifications/edit/$', assessment_edit, name="assessment_edit"),
#    url(r'^hes-upload/$', helix_hes_upload, name='hes_upload'),
    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
#    url(r'^helix-hes-upload/$', helix_hes_upload, name='helix_hes_upload'),
    url(r'^helix-csv-upload/$', helix_csv_upload, name="helix_csv_upload"),
    url(r'^helix-csv-export/$', helix_csv_export, name="helix_csv_export"),
    url(r'^helix-reso-export-xml/$', helix_reso_export_xml, name="helix_reso_export_xml"),
]