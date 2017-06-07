from django.conf.urls import patterns, url

urlpatterns = patterns(
    'helix.views',
    url(r'^$','helix',name='helix'),
)
