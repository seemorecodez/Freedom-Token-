#!/usr/bin/env node
/**
 * FREEDOMTOKEN PRODUCTION DEPLOYMENT
 * Deploys all 4 contracts to Sepolia testnet
 * 
 * Prerequisites:
 * - Foundry installed and contracts compiled
 * - .env configured with DEPLOYER_KEY and SEPOLIA_RPC_URL
 * - Deployer wallet has >0.05 ETH
 * 
 * Usage: npm run deploy:all
 */

import { createPublicClient, createWalletClient, http, parseEther, defineChain } from 'viem';
import { sepolia } from 'viem/chains';
import { privateKeyToAccount } from 'viem/accounts';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import dotenv from 'dotenv';

dotenv.config();

// Contract configurations with real compiled bytecode
const CONTRACTS = {
  FreedomToken: {
    name: 'FreedomToken',
    artifactPath: 'out/FreedomToken.sol/FreedomToken.json',
    constructorArgsTypes: ['address', 'address']
  },
  GasDAO: {
    name: 'GasDAO',
    artifactPath: 'out/GasDAO.sol/GasDAO.json',
    constructorArgsTypes: ['address', 'address', 'address', 'address']
  },
  AITreasury: {
    name: 'AITreasury',
    artifactPath: 'out/AITreasury.sol/AITreasury.json',
    constructorArgsTypes: ['address', 'address', 'address', 'address']
  },
  GaslessRelayer: {
    name: 'GaslessRelayer',
    artifactPath: 'out/GaslessRelayer.sol/GaslessRelayer.json',
    constructorArgsTypes: ['address', 'address']
  }
};

const log = (msg) => console.log(`[${new Date().toISOString()}] ${msg}`);
const error = (msg) => { console.error(`[ERROR] ${msg}`); process.exit(1); };

// Load contract artifact and extract bytecode/ABI
function loadContractArtifact(artifactPath) {
  const fullPath = resolve('/root/.openclaw/workspace/freedomtoken-deploy', artifactPath);
  const artifact = JSON.parse(readFileSync(fullPath, 'utf8'));
  return {
    abi: artifact.abi,
    bytecode: artifact.bytecode.object,
    deployedBytecode: artifact.deployedBytecode.object
  };
}

