import json
import pytest
from urllib.error import URLError
from canicommerce.paypal_transport import PayPalSandboxTransport,PayPalTransportError,adapter_from_environment

class Response:
    status=200
    def __init__(self,data): self.data=json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.data[:size]

def test_oauth_and_api_transport_without_network():
    calls=[]
    def opener(req,timeout):
        calls.append((req.full_url,req.get_method(),dict(req.header_items())))
        if req.full_url.endswith("/v1/oauth2/token"):
            return Response({"access_token":"sandbox-test-token"})
        return Response({"verification_status":"SUCCESS"})
    transport=PayPalSandboxTransport(client_id="id",client_secret="secret",opener=opener)
    token=transport.get_access_token()
    assert token=="sandbox-test-token"
    result=transport.post_json("https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature",{"webhook_event":{}},token)
    assert result["verification_status"]=="SUCCESS"
    assert len(calls)==2
    assert all(url.startswith("https://api-m.sandbox.paypal.com/") for url,_,_ in calls)

@pytest.mark.parametrize("url",[
    "https://api-m.paypal.com/v2/payments/captures/CAP",
    "http://api-m.sandbox.paypal.com/v2/payments/captures/CAP",
    "https://api-m.sandbox.paypal.com.evil.test/v2/payments/captures/CAP",
    "https://evil.test@api-m.sandbox.paypal.com/v2/payments/captures/CAP"
])
def test_reject_non_sandbox_urls(url):
    transport=PayPalSandboxTransport(client_id="id",client_secret="secret",
                                     opener=lambda *a,**kw:pytest.fail("network attempted"))
    with pytest.raises(PayPalTransportError):
        transport.get_json(url,"token")

def test_network_error_is_fail_closed():
    def opener(*args,**kwargs): raise URLError("offline")
    transport=PayPalSandboxTransport(client_id="id",client_secret="secret",opener=opener)
    with pytest.raises(PayPalTransportError,match="transport failed"):
        transport.get_access_token()

def test_missing_environment_does_not_open_network(monkeypatch):
    for key in ("PAYPAL_SANDBOX_WEBHOOK_ID","PAYPAL_SANDBOX_CLIENT_ID","PAYPAL_SANDBOX_CLIENT_SECRET"):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(PayPalTransportError):
        adapter_from_environment(opener=lambda *a,**kw:pytest.fail("network attempted"))
