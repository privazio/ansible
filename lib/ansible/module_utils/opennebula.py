#!/usr/bin/python
#
# Copyright 2018 www.privaz.io Valletech AB
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


HAS_PYONE = True

try:
    import pyone
except ImportError:
    HAS_PYONE = False

OPENNEBULA_COMMON_ARGS = dict(
    endpoint = dict(type='str'),
    username = dict(type='str', no_log=True),
    password = dict(type='str', no_log=True)
)