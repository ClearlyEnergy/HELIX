# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2017, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""

import re

import usaddress
from streetaddress import StreetAddressFormatter

STATE_MAP = {
        'Alaska': 'AK',
        'Alabama': 'AL',
        'Arkansas': 'AR',
        'American Samoa': 'AS',
        'Arizona': 'AZ',
        'California': 'CA',
        'Colorado': 'CO',
        'Connecticut': 'CT',
        'District of Columbia': 'DC',
        'Delaware': 'DE',
        'Florida': 'FL',
        'Georgia': 'GA',
        'Guam': 'GU',
        'Hawaii': 'HI',
        'Iowa': 'IA',
        'Idaho': 'ID',
        'Illinois': 'IL',
        'Indiana': 'IN',
        'Kansas': 'KS',
        'Kentucky': 'KY',
        'Louisiana': 'LA',
        'Massachusetts': 'MA',
        'Maryland': 'MD',
        'Maine': 'ME',
        'Michigan': 'MI',
        'Minnesota': 'MN',
        'Missouri': 'MO',
        'Northern Mariana Islands': 'MP',
        'Mississippi': 'MS',
        'Montana': 'MT',
        'National': 'NA',
        'North Carolina': 'NC',
        'North Dakota': 'ND',
        'Nebraska': 'NE',
        'New Hampshire': 'NH',
        'New Jersey': 'NJ',
        'New Mexico': 'NM',
        'Nevada': 'NV',
        'New York': 'NY',
        'Ohio': 'OH',
        'Oklahoma': 'OK',
        'Oregon': 'OR',
        'Pennsylvania': 'PA',
        'Puerto Rico': 'PR',
        'Rhode Island': 'RI',
        'South Carolina': 'SC',
        'South Dakota': 'SD',
        'Tennessee': 'TN',
        'Texas': 'TX',
        'Utah': 'UT',
        'Virginia': 'VA',
        'Virgin Islands': 'VI',
        'Vermont': 'VT',
        'Washington': 'WA',
        'Wisconsin': 'WI',
        'West Virginia': 'WV',
        'Wyoming': 'WY'
}

def _normalize_address_direction(direction):
    direction = direction.lower().replace('.', '')
    direction_map = {
        'east': 'e',
        'west': 'w',
        'north': 'n',
        'south': 's',
        'northeast': 'ne',
        'northwest': 'nw',
        'southeast': 'se',
        'southwest': 'sw'
    }
    if direction in direction_map:
        return direction_map[direction]
    return direction


POST_TYPE_MAP = {
    'avenue': 'ave',
}


def _normalize_address_post_type(post_type):
    value = post_type.lower().replace('.', '')
    return POST_TYPE_MAP.get(value, value)


ADDRESS_NUMBER_RE = re.compile((
    r''
    r'(?P<start>[0-9]+)'  # The left part of the range
    r'\s?'  # Optional whitespace before the separator
    r'[\\/-]?'  # Optional Separator
    r'\s?'  # Optional whitespace after the separator
    r'(?<=[\s\\/-])'  # Enforce match of at least one separator char.
    r'(?P<end>[0-9]+)'  # THe right part of the range
))


def _normalize_address_number(address_number):
    """
    Given the numeric portion of an address, normalize it.
    - strip leading zeros from numbers.
    - remove whitespace from ranges.
    - convert ranges to use dash as separator.
    - expand any numbers that appear to have had their leading digits
      truncated.
    """
    match = ADDRESS_NUMBER_RE.match(address_number)
    if match:
        # This address number is a range, so normalize it.
        components = match.groupdict()
        range_start = components['start'].lstrip("0")
        range_end = components['end'].lstrip("0")
        if len(range_end) < len(range_start):
            # The end range value is omitting a common prefix.  Add it back.
            prefix_length = len(range_start) - len(range_end)
            range_end = range_start[:prefix_length] + range_end
        return '-'.join([range_start, range_end])

    # some addresses have leading zeros, strip them here
    return address_number.lstrip("0")
    
