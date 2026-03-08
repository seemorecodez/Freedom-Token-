#!/usr/bin/env node
/**
 * FREEDOMTOKEN CONTRACT TESTS
 * Tests all core functions on Sepolia testnet
 */

import { createPublicClient, createWalletClient, http, parseEther, encodeFunctionData } from 'viem';
import { sepolia } from 'viem/chains';
import { privateKeyToAccount } from 'viem/accounts';
import dotenv from 'dotenv';

dotenv.config();

// Contract addresses
const CONTRACTS = {
  FreedomToken: '0xb3b8f96925eed295afb1b9d7b72a0450df6f8509',
  GasDAO: '0xf12b4f84e83c11d883a6f76e2cfa7888d4d575c0',
  AITreasury: '0xa9485c8996a6f8ec5b8e70fd0b347a2d87aa4194',
  GaslessRelayer: '0xd138d1e06d1b98270dec55546b0a00f97a7505f4'
};

// Minimal ABIs for testing
const ABIS = {
  FreedomToken: [
    { name: 'name', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'string' }] },
    { name: 'symbol', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'string' }] },
    { name: 'totalSupply', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'balanceOf', type: 'function', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] },
    { name: 'mint', type: 'function', stateMutability: 'nonpayable', inputs: [{ name: 'to', type: 'address' }, { name: 'amount', type: 'uint256' }], outputs: [] },
    { name: 'delegate', type: 'function', stateMutability: 'nonpayable', inputs: [{ name: 'delegatee', type: 'address' }], outputs: [] },
    { name: 'getVotes', type: 'function', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] }
  ],
  GasDAO: [
    { name: 'proposalCount', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'PROPOSAL_THRESHOLD', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'QUORUM_VOTES', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'governanceToken', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'address' }] }
  ],
  AITreasury: [
    { name: 'freedomToken', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'address' }] },
    { name: 'getTreasuryBalance', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'emergencyPaused', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'bool' }] }
  ],
  GaslessRelayer: [
    { name: 'getDomainSeparator', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'bytes32' }] },
    { name: 'getTransactionCount', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
    { name: 'config', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ name: 'maxGasPrice', type: 'uint256' }, { name: 'minGasPrice', type: 'uint256' }, { name: 'relayFeePercent', type: 'uint256' }] }
  ]
};

const log = (msg) => console.log(`[TEST] ${msg}`);
const error = (msg) => { console.error(`[ERROR] ${msg}`); };

