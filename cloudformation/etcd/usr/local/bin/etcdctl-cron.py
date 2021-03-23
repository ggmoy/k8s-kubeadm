#!/usr/bin/python3

import sys
import etcdctl_utils as etcd

unhealthy_members = etcd.get_unhealthy_members()
healthy_members = etcd.get_healthy_members()

if not unhealthy_members:
    print("[INFO]: There are not unhealthy members. Exiting ...")
    sys.exit(0)

if len(healthy_members) < 2:
    print("[ERROR]: The amount of healthy members is less than 2. The cluster is unhealthy. Exiting ...")
    sys.exit(1)

for member in unhealthy_members:
    if etcd.etcd_remove_member(member):
        print("[INFO]: Member %s has been removed from the cluster" % member['name'])
    else:
        print("[ERROR]: Member %s could not be removed from the cluster" % member['name'])
