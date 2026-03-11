# Resurrection Hash Verifier

Verify integrity before reactivation. This skill provides cryptographic verification mechanisms to ensure system state integrity before reactivation.

## Purpose

When a system or agent needs to be reactivated after suspension, hibernation, or transfer, it's critical to verify that the state hasn't been tampered with or corrupted. This skill computes and verifies resurrection hashes to establish a chain of trust.

## Components

### ResurrectionConfig

Configuration class for resurrection verification parameters.

```python
config = ResurrectionConfig(
    salt="unique-salt-value",
    algorithm="sha256",
    expected_hash="abc123...",
    trusted_sources=["source1", "source2"]
)
```

### compute_resurrection_hash()

Computes a cryptographic hash of the current state.

```python
hash_value = compute_resurrection_hash(
    state_data={...},
    config=config
)
```

### verify_before_reactivation()

Validates state integrity before allowing reactivation.

```python
is_valid = verify_before_reactivation(
    current_state={...},
    expected_hash="...",
    config=config
)
```

### chain_of_trust()

Establishes and verifies a chain of trust across multiple verification points.

```python
trust_result = chain_of_trust(
    checkpoints=[checkpoint1, checkpoint2, ...],
    root_trust="root-hash"
)
```

## Usage Example

```python
from resurrection_hash_verifier import (
    ResurrectionConfig,
    compute_resurrection_hash,
    verify_before_reactivation,
    chain_of_trust
)

# Configure verification
config = ResurrectionConfig(
    salt="my-secret-salt",
    algorithm="sha256"
)

# Before suspension - compute hash
state = {"memory": {...}, "config": {...}}
resurrection_hash = compute_resurrection_hash(state, config)
# Store: resurrection_hash

# Before reactivation - verify
is_valid = verify_before_reactivation(state, resurrection_hash, config)
if is_valid:
    reactivate_system()
else:
    raise IntegrityError("State has been tampered with!")
```

## Security Considerations

- Always use a unique, cryptographically secure salt
- Store expected hashes in a secure, tamper-proof location
- Rotate salts periodically
- Use strong hash algorithms (SHA-256 or better)
- Never log or expose hash values in plain text

## Testing

Run tests with:
```bash
python -m pytest test_resurrection_hash_verifier.py -v
```
