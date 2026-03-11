"""
Tests for Resurrection Hash Verifier

Verify integrity before reactivation.
"""

import json
import pytest
from dataclasses import dataclass

from resurrection_hash_verifier import (
    ResurrectionConfig,
    compute_resurrection_hash,
    verify_before_reactivation,
    chain_of_trust,
    create_checkpoint,
    quick_verify,
    Checkpoint,
    IntegrityError,
    ChainOfTrustError,
)


class TestResurrectionConfig:
    """Tests for ResurrectionConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ResurrectionConfig()
        assert config.algorithm == "sha256"
        assert config.iterations == 100000
        assert config.expected_hash is None
        assert config.trusted_sources == []
        assert len(config.salt) == 64  # 32 bytes hex = 64 chars
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ResurrectionConfig(
            salt="my-custom-salt",
            algorithm="sha512",
            expected_hash="abc123",
            trusted_sources=["source1", "source2"],
            iterations=50000
        )
        assert config.salt == "my-custom-salt"
        assert config.algorithm == "sha512"
        assert config.expected_hash == "abc123"
        assert config.trusted_sources == ["source1", "source2"]
        assert config.iterations == 50000
    
    def test_invalid_algorithm(self):
        """Test that invalid algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Invalid algorithm"):
            ResurrectionConfig(algorithm="invalid_hash")
    
    def test_invalid_iterations(self):
        """Test that invalid iterations raises ValueError."""
        with pytest.raises(ValueError, match="Iterations must be at least 1"):
            ResurrectionConfig(iterations=0)
        with pytest.raises(ValueError, match="Iterations must be at least 1"):
            ResurrectionConfig(iterations=-1)
    
    def test_empty_salt(self):
        """Test that empty salt raises ValueError."""
        with pytest.raises(ValueError, match="Salt cannot be empty"):
            ResurrectionConfig(salt="")


class TestComputeResurrectionHash:
    """Tests for compute_resurrection_hash function."""
    
    def test_hash_dict(self):
        """Test hashing a dictionary."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"key": "value", "number": 42}
        hash1 = compute_resurrection_hash(state, config)
        hash2 = compute_resurrection_hash(state, config)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars
        assert hash1 == hash2  # Deterministic
    
    def test_hash_string(self):
        """Test hashing a string."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        hash1 = compute_resurrection_hash("hello world", config)
        hash2 = compute_resurrection_hash("hello world", config)
        
        assert isinstance(hash1, str)
        assert hash1 == hash2
    
    def test_hash_bytes(self):
        """Test hashing bytes."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        hash1 = compute_resurrection_hash(b"hello world", config)
        hash2 = compute_resurrection_hash(b"hello world", config)
        
        assert isinstance(hash1, str)
        assert hash1 == hash2
    
    def test_different_states_produce_different_hashes(self):
        """Test that different states produce different hashes."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        hash1 = compute_resurrection_hash({"a": 1}, config)
        hash2 = compute_resurrection_hash({"a": 2}, config)
        
        assert hash1 != hash2
    
    def test_different_salts_produce_different_hashes(self):
        """Test that different salts produce different hashes."""
        config1 = ResurrectionConfig(salt="salt1", iterations=1000)
        config2 = ResurrectionConfig(salt="salt2", iterations=1000)
        state = {"key": "value"}
        
        hash1 = compute_resurrection_hash(state, config1)
        hash2 = compute_resurrection_hash(state, config2)
        
        assert hash1 != hash2
    
    def test_deterministic_hashing(self):
        """Test that hashing is deterministic with same inputs."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"b": 2, "a": 1}  # Order shouldn't matter with dict sorting
        
        hash1 = compute_resurrection_hash(state, config)
        hash2 = compute_resurrection_hash(state, config)
        hash3 = compute_resurrection_hash({"a": 1, "b": 2}, config)  # Different order
        
        assert hash1 == hash2 == hash3
    
    def test_hash_with_list(self):
        """Test hashing a list."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = [1, 2, 3, "four"]
        hash1 = compute_resurrection_hash(state, config)
        hash2 = compute_resurrection_hash(state, config)
        
        assert hash1 == hash2


class TestVerifyBeforeReactivation:
    """Tests for verify_before_reactivation function."""
    
    def test_valid_verification(self):
        """Test successful verification."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"key": "value"}
        expected_hash = compute_resurrection_hash(state, config)
        
        result = verify_before_reactivation(state, expected_hash, config)
        assert result is True
    
    def test_invalid_verification(self):
        """Test failed verification with wrong state."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"key": "value"}
        expected_hash = compute_resurrection_hash(state, config)
        
        tampered_state = {"key": "tampered"}
        result = verify_before_reactivation(tampered_state, expected_hash, config)
        assert result is False
    
    def test_invalid_verification_wrong_hash(self):
        """Test failed verification with wrong expected hash."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"key": "value"}
        
        wrong_hash = "a" * 64  # Wrong hash
        result = verify_before_reactivation(state, wrong_hash, config)
        assert result is False
    
    def test_empty_expected_hash(self):
        """Test that empty expected hash raises ValueError."""
        config = ResurrectionConfig(salt="test-salt")
        state = {"key": "value"}
        
        with pytest.raises(ValueError, match="Expected hash cannot be empty"):
            verify_before_reactivation(state, "", config)
    
    def test_case_insensitive_comparison(self):
        """Test that hash comparison is case insensitive."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"key": "value"}
        expected_hash = compute_resurrection_hash(state, config).upper()
        
        result = verify_before_reactivation(state, expected_hash, config)
        assert result is True


