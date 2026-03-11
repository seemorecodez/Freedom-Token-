"""
Blockchain Entropy Balancer

A Python module for blockchain hash-based masking and decoy generation.
Provides entropy balancing, hash masking, and synthetic blockchain data
generation for Bitcoin and Ethereum.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class HashType(Enum):
    """Supported blockchain hash types."""
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"


@dataclass
class EntropyConfig:
    """
    Configuration for entropy balancing operations.
    
    Attributes:
        mask_strength: Bits of entropy for masks (64, 128, 256)
        output_count: Number of balanced outputs to generate
        decoy_count: Number of decoy entries to generate
        salt: Optional salt for deterministic masking
    """
    mask_strength: int = 128
    output_count: int = 4
    decoy_count: int = 10
    salt: Optional[bytes] = None
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.mask_strength not in (64, 128, 256):
            raise ValueError("mask_strength must be 64, 128, or 256")
        if self.output_count < 1:
            raise ValueError("output_count must be at least 1")
        if self.decoy_count < 0:
            raise ValueError("decoy_count must be non-negative")


def _get_hash_algorithm(hash_type: str) -> str:
    """Get the algorithm name for a given hash type."""
    algorithms = {
        HashType.BITCOIN.value: "sha256",
        HashType.ETHEREUM.value: "keccak256"
    }
    if hash_type not in algorithms:
        raise ValueError(f"Unsupported hash type: {hash_type}. Use 'bitcoin' or 'ethereum'")
    return algorithms[hash_type]


def _normalize_hash(hash_input: str, hash_type: str) -> str:
    """Normalize a hash string based on its type."""
    hash_input = hash_input.lower().strip()
    
    if hash_type == HashType.ETHEREUM.value:
        # Ethereum hashes should have 0x prefix
        if not hash_input.startswith("0x"):
            hash_input = "0x" + hash_input
        # Remove 0x for processing, validate length
        clean = hash_input[2:]
        if len(clean) != 64:
            raise ValueError(f"Ethereum hash must be 64 hex chars (got {len(clean)})")
    elif hash_type == HashType.BITCOIN.value:
        # Bitcoin hashes are 64 hex chars
        if hash_input.startswith("0x"):
            hash_input = hash_input[2:]
        if len(hash_input) != 64:
            raise ValueError(f"Bitcoin hash must be 64 hex chars (got {len(hash_input)})")
    
    return hash_input


def _generate_random_bytes(length: int) -> bytes:
    """Generate cryptographically secure random bytes."""
    return secrets.token_bytes(length)


def _apply_mask(hash_bytes: bytes, mask: bytes) -> bytes:
    """Apply XOR mask to hash bytes."""
    # Extend mask to match hash length if needed
    if len(mask) < len(hash_bytes):
        # Repeat mask pattern
        extended_mask = (mask * ((len(hash_bytes) // len(mask)) + 1))[:len(hash_bytes)]
    else:
        extended_mask = mask[:len(hash_bytes)]
    
    return bytes(a ^ b for a, b in zip(hash_bytes, extended_mask))


def generate_hash_mask(config: EntropyConfig, hash_type: str) -> Dict:
    """
    Generate an entropy mask for the specified blockchain hash type.
    
    Args:
        config: EntropyConfig instance with mask parameters
        hash_type: Type of hash - "bitcoin" or "ethereum"
    
    Returns:
        Dictionary containing mask metadata
    """
    algorithm = _get_hash_algorithm(hash_type)
    
    # Calculate mask bytes needed
    mask_bytes = config.mask_strength // 8
    
    # Generate cryptographically secure mask
    if config.salt is not None:
        # Use salt for deterministic generation
        mask_input = config.salt + hash_type.encode()
        # Derive mask using hash-based method
        mask = hashlib.sha256(mask_input).digest()
        if mask_bytes > 32:
            # Extend mask if needed
            mask = (mask + hashlib.sha256(mask_input + b"extend").digest())[:mask_bytes]
        else:
            mask = mask[:mask_bytes]
    else:
        # Random mask
        mask = _generate_random_bytes(mask_bytes)
    
    return {
        "mask": mask,
        "strength": config.mask_strength,
        "hash_type": hash_type,
        "algorithm": algorithm,
        "mask_hex": mask.hex()
    }


def balance_entropy(hash_input: str, config: EntropyConfig) -> List[Dict]:
    """
    Distribute a hash across multiple balanced outputs using entropy masking.
    
    Args:
        hash_input: Blockchain hash (hex string)
        config: EntropyConfig instance
    
    Returns:
        List of balanced hash outputs with metadata
    """
    # Determine hash type from format
    hash_input_clean = hash_input.lower().strip()
    if hash_input_clean.startswith("0x"):
        hash_type = HashType.ETHEREUM.value
    else:
        hash_type = HashType.BITCOIN.value
    
    # Normalize the hash
    normalized = _normalize_hash(hash_input, hash_type)
    
    # Convert to bytes
    try:
        hash_bytes = bytes.fromhex(normalized.replace("0x", ""))
    except ValueError:
        raise ValueError("Invalid hex string in hash input")
    
    outputs = []
    
    for i in range(config.output_count):
        # Generate unique mask for each output
        mask_config = EntropyConfig(
            mask_strength=config.mask_strength,
            output_count=1,
            salt=config.salt + i.to_bytes(4, 'big') if config.salt else None
        )
        mask_data = generate_hash_mask(mask_config, hash_type)
        mask = mask_data["mask"]
        
        # Apply mask to hash
        masked_bytes = _apply_mask(hash_bytes, mask)
        
        # Generate additional entropy layer
        entropy_layer = _generate_random_bytes(len(masked_bytes))
        final_bytes = _apply_mask(masked_bytes, entropy_layer)
        
        # Format output based on hash type
        if hash_type == HashType.ETHEREUM.value:
            output_hash = "0x" + final_bytes.hex()
        else:
            output_hash = final_bytes.hex()
        
        outputs.append({
            "output": output_hash,
            "mask": mask.hex(),
            "entropy_layer": entropy_layer.hex(),
            "index": i,
            "hash_type": hash_type,
            "original_length": len(hash_input)
        })
    
    return outputs


def _generate_bitcoin_decoy(config: EntropyConfig) -> Dict:
    """Generate a synthetic Bitcoin block hash."""
    # Generate random 32 bytes for block hash
    random_hash = _generate_random_bytes(32)
    
    # Create synthetic block data
    block_hash = random_hash.hex()
    
    return {
        "hash": block_hash,
        "type": "bitcoin",
        "block_height": secrets.randbelow(800000) + 1,
        "timestamp": int(time.time()) - secrets.randbelow(31536000),  # Up to 1 year ago
        "difficulty": secrets.randbelow(1000000000000),
        "nonce": secrets.randbelow(4294967295),
        "synthetic": True
    }


def _generate_ethereum_decoy(config: EntropyConfig) -> Dict:
    """Generate a synthetic Ethereum transaction/block hash."""
    # Generate random 32 bytes
    random_hash = _generate_random_bytes(32)
    
    # Format with 0x prefix
    tx_hash = "0x" + random_hash.hex()
    
    # Generate synthetic address
    address = "0x" + _generate_random_bytes(20).hex()
    
    return {
        "hash": tx_hash,
        "type": "ethereum",
        "address": address,
        "timestamp": int(time.time()) - secrets.randbelow(31536000),
        "gas_price": secrets.randbelow(500000000000),  # Up to 500 gwei
        "gas_limit": secrets.randbelow(8000000) + 21000,
        "value": secrets.randbelow(10000000000000000000),  # Up to 10 ETH in wei
        "synthetic": True
    }


def decoy_generation(hash_type: str, config: EntropyConfig) -> List[Dict]:
    """
    Generate synthetic blockchain data for decoy purposes.
    
    Args:
        hash_type: Type of hash - "bitcoin" or "ethereum"
        config: EntropyConfig instance
    
    Returns:
        List of synthetic blockchain entries
    """
    if hash_type not in (HashType.BITCOIN.value, HashType.ETHEREUM.value):
        raise ValueError(f"Unsupported hash type: {hash_type}. Use 'bitcoin' or 'ethereum'")
    
    decoys = []
    
    for _ in range(config.decoy_count):
        if hash_type == HashType.BITCOIN.value:
            decoy = _generate_bitcoin_decoy(config)
        else:
            decoy = _generate_ethereum_decoy(config)
        
        decoys.append(decoy)
    
    return decoys


def verify_mask_balance(original_hash: str, balanced_outputs: List[Dict]) -> Dict:
    """
    Verify that balanced outputs maintain proper entropy distribution.
    
    Args:
        original_hash: The original blockchain hash
        balanced_outputs: List of outputs from balance_entropy()
    
    Returns:
        Verification results with statistics
    """
    # Calculate entropy statistics
    import math
    
    def calculate_entropy(data: bytes) -> float:
        """Calculate Shannon entropy of byte data."""
        if not data:
            return 0.0
        
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1
        
        entropy = 0.0
        length = len(data)
        for count in byte_counts:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        
        return entropy
    
    # Analyze original
    original_clean = original_hash.lower().replace("0x", "")
    original_bytes = bytes.fromhex(original_clean)
    original_entropy = calculate_entropy(original_bytes)
    
    # Analyze outputs
    output_entropies = []
    for output in balanced_outputs:
        output_clean = output["output"].lower().replace("0x", "")
        output_bytes = bytes.fromhex(output_clean)
        output_entropies.append(calculate_entropy(output_bytes))
    
    avg_entropy = sum(output_entropies) / len(output_entropies) if output_entropies else 0
    
    return {
        "original_entropy": original_entropy,
        "average_output_entropy": avg_entropy,
        "entropy_difference": abs(original_entropy - avg_entropy),
        "output_count": len(balanced_outputs),
        "verified": all(e > 3.0 for e in output_entropies),  # High entropy threshold
        "max_entropy": max(output_entropies) if output_entropies else 0,
        "min_entropy": min(output_entropies) if output_entropies else 0
    }


# Convenience functions for common operations

def mask_bitcoin_hash(hash_hex: str, strength: int = 128) -> Dict:
    """
    Quick mask generation for Bitcoin hashes.
    
    Args:
        hash_hex: Bitcoin block hash (64 hex chars)
        strength: Mask strength in bits (64, 128, 256)
    
    Returns:
        Mask metadata dictionary
    """
    config = EntropyConfig(mask_strength=strength, output_count=1)
    return generate_hash_mask(config, "bitcoin")


def mask_ethereum_hash(hash_hex: str, strength: int = 128) -> Dict:
    """
    Quick mask generation for Ethereum hashes.
    
    Args:
        hash_hex: Ethereum transaction/block hash (64 hex chars, with or without 0x)
        strength: Mask strength in bits (64, 128, 256)
    
    Returns:
        Mask metadata dictionary
    """
    config = EntropyConfig(mask_strength=strength, output_count=1)
    return generate_hash_mask(config, "ethereum")


def generate_mixed_decoys(config: EntropyConfig) -> Dict[str, List[Dict]]:
    """
    Generate decoys for both Bitcoin and Ethereum.
    
    Args:
        config: EntropyConfig instance
    
    Returns:
        Dictionary with 'bitcoin' and 'ethereum' decoy lists
    """
    return {
        "bitcoin": decoy_generation("bitcoin", config),
        "ethereum": decoy_generation("ethereum", config)
    }
