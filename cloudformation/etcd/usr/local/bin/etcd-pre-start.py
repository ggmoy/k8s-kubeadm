################################################################################
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
import subprocess

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

os.unsetenv('ETCDCTL_ENDPOINTS')

print("[INFO]: Checking the amount of healthy members")
healthy_members = get_healthy_members()
print("[INFO]: There are {} healthy members".format(len(healthy_members)))

if len(healthy_members) < 2:
    print("[ERROR]: The cluster is not healthy".format(len(healthy_members)))
    sys.exit(1)

print("[INFO]: Checking the amount of unhealthy members")
unhealthy_members = get_unhealthy_members()
print("[INFO]: There are {} unhealthy members".format(len(unhealthy_members)))

if len(unhealthy_members) > 0:
    print("[INFO]: Removing unhealthy members")

    failed = False
    for member in unhealthy_members:
        if etcd_remove_member(member):
            print("[INFO]: Member {} has been removed".format(member['name']))
        else:
            print("[ERROR]: Member {} could not be removed".format(member['name']))
            failed = True
    if failed:
        sys.exit(1)

print("[INFO]: Removing this node from the cluster")
for member in healthy_members:
    if not (member['name'] == os.environ['INSTANCE_ID'] or
            re.match('.*{}'.format(os.environ['LOCAL_IPV4']), member['peer_addrs'])):
        continue

    if etcd_remove_member(member):
        print("[INFO]: Member {} has been removed".format(member['name']))
        break
    else:
        print("[ERROR]: Member {} could not be removed".format(member['name']))
        sys.exit(1)

print("[INFO]: Adding member {} to the cluster".format(os.environ['INSTANCE_ID']))
if etcd_add_member({
    'name': os.environ['INSTANCE_ID'],
    'peer_addrs': 'https://{}:2380'.format(os.environ['LOCAL_IPV4'])
}):
    print("[INFO]: Member {} has been added to the cluster".format(member['name']))
else:
    print("[ERROR]: Member {} could not be added to the cluster".format(member['name']))
    sys.exit(1)

print("[INFO]: Updating etcd config file")
with open('/etc/etcd/etcd.conf.tmpl', 'r') as in_file:
    with open('/etc/etcd/etcd.conf', 'w') as out_file:
        initial_cluster = ','.join(['{}={}'.format(member['name'], member['peer_addrs']) for member in healthy_members])
        initial_cluster += ',{}=https://{}:2380'.format(os.environ['INSTANCE_ID'], os.environ['LOCAL_IPV4'])
        for line in in_file:
            line = line.replace('INSTANCE_ID', os.environ['INSTANCE_ID'])
            line = line.replace('LOCAL_IPV4', os.environ['LOCAL_IPV4'])
            line = line.replace('INITIAL_CLUSTER_STATE', 'existing')
            line = line.replace('INITIAL_CLUSTER', initial_cluster)
            out_file.write(line)
