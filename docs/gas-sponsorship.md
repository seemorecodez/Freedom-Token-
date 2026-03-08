# Gas Sponsorship (Paymaster) Explained

## The Problem

Normally, every Ethereum transaction requires the sender to pay gas in ETH:

```
User wants to send tokens
        ↓
Need ETH for gas
        ↓
User must buy ETH first
        ↓
High friction for new users
```

## The Solution: Gas Sponsorship

With Account Abstraction (ERC-4337), a **Paymaster** can pay the gas:

```
User wants to send tokens
        ↓
Smart Account creates transaction
        ↓
Paymaster pays gas (in ETH)
        ↓
User pays Paymaster back (in USDC, tokens, or nothing)
        ↓
Transaction executes
        ↓
User never needs ETH!
```

---

## How It Works

### Traditional Transaction
```
User Wallet (EOA)
    ↓ signs
Transaction
    ↓ pays
Gas Fee (ETH)
    ↓ executes
On-chain
```

### Sponsored Transaction (ERC-4337)
```
User Smart Account
    ↓ signs UserOperation
UserOperation
    ↓ sent to
Bundler
    ↓ asks
Paymaster: "Will you sponsor this?"
    ↓ checks
Policy: "Is this allowed?"
    ↓ if yes
Paymaster pays gas (ETH)
    ↓ executes
EntryPoint → Target Contract
    ↓ optional
User pays Paymaster (USDC)
```

---

## Types of Gas Sponsorship

### 1. **Fully Sponsored** (Free for users)
```javascript
// Paymaster pays 100% of gas
// User pays $0

Policy: {
  type: "sponsored",
  maxGasPerUserOp: "0.01",  // Max $0.01 worth of gas
  maxOpsPerDay: 1000
}

Use case: Onboarding, promotions, first-time users
```

### 2. **Token Paymaster** (Pay with ERC-20)
```javascript
// User pays gas in USDC instead of ETH
// Paymaster converts USDC → ETH for gas

Policy: {
  type: "erc20",
  token: "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eB48", // USDC
  exchangeRate: "1.05"  // 5% fee
}

Use case: Users have tokens but no ETH
```

### 3. **Hybrid** (Sponsor + User pays)
```javascript
// App sponsors first 10 transactions
// Then user pays with tokens

Policy: {
  type: "hybrid",
  sponsoredOps: 10,
  then: "erc20",
  token: "USDC"
}
```

---

## For FreedomToken: Which Policy?

### Option A: Fully Sponsored (Recommended for launch)

**Users pay $0 gas**

```javascript
// Alchemy Gas Manager Policy
{
  "name": "FreedomToken Launch",
  "type": "sponsored",
  "rules": {
    // Only sponsor FreedomToken contract interactions
    "targetContracts": [
      "0x...ECT_TOKEN",
      "0x...TREASURY",
      "0x...STAKING"
    ],
    
    // Max gas per transaction
    "maxGasPerUserOp": "0.005 ETH",
    
    // Daily limit per user
    "maxOpsPerDayPerUser": 10,
    
    // Total budget
    "monthlyBudget": "1 ETH"
  }
}
```

**Pros:**
- Zero friction for users
- Anyone can use FreedomToken without buying ETH
- Great for adoption

**Cons:**
- You pay for gas (but testnet = free)
- Need to monitor budget on mainnet

---

### Option B: Token Paymaster (For ECT holders)

**Users pay gas in ECT tokens**

```javascript
// Custom Paymaster
{
  "type": "erc20",
  "token": "ECT_TOKEN_ADDRESS",
  "exchangeRate": "oracle",  // Use Chainlink price feed
  "minBalance": "10 ECT"     // Must have 10 ECT to use
}
```

**Pros:**
- Users don't need ETH
- Gas fees go to ecosystem (burn ECT?)
- Self-sustaining

**Cons:**
- More complex to implement
- Users need ECT first

---

## Setting Up Gas Sponsorship

### Step 1: Create Gas Manager Policy (Alchemy)

```bash
# Via Alchemy Dashboard
curl -X POST "https://manage.alchemy.com/gas-manager/policy" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "FreedomToken",
    "app_id": "your_app_id",
    "policy_type": "sponsored",
    "rules": {
      "max_gas_per_user_op": "500000",
      "max_user_ops_per_day": 1000
    }
  }'
```

### Step 2: Integrate in Deployment

```typescript
// Use paymaster in transactions
const bundlerClient = createBundlerClient({
  account: smartAccount,
  chain: sepolia,
  transport: http(ALCHEMY_RPC),
  sponsorUserOperation: async (userOperation) => {
    // Ask Alchemy Gas Manager to sponsor
    const paymasterClient = createPaymasterClient({
      transport: http(ALCHEMY_RPC),
      chain: sepolia
    });
    
    return paymasterClient.sponsorUserOperation({
      userOperation,
      policyId: "your-policy-id"
    });
  }
});

// Send gasless transaction
const hash = await bundlerClient.sendUserOperation({
  calls: [{
    to: tokenAddress,
    data: transferData
  }]
  // No value field - gas is sponsored!
});
```

---

## Cost Estimates

### Testnet (Sepolia)
```
Gas sponsorship: FREE
- Test ETH has no value
- Alchemy provides free testnet paymasters
- Perfect for testing
```

### Mainnet
```
Average transaction: ~$0.50-5.00 in gas

If you sponsor:
- 1000 users × 10 txs = 10,000 transactions
- Cost: ~$5,000-50,000/month

Solutions:
1. Start with sponsored (growth)
2. Transition to token paymaster (sustainability)
3. Hybrid: Sponsor first 5 txs, then user pays
```

---

## Summary

| Type | User Pays | You Pay | Best For |
|------|-----------|---------|----------|
| **No sponsorship** | ETH | Nothing | Power users |
| **Fully sponsored** | Nothing | ETH | Onboarding |
| **Token paymaster** | Tokens | Nothing (convert) | Ecosystem |
| **Hybrid** | Nothing then tokens | Initial | Balanced |

**For FreedomToken:**
- **Testnet:** Use fully sponsored (free)
- **Mainnet launch:** Start sponsored, transition to ECT paymaster

---

## Quick Setup for Testnet

```bash
# Alchemy provides free testnet paymasters
# Just add this to your bundler client

const bundlerClient = createBundlerClient({
  account: smartAccount,
  chain: sepolia,
  transport: http(ALCHEMY_RPC),
  // This enables gas sponsorship!
  sponsorUserOperation: alchemyPaymasterAndData({
    policyId: "testnet-free-policy"
  })
});
```

**Result:** Users pay $0 gas. You pay nothing (testnet).
