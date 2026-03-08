#!/usr/bin/env node
/**
 * Autonomous Deployment Bootstrap
 * Run once: node bootstrap.js
 * Then: npm run deploy:all
 */

const fs = require('fs');
const { execSync } = require('child_process');
const path = require('path');

console.log('FreedomToken Autonomous Deployment Bootstrap\n');

// Check if already bootstrapped
if (fs.existsSync('package.json')) {
  console.log('✓ Already bootstrapped');
  console.log('Run: npm install && npm run deploy:all');
  process.exit(0);
}

// Create package.json
const packageJson = {
  "name": "freedomtoken-deploy",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "env:check": "node scripts/check-env.js",
    "env:generate": "node scripts/generate-env.js",
    "faucet": "node scripts/faucet.js",
    "deploy:all": "npm run env:check && node scripts/deploy-all.js",
    "deploy:phase1": "node scripts/phase1-infrastructure.js",
    "deploy:phase2": "node scripts/phase2-token.js",
    "deploy:phase3": "node scripts/phase3-gasless.js",
    "deploy:phase4": "node scripts/phase4-treasury.js",
    "test": "vitest run",
    "test:watch": "vitest",
    "verify": "node scripts/verify-all.js"
  },
  "dependencies": {
    "@metamask/smart-accounts-kit": "^0.3.0",
    "viem": "^2.7.0",
    "permissionless": "^0.1.0",
    "dotenv": "^16.4.0",
    "node-fetch": "^3.3.0"
  },
  "devDependencies": {
    "vitest": "^1.2.0"
  }
};

fs.writeFileSync('package.json', JSON.stringify(packageJson, null, 2));
console.log('✓ Created package.json');

// Create .gitignore
fs.writeFileSync('.gitignore', `.env
.env.local
node_modules/
deployments/*.json
*.log
.DS_Store
`);
console.log('✓ Created .gitignore');

// Create directories
['scripts', 'tests', 'deployments', 'contracts'].forEach(dir => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
});
console.log('✓ Created directories');

console.log('\nNext steps:');
console.log('1. npm install');
console.log('2. npm run env:generate');
console.log('3. Get Sepolia ETH (check .env for addresses)');
console.log('4. npm run deploy:all');
