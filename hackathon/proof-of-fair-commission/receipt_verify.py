"""Read-only independent verification of a *confirmed* public EVM anchor receipt.

Requires an RPC endpoint, expected chain ID, deployed contract address, tx hash,
and event signature topic0 (from `cast keccak ...`). Never signs transactions.
"""
import argparse
import json
import random
import re
import urllib.request
import urllib.error
from pathlib import Path
from anchor import prepare

H64 = re.compile(r'^0x[0-9a-fA-F]{64}$')
ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject HTTP 301/302 redirects to prevent hijacking."""

    def http_error_302(self, req, fp, code, msg, headers):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_302


_no_redirect_opener = urllib.request.build_opener(NoRedirectHandler())


def verify_receipt(bundle, receipt, chain_id, expected_chain_id, contract, tx_hash, topic0):
    expected = prepare(bundle)
    if chain_id != expected_chain_id or not ADDRESS.fullmatch(contract):
        return False
    if not H64.fullmatch(tx_hash) or not H64.fullmatch(topic0):
        return False
    if not isinstance(receipt, dict) or receipt.get('status') != '0x1':
        return False
    if receipt.get('transactionHash', '').lower() != tx_hash.lower():
        return False
    if not receipt.get('blockHash') or receipt.get('blockNumber') is None:
        return False
    expected_topics = [topic0.lower(), expected['root'].lower(),
                       '0x' + format(expected['record_count'], '064x'),
                       expected['schema_hash'].lower()]
    for log in receipt.get('logs', []):
        if log.get('address', '').lower() == contract.lower() and [str(t).lower() for t in log.get('topics', [])] == expected_topics:
            if log.get('data') in ('0x', '') and not log.get('removed', False):
                return True
    return False


def rpc(url, method, params):
    if not url.startswith('https://'):
        raise ValueError('RPC URL must use HTTPS scheme')
    request_id = random.randint(1, 2**31 - 1)
    body = json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}).encode()
    req = urllib.request.Request(url, body, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'CaniCommerce-ReceiptVerify/0.4'
    })
    with _no_redirect_opener.open(req, timeout=20) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise RuntimeError(f'RPC {method} returned non-dict response')
    if result.get('id') != request_id:
        raise RuntimeError(f'RPC response id mismatch: expected {request_id}, got {result.get("id")}')
    if result.get('jsonrpc') != '2.0':
        raise RuntimeError(f'RPC response jsonrpc version mismatch: expected 2.0, got {result.get("jsonrpc")}')
    if 'error' in result or result.get('result') is None:
        raise RuntimeError(f'RPC {method} failed or returned null: {result.get("error")}')
    return result['result']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('bundle', type=Path)
    p.add_argument('--rpc-url', required=True)
    p.add_argument('--chain-id', required=True, type=int)
    p.add_argument('--contract', required=True)
    p.add_argument('--tx-hash', required=True)
    p.add_argument('--topic0', required=True, help='cast keccak "RootAnchored(bytes32,uint256,bytes32)"')
    args = p.parse_args()
    bundle = json.loads(args.bundle.read_text())
    live_chain = int(rpc(args.rpc_url, 'eth_chainId', []), 16)
    receipt = rpc(args.rpc_url, 'eth_getTransactionReceipt', [args.tx_hash])
    ok = verify_receipt(bundle, receipt, live_chain, args.chain_id, args.contract, args.tx_hash, args.topic0)
    print('PASS: confirmed matching anchor event' if ok else 'FAIL: unverified anchor receipt')
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
