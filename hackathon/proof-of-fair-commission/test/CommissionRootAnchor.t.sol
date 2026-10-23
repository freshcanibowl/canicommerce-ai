// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "../contracts/CommissionRootAnchor.sol";

interface Vm {
    function prank(address) external;
}

contract CommissionRootAnchorTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address private constant PUBLISHER = address(0xBEEF);
    address private constant STRANGER = address(0xCAFE);
    bytes32 private constant ROOT = bytes32(uint256(1));
    bytes32 private constant SCHEMA = bytes32(uint256(2));

    function testPublisherAnchors() public {
        CommissionRootAnchor a = new CommissionRootAnchor(PUBLISHER);
        vm.prank(PUBLISHER);
        a.anchor(ROOT, 2, SCHEMA);
        require(a.anchored(ROOT), "root missing");
        require(a.publisher() == PUBLISHER, "publisher mismatch");
    }

    function testUnauthorizedPublisherRejected() public {
        CommissionRootAnchor a = new CommissionRootAnchor(PUBLISHER);
        vm.prank(STRANGER);
        (bool ok,) = address(a).call(abi.encodeCall(a.anchor, (ROOT, 2, SCHEMA)));
        require(!ok, "unauthorized anchor accepted");
        require(!a.anchored(ROOT), "unauthorized state changed");
    }

    function testDuplicateRootRejected() public {
        CommissionRootAnchor a = new CommissionRootAnchor(PUBLISHER);
        vm.prank(PUBLISHER);
        a.anchor(ROOT, 2, SCHEMA);
        vm.prank(PUBLISHER);
        (bool ok,) = address(a).call(abi.encodeCall(a.anchor, (ROOT, 2, SCHEMA)));
        require(!ok, "duplicate root accepted");
    }

    function testInvalidInputsRejected() public {
        CommissionRootAnchor a = new CommissionRootAnchor(PUBLISHER);
        vm.prank(PUBLISHER);
        (bool badRoot,) = address(a).call(abi.encodeCall(a.anchor, (bytes32(0), 1, SCHEMA)));
        vm.prank(PUBLISHER);
        (bool badCount,) = address(a).call(abi.encodeCall(a.anchor, (ROOT, 0, SCHEMA)));
        vm.prank(PUBLISHER);
        (bool badSchema,) = address(a).call(abi.encodeCall(a.anchor, (ROOT, 1, bytes32(0))));
        require(!badRoot && !badCount && !badSchema, "invalid input accepted");
    }

    function testZeroPublisherRejected() public {
        try new CommissionRootAnchor(address(0)) returns (CommissionRootAnchor) {
            revert("zero publisher accepted");
        } catch {}
    }
}
