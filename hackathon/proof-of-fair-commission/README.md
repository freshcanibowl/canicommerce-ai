# Proof of Fair Commission — CaniCommerce V0.4

A verifiable commission-split proof for the SMU Web3 for Social Good Tech Track.
Data is synthetic; no real customers, money, or mainnet deployment.

## What V0.4 verifies

- **Commission arithmetic:** 3% (Original Agent) and 7% (Selling Partner) of stated MYR eligible amount, integer sen, half-up rounding.
- **Duplicate rejection:** `(order_id, role)` must be unique within a bundle.
- **Merkle inclusion:** Every record carries a SHA-256 domain-separated Merkle proof under one root.
- **Deterministic reproducibility:** Same input records always yield the same root and proofs.
- **Smart contract anchor:** `CommissionRootAnchor.sol` (Solidity ^0.8.20) lets an authorized publisher commit a Merkle root on-chain. The contract rejects zero inputs, duplicate roots, and non-publisher callers.
- **Independent receipt verification:** `receipt_verify.py` checks a public RPC for matching `RootAnchored` event, successful receipt status, and correct chain ID.

## Run locally (Python 3.10+; standard library only)

```bash
python -m unittest discover -v        # 22 tests
python cli.py export synthetic-records.json demo-bundle.json
python cli.py verify demo-bundle.json
python anchor.py prepare demo-bundle.json offline-anchor-manifest.json
```

## Foundry tests (requires Foundry 1.8.6+, Solc 0.8.20)

```bash
forge build
forge test -vvv                       # 5 tests
```

## Sepolia anchor: deployed evidence and reproduction

A synthetic three-record root has been anchored on Ethereum Sepolia. See `anchor-manifest.json` and `deployments/evidence-sepolia.json` for recorded evidence. The commands below are for **a separate new deployment**, not a prerequisite for verifying the existing anchor:

1. `forge create contracts/CommissionRootAnchor.sol:CommissionRootAnchor --constructor-args <publisher-address>`
2. `python cli.py export synthetic-records.json demo-bundle.json`
3. `python anchor.py prepare demo-bundle.json offline-anchor-manifest.json`
4. `cast send <contract-address> "anchor(bytes32,uint256,bytes32)" <root> <count> <schema-hash>`
5. `python receipt_verify.py demo-bundle.json --rpc-url <rpc> --chain-id 11155111 --contract <addr> --tx-hash <tx> --topic0 <topic0>`

## Security and scope limitations

- No provider capture verification, refund reconciliation, 28-day settlement enforcement, partner authentication, dual approval, or payouts in this prototype.
- A bundle generated and verified by the same party is **not independently anchored**. It proves only internal inclusion and deterministic arithmetic, not payment truth, completeness of transactions, or decentralized control.
- Testnet-only deployment. Do not claim mainnet verification.
- Not integrated with the CaniCommerce private PostgreSQL repository or its CI.
- Data is explicitly synthetic; partner identifiers are invented.
- `receipt_verify.py` checks receipt status and event match but does not verify confirmation depth or reorg protection.

**Existing deployment:** contract `0x8239C47aAe2512a42aE2D196787785b0f037756f`, deployment TX `0xcad229125e19a7da9977e1b03975adabf2ce0ba061a3ca73d4d0fe254be4fd78`, anchor TX `0xdb3b9a73012e5b8acce32e03a935ae7dc74c704a715fb858ed8f10b16f2a13c0`. Offline evidence is bundled; independent public RPC verification is required for live claims.
