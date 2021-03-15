#!/usr/bin/env node

const cdk = require('@aws-cdk/core');
const { K8SKubeadmCdkStack } = require('../lib/k8s-kubeadm-cdk-stack');

const app = new cdk.App();
new K8SKubeadmCdkStack(app, 'K8SKubeadmCdkStack');
