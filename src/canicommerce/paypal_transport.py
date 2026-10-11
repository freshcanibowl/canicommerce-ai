"""PayPal Sandbox HTTPS transport. No production PayPal endpoints.

Use only server-side credentials. Never log access tokens, secrets, or full
payment payloads. Network operations occur only when methods are called.
"""
import base64
import json
import os
import ssl
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from canicommerce.payment_boundary import PaymentVerificationError
from canicommerce.paypal_sandbox import PayPalSandboxAdapter

BASE = "https://api-m.sandbox.paypal.com"
MAX_RESPONSE_BYTES = 262144

class PayPalTransportError(PaymentVerificationError):
    pass

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PayPalTransportError("PayPal redirects forbidden")


def _secure_opener(request, *, timeout):
    # Never follow redirects: OAuth headers must not leak to another origin.
    return build_opener(_NoRedirect, HTTPSHandler(context=ssl.create_default_context())).open(request, timeout=timeout)


class PayPalSandboxTransport:
    def __init__(self, *, client_id: str, client_secret: str, timeout: float = 10,
                 opener=None):
        if not client_id or not client_secret:
            raise PayPalTransportError("server-side sandbox credentials required")
        if not 0 < timeout <= 30:
            raise PayPalTransportError("invalid timeout")
        self._client_id=client_id
        self._client_secret=client_secret
        self._timeout=timeout
        self._opener=opener or _secure_opener

    def _request(self, url: str, *, method: str, body: bytes = None, token: str = None,
                 content_type: str = "application/json"):
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.netloc!="api-m.sandbox.paypal.com" or parsed.username or parsed.password or parsed.fragment:
            raise PayPalTransportError("non-sandbox PayPal endpoint rejected")
        headers={"Accept":"application/json","Content-Type":content_type}
        if token:
            headers["Authorization"]="Bearer "+token
        request=Request(url,data=body,headers=headers,method=method)
        try:
            response=self._opener(request,timeout=self._timeout)
            with response:
                raw=response.read(MAX_RESPONSE_BYTES+1)
                if len(raw)>MAX_RESPONSE_BYTES:
                    raise PayPalTransportError("oversized PayPal response")
                if not 200<=response.status<300:
                    raise PayPalTransportError("PayPal API rejected request")
                return json.loads(raw)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
            raise PayPalTransportError("PayPal Sandbox transport failed") from exc

    def get_access_token(self):
        basic=base64.b64encode((self._client_id+":"+self._client_secret).encode()).decode()
        # OAuth Basic credentials never go through request logs.
        url=BASE+"/v1/oauth2/token"
        request=Request(url,data=urlencode({"grant_type":"client_credentials"}).encode(),
                        headers={"Authorization":"Basic "+basic,
                                 "Accept":"application/json",
                                 "Content-Type":"application/x-www-form-urlencoded"},
                        method="POST")
        try:
            with self._opener(request,timeout=self._timeout) as response:
                raw=response.read(MAX_RESPONSE_BYTES+1)
                if len(raw)>MAX_RESPONSE_BYTES or not 200<=response.status<300:
                    raise PayPalTransportError("PayPal OAuth rejected request")
                result=json.loads(raw)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
            raise PayPalTransportError("PayPal OAuth transport failed") from exc
        token=result.get("access_token") if isinstance(result,dict) else None
        if not isinstance(token,str) or not token:
            raise PayPalTransportError("PayPal OAuth token missing")
        return token

    def post_json(self,url,payload,token):
        return self._request(url,method="POST",body=json.dumps(payload).encode(),token=token)

    def get_json(self,url,token):
        return self._request(url,method="GET",token=token)

def adapter_from_environment(*, opener=None):
    """Explicit opt-in constructor. Never initialize on module import."""
    webhook_id=os.environ.get("PAYPAL_SANDBOX_WEBHOOK_ID")
    if not webhook_id:
        raise PayPalTransportError("PAYPAL_SANDBOX_WEBHOOK_ID required")
    transport=PayPalSandboxTransport(
        client_id=os.environ.get("PAYPAL_SANDBOX_CLIENT_ID",""),
        client_secret=os.environ.get("PAYPAL_SANDBOX_CLIENT_SECRET",""),
        opener=opener)
    return PayPalSandboxAdapter(
        webhook_id=webhook_id,get_access_token=transport.get_access_token,
        post_json=transport.post_json,get_json=transport.get_json)
