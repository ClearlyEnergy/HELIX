from django.test import TestCase

from helix.helix_utils import mapping_entry

class TestHelixUtil(TestCase):

    def test_dummy(self):
        self.assertEqual(mapping_entry("to","from"),
                         {"to_field": "to",
                          "from_field": "from",
                          "to_table_name": "PropertyState"})
