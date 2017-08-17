from django.contrib import admin

from seed.models.certification import GreenAssessment

# Adding this line lets GreenAssessments be modified through the django admin
# web page. While I have implemented a front end for GreenAssessment management,
# this interface should give finer control over assessments.
admin.site.register(GreenAssessment)
