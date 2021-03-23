################################################################################
#
# 1. The cluster is bootstrapping (initial-cluster-state = new)
#
#    - Get the instance list from the ASG
#    - Create /etc/etcd/etcd.conf file
#    - Finish and let etcd start
#
# 2. The cluster already bootstrapped (initial-cluster-state = existing)
#
#    - Get lock
#    - Check if the amount of healthy members is at least 2. Otherwise, exit(1)
#    - Delete unhealthy members
#    - Check if this node is part of the cluster and remove it
#    - Add this node to the cluster
#    - Create initial-cluster string
#
# TODO:
#
#    - Add a cron job in charge of removing unhealthy members. It has to check
#      the amount of healthy members in the cluster before doing anything.
#
#    - The etcd-pre-start.py script should terminate if there are unhealty
#      members. Then, it will retry until the cron job do the clean up.
#
################################################################################
import os
import re
import sys
import json
import time
import base64
import subprocess
import http.client

def get(key, revision=None):
    args = [
        "etcdctl",
        "get",
        "%s" % key,
        "--endpoints=https://etcd.esc-dev.com:2379",
        "--write-out=json"
    ]

    if revision:
        args.append("--rev=%s" % revision)

    sp = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    sp_stdout, sp_stderr = sp.communicate()

    return json.loads(sp_stdout.decode('utf-8')) if sp.wait() == 0 else None

def put(key, value, lease=None):
    args = [
            "etcdctl",
            "put",
            "%s" % key,
            "%s" % value,
            "--endpoints",
            "https://etcd.esc-dev.com:2379",
            "--write-out=json"
    ]

    if lease:
        args.append("--lease=%s" % lease)

    sp = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    sp_stdout, sp_stderr = sp.communicate()

    return json.loads(sp_stdout.decode('utf-8')) if sp.wait() == 0 else None

def delete(key):
    args = [
            "etcdctl",
            "del",
            "%s" % key,
            "--endpoints",
            "https://etcd.esc-dev.com:2379",
            "--write-out=json"
    ]

    sp = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    sp_stdout, sp_stderr = sp.communicate()

    return json.loads(sp_stdout.decode('utf-8')) if sp.wait() == 0 else None

def txn(tran):
    sp = subprocess.Popen(
        'etcdctl txn --endpoints https://etcd.esc-dev.com:2379 --write-out=json <<<\'%s\'' % tran,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        executable='/bin/bash'
    )
    sp_stdout, sp_stderr = sp.communicate()

    return json.loads(sp_stdout.decode('utf-8')) if sp.wait() == 0 else None

