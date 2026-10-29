# CaniCommerce V0.4.2 release audit (2026-10-24)

- ZIP unpacked and Python unittest discover: 22/22 PASS.
- Rebuilt demo bundle root, record count and schema hash match anchor-manifest.json.
- Bundled anchor receipt passes receipt_verify.verify_receipt with bundled topic0, address and chain ID.
- RPC live verification not performed in this environment.
- Foundry not installed here; Solidity tests not rerun.
- `anchor.py prepare` emits an OFFLINE NOT_DEPLOYED manifest by design. Patched to refuse overwriting an existing DEPLOYED manifest.
- README now distinguishes recorded Sepolia deployment from reproduction commands; BUILD-V0.4 marked historical.
- Secret scanning of Git history cannot occur before repository access.
- GitHub push and DoraHacks submission not performed.
