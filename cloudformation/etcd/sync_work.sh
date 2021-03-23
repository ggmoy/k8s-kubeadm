#!/bin/bash

IP=$1

rsync -av \
    --include="etcd-add-node.sh" \
    --include="etcd-init.sh" \
    --include="etcd-pre-start.py" \
    --include="etcdctl-cron.py" \
    --include="etcdctl-cron.sh" \
    --include="etcdctl-test.py" \
    --include="etcdctl_utils.py" \
    --exclude="*" \
    root@$IP:/usr/local/bin/ usr/local/bin/
