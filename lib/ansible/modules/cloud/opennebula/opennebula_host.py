#!/usr/bin/python
#
# Copyright 2018 www.privaz.io Valletech AB
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: opennebula_host

short_description: Manages OpenNebula Hosts

version_added: "2.5"

description:
    - "Manages OpenNebula Hosts"

options:
    name:
        description:
            - Hostname of the machine to manage.
        required: true
    endpoint:
        description:
            - The URL of the XMLRPC server.
              If not specified then the value of the PYONE_ENDPOINT environment variable, if any, is used.
    session:
        description:
            - Session string associated to the connected user.
              It has to be formed with the contents of OpenNebula's ONE_AUTH file, which is <username>:<password>
              with the default "core" auth driver.
              If not specified then the value of the PYONE_SESSION environment variable, if any, is used.
    state:
        description:
            - Takes the host to the desired lifecycle state.
            - If C(absent) the host will be deleted from the cluster.
            - If C(present) the host will be created in the cluster (includes C(enabled), C(disabled) and C(offline) states).
            - If C(enabled) the host is fully operational.
            - C(disabled), e.g. to perform maintenance operations.
            - C(offline), host is totally offline.
        choices:
            - absent
            - present
            - enabled
            - disabled
            - offline
        default: present
    validate_certs:
        description:
            - Wheather to validate the SSL certificates or not.
              This parameter is ignored if PYTHONHTTPSVERIFY evironment variable is used.
        default True
    im_mad_name:
        description:
            - The name of the information manager, this values are taken from the oned.conf with the tag name IM_MAD (name)
        default: kvm
    vmm_mad_name:
        description:
            - The name of the virtual machine manager mad name, this values are taken from the oned.conf with the tag name VM_MAD (name)
        default: kvm
    cluster_id:
        description:
            - The cluster ID. If it is -1, the default one will be used.
        default: -1

extends_documentation_fragment:
    - opennebula

author:
    - Rafael del Valle (@rvalle)
'''

EXAMPLES = '''
- name: Create a new host in OpenNebula
  opennebula_host:
    endpoint: http://127.0.0.1:2633/RPC2
    name: host1
    cluster_id: 1
'''

RETURN = '''
original_message:
    description: The original name param that was passed in
    type: str
message:
    description: The output message that the sample module generates
'''

# TODO: Documentation on valid state transitions is required to properly implement all valid cases
# TODO: To be coherent with CLI this module should also provide "flush" functionality

from ansible.module_utils.opennebula import OPENNEBULA_COMMON_ARGS, create_one_server, requires_template_update
from ansible.module_utils.basic import AnsibleModule

# Host State Constants, for request change and reported

try:
    from pyone import OneException, HOST_STATES, HOST_STATUS
except ImportError:
    OneException = Exception  #handled at module utils


HOST_ABSENT = -99 # the host is absent (special case defined by this module)


def get_host_by_name(one, name):
    hosts = one.hostpool.info()
    for h in hosts.HOST:
        if h.NAME == name:
            return h
    return None


def allocate_host(one, module, result):
    if not one.host.allocate(module.params.get('name'), module.params.get('vmm_mad_name'), module.params.get('im_mad_name'), module.params.get('cluster_id')):
        module.fail_json(msg="could not allocate host")
    else:
        result['changed']= True
    return True


def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = OPENNEBULA_COMMON_ARGS
    module_args.update(dict(
        name=dict(type='str', required=True),
        state=dict(choices=['present', 'absent', 'enabled', 'disabled', 'offline'], default='present'),
        im_mad_name=dict(type='str', default="kvm"),
        vmm_mad_name=dict(type='str', default="kvm"),
        cluster_id=dict(type='int', default=-1),
        template = dict(type='dict'),
    ))

    # seed the result dict in the object
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    try:

        # Create the opennebula XMLRPC client
        one = create_one_server(module)

        # Get the list of hots
        host_name = module.params.get("name")
        host = get_host_by_name(one, host_name)

        # manage host state
        desired_state = module.params.get('state')
        if bool(host):
            current_state = host.STATE
            current_state_name = HOST_STATES(host.STATE).name
        else:
            current_state = HOST_ABSENT
            current_state_name = "ABSENT"

        # apply properties

        if desired_state == 'present':
            if current_state == HOST_ABSENT:
                allocate_host(one, module, result)
                host = get_host_by_name(one, host_name)

        elif desired_state == 'enabled':
            if current_state == HOST_ABSENT:
                allocate_host(one, module, result)
                host = get_host_by_name(one, host_name)
            elif current_state in [HOST_STATES.DISABLED, HOST_STATES.OFFLINE]:
                if one.host.status(host.ID, HOST_STATUS.ENABLED):
                    result['changed'] = True
                else:
                    module.fail_json(msg="could not disable host")
            elif current_state in [HOST_STATES.MONITORED]:
                pass
            else:
                module.fail_json(msg="unknown host state %s, cowardly refusing to change state to enable" % current_state_name)

        elif desired_state == 'disabled':
            if current_state == HOST_ABSENT:
                module.fail_json(msg='absent host cannot be put in disabled state')
            elif current_state in [HOST_STATES.MONITORED, HOST_STATES.OFFLINE]:
                if one.host.status(host.ID, HOST_STATUS.DISABLED):
                    result['changed'] = True
                else:
                    module.fail_json(msg="could not disable host")
            elif current_state in [HOST_STATES.DISABLED]:
                pass
            else:
                module.fail_json(msg="unknown host state %s, cowardly refusing to change state to disable" % current_state_name)

        elif desired_state == 'offline':
            if current_state == HOST_ABSENT:
                module.fail_json(msg='absent host cannot be place in offline state')
            elif current_state in [HOST_STATES.MONITORED, HOST_STATES.DISABLED]:
                if one.host.status(host.ID, HOST_STATUS.OFFLINE):
                    result['changed'] = True
                else:
                    module.fail_json(msg="could not set host offline")
            elif current_state in [HOST_STATES.OFFLINE]:
                pass
            else:
                module.fail_json(msg="unknown host state %s, cowardly refusing to change state to offline" % current_state_name)

        elif desired_state == 'absent':
            if current_state != HOST_ABSENT:
                if one.host.delete(host.ID):
                    result['changed'] = True
                else:
                    module.fail_json(msg="could not delete host from cluster")

        # if we reach this point we can assume that the host was taken to the desired state
        # manipulate or modify the template

        desired_template_changes = module.params.get('template')
        if desired_state != "offline" and bool(desired_template_changes):
            if requires_template_update(host.TEMPLATE, desired_template_changes):
                # setup the root element so that pytone will generate XML instead of attribute vector
                desired_template_changes = {"TEMPLATE": desired_template_changes}
                if one.host.update(host.ID, desired_template_changes, 1):  # merge the template
                    result['changed'] = True
                else:
                    module.fail_json(msg="failed to update the host template")

        # return
        module.exit_json(**result)
    except OneException as e:
        module.fail_json(msg="OpenNebula Exception: %s" % e)

def main():
    run_module()

if __name__ == '__main__':
    main()
