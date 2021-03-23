#!/bin/bash

echo "[INFO]: etcd-add-node.sh ... STARTED"

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
LOCAL_IPV4=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

export ETCDCTL_API=3
export ETCDCTL_CACERT=/etc/etcd/ssl/certs/etcd-root-ca.pem
export ETCDCTL_CERT=/etc/etcd/ssl/certs/$INSTANCE_ID.pem
export ETCDCTL_KEY=/etc/etcd/ssl/private/$INSTANCE_ID-key.pem
export ETCDCTL_DIAL_TIMEOUT=3s
export ETCDCTL_ENDPOINTS=https://etcd.esc-dev.com:2379

CMD_OUT=$(etcdctl member list | sed "s/, /,/g")

while IFS= read -r line
do
    if [[ "$line" =~ ($INSTANCE_ID|$LOCAL_IPV4) ]]
    then
        member_id=$(echo "$line" | cut -d',' -f1)

        # Remove member
        etcdctl member remove $member_id
    fi
done < <(echo "$CMD_OUT")

# Add member
etcdctl member add $INSTANCE_ID --peer-urls=https://$LOCAL_IPV4:2380

echo "[INFO]: etcd-add-node.sh ... COMPLETE"