def _normalize_secondary_address(secondary):    
    secondary = secondary.lower().replace('.', '')
    secondary_map = {
        'apartment': 'apt',
        'building': 'bldg',
        'floor': 'fl',
        'suite': 'ste',
        'room': 'rm',
        'department': 'dept',
    }
    for k, v in secondary_map.items():
        secondary = secondary.replace(k, v)
    
    return secondary    

def normalize_address_str(address_val, address_val_2, extra_data):
    """
    Normalize the address to conform to short abbreviations.

    If an invalid address_val is provided, None is returned.

    If a valid address is provided, a normalized version is returned.
    """
    # if this string is empty the regular expression in the sa wont
    # like it, and fail, so leave returning nothing
    if not address_val:
        return None

    address_val = unicode(address_val).encode('utf-8')

    # Do some string replacements to remove odd characters that we come across
    replacements = {
        '\xef\xbf\xbd': '',
        '\uFFFD': '',
    }
    for k, v in replacements.items():
        address_val = address_val.replace(k, v)

    # now parse the address into number, street name and street type
    try:
        # Add in the mapping of CornerOf to the AddressNumber.
        if address_val_2:
            addr = usaddress.tag(str(address_val + ' ' + address_val_2), tag_mapping={'CornerOf': 'AddressNumber'})[0]
        else:
            addr = usaddress.tag(str(address_val), tag_mapping={'CornerOf': 'AddressNumber'})[0]  
            
        print addr
    except usaddress.RepeatedLabelError:
        # usaddress can't parse this at all
        normalized_address = str(address_val)
    except UnicodeEncodeError:
        # Some kind of odd character issue that we are not handling yet.
        normalized_address = str(address_val)
    else:
        # Address can be parsed, so let's format it.
        normalized_address = ''

        if 'AddressNumber' in addr and addr['AddressNumber'] is not None:
            normalized_address = _normalize_address_number(
                addr['AddressNumber'])

        if 'StreetNamePreDirectional' in addr and addr['StreetNamePreDirectional'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_address_direction(
                addr['StreetNamePreDirectional'])  # NOQA

        if 'StreetName' in addr and addr['StreetName'] is not None:
            normalized_address = normalized_address + ' ' + addr['StreetName']

        if 'StreetNamePostType' in addr and addr['StreetNamePostType'] is not None:
            # remove any periods from abbreviations
            normalized_address = normalized_address + ' ' + _normalize_address_post_type(
                addr['StreetNamePostType'])  # NOQA

        if 'StreetNamePostDirectional' in addr and addr['StreetNamePostDirectional'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_address_direction(
                addr['StreetNamePostDirectional'])  # NOQA
                
        if 'SubaddressType' in addr and addr['SubaddressType'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_secondary_address(addr['SubaddressType'])
            
        if 'SubaddressIdentifier' in addr and addr['SubaddressIdentifier'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_address_number(addr['SubaddressIdentifier'])
 
        if 'OccupancyType' in addr and addr['OccupancyType'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_secondary_address(addr['OccupancyType'])

        if 'OccupancyIdentifier' in addr and addr['OccupancyIdentifier'] is not None:
            normalized_address = normalized_address + ' ' + _normalize_address_number(addr['OccupancyIdentifier'])

        formatter = StreetAddressFormatter()
        normalized_address = formatter.abbrev_street_avenue_etc(normalized_address)

    return normalized_address.lower().strip()

def normalize_postal_code(postal_code_val):
    """
    Normalize the postal code to have a minimum of 5 digits
    
    If excel has for example changed 05720 to 5720, the normalization will return 05720
    """
    normalized_postal_code = str(postal_code_val).strip()
    if len(normalized_postal_code) < 5:
        normalized_postal_code = normalized_postal_code.zfill(5)
    return normalized_postal_code
    
def normalize_state(state_val):
    """
    Normalize the state to a two letter abbreviation
    """
    if len(state_val) > 2:
        if state_val.capitalize() in STATE_MAP:
            return STATE_MAP[state_val.capitalize()]
        else:
            return state_val
    else:
        return state_val.upper()
    