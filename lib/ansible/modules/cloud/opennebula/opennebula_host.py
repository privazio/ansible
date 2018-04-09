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
    cluster_name:
        description:
            - The cluster specified by name.
    template:
        description:
            - The template changes to merge into the host template.

extends_documentation_fragment: opennebula

author:
    - Rafael del Valle (@rvalle)
'''

EXAMPLES = '''
- name: Create a new host in OpenNebula
  opennebula_host:
    name: host1
    cluster_id: 1
    endpoint: http://127.0.0.1:2633/RPC2

- name: Create a host and adjust its template
  opennebula_host:
    name: host2
    cluster_name: default
    template:
        LABELS:
            - gold
            - ssd
        RESERVED_CPU: -100
'''

# TODO: what makes most sense to return?
RETURN = '''
'''

# TODO: Documentation on valid state transitions is required to properly implement all valid cases
# TODO: To be coherent with CLI this module should also provide "flush" functionality

from ansible.module_utils.opennebula import OPENNEBULA_COMMON_ARGS, create_one_server, get_host_by_name, requires_template_update, resolve_parameters
from ansible.module_utils.basic import AnsibleModule

# Host State Constants, for request change and reported

try:
    from pyone import OneException, HOST_STATES, HOST_STATUS
except ImportError:
    OneException = Exception  #handled at module utils


HOST_ABSENT = -99  # the host is absent (special case defined by this module)


def allocate_host(one, module, resolved_params, result):
    if not one.host.allocate(resolved_params.get('name'), resolved_params.get('vmm_mad_name'), resolved_params.get('im_mad_name'), resolved_params.get('cluster_id')):
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
        cluster_name=dict(type='str'),
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
        supports_check_mode=False,
        mutually_exclusive=[
            ['cluster_id', 'cluster_name']
        ]
    )

    try:

        # Create the opennebula XMLRPC client
        one = create_one_server(module)

        # Resolve parameters using secondary IDs
        resolved_params = resolve_parameters(one, module)

        # Get the list of hots
        host_name = resolved_params.get("name")
        host = get_host_by_name(one, host_name)

        # manage host state
        desired_state = resolved_params.get('state')
        if bool(host):
            current_state = host.STATE
            current_state_name = HOST_STATES(host.STATE).name
        else:
            current_state = HOST_ABSENT
            current_state_name = "ABSENT"

        # apply properties
        if desired_state == 'present':
            if current_state == HOST_ABSENT:
                allocate_host(one, module, resolved_params, result)
                host = get_host_by_name(one, host_name)

        elif desired_state == 'enabled':
            if current_state == HOST_ABSENT:
                allocate_host(one, module, resolved_params, result)
                host = get_host_by_name(one, host_name)
            elif current_state in [HOST_STATES.DISABLED, HOST_STATES.OFFLINE]:
                if one.host.status(host.ID, HOST_STATUS.ENABLED):
                    result['changed'] = True
                else:
                    module.fail_json(msg="could not enable host")
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
                module.fail_json(msg='absent host cannot be placed in offline state')
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

        if desired_state != "offline":

            # manipulate or modify the template
            desired_template_changes = resolved_params.get('template')
            if requires_template_update(host.TEMPLATE, desired_template_changes):
                # setup the root element so that pytone will generate XML instead of attribute vector
                desired_template_changes = {"TEMPLATE": desired_template_changes}
                if one.host.update(host.ID, desired_template_changes, 1):  # merge the template
                    result['changed'] = True
                else:
                    module.fail_json(msg="failed to update the host template")

            # the cluster
            if host.CLUSTER_ID != resolved_params.get('cluster_id'):
                if one.cluster.addhost(resolved_params.get('cluster_id'),host.ID):
                    result['changed'] = True
                else:
                    module.fail_json(msg="failed to update the host cluster")


        # return
        module.exit_json(**result)
    except OneException as e:
        module.fail_json(msg="OpenNebula Exception: %s" % e)

def main():
    run_module()

if __name__ == '__main__':
    main()
