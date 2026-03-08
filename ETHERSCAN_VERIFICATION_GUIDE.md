# Etherscan Contract Verification Guide

## Step 1: Get Free Etherscan API Key

### 1.1 Create Etherscan Account
1. Go to https://etherscan.io/register
2. Enter your email address
3. Create a password
4. Verify your email

### 1.2 Generate API Key
1. Log in to https://etherscan.io
2. Click on your profile (top right)
3. Select "API Keys"
4. Click "Create API Key"
5. Give it a name (e.g., "FreedomToken")
6. Copy the API key (starts with letters/numbers)

### 1.3 Add API Key to Project
```bash
# In your terminal, run:
cd /root/.openclaw/workspace/freedomtoken-deploy

# Add the API key to .env
echo "ETHERSCAN_API_KEY=YOUR_API_KEY_HERE" >> .env

# Verify it was added
cat .env | grep ETHERSCAN
```

---

## Step 2: Verify Contracts

### Option A: Run Automated Script (Recommended)
```bash
# Make sure you're in the project directory
cd /root/.openclaw/workspace/freedomtoken-deploy

# Run the verification script
./verify-contracts.sh
```

**What this does:**
- Verifies all 4 contracts automatically
- Includes constructor arguments
- Waits for confirmation
- Provides Etherscan links

### Option B: Manual Verification (If script fails)

#### Contract 1: FreedomToken
```bash
export PATH="$PATH:$HOME/.foundry/bin"

forge verify-contract \
  --chain sepolia \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2") \
  --watch \
  0xb3b8f96925eed295afb1b9d7b72a0450df6f8509 \
  FreedomToken
```

#### Contract 2: GasDAO
```bash
forge verify-contract \
  --chain sepolia \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address,address,address)" \
    "0xb3b8f96925eed295afb1b9d7b72a0450df6f8509" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2") \
  --watch \
  0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0 \
  GasDAO
```

#### Contract 3: AITreasury
```bash
forge verify-contract \
  --chain sepolia \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address,address,address)" \
    "0xb3b8f96925eed295afb1b9d7b72a0450df6f8509" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A") \
  --watch \
  0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194 \
  AITreasury
```

#### Contract 4: GaslessRelayer
```bash
forge verify-contract \
  --chain sepolia \
  --etherscan-api-key $ETHERSCAN_API_KEY \
  --constructor-args $(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A") \
  --watch \
  0xd138d1e06d1b98270dec55546b0a00f97a7505f4 \
  GaslessRelayer
```

---

## Step 3: Verify Success

### Check on Etherscan
Visit these URLs to confirm verification:

| Contract | Verification URL |
|----------|------------------|
| FreedomToken | https://sepolia.etherscan.io/address/0xb3b8f96925eed295afb1b9d7b72a0450df6f8509#code |
| GasDAO | https://sepolia.etherscan.io/address/0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0#code |
| AITreasury | https://sepolia.etherscan.io/address/0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194#code |
| GaslessRelayer | https://sepolia.etherscan.io/address/0xd138d1e06d1b98270dec55546b0a00f97a7505f4#code |

### What You Should See
✅ "Contract Source Code Verified" badge  
✅ Full Solidity source code visible  
✅ Constructor arguments decoded  
✅ ABI available for interaction  

---

## Troubleshooting

### Error: "Invalid API Key"
- Double-check your API key is correct
- Make sure you're using Sepolia API key (not mainnet)
- Verify key is added to .env file

### Error: "Contract already verified"
- Contract might already be verified
- Check Etherscan URL to confirm

### Error: "Bytecode doesn't match"
- Contracts may have been recompiled
- Make sure to use the exact bytecode from deployment
- Check `deployments/sepolia-*.json` for correct addresses

### Verification Taking Too Long
- Sepolia verification usually takes 1-5 minutes
- Use `--watch` flag to wait for confirmation
- Check Etherscan directly if script hangs

---

## Next Steps After Verification

1. **Update Grant Applications**
   - Add "✅ Verified on Etherscan" to applications
   - Increases credibility significantly

2. **Share Verified Contracts**
   - Tweet the Etherscan links
   - Add to project documentation
   - Include in demo

3. **Interact with Contracts**
   - Use Etherscan "Write Contract" tab
   - Test functions directly
   - No code needed

---

## Quick Reference

### Contract Addresses (Sepolia)
```
FreedomToken:     0xb3b8f96925eed295afb1b9d7b72a0450df6f8509
GasDAO:           0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0
AITreasury:       0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194
GaslessRelayer:   0xd138d1e06d1b98270dec55546b0a00f97a7505f4
```

### Constructor Arguments Summary
```
FreedomToken:     (treasury, aiController)
GasDAO:           (token, admin, guardian, aiController)
AITreasury:       (token, admin, aiController, guardian)
GaslessRelayer:   (admin, feeRecipient)
```
