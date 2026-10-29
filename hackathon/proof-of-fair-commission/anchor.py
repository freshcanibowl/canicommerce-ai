"""Prepare and independently check testnet anchor manifests. No chain writes."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from cli import verify_bundle

SCHEMA = 'proof-of-fair-commission/v0.2'
SCHEMA_HASH = hashlib.sha256(SCHEMA.encode('utf-8')).hexdigest()
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def prepare(bundle):
    if not verify_bundle(bundle):
        raise ValueError('invalid proof bundle')
    root = bundle['root']
    if not isinstance(root, str) or not HEX64.fullmatch(root):
        raise ValueError('invalid root')
    return {'schema': 'commission-root-anchor/v0.3', 'synthetic': True,
            'chain_status': 'NOT_DEPLOYED', 'root': '0x' + root,
            'record_count': bundle['leaf_count'], 'schema_hash': '0x' + SCHEMA_HASH,
            'contract_function': 'anchor(bytes32,uint256,bytes32)',
            'limitations': 'Deployment, confirmation and chain inclusion have not been verified.'}


def check_manifest(bundle, manifest):
    try:
        expected = prepare(bundle)
        return manifest == expected
    except (ValueError, TypeError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('bundle', type=Path)
    prep.add_argument('output', type=Path)
    check = sub.add_parser('check')
    check.add_argument('bundle', type=Path)
    check.add_argument('manifest', type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
    if args.command == 'prepare':
        manifest = prepare(bundle)
        if args.output.exists():
            existing = json.loads(args.output.read_text(encoding='utf-8'))
            if existing.get('chain_status') == 'DEPLOYED':
                raise SystemExit('Refusing to overwrite deployed anchor manifest; choose a new offline output path')
        args.output.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print('Prepared OFFLINE anchor manifest; NOT deployed:', args.output)
    else:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        ok = check_manifest(bundle, manifest)
        print('PASS: offline anchor manifest matches bundle' if ok else 'FAIL: mismatch')
        if not ok:
            raise SystemExit(1)

if __name__ == '__main__':
    main()
