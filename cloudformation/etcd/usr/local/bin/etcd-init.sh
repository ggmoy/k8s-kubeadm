#!/bin/bash

export INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
export LOCAL_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/local-hostname)
export LOCAL_IPV4=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

export ETCDCTL_API=3
export ETCDCTL_CACERT=/etc/etcd/ssl/certs/etcd-root-ca.pem
export ETCDCTL_CERT=/etc/etcd/ssl/certs/$INSTANCE_ID.pem
export ETCDCTL_KEY=/etc/etcd/ssl/private/$INSTANCE_ID-key.pem
export ETCDCTL_DIAL_TIMEOUT=3s
export ETCDCTL_ENDPOINTS=https://etcd.esc-dev.com:2379

SSL_DIR=/etc/etcd/ssl

##
# Return the ASG Healthy instance ids separated by a space
##
function get_healthy_instances {
    instances=""

    cmd_out=$(
        aws autoscaling describe-auto-scaling-groups --auto-scaling-group-name etcd-cluster --region us-east-1 | \
            jq -r '.AutoScalingGroups[0].Instances[] | select(.HealthStatus == "Healthy") | .InstanceId'
    )

    for instance_id in $cmd_out
    do
        [[ $instances != "" ]] && instances+=" "
        instances+=$instance_id
    done

    echo "$instances"
}

################################################################################
# Create certificate and private key                                           #
################################################################################
cat > $SSL_DIR/$INSTANCE_ID-ca-csr.json <<EOF
{
  "key": {
    "algo": "rsa",
    "size": 2048
  },
  "names": [
    {
      "O": "etcd",
      "OU": "etcd Security",
      "L": "San Francisco",
      "ST": "California",
      "C": "USA"
    }
  ],
  "CN": "$INSTANCE_ID",
  "hosts": [
    "$LOCAL_IPV4",
    "$LOCAL_HOSTNAME",
    "etcd.esc-dev.com"
  ]
}
EOF

cfssl gencert \
    --ca $SSL_DIR/certs/etcd-root-ca.pem \
    --ca-key $SSL_DIR/private/etcd-root-ca-key.pem \
    --config $SSL_DIR/etcd-gencert.json \
    $SSL_DIR/$INSTANCE_ID-ca-csr.json | cfssljson --bare $SSL_DIR/certs/$INSTANCE_ID

mv $SSL_DIR/certs/$INSTANCE_ID-key.pem $SSL_DIR/private/

# verify
#openssl x509 -in $SSL_DIR/certs/$INSTANCE_ID.pem -text -noout


##
# Check if we are bootstraping the cluster
##
INITIAL_CLUSTER_STATE=$(
    aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-name etcd-cluster \
        --region us-east-1 | jq -r '.AutoScalingGroups[0].Tags[] | select(.Key == "initial-cluster-state") | .Value'
)

initial_cluster=""

if [[ $INITIAL_CLUSTER_STATE = "new" ]]
then
    echo "[INFO]: The cluster is bootstrapping ..."

    declare -a healthy_instance_ids
    healthy_instance_ids=( $(get_healthy_instances) )
    echo "${healthy_instance_ids[@]}"

    while [[ ${#healthy_instance_ids[@]} -ne 3 ]]
    do
        echo "[INFO]: Amount of healthy instances ... ${#healthy_instance_ids[@]}"
        sleep 10

        healthy_instance_ids=( $(get_healthy_instances) )
        echo "${healthy_instance_ids[@]}"
    done

    for (( i=0; i<${#healthy_instance_ids[@]}; i++ ))
    do
        instance_ip=$(
            aws ec2 describe-instances \
                --instance-ids ${healthy_instance_ids[$i]} --region us-east-1 | \
                jq -r '.Reservations[0].Instances[0].NetworkInterfaces[0].PrivateIpAddress'
        )
        [[ $initial_cluster != "" ]] && initial_cluster+=","
        initial_cluster+="${healthy_instance_ids[$i]}=https://${instance_ip}:2380"
    done

    cp /etc/etcd/etcd.conf.tmpl /etc/etcd/etcd.conf
    sed -i "s/INSTANCE_ID/$INSTANCE_ID/g" /etc/etcd/etcd.conf
    sed -i "s/LOCAL_IPV4/$LOCAL_IPV4/g" /etc/etcd/etcd.conf
    sed -i "s/INITIAL_CLUSTER_STATE/$INITIAL_CLUSTER_STATE/g" /etc/etcd/etcd.conf
    sed -i "s|INITIAL_CLUSTER|$initial_cluster|g" /etc/etcd/etcd.conf

elif [[ $INITIAL_CLUSTER_STATE = "existing" ]]
then
    etcdctl lock add_node /usr/bin/python3 /usr/local/bin/etcd-pre-start.py
fi

rm -Rf /tmp/etcd
mkdir /tmp/etcd
chmod 700 /tmp/etcd