class TestCheckpoint:
    """Tests for Checkpoint class."""
    
    def test_checkpoint_creation(self):
        """Test checkpoint creation."""
        cp = Checkpoint(
            identifier="test-cp",
            state_hash="abc123",
            previous_hash="prev456",
            metadata={"version": "1.0"}
        )
        
        assert cp.identifier == "test-cp"
        assert cp.state_hash == "abc123"
        assert cp.previous_hash == "prev456"
        assert cp.metadata == {"version": "1.0"}
        assert cp.timestamp is not None
    
    def test_checkpoint_composite_hash(self):
        """Test checkpoint composite hash computation."""
        cp = Checkpoint(
            identifier="test-cp",
            state_hash="abc123",
            previous_hash="prev456"
        )
        
        hash1 = cp.compute_checkpoint_hash()
        hash2 = cp.compute_checkpoint_hash()
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64
        assert hash1 == hash2  # Deterministic
    
    def test_checkpoint_hash_changes_with_data(self):
        """Test that checkpoint hash changes with different data."""
        cp1 = Checkpoint(identifier="cp1", state_hash="hash1")
        cp2 = Checkpoint(identifier="cp2", state_hash="hash1")
        
        assert cp1.compute_checkpoint_hash() != cp2.compute_checkpoint_hash()


class TestChainOfTrust:
    """Tests for chain_of_trust function."""
    
    def test_empty_checkpoints_raises_error(self):
        """Test that empty checkpoints list raises ValueError."""
        with pytest.raises(ValueError, match="At least one checkpoint is required"):
            chain_of_trust([])
    
    def test_single_checkpoint_no_root(self):
        """Test chain with single checkpoint and no root trust."""
        cp = Checkpoint(identifier="start", state_hash="hash1")
        result = chain_of_trust([cp])
        
        assert result["valid"] is True
        assert result["broken_at"] is None
        assert result["checkpoint_count"] == 1
        assert len(result["verification_details"]) == 1
    
    def test_single_checkpoint_with_root_trust(self):
        """Test chain with single checkpoint and root trust."""
        cp = Checkpoint(identifier="start", state_hash="hash1")
        root_hash = cp.compute_checkpoint_hash()
        
        result = chain_of_trust([cp], root_trust=root_hash)
        
        assert result["valid"] is True
        assert result["broken_at"] is None
    
    def test_single_checkpoint_wrong_root_trust(self):
        """Test chain with wrong root trust fails."""
        cp = Checkpoint(identifier="start", state_hash="hash1")
        wrong_root = "a" * 64
        
        result = chain_of_trust([cp], root_trust=wrong_root)
        
        assert result["valid"] is False
        assert result["broken_at"] == 0
        assert result["verification_details"][0]["error"] == "Root trust mismatch"
    
    def test_valid_chain(self):
        """Test valid chain of checkpoints."""
        cp1 = Checkpoint(identifier="init", state_hash="hash1")
        cp2 = Checkpoint(
            identifier="step1", 
            state_hash="hash2",
            previous_hash=cp1.compute_checkpoint_hash()
        )
        cp3 = Checkpoint(
            identifier="step2",
            state_hash="hash3", 
            previous_hash=cp2.compute_checkpoint_hash()
        )
        
        result = chain_of_trust([cp1, cp2, cp3])
        
        assert result["valid"] is True
        assert result["broken_at"] is None
        assert result["checkpoint_count"] == 3
        assert all(d["verified"] for d in result["verification_details"])
    
    def test_broken_chain(self):
        """Test detection of broken chain."""
        cp1 = Checkpoint(identifier="init", state_hash="hash1")
        cp2 = Checkpoint(
            identifier="step1",
            state_hash="hash2", 
            previous_hash="wrong-hash"  # Broken link
        )
        
        result = chain_of_trust([cp1, cp2])
        
        assert result["valid"] is False
        assert result["broken_at"] == 1
        assert result["verification_details"][1]["error"] == "Chain broken - previous hash mismatch"
    
    def test_chain_with_missing_previous_hash(self):
        """Test detection of missing previous hash."""
        cp1 = Checkpoint(identifier="init", state_hash="hash1")
        cp2 = Checkpoint(identifier="step1", state_hash="hash2", previous_hash=None)
        
        result = chain_of_trust([cp1, cp2])
        
        assert result["valid"] is False
        assert result["broken_at"] == 1
        assert result["verification_details"][1]["error"] == "Missing previous hash"
    
    def test_chain_hash_is_deterministic(self):
        """Test that chain hash is deterministic."""
        cp1 = Checkpoint(identifier="init", state_hash="hash1")
        cp2 = Checkpoint(
            identifier="step1",
            state_hash="hash2",
            previous_hash=cp1.compute_checkpoint_hash()
        )
        
        result1 = chain_of_trust([cp1, cp2])
        result2 = chain_of_trust([cp1, cp2])
        
        assert result1["chain_hash"] == result2["chain_hash"]


