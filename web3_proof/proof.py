"""Offline deterministic Merkle commitments for synthetic commission entries.
Not proof of payment or of source authenticity.
"""
import hashlib
import json


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def leaf(record):
    return hashlib.sha256(b'\x00' + canonical(record)).digest()


def parent(left, right):
    return hashlib.sha256(b'\x01' + left + right).digest()


def build(records):
    if not records:
        raise ValueError('records cannot be empty')
    level = [leaf(r) for r in records]
    layers = [level]
    while len(level) > 1:
        level = [parent(level[i], level[i + 1] if i + 1 < len(level) else level[i]) for i in range(0, len(level), 2)]
        layers.append(level)
    return layers


def proof(layers, index):
    if not 0 <= index < len(layers[0]):
        raise IndexError(index)
    path = []
    for level in layers[:-1]:
        other = index ^ 1
        if other >= len(level):
            other = index
        path.append({'side': 'left' if index & 1 else 'right', 'hash': level[other].hex()})
        index //= 2
    return path


def verify(record, path, root):
    value = leaf(record)
    for item in path:
        sibling = bytes.fromhex(item['hash'])
        if item['side'] == 'left':
            value = parent(sibling, value)
        elif item['side'] == 'right':
            value = parent(value, sibling)
        else:
            return False
    return value.hex() == root


if __name__ == '__main__':
    records = [
        {'order_id': 'synthetic-001', 'role': 'ORIGINAL', 'partner_id': 'A', 'amount_sen': 300},
        {'order_id': 'synthetic-001', 'role': 'SELLER', 'partner_id': 'B', 'amount_sen': 700},
        {'order_id': 'synthetic-002', 'role': 'ORIGINAL', 'partner_id': 'A', 'amount_sen': 600},
    ]
    layers = build(records)
    root = layers[-1][0].hex()
    result = {'synthetic': True, 'algorithm': 'sha256-domain-separated-duplicate-last-v1', 'root': root, 'record': records[0], 'proof': proof(layers, 0)}
    assert verify(result['record'], result['proof'], root)
    print(json.dumps(result, indent=2))
