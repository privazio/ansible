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
    - "This is my longer description explaining my sample module"

options:
    name:
        description:
            - Hostname of the machine to manage.
        required: true
    im_mad_name:
        description:
            - The name of the information manager, this values are taken from the oned.conf with the tag name IM_MAD (name)
        required: true
    vmm_mad_name:
        description:
            - The name of the virtual machine manager mad name, this values are taken from the oned.conf with the tag name VM_MAD (name)
        required: true
    cluster_id:
        description:
            - The cluster ID. If it is -1, the default one will be used.
        required: true
        default: -1

extends_documentation_fragment:
    - opennebula

author:
    - Rafael del Valle (@rvalle)
'''

EXAMPLES = '''
#  Allocates a new host in OpenNebula
- name:
  opennebula_host:
    name: host1
    im_mad_name: kvm
    vmm_mad_name: kvm
    cluster_id: 1
'''

RETURN = '''
original_message:
    description: The original name param that was passed in
    type: str
message:
    description: The output message that the sample module generates
'''

from ansible.module_utils.basic import AnsibleModule

def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        name=dict(type='str', required=True),
        new=dict(type='bool', required=False, default=False)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        return result

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    result['original_message'] = module.params['name']
    result['message'] = 'goodbye'

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    if module.params['new']:
        result['changed'] = True

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    if module.params['name'] == 'fail me':
        module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
