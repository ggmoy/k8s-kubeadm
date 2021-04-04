import grpc
import rpc_pb2 
import rpc_pb2_grpc

ca_file = None
with open('/etc/etcd/ssl/certs/etcd-root-ca.pem', 'rb') as f:
    ca_file = f.read()

cert_file = None
with open('/etc/etcd/ssl/certs/i-0d0bc816344429074.pem', 'rb') as f:
    cert_file = f.read()

key_file = None
with open('/etc/etcd/ssl/private/i-0d0bc816344429074-key.pem', 'rb') as f:
    key_file = f.read()

credentials = grpc.ssl_channel_credentials(ca_file, key_file, cert_file)

channel = grpc.secure_channel('etcd.esc-dev.com:2379', credentials, options=None)

clusterstub = rpc_pb2_grpc.ClusterStub(channel)

member_list_request = rpc_pb2.MemberListRequest()
member_list_response = clusterstub.MemberList(
    member_list_request,
    None,
    credentials=None,
    metadata=None
)

for member in member_list_response.members:
    print(member)
