"""
Tests for the Rehydration Algorithm module.

Run with: python -m pytest test_rehydration_algorithm.py -v
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from rehydration_algorithm import (
    RehydrationConfig,
    RestorationResult,
    RestorationStatus,
    IntegrityResult,
    MemoryFragment,
    MemoryReconstructor,
    parse_seed_file,
    restore_state,
    verify_integrity,
    compute_checksum,
    generate_seed_template,
    save_seed_file,
    RehydrationError,
    SeedFormatError,
    IntegrityError,
    ComponentError
)


class TestRehydrationConfig:
    """Tests for RehydrationConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RehydrationConfig(seed_path="test.seed")
        assert config.seed_path == "test.seed"
        assert config.strict_mode is True
        assert config.backup_existing is True
        assert config.verify_after is True
        assert config.memory_reconstruction is True
        assert config.max_retries == 3
        assert config.backup_path is not None
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RehydrationConfig(
            seed_path="custom.seed",
            strict_mode=False,
            backup_existing=False,
            verify_after=False,
            memory_reconstruction=False,
            max_retries=5
        )
        assert config.strict_mode is False
        assert config.max_retries == 5
    
    def test_backup_path_auto_generation(self):
        """Test that backup path is auto-generated with timestamp."""
        config = RehydrationConfig(seed_path="test.seed")
        assert "backup_" in config.backup_path


class TestMemoryFragment:
    """Tests for MemoryFragment class."""
    
    def test_fragment_creation(self):
        """Test memory fragment creation."""
        now = datetime.now()
        fragment = MemoryFragment(
            id="test_001",
            content="Test memory content",
            timestamp=now,
            priority=5,
            tags=["test", "memory"]
        )
        assert fragment.id == "test_001"
        assert fragment.content == "Test memory content"
        assert fragment.priority == 5
        assert "test" in fragment.tags
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now()
        fragment = MemoryFragment(
            id="test_001",
            content={"key": "value"},
            timestamp=now,
            priority=7
        )
        d = fragment.to_dict()
        assert d["id"] == "test_001"
        assert d["priority"] == 7
        assert d["source"] == "seed"


class TestMemoryReconstructor:
    """Tests for MemoryReconstructor class."""
    
    def test_add_fragment(self):
        """Test adding fragments to reconstructor."""
        recon = MemoryReconstructor()
        fragment = MemoryFragment(
            id="frag_1",
            content="Content 1",
            timestamp=datetime.now()
        )
        recon.add_fragment(fragment)
        assert len(recon.fragments) == 1
        assert recon.get_fragment("frag_1") == fragment
    
    def test_reconstruct_from_seed(self):
        """Test reconstructing memory from seed data."""
        recon = MemoryReconstructor()
        memory_data = {
            "short_term": [
                {"id": "stm_1", "content": "Short term 1", "timestamp": datetime.now().isoformat(), "priority": 5},
                {"id": "stm_2", "content": "Short term 2", "timestamp": datetime.now().isoformat(), "priority": 3}
            ],
            "long_term": [
                {"id": "ltm_1", "content": "Long term 1", "timestamp": datetime.now().isoformat(), "priority": 8}
            ]
        }
        fragments = recon.reconstruct_from_seed(memory_data)
        assert len(fragments) == 3
        assert len(recon.fragments) == 3
    
    def test_reconstruct_sorts_by_priority(self):
        """Test that fragments are sorted by priority."""
        recon = MemoryReconstructor()
        memory_data = {
            "short_term": [
                {"id": "stm_1", "content": "Low priority", "timestamp": datetime.now().isoformat(), "priority": 2},
            ],
            "long_term": [
                {"id": "ltm_1", "content": "High priority", "timestamp": datetime.now().isoformat(), "priority": 9}
            ]
        }
        fragments = recon.reconstruct_from_seed(memory_data)
        assert fragments[0].id == "ltm_1"  # Higher priority first
        assert fragments[1].id == "stm_1"
    
    def test_search_by_tag(self):
        """Test searching fragments by tag."""
        recon = MemoryReconstructor()
        recon.add_fragment(MemoryFragment(
            id="f1", content="A", timestamp=datetime.now(), tags=["important", "work"]
        ))
        recon.add_fragment(MemoryFragment(
            id="f2", content="B", timestamp=datetime.now(), tags=["personal"]
        ))
        recon.add_fragment(MemoryFragment(
            id="f3", content="C", timestamp=datetime.now(), tags=["important", "home"]
        ))
        
        important = recon.search_by_tag("important")
        assert len(important) == 2
        assert all("important" in f.tags for f in important)
    
    def test_to_dict_export(self):
        """Test exporting all fragments to dict."""
        recon = MemoryReconstructor()
        recon.add_fragment(MemoryFragment(
            id="f1", content="A", timestamp=datetime.now(), tags=["tag1"]
        ))
        recon.add_fragment(MemoryFragment(
            id="f2", content="B", timestamp=datetime.now(), tags=["tag2"]
        ))
        
        result = recon.to_dict()
        assert result["count"] == 2
        assert len(result["fragments"]) == 2
        assert set(result["tags"]) == {"tag1", "tag2"}


