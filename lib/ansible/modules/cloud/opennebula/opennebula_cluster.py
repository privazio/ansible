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
module: opennebula_cluster

short_description: Manages OpenNebula Cluster

version_added: "2.5"

description:
    - "Manages OpenNebula Cluster"

options:
    name:
        description:
            - Name of the cluster to manage.
        required: true
    state:
        description:
            - If C(absent) the cluster will be allocated.
            - If C(present) the cluster will be deleted.
        choices:
            - absent
            - present
        default: present
'''

EXAMPLES = '''
- name: Create a Cluster
  opennebula_cluster:
    name: cluster7

- name: Create a Cluster and tune its template
  opennebula_cluster:
    name: cluster8
    template:
        LABELS:
            - gold
        RESERVED_CPU: -100
'''

# TODO: what makes most sense to return?
RETURN = '''
'''

from ansible.module_utils.opennebula import OPENNEBULA_COMMON_ARGS, create_one_server, get_cluster_by_name, requires_template_update, resolve_parameters
from ansible.module_utils.basic import AnsibleModule

# Host State Constants, for request change and reported

try:
    from pyone import OneException, HOST_STATES, HOST_STATUS
except ImportError:
    OneException = Exception  #handled at module utils

def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = OPENNEBULA_COMMON_ARGS
    module_args.update(dict(
        name=dict(type='str', required=True),
        state=dict(choices=['present', 'absent'], default='present'),
        template = dict(type='dict')
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

        # Resolve parameters using secondary IDs
        resolved_params = resolve_parameters(one, module)

        cluster_name = resolved_params.get("name")
        cluster = get_cluster_by_name(one,resolved_params.get('name'))

        # manage cluster state
        desired_state = resolved_params.get('state')

        if desired_state == "present":
            if not cluster:
                if one.cluster.allocate(cluster_name):
                    result['changed'] = True
                    cluster = get_cluster_by_name(one, cluster_name)
                else:
                    module.fail_json(msg="could not create cluster")
        else:
            if cluster:
                if one.cluster.delete(cluster.ID):
                    result['changed'] = True
                    cluster = None
                else:
                    module.fail_json(msg="could not delete cluster")

        # manage the cluster template, if it is present or was just created
        if cluster:
            desired_template_changes = resolved_params.get('template')
            if requires_template_update(cluster.TEMPLATE, desired_template_changes):
                # setup the root element so that pytone will generate XML instead of attribute vector
                desired_template_changes = {"TEMPLATE": desired_template_changes}
                if one.cluster.update(cluster.ID, desired_template_changes, 1):  # merge the template
                    result['changed'] = True
                else:
                    module.fail_json(msg="failed to update the cluster template")


        # return
        module.exit_json(**result)
    except OneException as e:
        module.fail_json(msg="OpenNebula Exception: %s" % e)

def main():
    run_module()

if __name__ == '__main__':
    main()
