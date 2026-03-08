/**
 * Generate 4 test wallets for FreedomToken deployment
 * Run: node scripts/generate_wallets.js
 */

const { generatePrivateKey, privateKeyToAccount } = require('viem/accounts');
const fs = require('fs');

console.log('Generating test wallets for FreedomToken deployment...\n');

const wallets = {
  DEPLOYER: generatePrivateKey(),
  TREASURY_OWNER: generatePrivateKey(),
  AI_BOT: generatePrivateKey(),
  USER_TEST: generatePrivateKey()
};

console.log('WALLETS GENERATED:');
console.log('==================\n');

Object.entries(wallets).forEach(([name, privateKey]) => {
  const account = privateKeyToAccount(privateKey);
  console.log(`${name}:`);
  console.log(`  Address: ${account.address}`);
  console.log(`  Private Key: ${privateKey}`);
  console.log();
});

// Generate .env content
const envContent = `# FreedomToken Environment
# Generated: ${new Date().toISOString()}
# Network: Sepolia Testnet

SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
SEPOLIA_CHAIN_ID=11155111
PIMLICO_API_KEY=your_pimlico_key_here

# Deployer
DEPLOYER_PRIVATE_KEY=${wallets.DEPLOYER}
DEPLOYER_ADDRESS=${privateKeyToAccount(wallets.DEPLOYER).address}

# Treasury Owner
TREASURY_OWNER_KEY=${wallets.TREASURY_OWNER}
TREASURY_OWNER_ADDRESS=${privateKeyToAccount(wallets.TREASURY_OWNER).address}

# AI Bot
AI_BOT_KEY=${wallets.AI_BOT}
AI_BOT_ADDRESS=${privateKeyToAccount(wallets.AI_BOT).address}

# Test User
USER_TEST_KEY=${wallets.USER_TEST}
USER_TEST_ADDRESS=${privateKeyToAccount(wallets.USER_TEST).address}
`;

// Save to file
fs.writeFileSync('.env.generated', envContent);

console.log('✅ Environment file saved to: .env.generated');
console.log();
console.log('NEXT STEPS:');
console.log('1. Get Infura API key: https://infura.io');
console.log('2. Get Pimlico API key: https://pimlico.io');
console.log('3. Copy .env.generated to .env');
console.log('4. Add your API keys to .env');
console.log('5. Fund these addresses with Sepolia ETH:');
Object.entries(wallets).forEach(([name, key]) => {
  console.log(`   - ${name}: ${privateKeyToAccount(key).address}`);
});
console.log('   Get ETH from: https://sepoliafaucet.com');
console.log('6. Run: node scripts/00_verify_env.js');
