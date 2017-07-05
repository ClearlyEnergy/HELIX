from django.conf.urls import patterns, url
from helix.views import helix_home, helix_hes

urlpatterns = patterns('',
    url(r'^$', helix_home, name='helix_home'),

    url(r'^helix-hes/$', helix_hes, name='helix_hes'),
)
