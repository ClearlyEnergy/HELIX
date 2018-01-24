from django.conf.urls import url
from helix.views import (
    assessment_view,
    assessment_edit,
    helix_hes,
    helix_csv_export,
    helix_reso_export_xml
)

urlpatterns = [
    url(r'^certifications/$', assessment_view, name="assessment_view"),
    url(r'^certifications/edit/$', assessment_edit, name="assessment_edit"),
    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
    url(r'^helix-csv-export/$', helix_csv_export, name="helix_csv_export"),
    url(r'^helix-reso-export-xml/$', helix_reso_export_xml, name="helix_reso_export_xml"),
]