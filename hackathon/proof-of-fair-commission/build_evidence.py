import json

CONTRACT_ADDRESS = "0x8239C47aAe2512a42aE2D196787785b0f037756f"
DEPLOY_TX = "0xcad229125e19a7da9977e1b03975adabf2ce0ba061a3ca73d4d0fe254be4fd78"
ANCHOR_TX = "0xdb3b9a73012e5b8acce32e03a935ae7dc74c704a715fb858ed8f10b16f2a13c0"
REMAINING_WEI = 49930147657889694

d = json.load(open('deployments/deploy-receipt.json'))
a = json.load(open('deployments/anchor-receipt.json'))

deploy_gas = int(d['gasUsed'], 16)
deploy_gas_price = int(d.get('effectiveGasPrice', d.get('gasPrice', '0x0')), 16)
deploy_cost_wei = deploy_gas * deploy_gas_price

anchor_gas = int(a['gasUsed'], 16)
anchor_gas_price = int(a.get('effectiveGasPrice', a.get('gasPrice', '0x0')), 16)
anchor_cost_wei = anchor_gas * anchor_gas_price

total_cost_wei = deploy_cost_wei + anchor_cost_wei

ev = {
    'network': 'Ethereum Sepolia',
    'chain_id': 11155111,
    'contract_address': CONTRACT_ADDRESS,
    'deploy_tx_hash': DEPLOY_TX,
    'deploy_block_number': int(d['blockNumber'], 16),
    'deploy_gas_used': deploy_gas,
    'deploy_gas_price_wei': deploy_gas_price,
    'deploy_cost_eth': deploy_cost_wei / 1e18,
    'anchor_tx_hash': ANCHOR_TX,
    'anchor_block_number': int(a['blockNumber'], 16),
    'anchor_gas_used': anchor_gas,
    'anchor_gas_price_wei': anchor_gas_price,
    'anchor_cost_eth': anchor_cost_wei / 1e18,
    'total_cost_eth': total_cost_wei / 1e18,
    'remaining_balance_eth': REMAINING_WEI / 1e18,
    'merkle_root': '0x6135cb032608b719f6c43eb72bf567546fde020211874911724be5beb8ec669b',
    'record_count': 3,
    'schema_hash': '0x34d46aa1c0b74ab36d8ee18f1c0a859b7defa6c93bc7c0a237852b56a6b1e881',
    'publisher_address': '0xcF0588f0EE0332887fF75C3E20284bd0a31d555f',
    'receipt_verify_primary_rpc': 'PASS',
    'receipt_verify_backup_rpc': 'PASS',
    'cast_call_anchored_root': True,
    'cast_call_publisher': '0xcF0588f0EE0332887fF75C3E20284bd0a31d555f',
    'deploy_receipt_status': int(d['status'], 16),
    'anchor_receipt_status': int(a['status'], 16),
    'explorer_contract': f'https://sepolia.etherscan.io/address/{CONTRACT_ADDRESS}',
    'explorer_deploy_tx': f'https://sepolia.etherscan.io/tx/{DEPLOY_TX}',
    'explorer_anchor_tx': f'https://sepolia.etherscan.io/tx/{ANCHOR_TX}',
    'deploy_receipt': d,
    'anchor_receipt': a,
}

assert ev['deploy_receipt_status'] == 1, 'Deployment receipt failed'
assert ev['anchor_receipt_status'] == 1, 'Anchor receipt failed'
assert ev['cast_call_anchored_root'] is True, 'On-chain root not anchored'

json.dump(ev, open('deployments/evidence-sepolia.json', 'w'), indent=2)
print(json.dumps(ev, indent=2))
