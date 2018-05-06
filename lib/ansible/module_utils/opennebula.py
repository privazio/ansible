#!/usr/bin/python
#
# Copyright 2018 www.privaz.io Valletech AB
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


import time
from os import environ
from ssl import _create_unverified_context
from six import string_types

HAS_PYONE = True

try:
    import pyone
    from pyone.tester import OneServerTester
except ImportError:
    HAS_PYONE = False

OPENNEBULA_COMMON_ARGS = dict(
    endpoint=dict(type='str'),
    session=dict(type='str', no_log=True),
    validate_certs=dict(default=True, type='bool'),
    wait_timeout=dict(type='int', default=300),
)


def create_one_server(module):
    """
    Creates an XMLPRC client to OpenNebula.
    Args:
        module:

    Returns:

    """
    endpoint = module.params.get("endpoint", environ.get("PYONE_ENDPOINT",False))
    session = module.params.get("session", environ.get("PYONE_SESSION",False))

    test_fixture = (environ.get("PYONE_TEST_FIXTURE", "False").lower() in ["1", "yes", "true"])
    test_fixture_file = environ.get("PYONE_TEST_FIXTURE_FILE", "undefined")
    test_fixture_replay = (environ.get("PYONE_TEST_FIXTURE_REPLAY", "True").lower() in ["1","yes","true"])
    test_fixture_unit = environ.get("PYONE_TEST_FIXTURE_UNIT", "init")

    # Check if the module can run
    if not HAS_PYONE:
        module.fail_json(msg="pyone is required for this module")

    if not endpoint:
        module.fail_json(msg= "Either endpoint or the environment variable PYONE_ENDPOINT must be provided")

    if not session:
        module.fail_json(msg= "Either session or the environment vairable PYONE_SESSION must be provided")

    if not test_fixture:
        if not module.params.get("validate_certs") and not "PYTHONHTTPSVERIFY" in environ:
            return pyone.OneServer(endpoint, session=session, context=_create_unverified_context())
        else:
            return pyone.OneServer(endpoint, session)
    else:
        if not module.params.get("validate_certs") and not "PYTHONHTTPSVERIFY" in environ:
            one = OneServerTester(endpoint,
                                   fixture_file=test_fixture_file,
                                   fixture_replay=test_fixture_replay,
                                   session=session,
                                   context=_create_unverified_context())
        else:
            one = OneServerTester(endpoint,
                                   fixture_file=test_fixture_file,
                                   fixture_replay=test_fixture_replay,
                                   session=session)
        one.set_fixture_unit_test(test_fixture_unit)
        return one

def close_one_server(one):
    """
    Closing is only require in the event of fixture recording, as fixtures will be dumped to file
    """
    if environ.get("PYONE_TEST_FIXTURE", False):
        one._close_fixtures()


def get_host_by_name(one, name):
    '''
    Returns a host given its name.
    Args:
        one: the XMLRPC client object
        name: the name of the host

    Returns: the host object or None if the host is absent.

    '''
    hosts = one.hostpool.info()
    for h in hosts.HOST:
        if h.NAME == name:
            return h
    return None

def get_cluster_by_name(one, name):
    '''
    Returns a cluster given its name.
    Args:
        one: the XMLRPC client object
        name: the name of the cluster

    Returns: the cluster object or None if the host is absent.

    '''
    clusters = one.clusterpool.info()
    for c in clusters.CLUSTER:
        if c.NAME == name:
            return c
    return None


def get_template_by_name(one, name):
    '''
    Returns a template given its name.
    Args:
        one: the XMLRPC client object
        name: the name of the template

    Returns: the template object or None if the host is absent.

    '''
    templates = one.templatepool.info()
    for t in templates.TEMPLATE:
        if t.NAME == name:
            return t
    return None


def cast_template(template):
    """
    OpenNebula handles all template types as strings
    At some point there is a cast being performed on types provided by the user
    This function mimics that transformation so that required template updates are detected properly
    additionally an array will be converted to a comma separated list,
    which works for labels and hopefully for something more.

    Args:
        template: the template to transform

    Returns: the transformed template with data casts applied.
    """

    # TODO: check formally available data types in templates

    for key in template:
        value = template[key]
        if isinstance(value, dict):
            cast_template(template[key])
        elif isinstance(value, list):
            template[key] = ', '.join(value)
        elif not isinstance(value, string_types):
            template[key] = str(value)


def requires_template_update(current, desired):
    """
    This function will help decide if a template update is required or not
    If a desired key is missing from the current dictionary an update is required
    If the intersection of both dictionaries is not deep equal, an update is required
    Args:
        current: current template as a dictionary
        desired: desired template as a dictionary

    Returns: True if a template update is required
    """

    if not desired:
        return False

    cast_template(desired)
    intersection = dict()
    for dkey in desired.keys():
        if dkey in current.keys():
            intersection[dkey] = current[dkey]
        else:
            return True
    return not (desired == intersection)


def resolve_parameters(one, module):
    '''
    This function resolves parameters provided by a secondary ID to the primary ID.
    For example if cluster_name is present, cluster_id will be introduced by performing
    the required resolution
    Args:
        module: the module to get the parameters from

    Returns: a copy of the paramters that includes the resolved parameters.

    '''

    resolved_params = dict(module.params)

    if 'cluster_name' in module.params:
        clusters = one.clusterpool.info()
        for cluster in clusters.CLUSTER:
            if cluster.NAME == module.params.get('cluster_name'):
                resolved_params['cluster_id'] = cluster.ID

    return resolved_params

def wait_for_state(module, element_name, state, state_name, target_states, invalid_states=[],transition_states=None, wait_timeout=None):
    '''

    Args:
        module: Ansible module in execution
        element_name: the name of the object we are waiting for: HOST, VM, etc.
        state: lambda that returns the current state, will be queried until target state is reached
        state_name: lambda that returns the readable form of a given state
        target_states: states expected to be reached
        invalid_states: if any of this states is reached, fail
        transition_states: when used, these are the valid states during the transition.
        wait_timeout: timeout period in seconds. Defaults to the provided parameter.

    '''

    if not wait_timeout:
        wait_timeout = module.params.get("wait_timeout")

    if module.params.get('_test_fixture_replay'):
        sleep_time_ms = 0.1
    else:
        sleep_time_ms = 1

    start_time = time.time()

    while (time.time() - start_time) < wait_timeout:
        current_state = state()

        if current_state in invalid_states:
            module.fail_json(msg='invalid %s state %s' % (element_name, state_name(current_state)))

        if transition_states:
            if current_state not in transition_states:
                module.fail_json(msg='invalid %s transition state %s' % (element_name, state_name(current_state)))

        if current_state in target_states:
            return True

        time.sleep(sleep_time_ms)

    module.fail_json(msg="Wait timeout has expired!")