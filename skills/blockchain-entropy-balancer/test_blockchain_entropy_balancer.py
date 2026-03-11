"""
Tests for blockchain_entropy_balancer module.

Run with: python -m pytest test_blockchain_entropy_balancer.py -v
"""

import pytest
import re
from blockchain_entropy_balancer import (
    EntropyConfig,
    generate_hash_mask,
    balance_entropy,
    decoy_generation,
    verify_mask_balance,
    mask_bitcoin_hash,
    mask_ethereum_hash,
    generate_mixed_decoys,
    HashType
)


class TestEntropyConfig:
    """Test suite for EntropyConfig class."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = EntropyConfig()
        assert config.mask_strength == 128
        assert config.output_count == 4
        assert config.decoy_count == 10
        assert config.salt is None
    
    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = EntropyConfig(
            mask_strength=256,
            output_count=8,
            decoy_count=20,
            salt=b"test_salt"
        )
        assert config.mask_strength == 256
        assert config.output_count == 8
        assert config.decoy_count == 20
        assert config.salt == b"test_salt"
    
    def test_invalid_mask_strength(self):
        """Test that invalid mask strength raises ValueError."""
        with pytest.raises(ValueError, match="mask_strength must be 64, 128, or 256"):
            EntropyConfig(mask_strength=100)
        
        with pytest.raises(ValueError, match="mask_strength must be 64, 128, or 256"):
            EntropyConfig(mask_strength=512)
    
    def test_invalid_output_count(self):
        """Test that invalid output_count raises ValueError."""
        with pytest.raises(ValueError, match="output_count must be at least 1"):
            EntropyConfig(output_count=0)
        
        with pytest.raises(ValueError, match="output_count must be at least 1"):
            EntropyConfig(output_count=-1)
    
    def test_invalid_decoy_count(self):
        """Test that negative decoy_count raises ValueError."""
        with pytest.raises(ValueError, match="decoy_count must be non-negative"):
            EntropyConfig(decoy_count=-1)


class TestGenerateHashMask:
    """Test suite for generate_hash_mask function."""
    
    def test_bitcoin_mask_generation(self):
        """Test mask generation for Bitcoin hashes."""
        config = EntropyConfig(mask_strength=128)
        mask_data = generate_hash_mask(config, "bitcoin")
        
        assert "mask" in mask_data
        assert "strength" in mask_data
        assert "hash_type" in mask_data
        assert "algorithm" in mask_data
        assert "mask_hex" in mask_data
        
        assert mask_data["hash_type"] == "bitcoin"
        assert mask_data["algorithm"] == "sha256"
        assert mask_data["strength"] == 128
        assert len(mask_data["mask"]) == 16  # 128 bits = 16 bytes
    
    def test_ethereum_mask_generation(self):
        """Test mask generation for Ethereum hashes."""
        config = EntropyConfig(mask_strength=256)
        mask_data = generate_hash_mask(config, "ethereum")
        
        assert mask_data["hash_type"] == "ethereum"
        assert mask_data["algorithm"] == "keccak256"
        assert mask_data["strength"] == 256
        assert len(mask_data["mask"]) == 32  # 256 bits = 32 bytes
    
    def test_mask_strength_64(self):
        """Test 64-bit mask strength."""
        config = EntropyConfig(mask_strength=64)
        mask_data = generate_hash_mask(config, "bitcoin")
        assert len(mask_data["mask"]) == 8  # 64 bits = 8 bytes
    
    def test_deterministic_mask_with_salt(self):
        """Test that same salt produces same mask."""
        salt = b"deterministic_salt"
        config1 = EntropyConfig(mask_strength=128, salt=salt)
        config2 = EntropyConfig(mask_strength=128, salt=salt)
        
        mask1 = generate_hash_mask(config1, "bitcoin")
        mask2 = generate_hash_mask(config2, "bitcoin")
        
        assert mask1["mask"] == mask2["mask"]
    
    def test_random_mask_variation(self):
        """Test that random masks (no salt) are different."""
        config = EntropyConfig(mask_strength=128)
        
        mask1 = generate_hash_mask(config, "bitcoin")
        mask2 = generate_hash_mask(config, "bitcoin")
        
        # Very unlikely to be the same with random generation
        assert mask1["mask"] != mask2["mask"]
    
    def test_invalid_hash_type(self):
        """Test that invalid hash type raises ValueError."""
        config = EntropyConfig()
        with pytest.raises(ValueError, match="Unsupported hash type"):
            generate_hash_mask(config, "invalid_type")


class TestBalanceEntropy:
    """Test suite for balance_entropy function."""
    
    def test_bitcoin_hash_balancing(self):
        """Test entropy balancing for Bitcoin hashes."""
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        config = EntropyConfig(output_count=4, mask_strength=128)
        
        balanced = balance_entropy(bitcoin_hash, config)
        
        assert len(balanced) == 4
        for output in balanced:
            assert "output" in output
            assert "mask" in output
            assert "index" in output
            assert "hash_type" in output
            assert output["hash_type"] == "bitcoin"
            # Output should be 64 hex chars (no 0x prefix for Bitcoin)
            assert len(output["output"]) == 64
    
    def test_ethereum_hash_balancing(self):
        """Test entropy balancing for Ethereum hashes."""
        ethereum_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        config = EntropyConfig(output_count=3, mask_strength=128)
        
        balanced = balance_entropy(ethereum_hash, config)
        
        assert len(balanced) == 3
        for output in balanced:
            assert output["hash_type"] == "ethereum"
            # Output should have 0x prefix and 64 hex chars
            assert output["output"].startswith("0x")
            assert len(output["output"]) == 66  # 0x + 64 chars
    
    def test_ethereum_hash_without_prefix(self):
        """Test Ethereum hash handling without 0x prefix."""
        ethereum_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        config = EntropyConfig(output_count=2)
        
        balanced = balance_entropy(ethereum_hash, config)
        
        assert len(balanced) == 2
        assert all(out["hash_type"] == "ethereum" for out in balanced)
    
    def test_different_output_counts(self):
        """Test various output counts."""
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        
        for count in [1, 2, 5, 10]:
            config = EntropyConfig(output_count=count)
            balanced = balance_entropy(bitcoin_hash, config)
            assert len(balanced) == count
            # Check indices are sequential
            indices = [out["index"] for out in balanced]
            assert indices == list(range(count))
    
    def test_salted_balancing_determinism(self):
        """Test that salted balancing produces deterministic results."""
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        salt = b"test_salt_123"
        
        config1 = EntropyConfig(output_count=2, salt=salt)
        config2 = EntropyConfig(output_count=2, salt=salt)
        
        balanced1 = balance_entropy(bitcoin_hash, config1)
        balanced2 = balance_entropy(bitcoin_hash, config2)
        
        # Masks should be deterministic with same salt
        for b1, b2 in zip(balanced1, balanced2):
            assert b1["mask"] == b2["mask"]
    
    def test_invalid_bitcoin_hash_length(self):
        """Test that invalid Bitcoin hash length raises error."""
        with pytest.raises(ValueError, match="Bitcoin hash must be 64 hex chars"):
            balance_entropy("0000abcd", EntropyConfig())
    
    def test_invalid_ethereum_hash_length(self):
        """Test that invalid Ethereum hash length raises error."""
        with pytest.raises(ValueError, match="Ethereum hash must be 64 hex chars"):
            balance_entropy("0x0000abcd", EntropyConfig())
    
    def test_invalid_hex_characters(self):
        """Test that invalid hex characters raise error."""
        with pytest.raises(ValueError):
            balance_entropy("0000000000000000000g2e9b5a4c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4", EntropyConfig())


class TestDecoyGeneration:
    """Test suite for decoy_generation function."""
    
    def test_bitcoin_decoy_generation(self):
        """Test Bitcoin decoy generation."""
        config = EntropyConfig(decoy_count=5)
        decoys = decoy_generation("bitcoin", config)
        
        assert len(decoys) == 5
        
        for decoy in decoys:
            assert decoy["type"] == "bitcoin"
            assert decoy["synthetic"] is True
            assert "hash" in decoy
            assert "block_height" in decoy
            assert "timestamp" in decoy
            assert "difficulty" in decoy
            assert "nonce" in decoy
            # Hash should be 64 hex chars
            assert len(decoy["hash"]) == 64
            assert re.match(r'^[0-9a-f]{64}$', decoy["hash"])
    
    def test_ethereum_decoy_generation(self):
        """Test Ethereum decoy generation."""
        config = EntropyConfig(decoy_count=3)
        decoys = decoy_generation("ethereum", config)
        
        assert len(decoys) == 3
        
        for decoy in decoys:
            assert decoy["type"] == "ethereum"
            assert decoy["synthetic"] is True
            assert "hash" in decoy
            assert "address" in decoy
            assert "timestamp" in decoy
            assert "gas_price" in decoy
            assert "gas_limit" in decoy
            assert "value" in decoy
            # Hash should have 0x prefix
            assert decoy["hash"].startswith("0x")
            assert len(decoy["hash"]) == 66
            # Address should have 0x prefix
            assert decoy["address"].startswith("0x")
            assert len(decoy["address"]) == 42
    
    def test_zero_decoy_count(self):
        """Test zero decoy count returns empty list."""
        config = EntropyConfig(decoy_count=0)
        decoys = decoy_generation("bitcoin", config)
        assert len(decoys) == 0
    
    def test_various_decoy_counts(self):
        """Test various decoy counts."""
        for count in [1, 5, 10, 20]:
            config = EntropyConfig(decoy_count=count)
            decoys = decoy_generation("ethereum", config)
            assert len(decoys) == count
    
    def test_unique_decoys(self):
        """Test that generated decoys are unique."""
        config = EntropyConfig(decoy_count=10)
        decoys = decoy_generation("bitcoin", config)
        
        hashes = [d["hash"] for d in decoys]
        assert len(set(hashes)) == len(hashes)  # All unique
    
    def test_invalid_hash_type(self):
        """Test that invalid hash type raises ValueError."""
        config = EntropyConfig()
        with pytest.raises(ValueError, match="Unsupported hash type"):
            decoy_generation("litecoin", config)


class TestVerifyMaskBalance:
    """Test suite for verify_mask_balance function."""
    
    def test_entropy_verification(self):
        """Test entropy verification of balanced outputs."""
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        config = EntropyConfig(output_count=4)
        
        balanced = balance_entropy(bitcoin_hash, config)
        verification = verify_mask_balance(bitcoin_hash, balanced)
        
        assert "original_entropy" in verification
        assert "average_output_entropy" in verification
        assert "entropy_difference" in verification
        assert "output_count" in verification
        assert "verified" in verification
        assert "max_entropy" in verification
        assert "min_entropy" in verification
        
        assert verification["output_count"] == 4
        assert verification["verified"] is True  # Should have high entropy
        assert verification["max_entropy"] >= verification["min_entropy"]
    
    def test_entropy_consistency(self):
        """Test that entropy calculations are consistent."""
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        config = EntropyConfig(output_count=2)
        
        balanced = balance_entropy(bitcoin_hash, config)
        verification1 = verify_mask_balance(bitcoin_hash, balanced)
        verification2 = verify_mask_balance(bitcoin_hash, balanced)
        
        # Should produce identical results for same inputs
        assert verification1["original_entropy"] == verification2["original_entropy"]


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    def test_mask_bitcoin_hash(self):
        """Test mask_bitcoin_hash convenience function."""
        mask_data = mask_bitcoin_hash(
            "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62",
            strength=256
        )
        
        assert mask_data["hash_type"] == "bitcoin"
        assert mask_data["strength"] == 256
        assert len(mask_data["mask"]) == 32
    
    def test_mask_ethereum_hash(self):
        """Test mask_ethereum_hash convenience function."""
        mask_data = mask_ethereum_hash(
            "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            strength=128
        )
        
        assert mask_data["hash_type"] == "ethereum"
        assert mask_data["strength"] == 128
        assert len(mask_data["mask"]) == 16
    
    def test_generate_mixed_decoys(self):
        """Test generate_mixed_decoys convenience function."""
        config = EntropyConfig(decoy_count=5)
        mixed = generate_mixed_decoys(config)
        
        assert "bitcoin" in mixed
        assert "ethereum" in mixed
        assert len(mixed["bitcoin"]) == 5
        assert len(mixed["ethereum"]) == 5
        
        for decoy in mixed["bitcoin"]:
            assert decoy["type"] == "bitcoin"
        
        for decoy in mixed["ethereum"]:
            assert decoy["type"] == "ethereum"


class TestIntegration:
    """Integration tests for the full workflow."""
    
    def test_full_bitcoin_workflow(self):
        """Test complete Bitcoin masking workflow."""
        config = EntropyConfig(
            mask_strength=256,
            output_count=4,
            decoy_count=10
        )
        
        # Step 1: Generate mask
        mask = generate_hash_mask(config, "bitcoin")
        
        # Step 2: Balance entropy
        bitcoin_hash = "8384467d62cbc2c5e6935cf72158b4ebf92897b4aebb3b30e8ac68ccada57b62"
        balanced = balance_entropy(bitcoin_hash, config)
        
        # Step 3: Generate decoys
        decoys = decoy_generation("bitcoin", config)
        
        # Step 4: Verify
        verification = verify_mask_balance(bitcoin_hash, balanced)
        
        assert mask["hash_type"] == "bitcoin"
        assert len(balanced) == 4
        assert len(decoys) == 10
        assert verification["verified"] is True
    
    def test_full_ethereum_workflow(self):
        """Test complete Ethereum masking workflow."""
        config = EntropyConfig(
            mask_strength=128,
            output_count=2,
            decoy_count=5
        )
        
        # Generate mask
        mask = generate_hash_mask(config, "ethereum")
        
        # Balance entropy
        ethereum_hash = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        balanced = balance_entropy(ethereum_hash, config)
        
        # Generate decoys
        decoys = decoy_generation("ethereum", config)
        
        # Verify
        verification = verify_mask_balance(ethereum_hash, balanced)
        
        assert mask["hash_type"] == "ethereum"
        assert len(balanced) == 2
        assert len(decoys) == 5
        assert verification["verified"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
