# Proof of Fair Commission — Build V0.3

Synthetic, offline, testnet-ready demonstration. No mainnet, payments, or actual chain deployment.

## Run (Windows PowerShell)

```powershell
python -m unittest discover -v
python cli.py export synthetic-records.json demo-bundle.json
python cli.py verify demo-bundle.json
python anchor.py prepare demo-bundle.json anchor-manifest.json
python anchor.py check demo-bundle.json anchor-manifest.json
```

## Smart contract

`contracts/CommissionRootAnchor.sol` has one immutable publisher; rejects zero values, unauthorized publishers and duplicate roots. It emits a public event, but **does not prove the original data was accurate or that commissions were paid**. Deploy only to an isolated public testnet with a disposable test account after compiling/testing the Solidity code in a suitable EVM toolchain. Solidity compilation and on-chain testing have NOT been run in this package.

## Proof format

SHA-256 domain-separated leaves and internal nodes; JSON canonicalization defined in `proof.py`. Do not publish real customer names, contact details, or identifiers in publicly distributed proof bundles. The manifest is a **deployment input**, not evidence of deployment. An external party must independently confirm the chain ID, contract address, transaction receipt, event, and on-chain `anchored(root)` state before claiming chain verification.

## IP and safety

Standalone synthetic demonstration; no CaniPay integration, production access, settlement, token, or payout. Existing EvidenceKit code has not been imported. This implementation is a standalone prototype inspired by the EvidenceKit proof-layer concept, not an assertion of code-level integration.
