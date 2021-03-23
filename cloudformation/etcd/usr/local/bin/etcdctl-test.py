#!/usr/bin/python3

import os
import json
import time
import random
import etcdctl_utils as etcd

#print(json.dumps(etcd.get_members_list(), indent=4))

#print("instance-id: %s" % etcd.get_instance_id())
#print("local-ipv4: %s" % etcd.get_local_ipv4())

#lease = etcd.get_lease(30)
#print(etcd.put('Name', 'Gustavo', lease))
#print(etcd.get('Name'))

lease = etcd.acquire_lock("kk", os.getpid(), 60)
if lease:
    secs = random.randrange(1)
    print("[%.6f][%s]: Working during the next %s seconds ..." % (time.time(), os.getpid(), secs))
    time.sleep(secs)
    print("[%.6f][%s]: Done!" % (time.time(), os.getpid()))
#    print(json.dumps(etcd.delete("kk")))
    etcd.revoke_lease(lease)
else:
    print("There was an error on pid %s"  % os.getpid())