class TestParseSeedFile:
    """Tests for parse_seed_file function."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_parse_valid_seed(self, temp_dir):
        """Test parsing a valid seed file."""
        seed_path = Path(temp_dir) / "test.seed"
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"name": "test"}
        }
        with open(seed_path, 'w') as f:
            json.dump(seed_data, f)
        
        result = parse_seed_file(str(seed_path))
        assert result["version"] == "1.0.0"
        assert "system" in result
    
    def test_parse_missing_file(self, temp_dir):
        """Test parsing non-existent file raises error."""
        with pytest.raises(SeedFormatError, match="not found"):
            parse_seed_file(str(Path(temp_dir) / "nonexistent.seed"))
    
    def test_parse_invalid_json(self, temp_dir):
        """Test parsing invalid JSON raises error."""
        seed_path = Path(temp_dir) / "bad.seed"
        with open(seed_path, 'w') as f:
            f.write("not valid json {{{")
        
        with pytest.raises(SeedFormatError, match="Invalid JSON"):
            parse_seed_file(str(seed_path))
    
    def test_parse_missing_required_fields(self, temp_dir):
        """Test parsing seed with missing required fields raises error."""
        seed_path = Path(temp_dir) / "incomplete.seed"
        with open(seed_path, 'w') as f:
            json.dump({"version": "1.0.0"}, f)  # Missing timestamp and system
        
        with pytest.raises(SeedFormatError, match="Missing required"):
            parse_seed_file(str(seed_path))
    
    def test_parse_checksum_validation(self, temp_dir):
        """Test checksum validation during parsing."""
        seed_path = Path(temp_dir) / "checksum.seed"
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"name": "test"},
            "checksum": "invalid_checksum"
        }
        with open(seed_path, 'w') as f:
            json.dump(seed_data, f)
        
        with pytest.raises(SeedFormatError, match="checksum mismatch"):
            parse_seed_file(str(seed_path))


class TestComputeChecksum:
    """Tests for checksum computation."""
    
    def test_checksum_deterministic(self):
        """Test that checksum is deterministic for same data."""
        data = {"a": 1, "b": 2, "version": "1.0.0"}
        checksum1 = compute_checksum(data)
        checksum2 = compute_checksum(data)
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA-256 hex length
    
    def test_checksum_excludes_checksum_field(self):
        """Test that checksum computation excludes existing checksum."""
        data1 = {"version": "1.0.0", "data": "test"}
        data2 = {"version": "1.0.0", "data": "test", "checksum": "abc123"}
        
        assert compute_checksum(data1) == compute_checksum(data2)
    
    def test_checksum_changes_with_data(self):
        """Test that checksum changes when data changes."""
        data1 = {"version": "1.0.0", "data": "test1"}
        data2 = {"version": "1.0.0", "data": "test2"}
        
        assert compute_checksum(data1) != compute_checksum(data2)


class TestVerifyIntegrity:
    """Tests for verify_integrity function."""
    
    def test_verify_all_pass(self):
        """Test integrity verification passes for valid state."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": [{"name": "comp1"}, {"name": "comp2"}]},
            "checksum": ""
        }
        seed_data["checksum"] = compute_checksum(seed_data)
        
        restored_state = {
            "restored_components": ["comp1", "comp2"],
            "failed_components": []
        }
        
        result = verify_integrity(seed_data, restored_state)
        assert result.passed is True
        assert len(result.errors) == 0
    
    def test_verify_component_count_mismatch(self):
        """Test integrity check fails on component count mismatch."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": [{"name": "comp1"}, {"name": "comp2"}]}
        }
        
        restored_state = {
            "restored_components": ["comp1"],  # Missing comp2
            "failed_components": []
        }
        
        result = verify_integrity(seed_data, restored_state)
        assert result.passed is False
        assert any("Component count mismatch" in e for e in result.errors)
    
    def test_verify_failed_components(self):
        """Test integrity check fails when components failed."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": [{"name": "comp1"}]}
        }
        
        restored_state = {
            "restored_components": [],
            "failed_components": ["comp1"]
        }
        
        result = verify_integrity(seed_data, restored_state)
        assert result.passed is False
        assert any("Components failed" in e for e in result.errors)
    
    def test_verify_checksum_mismatch(self):
        """Test integrity check fails on checksum mismatch."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []},
            "checksum": "wrong_checksum"
        }
        
        restored_state = {"restored_components": [], "failed_components": []}
        
        result = verify_integrity(seed_data, restored_state)
        assert result.passed is False
        assert result.checksum_match is False
    
    def test_verify_missing_checksum_warning(self):
        """Test warning when no checksum in seed."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []}
            # No checksum
        }
        
        restored_state = {"restored_components": [], "failed_components": []}
        
        result = verify_integrity(seed_data, restored_state)
        assert any("No checksum" in w for w in result.warnings)
    
    def test_verify_memory_reconstruction(self):
        """Test memory reconstruction verification."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []},
            "memory": {
                "short_term": [{"id": "s1"}],
                "long_term": [{"id": "l1"}]
            }
        }
        
        recon = MemoryReconstructor()
        recon.add_fragment(MemoryFragment(id="s1", content="", timestamp=datetime.now()))
        recon.add_fragment(MemoryFragment(id="l1", content="", timestamp=datetime.now()))
        
        restored_state = {
            "restored_components": [],
            "failed_components": [],
            "memory_reconstructor": recon
        }
        
        result = verify_integrity(seed_data, restored_state)
        assert result.checks.get("memory_reconstruction") is True
    
    def test_verify_component_status_map(self):
        """Test component status map in result."""
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": [{"name": "comp1"}, {"name": "comp2"}]}
        }
        
        restored_state = {
            "restored_components": ["comp1"],  # comp2 failed
            "failed_components": ["comp2"]
        }
        
        result = verify_integrity(seed_data, restored_state)
        assert result.component_status["comp1"] is True
        assert result.component_status["comp2"] is False


class TestRestoreState:
    """Tests for restore_state function."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_restore_basic(self, temp_dir):
        """Test basic restoration flow."""
        config = RehydrationConfig(
            seed_path="test.seed",
            backup_existing=False,
            verify_after=False
        )
        
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "components": []
            }
        }
        
        result = restore_state(seed_data, config)
        assert result.status == RestorationStatus.COMPLETED
        assert result.seed_version == "1.0.0"
    
    def test_restore_with_verification(self, temp_dir):
        """Test restoration with integrity verification."""
        config = RehydrationConfig(
            seed_path="test.seed",
            backup_existing=False,
            verify_after=True
        )
        
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []}
        }
        
        result = restore_state(seed_data, config)
        assert result.status == RestorationStatus.VERIFIED
        assert result.integrity_check is not None
        assert result.integrity_check.passed is True
    
    def test_restore_with_memory_reconstruction(self, temp_dir):
        """Test restoration with memory reconstruction."""
        config = RehydrationConfig(
            seed_path="test.seed",
            backup_existing=False,
            verify_after=False,
            memory_reconstruction=True
        )
        
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []},
            "memory": {
                "short_term": [
                    {"id": "s1", "content": "test", "timestamp": datetime.now().isoformat()}
                ]
            }
        }
        
        result = restore_state(seed_data, config)
        assert result.status == RestorationStatus.COMPLETED
        assert result.metadata.get("memory_fragments") == 1
    
    def test_restore_creates_backup(self, temp_dir):
        """Test that backup is created when requested."""
        backup_dir = Path(temp_dir) / "backups"
        config = RehydrationConfig(
            seed_path="test.seed",
            backup_existing=True,
            verify_after=False,
            backup_path=str(backup_dir)
        )
        
        seed_data = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "system": {"components": []}
        }
        
        result = restore_state(seed_data, config)
        assert "backup_path" in result.metadata


