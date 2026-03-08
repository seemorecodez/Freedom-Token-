#!/usr/bin/env node
/**
 * Generate environment file with wallets
 */

import { generatePrivateKey, privateKeyToAccount } from 'viem/accounts';
import fs from 'fs';

console.log('Generating FreedomToken environment...\n');

const wallets = {
  DEPLOYER: generatePrivateKey(),
  TREASURY: generatePrivateKey(),
  AI_BOT: generatePrivateKey(),
  USER: generatePrivateKey()
};

console.log('WALLETS:');
console.log('========\n');

const envVars = [];

Object.entries(wallets).forEach(([name, key]) => {
  const account = privateKeyToAccount(key);
  console.log(`${name}:`);
  console.log(`  Address: ${account.address}`);
  console.log(`  Key: ${key}`);
  console.log();
  
  envVars.push(`${name}_KEY=${key}`);
  envVars.push(`${name}_ADDRESS=${account.address}`);
});

envVars.push('');
envVars.push('# Required: Get from https://infura.io');
envVars.push('SEPOLIA_RPC_URL=');
envVars.push('');
envVars.push('# Optional: Get from https://pimlico.io for gasless tx');
envVars.push('PIMLICO_API_KEY=');

fs.writeFileSync('.env', envVars.join('\n') + '\n');
console.log('✓ Saved to .env');
console.log('✓ Saved example to .env.example\n');

console.log('NEXT:');
console.log('1. Sign up at https://infura.io');
console.log('2. Create Ethereum Sepolia endpoint');
console.log('3. Copy the RPC URL into .env (SEPOLIA_RPC_URL)');
console.log('4. Get Sepolia ETH from https://sepoliafaucet.com');
console.log('   Fund these addresses:');
Object.entries(wallets).forEach(([name, key]) => {
  console.log(`   - ${name}: ${privateKeyToAccount(key).address}`);
});
console.log('5. Run: npm run deploy:all\n');
