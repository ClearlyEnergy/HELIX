# Setup
  * Copy helix module folder into seed directoy
  * Add to config/settings/common.py
     ```
     INSTALLED_APPS = ('helix',) + INSTALLED_APPS 
     ```
    This should place helix templates at a higher priority than existing seed templates.
    (It might be better to add this to config/settings/local_untracked.py)
  * Start server. Seed logo should be replaced with helix.
