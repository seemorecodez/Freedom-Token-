#!/usr/bin/env node
/**
 * Check environment is ready for deployment
 */

import { privateKeyToAccount } from 'viem/accounts';
import { createPublicClient, http } from 'viem';
import { sepolia } from 'viem/chains';
import dotenv from 'dotenv';
import fs from 'fs';

dotenv.config();

const checks = { pass: 0, fail: 0 };

function check(name, condition, critical = true) {
  const status = condition ? '✓' : critical ? '✗' : '⚠';
  console.log(`${status} ${name}`);
  if (condition) checks.pass++;
  else if (critical) checks.fail++;
  return condition;
}

console.log('Environment Check\n');
console.log('==================\n');

// Check .env exists
check('.env file exists', fs.existsSync('.env'));

// Check required vars
const required = ['DEPLOYER_KEY', 'TREASURY_KEY', 'AI_BOT_KEY', 'USER_KEY', 'SEPOLIA_RPC_URL'];
required.forEach(v => check(`Environment variable: ${v}`, !!process.env[v]));

// Validate keys
check('DEPLOYER_KEY is valid hex', /^0x[0-9a-fA-F]{64}$/.test(process.env.DEPLOYER_KEY || ''));

// Check RPC connection
if (process.env.SEPOLIA_RPC_URL) {
  try {
    const client = createPublicClient({
      chain: sepolia,
      transport: http(process.env.SEPOLIA_RPC_URL)
    });
    
    const blockNumber = await client.getBlockNumber();
    check('Can connect to Sepolia', blockNumber > 0n);
    
    // Check balance
    if (process.env.DEPLOYER_KEY) {
      const account = privateKeyToAccount(process.env.DEPLOYER_KEY);
      const balance = await client.getBalance({ address: account.address });
      const eth = Number(balance) / 1e18;
      check(`Deployer has ETH (${eth.toFixed(4)} ETH)`, eth > 0.05);
    }
  } catch (e) {
    check('Can connect to Sepolia', false);
    console.log(`  Error: ${e.message}`);
  }
}

console.log('\n==================');
console.log(`Passed: ${checks.pass}, Failed: ${checks.fail}`);

if (checks.fail === 0) {
  console.log('\n✓ Environment ready');
  console.log('Run: npm run deploy:all');
  process.exit(0);
} else {
  console.log('\n✗ Environment incomplete');
  console.log('Fix the failed checks above');
  process.exit(1);
}
