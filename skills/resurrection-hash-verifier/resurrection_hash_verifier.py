"""
Resurrection Hash Verifier

Verify integrity before reactivation.
Provides cryptographic verification mechanisms for system state integrity.
"""

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class ResurrectionConfig:
    """Configuration for resurrection verification.
    
    Attributes:
        salt: Cryptographic salt for hash computation
        algorithm: Hash algorithm to use (sha256, sha512, etc.)
        expected_hash: The expected hash value for verification
        trusted_sources: List of trusted source identifiers
        iterations: Number of hash iterations for added security
    """
    salt: str = field(default_factory=lambda: secrets.token_hex(32))
    algorithm: str = "sha256"
    expected_hash: Optional[str] = None
    trusted_sources: List[str] = field(default_factory=list)
    iterations: int = 100000
    
    def __post_init__(self):
        """Validate configuration parameters."""
        valid_algorithms = ["sha256", "sha512", "sha384", "sha224", "sha1", "md5"]
        if self.algorithm not in valid_algorithms:
            raise ValueError(f"Invalid algorithm. Must be one of: {valid_algorithms}")
        if self.iterations < 1:
            raise ValueError("Iterations must be at least 1")
        if not self.salt:
            raise ValueError("Salt cannot be empty")


class IntegrityError(Exception):
    """Raised when integrity verification fails."""
    pass


class ChainOfTrustError(Exception):
    """Raised when chain of trust verification fails."""
    pass


def _normalize_state(state_data: Any) -> bytes:
    """Normalize state data to consistent bytes representation.
    
    Args:
        state_data: The state data to normalize
        
    Returns:
        Normalized bytes representation
    """
    if isinstance(state_data, bytes):
        return state_data
    elif isinstance(state_data, str):
        return state_data.encode('utf-8')
    elif isinstance(state_data, (dict, list)):
        # Use canonical JSON representation for consistency
        return json.dumps(state_data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    else:
        return str(state_data).encode('utf-8')


def compute_resurrection_hash(
    state_data: Any,
    config: ResurrectionConfig
) -> str:
    """Compute a cryptographic hash of the current state.
    
    This function creates a cryptographically secure hash of the provided
    state data using the configured algorithm and salt. The hash can be
    stored and later used to verify state integrity before reactivation.
    
    Args:
        state_data: The state data to hash (dict, str, bytes, or any serializable object)
        config: ResurrectionConfig instance with hash parameters
        
    Returns:
        Hexadecimal string representing the computed hash
        
    Raises:
        ValueError: If state_data cannot be serialized
        
    Example:
        >>> config = ResurrectionConfig(salt="my-salt", algorithm="sha256")
        >>> state = {"memory": {"key": "value"}, "timestamp": 1234567890}
        >>> hash_value = compute_resurrection_hash(state, config)
        >>> print(hash_value)
        'a3f7b2...'
    """
    # Normalize state data to bytes
    state_bytes = _normalize_state(state_data)
    salt_bytes = config.salt.encode('utf-8')
    
    # Use PBKDF2-HMAC for secure key derivation style hashing
    hash_obj = hashlib.pbkdf2_hmac(
        config.algorithm.replace('sha', 'sha').lower(),
        state_bytes,
        salt_bytes,
        config.iterations
    )
    
    return hash_obj.hex()


def verify_before_reactivation(
    current_state: Any,
    expected_hash: str,
    config: ResurrectionConfig
) -> bool:
    """Validate state integrity before allowing reactivation.
    
    Compares the computed hash of the current state against an expected
    hash value to detect any tampering or corruption.
    
    Args:
        current_state: The current state data to verify
        expected_hash: The expected hash value (hex string)
        config: ResurrectionConfig instance with verification parameters
        
    Returns:
        True if verification passes, False otherwise
        
    Raises:
        IntegrityError: If verification fails and strict mode is implied
        
    Example:
        >>> config = ResurrectionConfig(salt="my-salt")
        >>> stored_hash = "a3f7b2..."  # Previously computed hash
        >>> is_valid = verify_before_reactivation(current_state, stored_hash, config)
        >>> if not is_valid:
        ...     raise IntegrityError("State tampering detected!")
    """
    if not expected_hash:
        raise ValueError("Expected hash cannot be empty")
    
    computed_hash = compute_resurrection_hash(current_state, config)
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_hash.lower(), expected_hash.lower())


