const cdk = require('@aws-cdk/core');
const ec2 = require('@aws-cdk/aws-ec2');

class K8SKubeadmCdkStack extends cdk.Stack {
  /**
   *
   * @param {cdk.Construct} scope
   * @param {string} id
   * @param {cdk.StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    // The code that defines your stack goes here
    const vpc = new ec2.Vpc(this, 'TheVPC', {
      cidr: '10.0.0.0/16',
      maxAzs: 2,
      subnetConfiguration: [],
      natGateways: 0
    });
  }
}

module.exports = { K8SKubeadmCdkStack }
