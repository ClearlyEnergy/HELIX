# Setup
  * Copy helix module folder into seed directoy 
  * Install modules helix-hes and seed-autoload
  * Add to config/settings/common.py
     ```
     INSTALLED_APPS = ('helix',) + INSTALLED_APPS 
     ```
    This should place helix templates at a higher priority than existing seed templates.
    (It might be better to add this to config/settings/local_untracked.py)
  * Add to config/urls.py
    ```
    urlpatterns = [url(r'^helix/', include('helix.urls', namespace="helix", app_name="helix"))] + urlpatterns
    ```
    This should register the url unique to the HELIX module with django.
  * Start server. Seed logo should be replaced with helix.
  * Navigate to http://localhost:8000/helix to verify that the page displays correctly
