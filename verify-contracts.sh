#!/bin/bash
# Etherscan Contract Verification Script
# Run this after adding ETHERSCAN_API_KEY to .env

set -e

cd /root/.openclaw/workspace/freedomtoken-deploy
export PATH="$PATH:$HOME/.foundry/bin"

# Load environment
export $(grep -v '^#' .env | xargs)

if [ -z "$ETHERSCAN_API_KEY" ]; then
    echo "❌ Error: ETHERSCAN_API_KEY not set in .env"
    echo "Get a free API key at: https://etherscan.io/apis"
    exit 1
fi

echo "🔍 Verifying FreedomToken contracts on Etherscan (Sepolia)..."
echo ""

# Contract addresses from deployment
FREEDOM_TOKEN="0xb3b8f96925eed295afb1b9d7b72a0450df6f8509"
GAS_DAO="0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0"
AI_TREASURY="0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194"
GASLESS_RELAYER="0xd138d1e06d1b98270dec55546b0a00f97a7505f4"

# Constructor arguments (ABI encoded)
# FreedomToken: (treasury, aiController)
FREEDOM_TOKEN_ARGS=$(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2")

# GasDAO: (token, admin, guardian, aiController)
GAS_DAO_ARGS=$(cast abi-encode "constructor(address,address,address,address)" \
    "$FREEDOM_TOKEN" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2")

# AITreasury: (token, admin, aiController, guardian)
AI_TREASURY_ARGS=$(cast abi-encode "constructor(address,address,address,address)" \
    "$FREEDOM_TOKEN" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x46c92f42e3c1eb45e68ee54518362B7c481A7df2" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A")

# GaslessRelayer: (admin, feeRecipient)
RELAYER_ARGS=$(cast abi-encode "constructor(address,address)" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A" \
    "0x32e9477d0887dFA680d145bE13802FB6Aa15679A")

echo "1. Verifying FreedomToken..."
echo "   Address: $FREEDOM_TOKEN"
forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $FREEDOM_TOKEN_ARGS \
    --watch \
    $FREEDOM_TOKEN \
    FreedomToken || echo "⚠️ Verification may need manual check"

echo ""
echo "2. Verifying GasDAO..."
echo "   Address: $GAS_DAO"
forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $GAS_DAO_ARGS \
    --watch \
    $GAS_DAO \
    GasDAO || echo "⚠️ Verification may need manual check"

echo ""
echo "3. Verifying AITreasury..."
echo "   Address: $AI_TREASURY"
forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $AI_TREASURY_ARGS \
    --watch \
    $AI_TREASURY \
    AITreasury || echo "⚠️ Verification may need manual check"

echo ""
echo "4. Verifying GaslessRelayer..."
echo "   Address: $GASLESS_RELAYER"
forge verify-contract \
    --chain sepolia \
    --etherscan-api-key $ETHERSCAN_API_KEY \
    --constructor-args $RELAYER_ARGS \
    --watch \
    $GASLESS_RELAYER \
    GaslessRelayer || echo "⚠️ Verification may need manual check"

echo ""
echo "✅ Verification complete!"
echo ""
echo "View verified contracts:"
echo "  FreedomToken: https://sepolia.etherscan.io/address/$FREEDOM_TOKEN#code"
echo "  GasDAO: https://sepolia.etherscan.io/address/$GAS_DAO#code"
echo "  AITreasury: https://sepolia.etherscan.io/address/$AI_TREASURY#code"
echo "  GaslessRelayer: https://sepolia.etherscan.io/address/$GASLESS_RELAYER#code"