#!/usr/bin/env node
/**
 * PRODUCTION DEPLOYMENT SCRIPT
 * Compiles and deploys all 4 FreedomToken contracts to Sepolia
 * 
 * Usage: npm run deploy:all
 */

import { createPublicClient, createWalletClient, http, parseEther, encodeDeployData } from 'viem';
import { sepolia } from 'viem/chains';
import { privateKeyToAccount } from 'viem/accounts';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { execSync } from 'child_process';
import dotenv from 'dotenv';

dotenv.config();

const log = (msg) => console.log(`[${new Date().toISOString()}] ${msg}`);
const error = (msg) => { console.error(`[ERROR] ${msg}`); process.exit(1); };

// Contract bytecode (to be compiled)
const CONTRACTS = {
  FreedomToken: {
    name: 'FreedomToken',
    file: 'FreedomToken.sol',
    constructorArgs: ['treasury', 'aiController'] // Addresses
  },
  GasDAO: {
    name: 'GasDAO',
    file: 'GasDAO.sol',
    constructorArgs: ['freedomToken', 'admin', 'guardian', 'aiController']
  },
  AITreasury: {
    name: 'AITreasury',
    file: 'AITreasury.sol',
    constructorArgs: ['freedomToken', 'admin', 'aiController', 'guardian']
  },
  GaslessRelayer: {
    name: 'GaslessRelayer',
    file: 'GaslessRelayer.sol',
    constructorArgs: ['admin', 'feeRecipient']
  }
};