// Verify environment variables
async function verifyEnvironment() {
  log('\n╔════════════════════════════════════════════════╗');
  log('║   FreedomToken Production Deployment           ║');
  log('╚════════════════════════════════════════════════╝');
  
  log('\n📋 STEP 1: Environment Verification');
  
  const required = [
    'DEPLOYER_KEY',
    'DEPLOYER_ADDRESS',
    'SEPOLIA_RPC_URL',
    'TREASURY_ADDRESS',
    'AI_BOT_ADDRESS',
    'USER_ADDRESS'
  ];
  
  const missing = required.filter(v => !process.env[v]);
  if (missing.length > 0) {
    error(`Missing environment variables: ${missing.join(', ')}`);
  }
  
  // Verify deployer key matches address
  const deployer = privateKeyToAccount(process.env.DEPLOYER_KEY);
  if (deployer.address.toLowerCase() !== process.env.DEPLOYER_ADDRESS.toLowerCase()) {
    error('DEPLOYER_KEY does not match DEPLOYER_ADDRESS');
  }
  
  log(`✓ Deployer: ${deployer.address}`);
  log(`✓ Treasury: ${process.env.TREASURY_ADDRESS}`);
  log(`✓ AI Bot: ${process.env.AI_BOT_ADDRESS}`);
  log(`✓ User: ${process.env.USER_ADDRESS}`);
  
  // Check compiled artifacts exist
  for (const [name, config] of Object.entries(CONTRACTS)) {
    const artifactPath = resolve('/root/.openclaw/workspace/freedomtoken-deploy', config.artifactPath);
    if (!existsSync(artifactPath)) {
      error(`Contract artifact not found: ${artifactPath}. Run 'forge build' first.`);
    }
    log(`✓ ${name} artifact ready`);
  }
  
  // Check balance
  const publicClient = createPublicClient({
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  const balance = await publicClient.getBalance({ address: deployer.address });
  const balanceEth = Number(balance) / 1e18;
  
  log(`\n💰 Deployer Balance: ${balanceEth.toFixed(4)} ETH`);
  
  if (balanceEth < 0.05) {
    error(`Insufficient balance. Need >0.05 ETH, have ${balanceEth.toFixed(4)} ETH\n` +
          `Get Sepolia ETH from: https://sepoliafaucet.com`);
  }
  
  // Estimate gas costs
  const estimatedGas = 0.02; // Rough estimate for 4 contract deployments
  if (balanceEth < estimatedGas) {
    log(`⚠️  Warning: Balance may be insufficient for full deployment`);
    log(`   Estimated need: ~${estimatedGas} ETH`);
    log(`   Current: ${balanceEth.toFixed(4)} ETH`);
  }
  
  return { publicClient, deployer, balanceEth };
}

// Deploy a single contract
async function deployContract(publicClient, deployer, contractName, constructorArgs) {
  log(`\n🚀 Deploying ${contractName}...`);
  
  const config = CONTRACTS[contractName];
  const { abi, bytecode } = loadContractArtifact(config.artifactPath);
  
  const walletClient = createWalletClient({
    account: deployer,
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  // Deploy contract
  const hash = await walletClient.deployContract({
    abi,
    bytecode,
    args: constructorArgs
  });
  
  log(`   Transaction: ${hash}`);
  log(`   Waiting for confirmation...`);
  
  // Wait for receipt
  const receipt = await publicClient.waitForTransactionReceipt({ hash });
  
  if (receipt.status !== 'success') {
    error(`${contractName} deployment failed`);
  }
  
  const address = receipt.contractAddress;
  const gasUsed = receipt.gasUsed;
  const gasCost = Number(receipt.effectiveGasPrice * gasUsed) / 1e18;
  
  log(`✓ ${contractName} deployed at: ${address}`);
  log(`   Gas used: ${gasUsed.toLocaleString()} (~${gasCost.toFixed(6)} ETH)`);
  
  return {
    address,
    hash,
    abi,
    bytecode,
    gasUsed: gasUsed.toString(),
    constructorArgs
  };
}

// Main deployment sequence
async function main() {
  const { publicClient, deployer, balanceEth } = await verifyEnvironment();
  
  log(`\n📊 Pre-deployment Summary:`);
  log(`   Deployer: ${deployer.address}`);
  log(`   Balance: ${balanceEth.toFixed(4)} ETH`);
  log(`   Network: Sepolia Testnet`);
  log(`   Contracts: 4 to deploy`);
  
  const deployments = {};
  let totalGasUsed = 0n;
  
  // Deploy 1: FreedomToken
  deployments.FreedomToken = await deployContract(
    publicClient,
    deployer,
    'FreedomToken',
    [
      process.env.TREASURY_ADDRESS,  // treasury
      process.env.AI_BOT_ADDRESS     // aiController
    ]
  );
  totalGasUsed += BigInt(deployments.FreedomToken.gasUsed);
  
  // Deploy 2: GasDAO (depends on FreedomToken)
  deployments.GasDAO = await deployContract(
    publicClient,
    deployer,
    'GasDAO',
    [
      deployments.FreedomToken.address,  // governanceToken
      process.env.TREASURY_ADDRESS,      // admin
      process.env.TREASURY_ADDRESS,      // guardian (use treasury initially)
      process.env.AI_BOT_ADDRESS         // aiController
    ]
  );
  totalGasUsed += BigInt(deployments.GasDAO.gasUsed);
  
  // Deploy 3: AITreasury (depends on FreedomToken)
  deployments.AITreasury = await deployContract(
    publicClient,
    deployer,
    'AITreasury',
    [
      deployments.FreedomToken.address,  // freedomToken
      process.env.TREASURY_ADDRESS,      // admin
      process.env.AI_BOT_ADDRESS,        // aiController
      process.env.TREASURY_ADDRESS       // guardian
    ]
  );
  totalGasUsed += BigInt(deployments.AITreasury.gasUsed);
  
  // Deploy 4: GaslessRelayer (independent)
  deployments.GaslessRelayer = await deployContract(
    publicClient,
    deployer,
    'GaslessRelayer',
    [
      process.env.TREASURY_ADDRESS,  // admin
      process.env.TREASURY_ADDRESS   // feeRecipient
    ]
  );
  totalGasUsed += BigInt(deployments.GaslessRelayer.gasUsed);
  
  // Save deployment record
  const deploymentRecord = {
    network: 'sepolia',
    chainId: 11155111,
    timestamp: new Date().toISOString(),
    deployer: deployer.address,
    totalGasUsed: totalGasUsed.toString(),
    deployments
  };
  
  // Ensure deployments directory exists
  if (!existsSync('deployments')) {
    mkdirSync('deployments');
  }
  
  const deploymentFile = `deployments/sepolia-${Date.now()}.json`;
  writeFileSync(deploymentFile, JSON.stringify(deploymentRecord, null, 2));
  
  // Print final summary
  log('\n' + '═'.repeat(60));
  log('🎉 DEPLOYMENT COMPLETE');
  log('═'.repeat(60));
  
  log('\n📋 Contract Addresses:');
  for (const [name, data] of Object.entries(deployments)) {
    log(`   ${name}: ${data.address}`);
  }
  
  log(`\n💰 Total Gas Used: ${totalGasUsed.toLocaleString()}`);
  
  log('\n📁 Deployment Record:');
  log(`   ${deploymentFile}`);
  
  log('\n🔗 View on Etherscan:');
  for (const [name, data] of Object.entries(deployments)) {
    log(`   ${name}: https://sepolia.etherscan.io/address/${data.address}`);
  }
  
  log('\n✅ Next Steps:');
  log('   1. Verify contracts on Etherscan');
  log('   2. Run integration tests');
  log('   3. Submit grant applications');
  log('   4. Gather community feedback');
  
  log('\n' + '═'.repeat(60));
}

main().catch((err) => {
  console.error('\n❌ Deployment failed:', err.message);
  process.exit(1);
});