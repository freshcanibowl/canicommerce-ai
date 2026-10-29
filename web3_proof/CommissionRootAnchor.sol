// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Commitments only. No personal data, tokens, transfers or payment claims.
contract CommissionRootAnchor {
    address public immutable publisher;
    mapping(bytes32 => bool) public anchored;
    event RootAnchored(bytes32 indexed root, uint256 indexed recordCount, bytes32 indexed schemaHash);
    error NotPublisher();
    error InvalidCommitment();
    error AlreadyAnchored();

    constructor(address authorizedPublisher) {
        if (authorizedPublisher == address(0)) revert InvalidCommitment();
        publisher = authorizedPublisher;
    }

    function anchor(bytes32 root, uint256 recordCount, bytes32 schemaHash) external {
        if (msg.sender != publisher) revert NotPublisher();
        if (root == bytes32(0) || recordCount == 0 || schemaHash == bytes32(0)) revert InvalidCommitment();
        if (anchored[root]) revert AlreadyAnchored();
        anchored[root] = true;
        emit RootAnchored(root, recordCount, schemaHash);
    }
}