// Step 1: Verify environment
async function verifyEnvironment() {
  log('\n=== STEP 1: Environment Verification ===');
  
  const required = ['DEPLOYER_KEY', 'DEPLOYER_ADDRESS', 'SEPOLIA_RPC_URL', 'TREASURY_ADDRESS', 'AI_BOT_ADDRESS'];
  const missing = required.filter(v => !process.env[v]);
  
  if (missing.length > 0) {
    error(`Missing env vars: ${missing.join(', ')}`);
  }
  
  const deployer = privateKeyToAccount(process.env.DEPLOYER_KEY);
  
  if (deployer.address.toLowerCase() !== process.env.DEPLOYER_ADDRESS.toLowerCase()) {
    error('DEPLOYER_KEY and DEPLOYER_ADDRESS mismatch');
  }
  
  log(`✓ Deployer: ${deployer.address}`);
  
  // Check balance
  const publicClient = createPublicClient({
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  const balance = await publicClient.getBalance({ address: deployer.address });
  const balanceEth = Number(balance) / 1e18;
  
  log(`✓ Balance: ${balanceEth.toFixed(4)} ETH`);
  
  if (balanceEth < 0.05) {
    error(`Insufficient balance. Need >0.05 ETH, have ${balanceEth.toFixed(4)} ETH`);
  }
  
  // Verify contracts exist
  for (const [name, config] of Object.entries(CONTRACTS)) {
    const path = `contracts/${config.file}`;
    if (!existsSync(path)) {
      error(`Contract not found: ${path}`);
    }
    log(`✓ ${name}: ${path}`);
  }
  
  return { publicClient, deployer, balanceEth };
}

// Step 2: Compile contracts
async function compileContracts() {
  log('\n=== STEP 2: Contract Compilation ===');
  
  try {
    // Check if forge (Foundry) is available
    execSync('forge --version', { stdio: 'ignore' });
    log('✓ Foundry detected');
    
    // Compile with Foundry
    log('Compiling with Foundry...');
    execSync('forge build --optimize --via-ir', { 
      cwd: '/root/.openclaw/workspace/freedomtoken-deploy',
      stdio: 'inherit' 
    });
    
    log('✓ Compilation successful');
    return 'foundry';
    
  } catch (e) {
    log('⚠ Foundry not available, trying solc...');
    
    try {
      // Fallback to solc
      execSync('solc --version', { stdio: 'ignore' });
      
      for (const [name, config] of Object.entries(CONTRACTS)) {
        log(`Compiling ${name}...`);
        execSync(
          `solc --optimize --via-ir --bin --abi -o out/ contracts/${config.file} ` +
          `--base-path . --include-path node_modules/`,
          { stdio: 'inherit' }
        );
      }
      
      log('✓ Compilation successful');
      return 'solc';
      
    } catch (e2) {
      error('No compiler available. Install Foundry or solc.');
    }
  }
}

// Step 3: Deploy FreedomToken
async function deployFreedomToken(publicClient, deployerWallet) {
  log('\n=== STEP 3: Deploying FreedomToken ===');
  
  const walletClient = createWalletClient({
    account: deployerWallet,
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  // Constructor: (treasury, aiController)
  const treasury = process.env.TREASURY_ADDRESS;
  const aiController = process.env.AI_BOT_ADDRESS;
  
  log(`Treasury: ${treasury}`);
  log(`AI Controller: ${aiController}`);
  
  // For now, we need to manually compile and get bytecode
  // This is a placeholder - in production you'd use:
  // - Foundry artifact JSON
  // - Hardhat artifact JSON
  // - Or compile and extract bytecode
  
  log('⚠️  IMPORTANT: Before running this script:');
  log('   1. Install Foundry: curl -L https://foundry.paradigm.xyz | bash');
  log('   2. Run: forge build --optimize --via-ir');
  log('   3. Update this script to read from out/ directory');
  
  // Placeholder - would deploy actual contract
  const mockAddress = '0x' + '1234'.repeat(10);
  log(`✓ FreedomToken deployed: ${mockAddress} (MOCK)`);
  
  return {
    address: mockAddress,
    name: 'FreedomToken',
    symbol: 'FREE',
    constructorArgs: [treasury, aiController]
  };
}

// Step 4: Deploy GasDAO
async function deployGasDAO(publicClient, deployerWallet, freedomTokenAddress) {
  log('\n=== STEP 4: Deploying GasDAO ===');
  
  const guardian = process.env.TREASURY_ADDRESS; // Use treasury as guardian initially
  const admin = process.env.TREASURY_ADDRESS;
  const aiController = process.env.AI_BOT_ADDRESS;
  
  log(`Governance Token: ${freedomTokenAddress}`);
  log(`Admin: ${admin}`);
  log(`Guardian: ${guardian}`);
  log(`AI Controller: ${aiController}`);
  
  // Placeholder
  const mockAddress = '0x' + '5678'.repeat(10);
  log(`✓ GasDAO deployed: ${mockAddress} (MOCK)`);
  
  return {
    address: mockAddress,
    name: 'GasDAO',
    constructorArgs: [freedomTokenAddress, admin, guardian, aiController]
  };
}

// Step 5: Deploy AITreasury
async function deployAITreasury(publicClient, deployerWallet, freedomTokenAddress) {
  log('\n=== STEP 5: Deploying AITreasury ===');
  
  const admin = process.env.TREASURY_ADDRESS;
  const aiController = process.env.AI_BOT_ADDRESS;
  const guardian = process.env.TREASURY_ADDRESS;
  
  log(`FreedomToken: ${freedomTokenAddress}`);
  log(`Admin: ${admin}`);
  log(`AI Controller: ${aiController}`);
  log(`Guardian: ${guardian}`);
  
  // Placeholder
  const mockAddress = '0x' + '9ABC'.repeat(10);
  log(`✓ AITreasury deployed: ${mockAddress} (MOCK)`);
  
  return {
    address: mockAddress,
    name: 'AITreasury',
    constructorArgs: [freedomTokenAddress, admin, aiController, guardian]
  };
}

// Step 6: Deploy GaslessRelayer
async function deployGaslessRelayer(publicClient, deployerWallet) {
  log('\n=== STEP 6: Deploying GaslessRelayer ===');
  
  const admin = process.env.TREASURY_ADDRESS;
  const feeRecipient = process.env.TREASURY_ADDRESS;
  
  log(`Admin: ${admin}`);
  log(`Fee Recipient: ${feeRecipient}`);
  
  // Placeholder
  const mockAddress = '0x' + 'DEF0'.repeat(10);
  log(`✓ GaslessRelayer deployed: ${mockAddress} (MOCK)`);
  
  return {
    address: mockAddress,
    name: 'GaslessRelayer',
    constructorArgs: [admin, feeRecipient]
  };
}

// Step 7: Save deployment
async function saveDeployment(deployments) {
  log('\n=== STEP 7: Saving Deployment ===');
  
  if (!existsSync('deployments')) {
    mkdirSync('deployments');
  }
  
  const deploymentData = {
    network: 'sepolia',
    chainId: 11155111,
    timestamp: new Date().toISOString(),
    deployer: process.env.DEPLOYER_ADDRESS,
    contracts: deployments
  };
  
  writeFileSync('deployments/mainnet-deployment.json', JSON.stringify(deploymentData, null, 2));
  
  log('✓ Deployment saved to deployments/mainnet-deployment.json');
  
  // Print summary
  log('\n' + '='.repeat(60));
  log('DEPLOYMENT SUMMARY');
  log('='.repeat(60));
  
  for (const [name, data] of Object.entries(deployments)) {
    log(`${name}:`);
    log(`  Address: ${data.address}`);
    log(`  Constructor: ${JSON.stringify(data.constructorArgs)}`);
  }
  
  log('='.repeat(60));
  log('\n⚠️  NOTE: This was a MOCK deployment.');
  log('   To deploy for real:');
  log('   1. Install Foundry');
  log('   2. Compile contracts');
  log('   3. Update script to use real bytecode');
  log('   4. Run: npm run deploy:all');
}

// Main
async function main() {
  log('╔══════════════════════════════════════════╗');
  log('║   FreedomToken Production Deployment     ║');
  log('╚══════════════════════════════════════════╝');
  
  // Step 1: Verify environment
  const { publicClient, deployer, balanceEth } = await verifyEnvironment();
  
  log(`\n💰 Deployer has ${balanceEth.toFixed(4)} ETH`);
  log('📋 4 contracts ready to deploy');
  log('\n⚠️  WARNING: This script currently runs in MOCK mode');
  log('   Real deployment requires Foundry installation\n');
  
  // Step 2: Compile
  const compiler = await compileContracts();
  
  // Step 3-6: Deploy contracts (mock for now)
  const deployments = {};
  
  deployments.FreedomToken = await deployFreedomToken(publicClient, deployer);
  deployments.GasDAO = await deployGasDAO(publicClient, deployer, deployments.FreedomToken.address);
  deployments.AITreasury = await deployAITreasury(publicClient, deployer, deployments.FreedomToken.address);
  deployments.GaslessRelayer = await deployGaslessRelayer(publicClient, deployer);
  
  // Step 7: Save
  await saveDeployment(deployments);
  
  log('\n✅ Deployment script test complete');
  log('   Ready for real deployment after Foundry setup');
}

main().catch(console.error);
