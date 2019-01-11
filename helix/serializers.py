# !/usr/bin/env python
# encoding: utf-8
"""
"""

from rest_framework import serializers
from helix.models import HelixMeasurement

class HelixMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelixMeasurement
        fields = '__all__'