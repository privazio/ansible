#
# Copyright 2018 www.privaz.io Valletech AB
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


import time
import ssl
from os import environ
from ansible.module_utils.six import string_types
from ansible.module_utils.basic import AnsibleModule


HAS_PYONE = True

try:
    import pyone
    from pyone import OneException
    from pyone.tester import OneServerTester
except ImportError:
    OneException = Exception
    HAS_PYONE = False


class OpenNebulaModule:
    """
    Base class for all OpenNebula Ansible Modules.
    This is basically a wrapper of the common arguments, the pyone client and
    Some utility methods. It will also create a Test client if fixtures are
    to be replayed or recorded and manage that they are flush to disk when
    required.
    """

    common_args = dict(
        endpoint=dict(type='str'),
        session=dict(type='str', no_log=True),
        validate_certs=dict(default=True, type='bool'),
        wait_timeout=dict(type='int', default=300),
    )

    def __init__(self, argument_spec, supports_check_mode=False, mutually_exclusive=None):

        module_args = OpenNebulaModule.common_args
        module_args.update(argument_spec)

        self.module = AnsibleModule(argument_spec=module_args,
                                    supports_check_mode=supports_check_mode,
                                    mutually_exclusive=mutually_exclusive)
        self.result = dict(changed=False,
                           original_message='',
                           message='')
        self.one = self.create_one_client()

        self.resolved_parameters = self.resolve_parameters()

    def create_one_client(self):
        """
        Creates an XMLPRC client to OpenNebula.
        Dependign on environment variables it will implement a test client.

        Returns: the new xmlrpc client.

        """

        test_fixture = (environ.get("PYONE_TEST_FIXTURE", "False").lower() in ["1", "yes", "true"])
        test_fixture_file = environ.get("PYONE_TEST_FIXTURE_FILE", "undefined")
        test_fixture_replay = (environ.get("PYONE_TEST_FIXTURE_REPLAY", "True").lower() in ["1", "yes", "true"])
        test_fixture_unit = environ.get("PYONE_TEST_FIXTURE_UNIT", "init")

        # context required for not validating SSL, old python versions won't validate anyway.
        if hasattr(ssl, '_create_unverified_context'):
            no_ssl_validation_context = ssl._create_unverified_context()
        else:
            no_ssl_validation_context = None

        # Check if the module can run
        if not HAS_PYONE:
            self.fail("pyone is required for this module")

        if 'endpoint' in self.module.params:
            endpoint = self.module.params.get("endpoint", environ.get("PYONE_ENDPOINT", False))
        else:
            self.fail("Either endpoint or the environment variable PYONE_ENDPOINT must be provided")

        if 'session' in self.module.params:
            session = self.module.params.get("session", environ.get("PYONE_SESSION", False))
        else:
            self.fail("Either session or the environment vairable PYONE_SESSION must be provided")

        if not test_fixture:
            if not self.module.params.get("validate_certs") and "PYTHONHTTPSVERIFY" not in environ:
                return pyone.OneServer(endpoint, session=session, context=no_ssl_validation_context)
            else:
                return pyone.OneServer(endpoint, session)
        else:
            if not self.module.params.get("validate_certs") and "PYTHONHTTPSVERIFY" not in environ:
                one = OneServerTester(endpoint,
                                      fixture_file=test_fixture_file,
                                      fixture_replay=test_fixture_replay,
                                      session=session,
                                      context=no_ssl_validation_context)
            else:
                one = OneServerTester(endpoint,
                                      fixture_file=test_fixture_file,
                                      fixture_replay=test_fixture_replay,
                                      session=session)
            one.set_fixture_unit_test(test_fixture_unit)
            return one

    def close_one_client(self):
        """
        Closing is only require in the event of fixture recording, as fixtures will be dumped to file
        """
        if self.is_fixture_writing():
            self.one._close_fixtures()

    def fail(self, msg):
        """
        Utility failure method, will ensure fixtures are flushed before failing.
        Args:
            msg: human readable failure reason.
        """
        if hasattr(self, 'one'):
            self.close_one_client()
        self.module.fail_json(msg=msg)

    def exit(self):
        """
        Utility exit method, will ensure fixtures are flushed before exiting.

        """
        if hasattr(self, 'one'):
            self.close_one_client()
        self.module.exit_json(**self.result)

    def resolve_parameters(self):
        """
        This method resolves parameters provided by a secondary ID to the primary ID.
        For example if cluster_name is present, cluster_id will be introduced by performing
        the required resolution

        Returns: a copy of the parameters that includes the resolved parameters.

        """

        resolved_params = dict(self.module.params)

        if 'cluster_name' in self.module.params:
            clusters = self.one.clusterpool.info()
            for cluster in clusters.CLUSTER:
                if cluster.NAME == self.module.params.get('cluster_name'):
                    resolved_params['cluster_id'] = cluster.ID

        return resolved_params

    def get_parameter(self, name):
        """
        Utility method for accessing parameters that includes resolved ID
        parameters from provided Name parameters.
        """
        return self.resolved_parameters.get(name)

    def is_fixture_replay(self):
        """
        Returns: true if we are currently running fixtures in replay mode.

        """
        return (environ.get("PYONE_TEST_FIXTURE", "False").lower() in ["1", "yes", "true"]) and \
               (environ.get("PYONE_TEST_FIXTURE_REPLAY", "True").lower() in ["1", "yes", "true"])

    def is_fixture_writing(self):
        """
        Returns: true if we are currently running fixtures in write mode.

        """
        return  (environ.get("PYONE_TEST_FIXTURE", "False").lower() in ["1", "yes", "true"]) and \
                (environ.get("PYONE_TEST_FIXTURE_REPLAY", "True").lower() in ["0", "no", "false"])

    def get_host_by_name(self, name):
        '''
        Returns a host given its name.
        Args:
            name: the name of the host

        Returns: the host object or None if the host is absent.

        '''
        hosts = self.one.hostpool.info()
        for h in hosts.HOST:
            if h.NAME == name:
                return h
        return None

    def get_cluster_by_name(self, name):
        """
        Returns a cluster given its name.
        Args:
            name: the name of the cluster

        Returns: the cluster object or None if the host is absent.
        """

        clusters = self.one.clusterpool.info()
        for c in clusters.CLUSTER:
            if c.NAME == name:
                return c
        return None

    def get_template_by_name(self, name):
        '''
        Returns a template given its name.
        Args:
            name: the name of the template

        Returns: the template object or None if the host is absent.

        '''
        templates = self.one.templatepool.info()
        for t in templates.TEMPLATE:
            if t.NAME == name:
                return t
        return None

    def cast_template(self, template):
        """
        OpenNebula handles all template elements as strings
        At some point there is a cast being performed on types provided by the user
        This function mimics that transformation so that required template updates are detected properly
        additionally an array will be converted to a comma separated list,
        which works for labels and hopefully for something more.

        Args:
            template: the template to transform

        Returns: the transformed template with data casts applied.
        """

        # TODO: check formally available data types in templates
        # TODO: some arrays might be converted to space separated

        for key in template:
            value = template[key]
            if isinstance(value, dict):
                self.cast_template(template[key])
            elif isinstance(value, list):
                template[key] = ', '.join(value)
            elif not isinstance(value, string_types):
                template[key] = str(value)

    def requires_template_update(self, current, desired):
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

        self.cast_template(desired)
        intersection = dict()
        for dkey in desired.keys():
            if dkey in current.keys():
                intersection[dkey] = current[dkey]
            else:
                return True
        return not (desired == intersection)

    def wait_for_state(self, element_name, state, state_name, target_states,
                       invalid_states=None, transition_states=None,
                       wait_timeout=None):
        """
        Args:
            element_name: the name of the object we are waiting for: HOST, VM, etc.
            state: lambda that returns the current state, will be queried until target state is reached
            state_name: lambda that returns the readable form of a given state
            target_states: states expected to be reached
            invalid_states: if any of this states is reached, fail
            transition_states: when used, these are the valid states during the transition.
            wait_timeout: timeout period in seconds. Defaults to the provided parameter.
        """

        if not wait_timeout:
            wait_timeout = self.module.params.get("wait_timeout")

        if self.is_fixture_replay():
            sleep_time_ms = 0.01
        else:
            sleep_time_ms = 1

        start_time = time.time()

        while (time.time() - start_time) < wait_timeout:
            current_state = state()

            if current_state in invalid_states:
                self.fail('invalid %s state %s' % (element_name, state_name(current_state)))

            if transition_states:
                if current_state not in transition_states:
                    self.fail('invalid %s transition state %s' % (element_name, state_name(current_state)))

            if current_state in target_states:
                return True

            time.sleep(sleep_time_ms)

        self.fail(msg="Wait timeout has expired!")

    def run_module(self):
        """
        trigger the start of the execution of the module.
        Returns:

        """
        try:
            self.run(self.one, self.module, self.result)
        except OneException as e:
            self.fail(msg="OpenNebula Exception: %s" % e)

    def run(self, one, module, result):
        """
        to be implemented by subclass with the actual module actions.
        Args:
            one: the OpenNebula XMLRPC client
            module: the Ansible Module object
            result: the Ansible result
        """
        raise NotImplementedError("Method requires implementation")