class TestGenerateSeedTemplate:
    """Tests for generate_seed_template function."""
    
    def test_template_structure(self):
        """Test template has correct structure."""
        template = generate_seed_template()
        
        assert "version" in template
        assert "timestamp" in template
        assert "checksum" in template
        assert "system" in template
        assert "memory" in template
        assert "state" in template
        
        assert "short_term" in template["memory"]
        assert "long_term" in template["memory"]
        assert "episodic" in template["memory"]
    
    def test_template_has_checksum(self):
        """Test template includes computed checksum."""
        template = generate_seed_template()
        assert template["checksum"] != ""
        assert len(template["checksum"]) == 64


class TestSaveSeedFile:
    """Tests for save_seed_file function."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_save_creates_file(self, temp_dir):
        """Test that save creates the file."""
        seed_path = Path(temp_dir) / "output.seed"
        data = {"version": "1.0.0", "test": "data"}
        
        save_seed_file(data, str(seed_path))
        
        assert seed_path.exists()
    
    def test_save_computes_checksum(self, temp_dir):
        """Test that save computes checksum if missing."""
        seed_path = Path(temp_dir) / "output.seed"
        data = {"version": "1.0.0", "test": "data"}
        
        save_seed_file(data, str(seed_path))
        
        with open(seed_path, 'r') as f:
            saved = json.load(f)
        
        assert "checksum" in saved
        assert saved["checksum"] != ""
    
    def test_save_recomputes_checksum(self, temp_dir):
        """Test that save always recomputes checksum."""
        seed_path = Path(temp_dir) / "output.seed"
        data = {"version": "1.0.0", "test": "data", "checksum": "existing"}
        
        save_seed_file(data, str(seed_path))
        
        with open(seed_path, 'r') as f:
            saved = json.load(f)
        
        # Should recompute since we always compute fresh checksum
        assert saved["checksum"] != "existing"
        # Verify it's a valid SHA-256 hex
        assert len(saved["checksum"]) == 64


class TestIntegration:
    """Integration tests for the full rehydration flow."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_full_roundtrip(self, temp_dir):
        """Test full roundtrip: create seed -> save -> parse -> restore."""
        # Generate template
        seed_data = generate_seed_template()
        seed_data["system"]["components"] = [
            {"name": "core", "type": "system", "enabled": True},
            {"name": "memory_manager", "type": "memory", "enabled": True}
        ]
        seed_data["memory"]["short_term"] = [
            {"id": "s1", "content": "Recent thought", "timestamp": datetime.now().isoformat(), "priority": 5}
        ]
        seed_data["memory"]["long_term"] = [
            {"id": "l1", "content": "Important fact", "timestamp": datetime.now().isoformat(), "priority": 9}
        ]
        # Regenerate checksum after all modifications
        seed_data["checksum"] = compute_checksum(seed_data)
        
        # Save seed file
        seed_path = Path(temp_dir) / "system.seed"
        save_seed_file(seed_data, str(seed_path))
        
        # Parse seed file
        parsed = parse_seed_file(str(seed_path))
        assert parsed["version"] == seed_data["version"]
        
        # Restore with config
        config = RehydrationConfig(
            seed_path=str(seed_path),
            backup_existing=False,
            verify_after=True,
            memory_reconstruction=True
        )
        
        result = restore_state(parsed, config)
        
        assert result.status == RestorationStatus.VERIFIED
        assert result.integrity_check.passed is True
        assert len(result.restored_components) == 2
        assert result.metadata.get("memory_fragments") == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
