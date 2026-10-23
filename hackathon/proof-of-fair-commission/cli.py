"""Offline CLI for synthetic fair-commission proof; no payments or blockchain."""
import argparse
import copy
import json
import sys
from pathlib import Path
from proof import build, proof, verify


def exact_commission(eligible_sen, percent):
    if type(eligible_sen) is not int or eligible_sen < 0:
        raise ValueError('eligible_sen must be a nonnegative integer')
    return (eligible_sen * percent + 50) // 100  # half-up for integer sen


def validate_records(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('nonempty records list required')
    keys = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('record must be an object')
        if row.get('role') not in ('ORIGINAL', 'SELLER'):
            raise ValueError('invalid role')
        if not isinstance(row.get('order_id'), str) or not row['order_id']:
            raise ValueError('order_id required')
        if not isinstance(row.get('partner_id'), str) or not row['partner_id']:
            raise ValueError('partner_id required')
        if row.get('currency') != 'MYR':
            raise ValueError('only MYR synthetic demonstration supported')
        if type(row.get('amount_sen')) is not int:
            raise ValueError('amount_sen must be integer')
        expected = exact_commission(row.get('eligible_sen'), 3 if row['role'] == 'ORIGINAL' else 7)
        if row['amount_sen'] != expected:
            raise ValueError('commission does not match stated eligible amount')
        key = (row['order_id'], row['role'])
        if key in keys:
            raise ValueError('duplicate commission role for order')
        keys.add(key)


def export_bundle(rows):
    validate_records(rows)
    # Stable ordering and duplicate role rejection before hashing
    rows = sorted(copy.deepcopy(rows), key=lambda r: (r['order_id'], r['role']))
    tree = build(rows)
    root = tree[-1][0].hex()
    return {
        'schema': 'proof-of-fair-commission/v0.2',
        'synthetic': True,
        'algorithm': 'sha256-domain-separated-duplicate-last-v1',
        'root': root,
        'leaf_count': len(rows),
        'proofs': [{'record': row, 'path': proof(tree, i)} for i, row in enumerate(rows)],
        'limitations': 'Proves inclusion in this bundle only; not payment, completeness, authenticity, or blockchain anchoring.'
    }


def verify_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get('schema') != 'proof-of-fair-commission/v0.2':
        return False
    if bundle.get('synthetic') is not True or bundle.get('algorithm') != 'sha256-domain-separated-duplicate-last-v1':
        return False
    entries = bundle.get('proofs')
    if not isinstance(entries, list) or type(bundle.get('leaf_count')) is not int or len(entries) != bundle['leaf_count'] or not entries:
        return False
    try:
        rows = [item['record'] for item in entries]
        validate_records(rows)
        if rows != sorted(rows, key=lambda r: (r['order_id'], r['role'])):
            return False
        rebuilt = build(rows)[-1][0].hex()
        if rebuilt != bundle['root']:
            return False
        return all(verify(item['record'], item['path'], bundle['root']) for item in entries)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description='Offline synthetic commission proof CLI')
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('records', type=Path)
    exp.add_argument('output', type=Path)
    check = sub.add_parser('verify')
    check.add_argument('bundle', type=Path)
    args = parser.parse_args()
    if args.command == 'export':
        rows = json.loads(args.records.read_text(encoding='utf-8'))
        args.output.write_text(json.dumps(export_bundle(rows), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print('SYNTHETIC PROOF EXPORTED:', args.output)
    else:
        bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
        ok = verify_bundle(bundle)
        print('PASS: proof and commission checks' if ok else 'FAIL: invalid proof or commission')
        if not ok:
            sys.exit(1)


if __name__ == '__main__':
    main()