class TestCreateCheckpoint:
    """Tests for create_checkpoint helper function."""
    
    def test_create_first_checkpoint(self):
        """Test creating first checkpoint without previous."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        state = {"step": 1}
        
        cp = create_checkpoint("first", state, config=config)
        
        assert cp.identifier == "first"
        assert cp.previous_hash is None
        assert cp.state_hash is not None
    
    def test_create_chained_checkpoint(self):
        """Test creating checkpoint chained to previous."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        
        cp1 = create_checkpoint("first", {"step": 1}, config=config)
        cp2 = create_checkpoint("second", {"step": 2}, previous_checkpoint=cp1, config=config)
        
        assert cp2.previous_hash == cp1.compute_checkpoint_hash()
        assert cp2.identifier == "second"
    
    def test_create_checkpoint_with_metadata(self):
        """Test creating checkpoint with metadata."""
        config = ResurrectionConfig(salt="test-salt", iterations=1000)
        metadata = {"version": "1.0", "author": "test"}
        
        cp = create_checkpoint("first", {"step": 1}, config=config, metadata=metadata)
        
        assert cp.metadata == metadata


class TestQuickVerify:
    """Tests for quick_verify helper function."""
    
    def test_quick_verify_success(self):
        """Test successful quick verification."""
        state = {"key": "value"}
        salt = "test-salt"
        
        # Compute expected hash using config
        config = ResurrectionConfig(salt=salt, iterations=100000)
        expected_hash = compute_resurrection_hash(state, config)
        
        result = quick_verify(state, expected_hash, salt=salt)
        assert result is True
    
    def test_quick_verify_failure(self):
        """Test failed quick verification."""
        state = {"key": "value"}
        
        result = quick_verify(state, "wrong-hash", salt="test-salt")
        assert result is False


class TestIntegration:
    """Integration tests for the complete workflow."""
    
    def test_full_resurrection_workflow(self):
        """Test complete resurrection workflow."""
        # Setup
        config = ResurrectionConfig(salt="secure-salt-for-production")
        
        # Initial state
        initial_state = {
            "memory": {"user": "Alice", "session_id": "sess-123"},
            "config": {"theme": "dark"},
            "timestamp": 1234567890
        }
        
        # Step 1: Before suspension, compute hash
        suspension_hash = compute_resurrection_hash(initial_state, config)
        
        # Step 2: Create checkpoint
        checkpoint = create_checkpoint(
            "pre-suspension",
            initial_state,
            config=config,
            metadata={"reason": "scheduled_maintenance"}
        )
        
        # Step 3: Simulate state restoration (assume same state)
        restored_state = initial_state.copy()
        
        # Step 4: Verify before reactivation
        is_valid = verify_before_reactivation(restored_state, suspension_hash, config)
        assert is_valid is True
        
        # Step 5: Verify checkpoint chain
        chain_result = chain_of_trust([checkpoint])
        assert chain_result["valid"] is True
    
    def test_tampered_state_detection(self):
        """Test that tampered state is detected."""
        config = ResurrectionConfig(salt="secure-salt")
        
        original_state = {"data": "sensitive", "checksum": "abc"}
        expected_hash = compute_resurrection_hash(original_state, config)
        
        # Tamper with state
        tampered_state = {"data": "tampered", "checksum": "abc"}
        
        result = verify_before_reactivation(tampered_state, expected_hash, config)
        assert result is False
    
    def test_multi_checkpoint_chain(self):
        """Test multi-checkpoint chain of trust."""
        config = ResurrectionConfig(salt="secure-salt", iterations=1000)
        
        # Create chain of 5 checkpoints
        state1 = {"step": 1}
        cp1 = create_checkpoint("cp1", state1, config=config)
        
        state2 = {"step": 2}
        cp2 = create_checkpoint("cp2", state2, previous_checkpoint=cp1, config=config)
        
        state3 = {"step": 3}
        cp3 = create_checkpoint("cp3", state3, previous_checkpoint=cp2, config=config)
        
        state4 = {"step": 4}
        cp4 = create_checkpoint("cp4", state4, previous_checkpoint=cp3, config=config)
        
        state5 = {"step": 5}
        cp5 = create_checkpoint("cp5", state5, previous_checkpoint=cp4, config=config)
        
        # Verify entire chain
        result = chain_of_trust([cp1, cp2, cp3, cp4, cp5])
        assert result["valid"] is True
        assert result["checkpoint_count"] == 5
        assert all(d["verified"] for d in result["verification_details"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
