#!/bin/bash

INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
LOCAL_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/local-hostname)
LOCAL_IPV4=$(curl -s http://169.254.169.254/latest/meta-data/local-ipv4)

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

    cat <<EOF > /run/etcd.conf
name: $INSTANCE_ID

data-dir: /tmp/etcd

listen-client-urls: https://0.0.0.0:2379
advertise-client-urls: https://$LOCAL_IPV4:2379

listen-peer-urls: https://0.0.0.0:2380
initial-advertise-peer-urls: https://$LOCAL_IPV4:2380

# Initial cluster configuration for bootstrapping.
initial-cluster: $initial_cluster

# Initial cluster token for the etcd cluster during bootstrap.
initial-cluster-token: etcd-cluster

# Initial cluster state ('new' or 'existing').
initial-cluster-state: $INITIAL_CLUSTER_STATE

# Health checks to port 80 to avoid AWS ELB errors.
listen-metrics-urls: http://$LOCAL_IPV4:80

client-transport-security:
    # Enable client cert authentication.
    client-cert-auth: true

    # Path to the client server TLS cert file.
    cert-file: /etc/etcd/ssl/certs/$INSTANCE_ID.pem

    # Path to the client server TLS key file.
    key-file: /etc/etcd/ssl/private/$INSTANCE_ID-key.pem

    # Path to the client server TLS cert file.
    trusted-ca-file: /etc/etcd/ssl/certs/etcd-root-ca.pem

peer-transport-security:
    # Enable peer client cert authentication.
    client-cert-auth: true

    # Path to the peer server TLS cert file.
    cert-file: /etc/etcd/ssl/certs/$INSTANCE_ID.pem

    # Path to the peer server TLS key file.
    key-file: /etc/etcd/ssl/private/$INSTANCE_ID-key.pem

    # Path to the peer server TLS trusted CA cert file.
    trusted-ca-file: /etc/etcd/ssl/certs/etcd-root-ca.pem
EOF

fi

rm -Rf /tmp/etcd
mkdir /tmp/etcd
chmod 700 /tmp/etcd
