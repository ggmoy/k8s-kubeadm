#!/bin/bash

aws cloudformation create-stack \
    --stack-name k8s-kubeadm-cluster \
    --template-body file://k8s-kubeadm.yaml \
    --capabilities CAPABILITY_IAM \
    --profile esc-dev 