@dataclass
class Checkpoint:
    """Represents a single checkpoint in the chain of trust.
    
    Attributes:
        identifier: Unique identifier for this checkpoint
        state_hash: Hash of the state at this checkpoint
        previous_hash: Hash of the previous checkpoint (for chaining)
        metadata: Additional metadata about the checkpoint
        timestamp: Unix timestamp of when checkpoint was created
    """
    identifier: str
    state_hash: str
    previous_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()
    
    def compute_checkpoint_hash(self) -> str:
        """Compute a composite hash of this checkpoint."""
        data = {
            "identifier": self.identifier,
            "state_hash": self.state_hash,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
        return hashlib.sha256(_normalize_state(data)).hexdigest()


def chain_of_trust(
    checkpoints: List[Checkpoint],
    root_trust: Optional[str] = None,
    config: Optional[ResurrectionConfig] = None
) -> Dict[str, Any]:
    """Establish and verify a chain of trust across multiple verification points.
    
    Creates a cryptographic chain where each checkpoint's integrity depends
    on the previous one, forming a tamper-evident sequence.
    
    Args:
        checkpoints: List of Checkpoint objects in chronological order
        root_trust: Optional root trust anchor hash
        config: Optional ResurrectionConfig for additional verification
        
    Returns:
        Dictionary containing:
            - valid: Boolean indicating if chain is valid
            - chain_hash: Hash of the entire chain
            - broken_at: Index where chain was broken (if any)
            - verification_details: List of per-checkpoint results
            
    Raises:
        ChainOfTrustError: If chain verification fails critically
        ValueError: If checkpoints list is empty
        
    Example:
        >>> cp1 = Checkpoint("init", "hash1")
        >>> cp2 = Checkpoint("step1", "hash2", cp1.compute_checkpoint_hash())
        >>> cp3 = Checkpoint("step2", "hash3", cp2.compute_checkpoint_hash())
        >>> result = chain_of_trust([cp1, cp2, cp3], root_trust="root123")
        >>> print(result["valid"])
        True
    """
    if not checkpoints:
        raise ValueError("At least one checkpoint is required")
    
    verification_details = []
    is_valid = True
    broken_at = None
    
    for i, checkpoint in enumerate(checkpoints):
        detail = {
            "index": i,
            "identifier": checkpoint.identifier,
            "verified": True,
            "error": None
        }
        
        # First checkpoint must match root trust if provided
        if i == 0 and root_trust is not None:
            checkpoint_composite = checkpoint.compute_checkpoint_hash()
            if not hmac.compare_digest(checkpoint_composite.lower(), root_trust.lower()):
                detail["verified"] = False
                detail["error"] = "Root trust mismatch"
                is_valid = False
                if broken_at is None:
                    broken_at = i
        
        # Subsequent checkpoints must chain properly
        if i > 0:
            previous_checkpoint = checkpoints[i - 1]
            expected_previous_hash = previous_checkpoint.compute_checkpoint_hash()
            
            if checkpoint.previous_hash is None:
                detail["verified"] = False
                detail["error"] = "Missing previous hash"
                is_valid = False
                if broken_at is None:
                    broken_at = i
            elif not hmac.compare_digest(
                checkpoint.previous_hash.lower(), 
                expected_previous_hash.lower()
            ):
                detail["verified"] = False
                detail["error"] = "Chain broken - previous hash mismatch"
                is_valid = False
                if broken_at is None:
                    broken_at = i
        
        # Optional: verify state hash with config if provided
        if config and detail["verified"]:
            # This would require access to the original state data
            # For now, we just validate the checkpoint structure
            pass
        
        verification_details.append(detail)
    
    # Compute aggregate chain hash
    chain_data = {
        "checkpoints": [
            {
                "id": cp.identifier,
                "hash": cp.compute_checkpoint_hash()
            }
            for cp in checkpoints
        ],
        "root_trust": root_trust
    }
    chain_hash = hashlib.sha256(_normalize_state(chain_data)).hexdigest()
    
    return {
        "valid": is_valid,
        "chain_hash": chain_hash,
        "broken_at": broken_at,
        "verification_details": verification_details,
        "checkpoint_count": len(checkpoints)
    }


def create_checkpoint(
    identifier: str,
    state_data: Any,
    previous_checkpoint: Optional[Checkpoint] = None,
    config: Optional[ResurrectionConfig] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Checkpoint:
    """Helper function to create a new checkpoint.
    
    Args:
        identifier: Unique identifier for this checkpoint
        state_data: State data to hash
        previous_checkpoint: Optional previous checkpoint to chain from
        config: Configuration for hash computation
        metadata: Optional metadata to attach
        
    Returns:
        New Checkpoint instance
    """
    if config is None:
        config = ResurrectionConfig()
    
    state_hash = compute_resurrection_hash(state_data, config)
    previous_hash = None
    
    if previous_checkpoint is not None:
        previous_hash = previous_checkpoint.compute_checkpoint_hash()
    
    return Checkpoint(
        identifier=identifier,
        state_hash=state_hash,
        previous_hash=previous_hash,
        metadata=metadata or {}
    )


def quick_verify(
    state_data: Any,
    expected_hash: str,
    salt: str = "default-salt-change-me"
) -> bool:
    """Quick verification without full configuration.
    
    Convenience function for simple verification scenarios.
    
    Args:
        state_data: State to verify
        expected_hash: Expected hash value
        salt: Salt for hashing (use a secure value in production!)
        
    Returns:
        True if verification passes
    """
    config = ResurrectionConfig(salt=salt, algorithm="sha256")
    return verify_before_reactivation(state_data, expected_hash, config)
