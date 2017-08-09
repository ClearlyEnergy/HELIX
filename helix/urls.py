from django.conf.urls import patterns, url
from helix.views import (
    helix_home,
    helix_hes,
    helix_csv_upload,
    assessment_view,
    assessment_edit)

urlpatterns = patterns('',
    url(r'^$', helix_home, name='helix_home'),
    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
    url(r'^helix-csv-upload/$', helix_csv_upload, name="helix_csv_upload"),
    url(r'^assessments/$', assessment_view, name="assessment_view"),
    url(r'^assessments/edit/$', assessment_edit, name="assessment_edit")
)
