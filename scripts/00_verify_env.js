#!/usr/bin/env node
/**
 * Phase 0: Environment Verification
 * Run this first before any deployment
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CHECKS = {
  passed: 0,
  failed: 0,
  warnings: 0
};

function check(name, test, critical = true) {
  process.stdout.write(`Checking ${name}... `);
  try {
    const result = test();
    if (result) {
      console.log('✅ PASS');
      CHECKS.passed++;
      return true;
    } else {
      console.log(critical ? '❌ FAIL' : '⚠️  WARN');
      if (critical) CHECKS.failed++;
      else CHECKS.warnings++;
      return false;
    }
  } catch (e) {
    console.log(critical ? `❌ FAIL: ${e.message}` : `⚠️  WARN: ${e.message}`);
    if (critical) CHECKS.failed++;
    else CHECKS.warnings++;
    return false;
  }
}

console.log('='.repeat(60));
console.log('FreedomToken Deployment - Phase 0 Verification');
console.log('='.repeat(60));
console.log();

// 1. Node.js version
check('Node.js version >= 18', () => {
  const version = process.version;
  const major = parseInt(version.slice(1).split('.')[0]);
  return major >= 18;
});

// 2. NPM available
check('npm available', () => {
  try {
    execSync('npm --version', { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
});

// 3. .env file exists
check('.env file exists', () => {
  return fs.existsSync('.env');
});

// 4. Required environment variables
let envVars = {};
if (fs.existsSync('.env')) {
  const envContent = fs.readFileSync('.env', 'utf8');
  envContent.split('\n').forEach(line => {
    const match = line.match(/^([A-Z_]+)=(.+)$/);
    if (match) {
      envVars[match[1]] = match[2];
    }
  });
}

const requiredVars = [
  'SEPOLIA_RPC_URL',
  'DEPLOYER_PRIVATE_KEY',
  'DEPLOYER_ADDRESS',
  'TREASURY_OWNER_KEY',
  'TREASURY_OWNER_ADDRESS',
  'AI_BOT_KEY',
  'AI_BOT_ADDRESS',
  'USER_TEST_KEY',
  'USER_TEST_ADDRESS'
];

requiredVars.forEach(varName => {
  check(`Environment variable: ${varName}`, () => {
    return envVars[varName] && envVars[varName].length > 0;
  });
});

// 5. Check private key format
check('Private keys are valid hex', () => {
  const keys = [
    envVars.DEPLOYER_PRIVATE_KEY,
    envVars.TREASURY_OWNER_KEY,
    envVars.AI_BOT_KEY,
    envVars.USER_TEST_KEY
  ];
  
  return keys.every(key => 
    key && /^0x[0-9a-fA-F]{64}$/.test(key)
  );
});

// 6. Check address format
check('Addresses are valid', () => {
  const addresses = [
    envVars.DEPLOYER_ADDRESS,
    envVars.TREASURY_OWNER_ADDRESS,
    envVars.AI_BOT_ADDRESS,
    envVars.USER_TEST_ADDRESS
  ];
  
  return addresses.every(addr => 
    addr && /^0x[0-9a-fA-F]{40}$/.test(addr)
  );
});

// 7. Check directories exist
check('scripts/ directory exists', () => fs.existsSync('scripts'));
check('tests/ directory exists', () => fs.existsSync('tests'));
check('deployments/ directory exists', () => fs.existsSync('deployments'));

// 8. Check .gitignore has .env
check('.gitignore ignores .env', () => {
  if (!fs.existsSync('.gitignore')) return false;
  const content = fs.readFileSync('.gitignore', 'utf8');
  return content.includes('.env');
}, false);

console.log();
console.log('='.repeat(60));
console.log('SUMMARY');
console.log('='.repeat(60));
console.log(`✅ Passed: ${CHECKS.passed}`);
console.log(`❌ Failed: ${CHECKS.failed}`);
console.log(`⚠️  Warnings: ${CHECKS.warnings}`);
console.log();

if (CHECKS.failed === 0) {
  console.log('🎉 ALL CHECKS PASSED!');
  console.log('You can proceed to Phase 1: Infrastructure Deployment');
  console.log();
  console.log('Next step: Run the infrastructure deployment script');
  process.exit(0);
} else {
  console.log('❌ VERIFICATION FAILED');
  console.log('Please fix the failed checks before proceeding.');
  console.log();
  console.log('Common fixes:');
  console.log('  - Copy .env.example to .env and fill in values');
  console.log('  - Generate wallets: node scripts/generate_wallets.js');
  console.log('  - Get Sepolia ETH from faucet');
  console.log('  - Run: mkdir -p scripts tests deployments');
  process.exit(1);
}