def get_lease(ttl):
    lease = None

    p = subprocess.Popen(
        [
            "etcdctl",
            "lease",
            "grant",
            "%s" % ttl,
            "--endpoints",
            "https://etcd.esc-dev.com:2379"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    p_stdout, p_stderr = p.communicate()

    if p.wait() == 0:
        lease = p_stdout.decode('utf-8').split(' ')[1]

    return lease

def revoke_lease(lease):
    p = subprocess.Popen(
        [
            "etcdctl",
            "lease",
            "revoke",
            "%s" % lease,
            "--endpoints",
            "https://etcd.esc-dev.com:2379"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    p_stdout, p_stderr = p.communicate()

    return True

def acquire_lock(key, value, ttl):
    lease = None

    while True:
        print("[%.6f][%s]: Trying to acquire the lock with ttl=%s" % (time.time(), os.getpid(), ttl))

        lease = get_lease(ttl)
        if not lease:
            return False

        resp = txn(f'version("{key}") = "0"\n\nput {key} "{value}" --lease={lease}\n\nget {key}\n\n')
        if not resp:
            return False

        if 'succeeded' in resp and resp['succeeded']:
            print("[%.6f][%s]: Lock acquired!" % (time.time(), os.getpid()))
            break



#{
#    "header": {
#        "cluster_id": 15821320785994664816,
#        "member_id": 2935593729910097743,
#        "revision": 9488,
#        "raft_term": 6
#    },
#    "responses": [
#        {
#            "Response": {
#                "ResponseRange": {
#                    "header": {
#                        "revision": 9488
#                    },
#                    "kvs": [
#                        {
#                            "key": "a2s=",
#                            "create_revision": 9482,
#                            "mod_revision": 9482,
#                            "version": 1,
#                            "value": "MTk4NTAz",
#                            "lease": 5138458032743614600
#                        }
#                    ],
#                    "count": 1
#                }
#            }
#        }
#    ]
#}

        print("[%.6f][%s]: Waiting for the lock ..." % (time.time(), os.getpid()))

        # Watch for lock's key
        sp = subprocess.Popen(
            [
                "etcdctl",
                "watch",
                "%s" % key,
                "--rev=%s" % int(resp['responses'][0]['Response']['ResponseRange']['kvs'][0]['create_revision'] + 1),
                "--endpoints",
                "https://etcd.esc-dev.com:2379"
            ],
            stdout=subprocess.PIPE
        )
        line = sp.stdout.readline()

        # Clean up process
        sp.kill()
        outs = sp.communicate()

    return lease

##
# Return a list of members
##
def get_members_list():
    members = list()

    p = subprocess.Popen(
        [
            "etcdctl",
            "member",
            "list",
            "--endpoints",
            "https://etcd.esc-dev.com:2379"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    p_stdout, p_stderr = p.communicate()

    for line in p_stdout.decode('utf-8').splitlines():
        fields = line.split(', ')
        members.append({
            'id': fields[0],
            'status': fields[1],
            'name': fields[2],
            'peer_addrs': fields[3],
            'client_addrs': fields[4],
            'is_learner': fields[5]
        })

    return members

def get_healthy_members():
    return [member for member in get_members_list() if is_member_healthy(member)]

def get_unhealthy_members():
    return [member for member in get_members_list() if not is_member_healthy(member)]

##
# Check if a member is healthy
##
def is_member_healthy(member):
    if member['status'] == 'unstarted':
        return False

    p = subprocess.Popen(
        [
            "etcdctl",
            "endpoint",
            "health",
            "--endpoints",
            member['client_addrs']
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return True if p.wait() == 0 else False

##
# Return True is succeeded of False if failed
##
def etcd_add_member(member):
    p = subprocess.Popen(
        [
            "etcdctl", "--endpoints", "https://etcd.esc-dev.com:2379",
            "member", "add",
            member['name'],
            "--peer-urls={}".format(member['peer_addrs'])
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return True if p.wait() == 0 else False

##
# Return True is succeeded of False if failed
##
def etcd_remove_member(member):
    p = subprocess.Popen(
        [
            "etcdctl", "--endpoints", "https://etcd.esc-dev.com:2379",
            "member", "remove", member['id']
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return True if p.wait() == 0 else False

def etcd_remove_members(members):
    fails = list()
 
    for member in members:
        if not etcd_remove_member(member):
            fails.append(member)

    return fails

def remove_unhealthy_members():
    unhealthy_members = get_unhealthy_members()
    print("[INFO]: There are {} unhealthy members".format(unhealthy_members))

    if len(unhealthy_members) == 0:
        return []

    healthy_members = get_healthy_members()
    print("[INFO]: There are {} healthy members".format(healthy_members))

    if len(healthy_members) < 2:
        print("[ERROR]: There are less than 2 healthy members")
        print("[ERROR]: The cluster is unhealthy")
        sys.exit(1)

    print("[INFO]: Removing unhealthy members")
    for member in unhealthy_members:
        print(json.dumps(member, indent=4))
        if etcd_remove_member(member):
            print("[INFO]: Member {} has been removed".format(member))
        else:
            print("[ERROR]: Member {} could not be removed".format(member))
            sys.exit(1)

################################################################################
# Code starts here                                                             #
################################################################################

instance_metadata = {
    'instance-id': None,
    'local-ipv4': None
}

def get_instance_id():
    global instance_metadata
    retries = 3

    while not instance_metadata['instance-id'] and retries > 0: #{
        conn = http.client.HTTPConnection("169.254.169.254")
        conn.request("GET", "/latest/meta-data/instance-id")
        resp = conn.getresponse()

        if resp.status == 200: #{
            instance_metadata['instance-id'] = resp.read().decode('utf-8')
            break
        #}

        time.sleep(10)
        retries -= 1
    #}

    return instance_metadata['instance-id']

def get_local_ipv4():
    global instance_metadata
    retries = 3

    while not instance_metadata['local-ipv4'] and retries > 0: #{
        conn = http.client.HTTPConnection("169.254.169.254")
        conn.request("GET", "/latest/meta-data/local-ipv4")
        resp = conn.getresponse()

        if resp.status == 200: #{
            instance_metadata['local-ipv4'] = resp.read().decode('utf-8')
            break
        #}

        time.sleep(10)
        retries -= 1
    #}

    return instance_metadata['local-ipv4']

# Set etcdctl environment
os.environ['ETCDCTL_API'] = '3'
os.environ['ETCDCTL_DIAL_TIMEOUT'] = '3s'
os.environ['ETCDCTL_CACERT'] = '/etc/etcd/ssl/certs/etcd-root-ca.pem'
os.environ['ETCDCTL_CERT'] = '/etc/etcd/ssl/certs/%s.pem' % get_instance_id()
os.environ['ETCDCTL_KEY'] = '/etc/etcd/ssl/private/%s-key.pem' % get_instance_id()
os.environ.pop('ETCDCTL_ENDPOINTS')
