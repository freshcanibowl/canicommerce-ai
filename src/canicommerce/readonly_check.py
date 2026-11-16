"""Safe CLI: PayPal Sandbox GET verification only; no money-moving actions."""
import argparse
import os
from .payment_contract import ExpectedPayment, EvidenceError
from .paypal_sandbox_readonly import verify_from_environment

def main() -> int:
    p = argparse.ArgumentParser(description="Read-only PayPal sandbox capture verification")
    p.add_argument("--order-id", required=True)
    p.add_argument("--amount-minor", type=int, required=True)
    p.add_argument("--currency", required=True)
    p.add_argument("--exponent", type=int, default=2)
    args = p.parse_args()
    try:
        expected = ExpectedPayment(
            order_id=args.order_id,
            amount_minor=args.amount_minor,
            currency=args.currency,
            merchant_id=os.environ.get("PAYPAL_MERCHANT_ID", ""),
            exponent=args.exponent,
        )
        receipt = verify_from_environment(expected)
    except EvidenceError as exc:
        print("G05_READONLY=NO_GO")
        print("REASON=" + str(exc))
        print("NO_CAPTURE_ATTEMPTED")
        return 2
    print("G05_READONLY=PASS_PROVIDER_READBACK_SANDBOX")
    print("ORDER_ID_SUFFIX=" + receipt.order_id[-4:])
    print("CAPTURE_ID_SUFFIX=" + receipt.capture_id[-4:])
    print("CURRENCY=" + receipt.currency)
    print("AMOUNT_MINOR=" + str(receipt.amount_minor))
    print("NO_CAPTURE_ATTEMPTED")
    print("NO_LEDGER_POSTED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
