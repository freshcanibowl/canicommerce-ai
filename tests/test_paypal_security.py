import pytest
from canicommerce.paypal_transport import _NoRedirect,PayPalTransportError
from canicommerce.payment_boundary import PaymentVerificationError
from test_paypal_sandbox import adapter,run,HEADERS

def test_redirects_are_forbidden():
    handler=_NoRedirect()
    with pytest.raises(PayPalTransportError,match="redirects forbidden"):
        handler.redirect_request(None,None,302,"Moved",{},"https://attacker.example/")

@pytest.mark.parametrize("url",[
    "https://user:pass@api-m.sandbox.paypal.com/cert",
    "https://api-m.sandbox.paypal.com:8443/cert",
    "https://api-m.sandbox.paypal.com/cert#fragment",
    "https://api-m.sandbox.paypal.com.attacker.test/cert",
])
def test_reject_unsafe_certificate_urls(url):
    with pytest.raises(PaymentVerificationError):
        run(adapter(),headers={**HEADERS,"PAYPAL-CERT-URL":url})
