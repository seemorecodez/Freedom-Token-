"""
Tests for the memory-reconstructor skill.

Run with: python -m pytest test_memory_reconstructor.py -v
"""

import pytest
import hashlib
from memory_reconstructor import (
    ReconstructorConfig,
    Shard,
    ReconstructedMemory,
    fetch_storage_shards,
    reconstruct_from_shards,
    verify_shard_integrity,
    compute_shard_checksum,
    create_shards,
    _simulate_storage_setup,
    _STORAGE_BACKENDS,
    ShardFetchError,
    IntegrityError,
    InsufficientShardsError,
    ReconstructionError,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return b"This is a test memory that will be sharded across storage."


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return ReconstructorConfig(
        shard_sources=["storage_0", "storage_1", "storage_2"],
        redundancy_factor=2,
        checksum_algorithm="sha256"
    )


@pytest.fixture
def clean_storage():
    """Clean storage before and after test."""
    _STORAGE_BACKENDS.clear()
    yield
    _STORAGE_BACKENDS.clear()


# ============================================================================
# ReconstructorConfig Tests
# ============================================================================

class TestReconstructorConfig:
    def test_default_config(self):
        config = ReconstructorConfig()
        assert config.shard_sources == []
        assert config.redundancy_factor == 2
        assert config.checksum_algorithm == "sha256"
        assert config.timeout_seconds == 30.0
        assert config.retry_attempts == 3
    
    def test_custom_config(self):
        config = ReconstructorConfig(
            shard_sources=["a", "b"],
            redundancy_factor=3,
            checksum_algorithm="md5",
            timeout_seconds=60.0,
            retry_attempts=5
        )
        assert config.shard_sources == ["a", "b"]
        assert config.redundancy_factor == 3
        assert config.checksum_algorithm == "md5"
    
    def test_invalid_redundancy_factor(self):
        with pytest.raises(ValueError, match="redundancy_factor"):
            ReconstructorConfig(redundancy_factor=0)
    
    def test_invalid_checksum_algorithm(self):
        with pytest.raises(ValueError, match="checksum_algorithm"):
            ReconstructorConfig(checksum_algorithm="invalid")


# ============================================================================
# Shard Tests
# ============================================================================

class TestShard:
    def test_shard_creation(self):
        shard = Shard(
            data=b"test data",
            index=0,
            source="storage_0",
            checksum="abc123",
            total_shards=3
        )
        assert shard.data == b"test data"
        assert shard.index == 0
        assert shard.source == "storage_0"
        assert shard.checksum == "abc123"
        assert shard.total_shards == 3
    
    def test_shard_repr(self):
        shard = Shard(
            data=b"test data",
            index=1,
            source="storage_1",
            checksum="abc",
            total_shards=2
        )
        assert "Shard(index=1" in repr(shard)
        assert "storage_1" in repr(shard)


# ============================================================================
# ReconstructedMemory Tests
# ============================================================================

class TestReconstructedMemory:
    def test_text_property(self):
        mem = ReconstructedMemory(
            data=b"hello world",
            metadata={},
            verified=True,
            shards_used=2,
            shards_total=2
        )
        assert mem.text == "hello world"
    
    def test_json_property(self):
        mem = ReconstructedMemory(
            data=b'{"key": "value"}',
            metadata={},
            verified=True,
            shards_used=1,
            shards_total=1
        )
        assert mem.json == {"key": "value"}
    
    def test_missing_shards_default(self):
        mem = ReconstructedMemory(
            data=b"test",
            metadata={},
            verified=True,
            shards_used=1,
            shards_total=2
        )
        assert mem.missing_shards == []


# ============================================================================
# verify_shard_integrity Tests
# ============================================================================

class TestVerifyShardIntegrity:
    def test_valid_sha256(self):
        data = b"test data"
        checksum = hashlib.sha256(data).hexdigest()
        shard = Shard(data=data, index=0, source="s", checksum=checksum, total_shards=1)
        assert verify_shard_integrity(shard, "sha256") is True
    
    def test_invalid_sha256(self):
        data = b"test data"
        shard = Shard(data=data, index=0, source="s", checksum="wrong", total_shards=1)
        assert verify_shard_integrity(shard, "sha256") is False
    
    def test_valid_md5(self):
        data = b"test data"
        checksum = hashlib.md5(data).hexdigest()
        shard = Shard(data=data, index=0, source="s", checksum=checksum, total_shards=1)
        assert verify_shard_integrity(shard, "md5") is True
    
    def test_valid_sha1(self):
        data = b"test data"
        checksum = hashlib.sha1(data).hexdigest()
        shard = Shard(data=data, index=0, source="s", checksum=checksum, total_shards=1)
        assert verify_shard_integrity(shard, "sha1") is True
    
    def test_unsupported_algorithm(self):
        shard = Shard(data=b"x", index=0, source="s", checksum="x", total_shards=1)
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            verify_shard_integrity(shard, "invalid")


# ============================================================================
# compute_shard_checksum Tests
# ============================================================================

class TestComputeShardChecksum:
    def test_sha256(self):
        data = b"hello"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_shard_checksum(data, "sha256") == expected
    
    def test_md5(self):
        data = b"hello"
        expected = hashlib.md5(data).hexdigest()
        assert compute_shard_checksum(data, "md5") == expected
    
    def test_sha1(self):
        data = b"hello"
        expected = hashlib.sha1(data).hexdigest()
        assert compute_shard_checksum(data, "sha1") == expected


# ============================================================================
# create_shards Tests
# ============================================================================

class TestCreateShards:
    def test_create_single_shard(self, sample_data):
        shards = create_shards(sample_data, 1, ["storage_0"])
        assert len(shards) == 1
        assert shards[0].index == 0
        assert shards[0].total_shards == 1
    
    def test_create_multiple_shards(self, sample_data):
        shards = create_shards(sample_data, 3, ["a", "b", "c"])
        assert len(shards) == 3
        assert shards[0].index == 0
        assert shards[1].index == 1
        assert shards[2].index == 2
    
    def test_shard_distribution_across_sources(self, sample_data):
        shards = create_shards(sample_data, 5, ["a", "b"])
        # Should distribute round-robin: a, b, a, b, a
        assert shards[0].source == "a"
        assert shards[1].source == "b"
        assert shards[2].source == "a"
        assert shards[3].source == "b"
        assert shards[4].source == "a"
    
    def test_data_reconstruction(self, sample_data):
        shards = create_shards(sample_data, 3, ["a", "b", "c"])
        # Concatenate all shard data
        reconstructed = b"".join(s.data for s in shards)
        assert reconstructed == sample_data
    
    def test_invalid_num_shards(self):
        with pytest.raises(ValueError, match="num_shards"):
            create_shards(b"data", 0, ["a"])
    
    def test_no_sources(self):
        with pytest.raises(ValueError, match="source"):
            create_shards(b"data", 2, [])


# ============================================================================
# fetch_storage_shards Tests
# ============================================================================

class TestFetchStorageShards:
    def test_fetch_success(self, sample_data, sample_config, clean_storage):
        _simulate_storage_setup("mem_001", sample_data, num_shards=3)
        shards = fetch_storage_shards(sample_config, "mem_001")
        
        assert len(shards) == 3
        assert all(isinstance(s, Shard) for s in shards)
        assert sorted([s.index for s in shards]) == [0, 1, 2]
    
    def test_fetch_from_subset(self, sample_data, clean_storage):
        config = ReconstructorConfig(shard_sources=["storage_0", "storage_1"])
        _simulate_storage_setup("mem_002", sample_data, num_shards=3)
        shards = fetch_storage_shards(config, "mem_002")
        
        # Should get shards from storage_0 and storage_1
        assert len(shards) >= 1
        assert all(s.source in ["storage_0", "storage_1"] for s in shards)
    
    def test_no_sources_configured(self, sample_data):
        config = ReconstructorConfig(shard_sources=[])
        with pytest.raises(ValueError, match="No shard sources"):
            fetch_storage_shards(config, "mem_003")
    
    def test_unknown_memory_returns_empty(self, sample_config, clean_storage):
        _simulate_storage_setup("other", b"data")
        shards = fetch_storage_shards(sample_config, "unknown")
        assert shards == []


# ============================================================================
# reconstruct_from_shards Tests
# ============================================================================

class TestReconstructFromShards:
    def test_full_reconstruction(self, sample_data, clean_storage):
        _simulate_storage_setup("mem_full", sample_data, num_shards=3)
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_full", []))
        
        result = reconstruct_from_shards(shards)
        
        assert result.data == sample_data
        assert result.verified is True
        assert result.shards_used == 3
        assert result.shards_total == 3
    
    def test_reconstruction_with_text(self, clean_storage):
        text = "Hello, World! This is test data."
        data = text.encode('utf-8')
        _simulate_storage_setup("mem_text", data, num_shards=2)
        
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_text", []))
        
        result = reconstruct_from_shards(shards)
        assert result.text == text
    
    def test_reconstruction_with_json(self, clean_storage):
        import json
        obj = {"name": "test", "value": 42, "items": [1, 2, 3]}
        data = json.dumps(obj).encode('utf-8')
        _simulate_storage_setup("mem_json", data, num_shards=2)
        
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_json", []))
        
        result = reconstruct_from_shards(shards)
        assert result.json == obj
    
    def test_no_shards(self):
        with pytest.raises(InsufficientShardsError, match="No shards"):
            reconstruct_from_shards([])
    
    def test_corrupted_shard_detected(self, sample_data, clean_storage):
        _simulate_storage_setup(
            "mem_corrupt", sample_data, num_shards=3,
            corruption_map={1: True}  # Corrupt shard 1
        )
        
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_corrupt", []))
        
        # With verify=True, should detect corruption
        result = reconstruct_from_shards(shards, verify=True)
        assert result.verified is False
        assert 1 in result.metadata["invalid_shards"]
    
    def test_skip_verification(self, sample_data, clean_storage):
        _simulate_storage_setup(
            "mem_skip", sample_data, num_shards=3,
            corruption_map={1: True}
        )
        
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_skip", []))
        
        # With verify=False, should not detect corruption
        result = reconstruct_from_shards(shards, verify=False)
        assert result.verified is True  # No verification done
    
    def test_reconstruction_metadata(self, sample_data, clean_storage):
        _simulate_storage_setup("mem_meta", sample_data, num_shards=2)
        
        shards = []
        for source in ["storage_0", "storage_1", "storage_2"]:
            shards.extend(_STORAGE_BACKENDS[source].get("mem_meta", []))
        
        result = reconstruct_from_shards(shards)
        
        assert "total_shards" in result.metadata
        assert "shards_used" in result.metadata
        assert "sources" in result.metadata
        assert result.metadata["total_shards"] == 2
        assert result.metadata["shards_used"] == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    def test_end_to_end_reconstruction(self, clean_storage):
        """Full workflow: create shards, setup storage, fetch, reconstruct."""
        # Original data
        original = b"This is important data that needs to be stored reliably."
        
        # Create shards
        shards = create_shards(original, 4, ["storage_0", "storage_1", "storage_2"])
        
        # Setup simulated storage
        memory_id = "integration_test_001"
        for source in ["storage_0", "storage_1", "storage_2"]:
            if source not in _STORAGE_BACKENDS:
                _STORAGE_BACKENDS[source] = {}
            _STORAGE_BACKENDS[source][memory_id] = [
                s for s in shards if s.source == source
            ]
        
        # Configure and fetch
        config = ReconstructorConfig(
            shard_sources=["storage_0", "storage_1", "storage_2"],
            redundancy_factor=2
        )
        fetched_shards = fetch_storage_shards(config, memory_id)
        
        # Verify each shard
        for shard in fetched_shards:
            assert verify_shard_integrity(shard) is True
        
        # Reconstruct
        result = reconstruct_from_shards(fetched_shards)
        
        # Verify result
        assert result.data == original
        assert result.verified is True
        assert result.shards_used == 4
    
    def test_partial_source_failure(self, clean_storage):
        """Test reconstruction when some sources are unavailable."""
        original = b"Test data for partial failure scenario."
        _simulate_storage_setup("partial_001", original, num_shards=3)
        
        # Only query available sources (storage_0 and storage_1 have data)
        config = ReconstructorConfig(
            shard_sources=["storage_0", "storage_1"],
            redundancy_factor=1
        )
        
        shards = fetch_storage_shards(config, "partial_001")
        assert len(shards) >= 1
        
        # Should still be able to reconstruct if we have all shards
        if len(shards) == 3:
            result = reconstruct_from_shards(shards)
            assert result.data == original


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
