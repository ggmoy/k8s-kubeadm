#!/bin/bash

export INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

export ETCDCTL_API=3
export ETCDCTL_CACERT=/etc/etcd/ssl/certs/etcd-root-ca.pem
export ETCDCTL_CERT=/etc/etcd/ssl/certs/$INSTANCE_ID.pem
export ETCDCTL_KEY=/etc/etcd/ssl/private/$INSTANCE_ID-key.pem
export ETCDCTL_DIAL_TIMEOUT=3s
export ETCDCTL_ENDPOINTS=https://etcd.esc-dev.com:2379

etcdctl lock remove_unhealthy_nodes /usr/local/bin/etcdctl-cron.py
