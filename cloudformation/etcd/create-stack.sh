#!/bin/bash

aws cloudformation create-stack \
    --stack-name etcd-cluster \
    --template-body file://etcd-cluster.yaml \
    --capabilities CAPABILITY_IAM \
    --profile esc-dev 
