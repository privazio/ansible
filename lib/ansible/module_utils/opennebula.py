#!/usr/bin/python
#
# Copyright 2018 www.privaz.io Valletech AB
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


HAS_PYONE = True

from os import environ
from ssl import _create_unverified_context
from six import string_types

try:
    import pyone
except ImportError:
    HAS_PYONE = False

OPENNEBULA_COMMON_ARGS = dict(
    endpoint = dict(type='str'),
    session = dict(type='str', no_log=True),
    validate_certs=dict(default=True, type='bool'),
)

def create_one_server(module):
    endpoint = module.params.get("endpoint", environ.get("PYONE_ENDPOINT",False))
    session = module.params.get("session", environ.get("PYONE_SESSION",False))

    #Check if the module can run
    if not HAS_PYONE:
        module.fail_json(msg="pyone is required for this module")

    if not endpoint:
        module.fail_json(msg= "Either endpoint or the environment variable PYONE_ENDPOINT must be provided")

    if not session:
        module.fail_json(msg= "Either session or the environment vairable PYONE_SESSION must be provided")

    if not module.params.get("validate_certs") and not "PYTHONHTTPSVERIFY" in environ:
        return pyone.OneServer(endpoint, session=session, context=_create_unverified_context())
    else:
        return pyone.OneServer(endpoint,session)




# TODO: check formally available data types in templates
# OpenNebula handles all template types as strings
# At some point there is a cast being performed on types provided by the user
# This method mimics that data cast so that required template updates are detected properly
# additionally an array will be converted to a comma separated list, which works for labels and hopefully for something else.

def cast_template(template):
    for key in template:
        value = template[key]
        if isinstance(value, dict):
            cast_template(template[key])
        elif isinstance(value, list):
            template[key] = ', '.join(value)
        elif not isinstance(value, string_types):
            template[key] = str(value)

# This method will help decide if a template update is required or not
# If a desired key is missing from the current dictionary an update is required
# If the intersection of both dictionaries is not deep equal, an update is required
def requires_template_update(current, desired):
    cast_template(desired)
    intersection = dict()
    for dkey in desired.keys():
        if dkey in current.keys():
            intersection[dkey] = current[dkey]
        else:
            return True
    return not (desired == intersection)