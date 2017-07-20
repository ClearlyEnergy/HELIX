from django.conf.urls import patterns, url
from helix.views import helix_home, helix_hes, helix_csv_upload

urlpatterns = patterns('',
    url(r'^$', helix_home, name='helix_home'),
    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
    url(r'^helix-csv-upload/$', helix_csv_upload, name="helix_csv_upload")
)
