#!/bin/bash
# Interactive Etherscan Verification Helper

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     FreedomToken Etherscan Verification Helper            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

cd /root/.openclaw/workspace/freedomtoken-deploy

# Check if ETHERSCAN_API_KEY exists
if grep -q "ETHERSCAN_API_KEY" .env 2>/dev/null; then
    echo "✓ ETHERSCAN_API_KEY found in .env"
    export $(grep "ETHERSCAN_API_KEY" .env | xargs)
else
    echo "❌ ETHERSCAN_API_KEY not found in .env"
    echo ""
    echo "To get your free API key:"
    echo "1. Go to https://etherscan.io/register"
    echo "2. Create an account"
    echo "3. Go to API Keys section"
    echo "4. Create a new key"
    echo ""
    echo "Once you have your API key, enter it below:"
    echo -n "ETHERSCAN_API_KEY: "
    read API_KEY
    
    if [ -z "$API_KEY" ]; then
        echo "❌ No API key provided. Exiting."
        exit 1
    fi
    
    echo "ETHERSCAN_API_KEY=$API_KEY" >> .env
    export ETHERSCAN_API_KEY=$API_KEY
    echo "✓ API key saved to .env"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Ready to verify contracts on Sepolia Testnet"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Contracts to verify:"
echo "  1. FreedomToken     → 0xb3b8f96925eed295afb1b9d7b72a0450df6f8509"
echo "  2. GasDAO           → 0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0"
echo "  3. AITreasury       → 0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194"
echo "  4. GaslessRelayer   → 0xd138d1e06d1b98270dec55546b0a00f97a7505f4"
echo ""
echo -n "Press Enter to start verification or Ctrl+C to cancel..."
read

export PATH="$PATH:$HOME/.foundry/bin"

# Contract addresses
FREEDOM_TOKEN="0xb3b8f96925eed295afb1b9d7b72a0450df6f8509"
GAS_DAO="0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0"
AI_TREASURY="0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194"
GASLESS_RELAYER="0xd138d1e06d1b98270dec55546b0a00f97a7505f4"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Verifying Contract 1/4: FreedomToken"
echo "═══════════════════════════════════════════════════════════"

FREEDOM_TOKEN_ARGS=$(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2")

forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $FREEDOM_TOKEN_ARGS \
    --watch \
    $FREEDOM_TOKEN \
    FreedomToken

if [ $? -eq 0 ]; then
    echo "✓ FreedomToken verified successfully"
else
    echo "⚠️ FreedomToken verification may have issues (check manually)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Verifying Contract 2/4: GasDAO"
echo "═══════════════════════════════════════════════════════════"

GAS_DAO_ARGS=$(cast abi-encode "constructor(address,address,address,address)" \
    "$FREEDOM_TOKEN" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2")

forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $GAS_DAO_ARGS \
    --watch \
    $GAS_DAO \
    GasDAO

if [ $? -eq 0 ]; then
    echo "✓ GasDAO verified successfully"
else
    echo "⚠️ GasDAO verification may have issues (check manually)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Verifying Contract 3/4: AITreasury"
echo "═══════════════════════════════════════════════════════════"

AI_TREASURY_ARGS=$(cast abi-encode "constructor(address,address,address,address)" \
    "$FREEDOM_TOKEN" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A")

forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $AI_TREASURY_ARGS \
    --watch \
    $AI_TREASURY \
    AITreasury

if [ $? -eq 0 ]; then
    echo "✓ AITreasury verified successfully"
else
    echo "⚠️ AITreasury verification may have issues (check manually)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Verifying Contract 4/4: GaslessRelayer"
echo "═══════════════════════════════════════════════════════════"

RELAYER_ARGS=$(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A")

forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $RELAYER_ARGS \
    --watch \
    $GASLESS_RELAYER \
    GaslessRelayer

if [ $? -eq 0 ]; then
    echo "✓ GaslessRelayer verified successfully"
else
    echo "⚠️ GaslessRelayer verification may have issues (check manually)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "🎉 VERIFICATION COMPLETE"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "View verified contracts:"
echo "  FreedomToken:   https://sepolia.etherscan.io/address/$FREEDOM_TOKEN#code"
echo "  GasDAO:         https://sepolia.etherscan.io/address/$GAS_DAO#code"
echo "  AITreasury:     https://sepolia.etherscan.io/address/$AI_TREASURY#code"
echo "  GaslessRelayer: https://sepolia.etherscan.io/address/$GASLESS_RELAYER#code"
echo ""
echo "Next steps:"
echo "  1. Click links above to confirm verification"
echo "  2. Update grant applications with '✅ Verified' status"
echo "  3. Share verified contract links"
echo ""
