# Setup
  * Copy or symlink `helix`, `seed-autoload` and, `helix-hes` directories into the seed directory.

    Assuming a directory structure like this
    ```
    .
    ├── HELIX
    │   └── helix
    ├── helix-hes
    │   └── hes
    ├── seed
    └── seed-autoload
        └── autoload
    ```
    execute the folowing commands from within the seed directory.

    ```
    $ ln -s ../HELIX/helix/ helix
    $ ln -s ../helix-hes/hes hes
    $ ln -s ../seed-autoload/autoload autoload
    ```
    This should yield the folowing directory structure
    ```
    .
    ├── HELIX
    │   └── helix
    ├── helix-hes
    │   └── hes
    ├── seed
    │   ├── autoload -> ../seed-autoload/autoload/
    │   ├── helix -> ../HELIX/helix/
    │   └── hes -> ../helix-hes/hes
    └── seed-autoload
        └── autoload
    ```
    (for deployment, helix-hes and seed-autoload could be installed through pip install but, this is inconvienient for development)
  * Add to config/settings/common.py below the last line where INSTALLED_APPS is modified by the existing seed code.
     ```
     INSTALLED_APPS = ('helix','autoload','hes',) + INSTALLED_APPS 
     ```
    This should place helix templates at a higher priority than existing seed templates.
    (It might be better to add this to config/settings/local_untracked.py)
  * Add to config/urls.py
    ```
    urlpatterns = [url(r'^helix/', include('helix.urls', namespace="helix", app_name="helix"))] + urlpatterns
    ```
    This should register the url unique to the HELIX module with django.
  * Run
    ```
    ./manage.py makemigrations
    ./manage.py migrate
    ```
  * Examine database with tool of choice to verify the presence of two new tables.
  * Start server. Seed logo should be replaced with helix.
  * Helix upload capabilities can be verified by attempting to upload a HELIX csv file through the interface on the seed main page.
  * Navigate to http://localhost:8000/helix to verify that the page displays correctly