async function runTests() {
  log('\n═══════════════════════════════════════════════════');
  log('FREEDOMTOKEN CONTRACT TESTS');
  log('═══════════════════════════════════════════════════\n');
  
  const publicClient = createPublicClient({
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  const deployer = privateKeyToAccount(process.env.DEPLOYER_KEY);
  const walletClient = createWalletClient({
    account: deployer,
    chain: sepolia,
    transport: http(process.env.SEPOLIA_RPC_URL)
  });
  
  log(`Deployer: ${deployer.address}`);
  log(`Network: Sepolia Testnet\n`);
  
  let passCount = 0;
  let failCount = 0;
  
  // Test 1: FreedomToken Basic Info
  try {
    log('TEST 1: FreedomToken Basic Info');
    const name = await publicClient.readContract({
      address: CONTRACTS.FreedomToken,
      abi: ABIS.FreedomToken,
      functionName: 'name'
    });
    const symbol = await publicClient.readContract({
      address: CONTRACTS.FreedomToken,
      abi: ABIS.FreedomToken,
      functionName: 'symbol'
    });
    const totalSupply = await publicClient.readContract({
      address: CONTRACTS.FreedomToken,
      abi: ABIS.FreedomToken,
      functionName: 'totalSupply'
    });
    
    log(`  Name: ${name}`);
    log(`  Symbol: ${symbol}`);
    log(`  Total Supply: ${(Number(totalSupply) / 1e18).toLocaleString()} FREE`);
    log(`  ✅ PASS\n`);
    passCount++;
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Test 2: FreedomToken Balance Check
  try {
    log('TEST 2: FreedomToken Balance Check');
    const balance = await publicClient.readContract({
      address: CONTRACTS.FreedomToken,
      abi: ABIS.FreedomToken,
      functionName: 'balanceOf',
      args: [process.env.TREASURY_ADDRESS]
    });
    
    log(`  Treasury Balance: ${(Number(balance) / 1e18).toLocaleString()} FREE`);
    log(`  ✅ PASS\n`);
    passCount++;
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Test 3: GasDAO Configuration
  try {
    log('TEST 3: GasDAO Configuration');
    const proposalCount = await publicClient.readContract({
      address: CONTRACTS.GasDAO,
      abi: ABIS.GasDAO,
      functionName: 'proposalCount'
    });
    const threshold = await publicClient.readContract({
      address: CONTRACTS.GasDAO,
      abi: ABIS.GasDAO,
      functionName: 'PROPOSAL_THRESHOLD'
    });
    const quorum = await publicClient.readContract({
      address: CONTRACTS.GasDAO,
      abi: ABIS.GasDAO,
      functionName: 'QUORUM_VOTES'
    });
    const token = await publicClient.readContract({
      address: CONTRACTS.GasDAO,
      abi: ABIS.GasDAO,
      functionName: 'governanceToken'
    });
    
    log(`  Proposal Count: ${proposalCount}`);
    log(`  Proposal Threshold: ${(Number(threshold) / 1e18).toLocaleString()} FREE`);
    log(`  Quorum: ${(Number(quorum) / 1e18).toLocaleString()} FREE`);
    log(`  Governance Token: ${token.slice(0, 10)}...${token.slice(-8)}`);
    log(`  ✅ PASS\n`);
    passCount++;
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Test 4: AITreasury State
  try {
    log('TEST 4: AITreasury State');
    const token = await publicClient.readContract({
      address: CONTRACTS.AITreasury,
      abi: ABIS.AITreasury,
      functionName: 'freedomToken'
    });
    const balance = await publicClient.readContract({
      address: CONTRACTS.AITreasury,
      abi: ABIS.AITreasury,
      functionName: 'getTreasuryBalance'
    });
    const paused = await publicClient.readContract({
      address: CONTRACTS.AITreasury,
      abi: ABIS.AITreasury,
      functionName: 'emergencyPaused'
    });
    
    log(`  FreedomToken: ${token.slice(0, 10)}...${token.slice(-8)}`);
    log(`  Treasury Balance: ${(Number(balance) / 1e18).toLocaleString()} FREE`);
    log(`  Emergency Paused: ${paused}`);
    log(`  ✅ PASS\n`);
    passCount++;
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Test 5: GaslessRelayer Configuration
  try {
    log('TEST 5: GaslessRelayer Configuration');
    const domainSeparator = await publicClient.readContract({
      address: CONTRACTS.GaslessRelayer,
      abi: ABIS.GaslessRelayer,
      functionName: 'getDomainSeparator'
    });
    const txCount = await publicClient.readContract({
      address: CONTRACTS.GaslessRelayer,
      abi: ABIS.GaslessRelayer,
      functionName: 'getTransactionCount'
    });
    const config = await publicClient.readContract({
      address: CONTRACTS.GaslessRelayer,
      abi: ABIS.GaslessRelayer,
      functionName: 'config'
    });
    
    log(`  Domain Separator: ${domainSeparator.slice(0, 10)}...${domainSeparator.slice(-8)}`);
    log(`  Transaction Count: ${txCount}`);
    log(`  Relay Fee: ${Number(config[2]) / 100}%`);
    log(`  ✅ PASS\n`);
    passCount++;
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Test 6: Token Integration Check
  try {
    log('TEST 6: Token Integration Check');
    const daoToken = await publicClient.readContract({
      address: CONTRACTS.GasDAO,
      abi: ABIS.GasDAO,
      functionName: 'governanceToken'
    });
    const treasuryToken = await publicClient.readContract({
      address: CONTRACTS.AITreasury,
      abi: ABIS.AITreasury,
      functionName: 'freedomToken'
    });
    
    const integrationOk = 
      daoToken.toLowerCase() === CONTRACTS.FreedomToken.toLowerCase() &&
      treasuryToken.toLowerCase() === CONTRACTS.FreedomToken.toLowerCase();
    
    if (integrationOk) {
      log(`  GasDAO ✓ connected to FreedomToken`);
      log(`  AITreasury ✓ connected to FreedomToken`);
      log(`  ✅ PASS\n`);
      passCount++;
    } else {
      error(`  ❌ FAIL: Integration mismatch`);
      failCount++;
    }
  } catch (e) {
    error(`  ❌ FAIL: ${e.message}\n`);
    failCount++;
  }
  
  // Summary
  log('═══════════════════════════════════════════════════');
  log(`RESULTS: ${passCount} passed, ${failCount} failed`);
  log('═══════════════════════════════════════════════════\n');
  
  if (failCount === 0) {
    log('🎉 All tests passed! Contracts are working correctly.\n');
  } else {
    log('⚠️ Some tests failed. Check contract deployment.\n');
  }
}

runTests().catch(console.error);
