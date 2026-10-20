import pytest
from canicommerce.paypal_transport import PayPalSandboxTransport,PayPalTransportError

class Response:
    status=200
    def __init__(self,payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.payload[:size]

@pytest.mark.parametrize("payload",[b"[]",b"null",b"42",b'"string"',b"not-json"])
def test_api_rejects_invalid_response_shape(payload):
    transport=PayPalSandboxTransport(client_id="id",client_secret="secret",
        opener=lambda req,timeout:Response(payload))
    with pytest.raises(PayPalTransportError):
        transport.get_json("https://api-m.sandbox.paypal.com/v2/payments/captures/CAP","token")

@pytest.mark.parametrize("payload",[b"[]",b"null",b"42",b'"string"',b"not-json",b'{}'])
def test_oauth_rejects_invalid_response_shape(payload):
    transport=PayPalSandboxTransport(client_id="id",client_secret="secret",
        opener=lambda req,timeout:Response(payload))
    with pytest.raises(PayPalTransportError):
        transport.get_access_token()
