# Memory Reconstructor Skill

Reconstructs data from distributed storage shards with integrity verification.

## Overview

The `memory-reconstructor` skill provides functionality to:
- Fetch data shards from distributed storage sources
- Reassemble fragmented data from multiple shards
- Verify shard integrity using checksums
- Handle partial failures and missing shards gracefully

## Components

### ReconstructorConfig

Configuration class for the memory reconstructor.

```python
from memory_reconstructor import ReconstructorConfig

config = ReconstructorConfig(
    shard_sources=["source1", "source2"],  # List of storage sources
    redundancy_factor=2,                    # Minimum shards needed
    checksum_algorithm="sha256"            # Hash algorithm for verification
)
```

### Core Functions

#### fetch_storage_shards()

Fetches shards from distributed storage sources.

```python
from memory_reconstructor import fetch_storage_shards, ReconstructorConfig

config = ReconstructorConfig(shard_sources=["db1", "db2", "db3"])
shards = fetch_storage_shards(config, memory_id="mem_001")
# Returns: List[Shard] objects containing raw data and metadata
```

**Parameters:**
- `config`: ReconstructorConfig instance
- `memory_id`: Unique identifier for the memory to reconstruct

**Returns:**
- List of Shard objects with `.data`, `.source`, `.index`, `.checksum` attributes

#### reconstruct_from_shards()

Assembles data from multiple shards.

```python
from memory_reconstructor import reconstruct_from_shards

reconstructed = reconstruct_from_shards(shards)
# Returns: ReconstructedMemory object
```

**Parameters:**
- `shards`: List of Shard objects from fetch_storage_shards()
- `verify`: Bool (default True) - whether to verify integrity before reconstruction

**Returns:**
- ReconstructedMemory object with `.data`, `.metadata`, `.verified` attributes

#### verify_shard_integrity()

Validates shard checksums.

```python
from memory_reconstructor import verify_shard_integrity

is_valid = verify_shard_integrity(shard, algorithm="sha256")
# Returns: True if checksum matches, False otherwise
```

**Parameters:**
- `shard`: Shard object to verify
- `algorithm`: Hash algorithm to use ("sha256", "md5", "sha1")

## Example Usage

```python
from memory_reconstructor import (
    ReconstructorConfig,
    fetch_storage_shards,
    reconstruct_from_shards,
    verify_shard_integrity
)

# Configure
config = ReconstructorConfig(
    shard_sources=["storage_a", "storage_b", "storage_c"],
    redundancy_factor=2,
    checksum_algorithm="sha256"
)

# Fetch shards
shards = fetch_storage_shards(config, memory_id="user_mem_42")

# Verify each shard
for shard in shards:
    if not verify_shard_integrity(shard):
        print(f"Shard {shard.index} from {shard.source} is corrupted!")

# Reconstruct memory
memory = reconstruct_from_shards(shards)
print(f"Reconstructed {len(memory.data)} bytes, verified: {memory.verified}")
```

## Error Handling

The skill raises these exceptions:

- `ShardFetchError`: Failed to fetch from a storage source
- `IntegrityError`: Checksum verification failed
- `InsufficientShardsError`: Not enough shards for reconstruction
- `ReconstructionError`: Failed to assemble data from shards

## Testing

Run tests:
```bash
python -m pytest test_memory_reconstructor.py -v
```
