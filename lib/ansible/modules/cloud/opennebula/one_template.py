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
module: one_template

short_description: Manages OpenNebula Templates

version_added: "2.5"

description:
    - "Manages OpenNebula Templates"

options:
    name:
        description:
            - Name of the template to manage.
        required: true
    state:
        description:
            - If C(absent) the cluster will be allocated.
            - If C(present) the cluster will be deleted.
    marketapp_id:
        description:
            - Create this template from the market app with the given ID.
    marketapp_name:
        description:
            - Create this template from the market app with the given name.
    template:
        description:
            - The template contents.
'''

EXAMPLES = '''
- name: Create a VM Templates from a Market Appliance
  one_template:
    name: Debian9
    marketapp_id: 18
'''

# TODO: what makes most sense to return?
RETURN = '''
'''


from ansible.module_utils.opennebula import OPENNEBULA_COMMON_ARGS, create_one_server, get_template_by_name, requires_template_update, resolve_parameters
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
        marketapp_id=dict(type='int'),
        marketapp_name=dict(type='str'),
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
        supports_check_mode=False,
        mutually_exclusive=[
            ['marketapp_id', 'marketapp_name']
        ],
        required_one_of=[
            ['template','marketapp_id','marketapp_name']
        ]
    )

    try:

        # Create the opennebula XMLRPC client
        one = create_one_server(module)

        # Resolve parameters using secondary IDs
        resolved_params = resolve_parameters(one, module)

        template_name = resolved_params.get("name")
        template = get_template_by_name(one,template_name)

        # manage cluster state
        desired_state = resolved_params.get('state')

        if desired_state == "present":
            if not template:
                if one.cluster.allocate(cluster_name):
                    result['changed'] = True
                    cluster = get_cluster_by_name(one, cluster_name)
                else:
                    module.fail_json(msg="could not create cluster")
        else:
            if template:
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
