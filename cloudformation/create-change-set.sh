#!/bin/bash

aws cloudformation create-change-set \
    --change-set-name "updating-k8s-kubeadm-cluster" \
    --stack-name k8s-kubeadm-cluster \
    --template-body file://k8s-kubeadm.yaml \
    --capabilities CAPABILITY_IAM \
    --profile esc-dev 
