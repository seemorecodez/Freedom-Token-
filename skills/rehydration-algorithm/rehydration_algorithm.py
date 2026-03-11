"""
Rehydration Algorithm - System State Restoration from Seed Files

This module provides functionality to restore a complete system state
from serialized seed data, including memory reconstruction and integrity verification.
"""

import json
import hashlib
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RehydrationError(Exception):
    """Base exception for rehydration errors."""
    pass


class SeedFormatError(RehydrationError):
    """Raised when seed file format is invalid."""
    pass


class IntegrityError(RehydrationError):
    """Raised when integrity verification fails."""
    pass


class ComponentError(RehydrationError):
    """Raised when component restoration fails."""
    pass


class RestorationStatus(Enum):
    """Status of restoration operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class IntegrityResult:
    """Result of integrity verification."""
    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checksum_match: bool = False
    component_status: Dict[str, bool] = field(default_factory=dict)


@dataclass
class RestorationResult:
    """Result of restoration operation."""
    status: RestorationStatus
    seed_version: str = ""
    restored_components: List[str] = field(default_factory=list)
    failed_components: List[str] = field(default_factory=list)
    integrity_check: Optional[IntegrityResult] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RehydrationConfig:
    """Configuration for system rehydration from seed files.
    
    Attributes:
        seed_path: Path to the seed file
        strict_mode: If True, fail on any integrity issue
        backup_existing: If True, backup existing system before restoration
        verify_after: If True, run integrity verification after restore
        memory_reconstruction: If True, reconstruct memory from seed
        backup_path: Custom path for backups
        component_hooks: Optional callbacks for component restoration
        max_retries: Maximum retries for failed components
    """
    seed_path: str
    strict_mode: bool = True
    backup_existing: bool = True
    verify_after: bool = True
    memory_reconstruction: bool = True
    backup_path: Optional[str] = None
    component_hooks: Dict[str, Callable] = field(default_factory=dict)
    max_retries: int = 3
    
    def __post_init__(self):
        if self.backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_path = f"backup_{timestamp}"


@dataclass
class MemoryFragment:
    """Represents a fragment of reconstructed memory."""
    id: str
    content: Any
    timestamp: datetime
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    source: str = "seed"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory fragment to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "tags": self.tags,
            "source": self.source
        }


class MemoryReconstructor:
    """Handles reconstruction of system memory from seed data."""
    
    def __init__(self):
        self.fragments: List[MemoryFragment] = []
        self.index: Dict[str, int] = {}
        
    def add_fragment(self, fragment: MemoryFragment) -> None:
        """Add a memory fragment to the reconstructor."""
        self.fragments.append(fragment)
        self.index[fragment.id] = len(self.fragments) - 1
        
    def reconstruct_from_seed(self, memory_data: Dict[str, Any]) -> List[MemoryFragment]:
        """Reconstruct memory from seed file data.
        
        Args:
            memory_data: Memory section from seed file
            
        Returns:
            List of reconstructed memory fragments
        """
        fragments = []
        
        # Process short-term memory
        if "short_term" in memory_data:
            for idx, item in enumerate(memory_data["short_term"]):
                fragment = MemoryFragment(
                    id=item.get("id", f"stm_{idx}"),
                    content=item.get("content"),
                    timestamp=datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat())),
                    priority=item.get("priority", 5),
                    tags=item.get("tags", ["short_term"]),
                    source="seed_short_term"
                )
                fragments.append(fragment)
                
        # Process long-term memory
        if "long_term" in memory_data:
            for idx, item in enumerate(memory_data["long_term"]):
                fragment = MemoryFragment(
                    id=item.get("id", f"ltm_{idx}"),
                    content=item.get("content"),
                    timestamp=datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat())),
                    priority=item.get("priority", 8),
                    tags=item.get("tags", ["long_term"]),
                    source="seed_long_term"
                )
                fragments.append(fragment)
                
        # Process episodic memory if present
        if "episodic" in memory_data:
            for idx, item in enumerate(memory_data["episodic"]):
                fragment = MemoryFragment(
                    id=item.get("id", f"epm_{idx}"),
                    content=item.get("content"),
                    timestamp=datetime.fromisoformat(item.get("timestamp", datetime.now().isoformat())),
                    priority=item.get("priority", 7),
                    tags=item.get("tags", ["episodic"]),
                    source="seed_episodic"
                )
                fragments.append(fragment)
                
        # Sort by priority (higher first) then timestamp
        fragments.sort(key=lambda f: (-f.priority, f.timestamp))
        
        for fragment in fragments:
            self.add_fragment(fragment)
            
        logger.info(f"Reconstructed {len(fragments)} memory fragments from seed")
        return fragments
    
    def get_fragment(self, fragment_id: str) -> Optional[MemoryFragment]:
        """Retrieve a specific memory fragment by ID."""
        if fragment_id in self.index:
            return self.fragments[self.index[fragment_id]]
        return None
    
    def search_by_tag(self, tag: str) -> List[MemoryFragment]:
        """Search memory fragments by tag."""
        return [f for f in self.fragments if tag in f.tags]
    
    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        """Export all fragments as dictionary."""
        return {
            "fragments": [f.to_dict() for f in self.fragments],
            "count": len(self.fragments),
            "tags": list(set(tag for f in self.fragments for tag in f.tags))
        }


def parse_seed_file(path: str) -> Dict[str, Any]:
    """Parse and validate a seed file.
    
    Args:
        path: Path to the seed file
        
    Returns:
        Parsed seed data as dictionary
        
    Raises:
        SeedFormatError: If seed file is invalid or corrupted
    """
    seed_path = Path(path)
    
    if not seed_path.exists():
        raise SeedFormatError(f"Seed file not found: {path}")
    
    try:
        with open(seed_path, 'r', encoding='utf-8') as f:
            content = f.read()
            seed_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise SeedFormatError(f"Invalid JSON in seed file: {e}")
    except Exception as e:
        raise SeedFormatError(f"Error reading seed file: {e}")
    
    # Validate required fields
    required_fields = ["version", "timestamp", "system"]
    missing = [f for f in required_fields if f not in seed_data]
    if missing:
        raise SeedFormatError(f"Missing required fields: {missing}")
    
    # Validate version format
    version = seed_data.get("version", "")
    if not isinstance(version, str) or not version:
        raise SeedFormatError("Invalid version format")
    
    # Validate checksum if present
    if "checksum" in seed_data:
        stored_checksum = seed_data["checksum"]
        computed_checksum = compute_checksum(seed_data)
        if stored_checksum != computed_checksum:
            raise SeedFormatError("Seed file checksum mismatch - file may be corrupted")
    
    logger.info(f"Successfully parsed seed file v{version} from {path}")
    return seed_data


def compute_checksum(data: Dict[str, Any]) -> str:
    """Compute SHA-256 checksum of seed data (excluding checksum field)."""
    check_data = {k: v for k, v in data.items() if k != "checksum"}
    content = json.dumps(check_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def backup_existing_system(config: RehydrationConfig) -> str:
    """Create backup of existing system state.
    
    Args:
        config: Rehydration configuration
        
    Returns:
        Path to backup directory
    """
    backup_dir = Path(config.backup_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Backup memory files if they exist
    memory_paths = ["memory", "MEMORY.md", "memory/"]
    for path_str in memory_paths:
        path = Path(path_str)
        if path.exists():
            dest = backup_dir / path.name
            if path.is_dir():
                shutil.copytree(path, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(path, dest)
    
    logger.info(f"System backed up to {backup_dir}")
    return str(backup_dir)


def restore_component(component_data: Dict[str, Any], 
                     hooks: Dict[str, Callable],
                     max_retries: int = 3) -> bool:
    """Restore a single component from seed data.
    
    Args:
        component_data: Component configuration from seed
        hooks: Optional restoration hooks
        max_retries: Maximum retry attempts
        
    Returns:
        True if restoration succeeded
    """
    name = component_data.get("name", "unknown")
    component_type = component_data.get("type", "generic")
    
    for attempt in range(max_retries):
        try:
            # Check for custom hook
            if name in hooks:
                hooks[name](component_data)
            elif component_type in hooks:
                hooks[component_type](component_data)
            else:
                # Default restoration
                _default_component_restore(component_data)
            
            logger.info(f"Restored component: {name}")
            return True
            
        except Exception as e:
            logger.warning(f"Component {name} restore attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to restore component {name} after {max_retries} attempts")
                return False
    
    return False


def _default_component_restore(component_data: Dict[str, Any]) -> None:
    """Default component restoration logic."""
    # Placeholder for actual component restoration
    # In practice, this would instantiate and configure components
    pass


def restore_state(seed_data: Dict[str, Any], 
                  config: RehydrationConfig) -> RestorationResult:
    """Restore system state from seed data.
    
    Args:
        seed_data: Parsed seed data from parse_seed_file()
        config: Rehydration configuration
        
    Returns:
        RestorationResult with status and details
    """
    result = RestorationResult(
        status=RestorationStatus.IN_PROGRESS,
        seed_version=seed_data.get("version", "unknown"),
        timestamp=datetime.now()
    )
    
    try:
        # Backup existing system if requested
        if config.backup_existing:
            backup_path = backup_existing_system(config)
            result.metadata["backup_path"] = backup_path
        
        # Restore system components
        system_data = seed_data.get("system", {})
        components = system_data.get("components", [])
        
        restored = []
        failed = []
        
        for component in components:
            if restore_component(component, config.component_hooks, config.max_retries):
                restored.append(component.get("name", "unknown"))
            else:
                failed.append(component.get("name", "unknown"))
                if config.strict_mode:
                    raise ComponentError(f"Failed to restore component in strict mode: {component.get('name')}")
        
        result.restored_components = restored
        result.failed_components = failed
        
        # Reconstruct memory if enabled
        memory_reconstructor = None
        if config.memory_reconstruction and "memory" in seed_data:
            memory_reconstructor = MemoryReconstructor()
            fragments = memory_reconstructor.reconstruct_from_seed(seed_data["memory"])
            result.metadata["memory_fragments"] = len(fragments)
        
        # Restore state variables
        if "state" in seed_data:
            state_data = seed_data["state"]
            result.metadata["state_variables"] = list(state_data.get("variables", {}).keys())
        
        # Verify integrity if requested
        if config.verify_after:
            integrity = verify_integrity(seed_data, {
                "restored_components": restored,
                "failed_components": failed,
                "memory_reconstructor": memory_reconstructor
            })
            result.integrity_check = integrity
            
            if not integrity.passed and config.strict_mode:
                raise IntegrityError(f"Integrity check failed: {integrity.errors}")
            
            result.status = RestorationStatus.VERIFIED if integrity.passed else RestorationStatus.COMPLETED
        else:
            result.status = RestorationStatus.COMPLETED
        
        logger.info(f"System restoration completed: {len(restored)} components restored")
        
    except Exception as e:
        result.status = RestorationStatus.FAILED
        result.metadata["error"] = str(e)
        logger.error(f"System restoration failed: {e}")
        raise
    
    return result


def verify_integrity(seed_data: Dict[str, Any], 
                    restored_state: Dict[str, Any]) -> IntegrityResult:
    """Verify integrity of restored system.
    
    Args:
        seed_data: Original seed data
        restored_state: State after restoration
        
    Returns:
        IntegrityResult with verification details
    """
    result = IntegrityResult(passed=True)
    checks = {}
    
    # Check 1: Component count match
    expected_components = len(seed_data.get("system", {}).get("components", []))
    actual_components = len(restored_state.get("restored_components", []))
    checks["component_count"] = expected_components == actual_components
    if not checks["component_count"]:
        result.errors.append(f"Component count mismatch: expected {expected_components}, got {actual_components}")
    
    # Check 2: No failed components
    failed = restored_state.get("failed_components", [])
    checks["no_failures"] = len(failed) == 0
    if not checks["no_failures"]:
        result.errors.append(f"Components failed to restore: {failed}")
    
    # Check 3: Checksum validation
    if "checksum" in seed_data:
        computed = compute_checksum(seed_data)
        checks["checksum"] = seed_data["checksum"] == computed
        result.checksum_match = checks["checksum"]
        if not checks["checksum"]:
            result.errors.append("Seed data checksum mismatch")
    else:
        checks["checksum"] = True  # No checksum to validate
        result.warnings.append("No checksum in seed data - integrity cannot be fully verified")
    
    # Check 4: Memory reconstruction
    if "memory" in seed_data:
        reconstructor = restored_state.get("memory_reconstructor")
        if reconstructor:
            expected_fragments = (len(seed_data["memory"].get("short_term", [])) +
                                len(seed_data["memory"].get("long_term", [])) +
                                len(seed_data["memory"].get("episodic", [])))
            actual_fragments = len(reconstructor.fragments)
            checks["memory_reconstruction"] = expected_fragments == actual_fragments
            if not checks["memory_reconstruction"]:
                result.errors.append(f"Memory fragment count mismatch: expected {expected_fragments}, got {actual_fragments}")
        else:
            checks["memory_reconstruction"] = False
            result.warnings.append("Memory reconstruction was not performed")
    
    # Check 5: Required fields present
    required = ["version", "timestamp", "system"]
    checks["required_fields"] = all(field in seed_data for field in required)
    if not checks["required_fields"]:
        missing = [f for f in required if f not in seed_data]
        result.errors.append(f"Missing required fields: {missing}")
    
    # Check 6: Version compatibility
    version = seed_data.get("version", "")
    checks["version_format"] = isinstance(version, str) and len(version.split(".")) >= 2
    if not checks["version_format"]:
        result.warnings.append(f"Unusual version format: {version}")
    
    # Determine overall pass/fail
    result.checks = checks
    result.passed = all(checks.values())
    
    # Component status map
    for comp in seed_data.get("system", {}).get("components", []):
        name = comp.get("name", "unknown")
        result.component_status[name] = name in restored_state.get("restored_components", [])
    
    if result.passed:
        logger.info("Integrity verification passed")
    else:
        logger.warning(f"Integrity verification failed with {len(result.errors)} errors")
    
    return result


def generate_seed_template() -> Dict[str, Any]:
    """Generate a template seed file structure.
    
    Returns:
        Template seed dictionary
    """
    template = {
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "checksum": "",
        "system": {
            "name": "agent-system",
            "version": "1.0.0",
            "components": [
                {
                    "name": "core",
                    "type": "system",
                    "config": {},
                    "enabled": True
                }
            ]
        },
        "memory": {
            "short_term": [],
            "long_term": [],
            "episodic": []
        },
        "state": {
            "variables": {},
            "connections": [],
            "metadata": {}
        }
    }
    
    # Compute and set checksum
    template["checksum"] = compute_checksum(template)
    
    return template


def save_seed_file(data: Dict[str, Any], path: str) -> None:
    """Save seed data to file with checksum.
    
    Args:
        data: Seed data dictionary
        path: Output file path
    """
    # Always compute fresh checksum to ensure validity
    data["checksum"] = compute_checksum(data)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Seed file saved to {path}")


# Convenience exports
__all__ = [
    'RehydrationConfig',
    'RestorationResult',
    'RestorationStatus',
    'IntegrityResult',
    'MemoryFragment',
    'MemoryReconstructor',
    'parse_seed_file',
    'restore_state',
    'verify_integrity',
    'compute_checksum',
    'generate_seed_template',
    'save_seed_file',
    'RehydrationError',
    'SeedFormatError',
    'IntegrityError',
    'ComponentError'
]
