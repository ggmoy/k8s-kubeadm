#!/bin/bash

aws cloudformation create-change-set \
    --change-set-name "updating-etcd-cluster" \
    --stack-name etcd-cluster \
    --template-body file://etcd-cluster.yaml \
    --capabilities CAPABILITY_IAM \
    --profile esc-dev 
