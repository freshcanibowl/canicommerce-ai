> Historical pre-deployment runbook. The original steps below describe the state before Sepolia deployment. For the recorded deployment, see `anchor-manifest.json` and `deployments/evidence-sepolia.json`. Do not overwrite the deployed manifest when preparing an offline example.

# Build V0.4 — independent verification and Solidity test gate

## What is verified
- 22 Python unit tests locally: synthetic commission, SHA-256 Merkle proof, offline manifest and mocked JSON-RPC receipt matching.
- 5 Solidity Foundry tests **authored but not executed** in this environment (no forge/solc installed).
- No public RPC accessed, no contract deployed, no transaction signed, no GitHub push.

## Windows / Foundry validation
From project root:
```powershell
python -m unittest discover -v
forge build
forge test -vvv
```

## Testnet-only deployment (after Foundry tests pass)
Use a **disposable funded testnet wallet**. Never paste a private key into chat, a shell command or the repository. Configure a local Foundry keystore and use `--account` (Foundry's keystore account); check your installed Foundry version's syntax. Example for Sepolia:
```powershell
$env:ETH_RPC_URL = '<trusted Sepolia HTTPS RPC URL>'
cast chain-id --rpc-url $env:ETH_RPC_URL  # must be 11155111
forge create contracts/CommissionRootAnchor.sol:CommissionRootAnchor --rpc-url $env:ETH_RPC_URL --account <local-keystore-account> --broadcast --constructor-args <publisher-wallet-address>
```
Record the actual deployed contract address, deployment transaction hash and chain ID. Then prepare an anchor input:
```powershell
python cli.py export synthetic-records.json demo-bundle.json
python anchor.py prepare demo-bundle.json anchor-manifest.json
```
Call `anchor(bytes32,uint256,bytes32)` **only from the configured publisher** using `cast send` with the three exact manifest fields, `--rpc-url`, and `--account` (or a hardware wallet). Obtain actual anchor tx hash.

## Independent public receipt verification
```powershell
$topic = cast keccak 'RootAnchored(bytes32,uint256,bytes32)'
python receipt_verify.py demo-bundle.json --rpc-url $env:ETH_RPC_URL --chain-id 11155111 --contract <deployed-contract-address> --tx-hash <anchor-transaction-hash> --topic0 $topic
cast call <deployed-contract-address> 'anchored(bytes32)(bool)' <manifest-root> --rpc-url $env:ETH_RPC_URL
```
**Both** receipt verification and `anchored(root) == true` are required before claiming a public chain checkpoint. The receipt verifier checks matching event, successful receipt and chain ID but does not itself query the contract storage, confirm canonical finality, verify the deployed bytecode, or establish authenticity of underlying sales. Use trusted RPC or independent explorer and record block confirmations.

## Security and IP
Synthetic only. Existing EvidenceKit code is **not** imported; this is a standalone proof concept, not a completed EvidenceKit code integration. No CaniPay, no settlement, no real funds. Do not merge to main or modify production.
