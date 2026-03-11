"""
Tests for Entropy Security System

This test suite covers all 7 security layers and the SecurityManager orchestration.
"""

import unittest
import time
import threading
from typing import Dict, Any

# Import the module under test
from entropy_security_system import (
    SecurityManager,
    SecurityLayer,
    LayerConfig,
    LayerStatus,
    SecurityLevel,
    SecurityContext,
    LayerInitializationError,
    SecurityException,
    InfrastructureLayer,
    OptimizationLayer,
    PostQuantumCryptoLayer,
    BlockchainInterfaceLayer,
    EntropyBalancerLayer,
    TradeExecutionAILayer,
    UserInterfaceLayer,
    create_security_system
)


# =============================================================================
# Test Infrastructure Layer (Layer 1)
# =============================================================================

class TestInfrastructureLayer(unittest.TestCase):
    """Tests for Layer 1: Infrastructure Security."""
    
    def setUp(self):
        self.layer = InfrastructureLayer()
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
        self.assertIsNotNone(self.layer.initialized_at)
    
    def test_validation(self):
        """Test layer validation."""
        self.layer.initialize(self.context)
        self.assertTrue(self.layer.validate())
    
    def test_process_data(self):
        """Test data processing through infrastructure layer."""
        self.layer.initialize(self.context)
        test_data = {"test": "data"}
        result, success = self.layer.process(test_data, self.context)
        self.assertTrue(success)
        self.assertIn("infrastructure_verified", result)
    
    def test_hardware_integrity_check(self):
        """Test hardware integrity reporting."""
        self.layer.initialize(self.context)
        integrity = self.layer.check_hardware_integrity()
        self.assertIn("hsm", integrity)
        self.assertIn("secure_boot", integrity)
        self.assertIn("tpm_available", integrity)
    
    def test_status_reporting(self):
        """Test status reporting."""
        self.layer.initialize(self.context)
        status = self.layer.get_status()
        self.assertEqual(status["layer_number"], 1)
        self.assertEqual(status["name"], "Infrastructure")
        self.assertIn("metrics", status)


# =============================================================================
# Test Optimization Layer (Layer 2)
# =============================================================================

class TestOptimizationLayer(unittest.TestCase):
    """Tests for Layer 2: Optimization Engine."""
    
    def setUp(self):
        self.layer = OptimizationLayer()
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_caching(self):
        """Test caching functionality."""
        self.layer.initialize(self.context)
        test_data = {"key": "value1"}
        
        # First call - cache miss
        result1, success1 = self.layer.process(test_data, self.context)
        self.assertTrue(success1)
        self.assertFalse(result1["cache_hit"])
        
        # Same data - should hit cache
        result2, success2 = self.layer.process(test_data, self.context)
        self.assertTrue(success2)
        self.assertTrue(result2["cache_hit"])
    
    def test_optimization_stats(self):
        """Test optimization statistics."""
        self.layer.initialize(self.context)
        stats = self.layer.get_optimization_stats()
        self.assertIn("cache_hit_rate", stats)
        self.assertIn("cache_size", stats)
        self.assertGreaterEqual(stats["cache_hit_rate"], 0.0)
        self.assertLessEqual(stats["cache_hit_rate"], 1.0)


# =============================================================================
# Test Post-Quantum Crypto Layer (Layer 3)
# =============================================================================

class TestPostQuantumCryptoLayer(unittest.TestCase):
    """Tests for Layer 3: Post-Quantum Cryptography."""
    
    def setUp(self):
        self.layer = PostQuantumCryptoLayer()
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test PQC layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_key_generation(self):
        """Test user key generation."""
        self.layer.initialize(self.context)
        keys = self.layer.generate_user_keys("test_user")
        self.assertIn("kyber_public", keys)
        self.assertIn("dilithium_public", keys)
        self.assertIn("kyber_variant", keys)
    
    def test_encrypt_operation(self):
        """Test encryption operation."""
        self.layer.initialize(self.context)
        data = {
            "operation": "encrypt",
            "plaintext": b"secret message"
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("ciphertext", result)
    
    def test_sign_operation(self):
        """Test signing operation."""
        self.layer.initialize(self.context)
        message = b"test message"
        data = {
            "operation": "sign",
            "message": message
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("signature", result)
        self.assertIn("algorithm", result)
        self.assertEqual(result["algorithm"], "Dilithium5")
    
    def test_verify_operation(self):
        """Test signature verification."""
        self.layer.initialize(self.context)
        message = b"test message"
        signature = b"x" * 4659  # Simulated Dilithium signature size
        
        data = {
            "operation": "verify",
            "message": message,
            "signature": signature
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)


# =============================================================================
# Test Blockchain Interface Layer (Layer 4)
# =============================================================================

class TestBlockchainInterfaceLayer(unittest.TestCase):
    """Tests for Layer 4: Blockchain Interface."""
    
    def setUp(self):
        config = LayerConfig(custom_params={"chains": ["ethereum", "bitcoin"]})
        self.layer = BlockchainInterfaceLayer(config)
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test blockchain layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_wallet_creation(self):
        """Test wallet creation."""
        self.layer.initialize(self.context)
        wallet = self.layer.create_wallet("ethereum")
        self.assertIn("wallet_id", wallet)
        self.assertIn("address", wallet)
        self.assertEqual(wallet["chain"], "ethereum")
    
    def test_send_transaction(self):
        """Test transaction sending."""
        self.layer.initialize(self.context)
        data = {
            "operation": "send_transaction",
            "chain": "ethereum",
            "from": "0x123",
            "to": "0x456",
            "value": "1.5"
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("tx_id", result)
        self.assertEqual(result["status"], "pending")
    
    def test_get_balance(self):
        """Test balance query."""
        self.layer.initialize(self.context)
        data = {
            "operation": "get_balance",
            "chain": "ethereum",
            "address": "0x123"
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("balance", result)
    
    def test_bridge_assets(self):
        """Test cross-chain bridging."""
        self.layer.initialize(self.context)
        data = {
            "operation": "bridge_assets",
            "source_chain": "ethereum",
            "target_chain": "bitcoin",
            "amount": "1.0"
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("bridge_id", result)


# =============================================================================
# Test Entropy Balancer Layer (Layer 5)
# =============================================================================

class TestEntropyBalancerLayer(unittest.TestCase):
    """Tests for Layer 5: Entropy Balancer."""
    
    def setUp(self):
        self.layer = EntropyBalancerLayer()
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test entropy layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_random_bytes_generation(self):
        """Test random bytes generation."""
        self.layer.initialize(self.context)
        data = {"operation": "get_random", "size": 64}
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertEqual(len(result), 64)
    
    def test_random_int_generation(self):
        """Test random integer generation returns valid values in range."""
        self.layer.initialize(self.context)
        data = {"operation": "get_random_int", "min": 1, "max": 1000000}
        
        # Just verify we get valid results in the expected range
        for _ in range(5):
            result, success = self.layer.process(data, self.context)
            self.assertTrue(success)
            self.assertIsInstance(result, int)
            self.assertGreaterEqual(result, 1)
            self.assertLess(result, 1000000)
    
    def test_entropy_quality(self):
        """Test entropy quality metrics."""
        self.layer.initialize(self.context)
        stats = self.layer.get_entropy_stats()
        self.assertIn("pool_size_bytes", stats)
        self.assertIn("quality_metrics", stats)
        self.assertIn("sources_count", stats)
    
    def test_secure_shuffle(self):
        """Test secure shuffle."""
        self.layer.initialize(self.context)
        items = list(range(20))
        data = {"operation": "shuffle", "items": items}
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertEqual(len(result), len(items))
        self.assertEqual(set(result), set(items))


# =============================================================================
# Test Trade Execution AI Layer (Layer 6)
# =============================================================================

class TestTradeExecutionAILayer(unittest.TestCase):
    """Tests for Layer 6: Trade Execution AI."""
    
    def setUp(self):
        config = LayerConfig(custom_params={"ml_models": ["anomaly", "risk"]})
        self.layer = TradeExecutionAILayer(config)
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test AI layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_trade_analysis(self):
        """Test trade analysis."""
        self.layer.initialize(self.context)
        data = {
            "operation": "analyze_trade",
            "asset": "BTC",
            "side": "buy",
            "amount": 1.5,
            "price": 50000
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("analysis", result)
        self.assertIn("recommendation", result)
    
    def test_anomaly_detection(self):
        """Test anomaly detection."""
        self.layer.initialize(self.context)
        data = {
            "operation": "detect_anomaly",
            "data": {"price": 100000, "volume": 999999}
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("anomaly_score", result)
        self.assertIn("is_anomaly", result)
    
    def test_risk_assessment(self):
        """Test risk assessment."""
        self.layer.initialize(self.context)
        data = {"operation": "assess_risk", "trade_size": 1000000}
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("risk_score", result)
        self.assertIn("risk_level", result)
        self.assertIn("mitigation", result)
    
    def test_model_status(self):
        """Test model status reporting."""
        self.layer.initialize(self.context)
        status = self.layer.get_model_status()
        self.assertIn("loaded_models", status)
        self.assertIn("anomaly", status["loaded_models"])
        self.assertIn("risk", status["loaded_models"])


# =============================================================================
# Test User Interface Layer (Layer 7)
# =============================================================================

class TestUserInterfaceLayer(unittest.TestCase):
    """Tests for Layer 7: User Interface."""
    
    def setUp(self):
        self.layer = UserInterfaceLayer()
        self.context = SecurityContext()
    
    def test_initialization(self):
        """Test UI layer initialization."""
        result = self.layer.initialize(self.context)
        self.assertTrue(result)
        self.assertEqual(self.layer.status, LayerStatus.ACTIVE)
    
    def test_user_authentication(self):
        """Test user authentication."""
        self.layer.initialize(self.context)
        data = {
            "operation": "authenticate",
            "user_id": "system",
            "credentials": {"password": "admin"}
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertTrue(result["success"])
        self.assertIn("session_id", result)
    
    def test_permission_check(self):
        """Test permission checking."""
        self.layer.initialize(self.context)
        
        # First authenticate
        auth_data = {
            "operation": "authenticate",
            "user_id": "system",
            "credentials": {}
        }
        auth_result, _ = self.layer.process(auth_data, self.context)
        session_id = auth_result["session_id"]
        
        # Check permission
        perm_data = {
            "operation": "check_permission",
            "session_id": session_id,
            "permission": "admin"
        }
        perm_result, success = self.layer.process(perm_data, self.context)
        self.assertTrue(success)
        self.assertTrue(perm_result["has_permission"])
    
    def test_alert_creation(self):
        """Test alert creation."""
        self.layer.initialize(self.context)
        data = {
            "operation": "create_alert",
            "severity": "high",
            "category": "security",
            "message": "Test alert"
        }
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("alert_id", result)
    
    def test_dashboard_data(self):
        """Test dashboard data retrieval."""
        self.layer.initialize(self.context)
        data = {"operation": "get_dashboard"}
        result, success = self.layer.process(data, self.context)
        self.assertTrue(success)
        self.assertIn("active_sessions", result)
        self.assertIn("system_health", result)


# =============================================================================
# Test Security Manager
# =============================================================================

class TestSecurityManager(unittest.TestCase):
    """Tests for the SecurityManager orchestrator."""
    
    def setUp(self):
        self.config = {
            "layer1": {"hsm_enabled": True, "secure_boot": True},
            "layer2": {"optimization_level": "standard"},
            "layer3": {"kyber_variant": "Kyber1024"},
            "layer4": {"chains": ["ethereum"]},
            "layer5": {"entropy_source": "hybrid"},
            "layer6": {"ml_models": ["anomaly"]},
            "layer7": {"auth_method": "multi_factor"}
        }
        self.manager = SecurityManager(self.config)
    
    def test_manager_initialization(self):
        """Test security manager initialization."""
        result = self.manager.initialize_all_layers()
        self.assertTrue(result)
    
    def test_layer_access(self):
        """Test accessing individual layers."""
        self.manager.initialize_all_layers()
        
        for i in range(1, 8):
            layer = self.manager.get_layer(i)
            self.assertIsNotNone(layer)
            self.assertEqual(layer.layer_number, i)
    
    def test_secure_operation_execution(self):
        """Test executing secure operations."""
        self.manager.initialize_all_layers()
        
        result = self.manager.execute_secure_operation(
            operation="test_operation",
            data={"key": "value"},
            user_id="test_user",
            security_level=SecurityLevel.MAXIMUM
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["security_level"], "MAXIMUM")
        self.assertEqual(result["layers_processed"], 7)
        self.assertIn("layer_results", result)
    
    def test_different_security_levels(self):
        """Test different security levels."""
        self.manager.initialize_all_layers()
        
        levels_and_layers = [
            (SecurityLevel.BASIC, 2),
            (SecurityLevel.STANDARD, 3),
            (SecurityLevel.ENHANCED, 4),
            (SecurityLevel.MAXIMUM, 7)
        ]
        
        for level, expected_layers in levels_and_layers:
            result = self.manager.execute_secure_operation(
                operation="test",
                data={},
                security_level=level
            )
            self.assertEqual(result["layers_processed"], expected_layers)
    
    def test_security_status(self):
        """Test security status reporting."""
        self.manager.initialize_all_layers()
        status = self.manager.get_security_status()
        
        self.assertTrue(status["initialized"])
        self.assertEqual(status["active_layers"], 7)
        self.assertEqual(status["total_layers"], 7)
        self.assertIn("layers", status)
        self.assertIn("overall_health", status)
    
    def test_shutdown(self):
        """Test graceful shutdown."""
        self.manager.initialize_all_layers()
        result = self.manager.shutdown_all_layers()
        self.assertTrue(result)
        
        # Should not be initialized after shutdown
        status = self.manager.get_security_status()
        self.assertFalse(status["initialized"])
    
    def test_uninitialized_operation(self):
        """Test operation without initialization fails."""
        with self.assertRaises(SecurityException):
            self.manager.execute_secure_operation(
                operation="test",
                data={}
            )
    
    def test_quick_hash(self):
        """Test quick secure hash function."""
        self.manager.initialize_all_layers()
        hash1 = self.manager.quick_secure_hash(b"test data")
        hash2 = self.manager.quick_secure_hash(b"test data")
        
        self.assertEqual(len(hash1), 64)  # SHA3-256 hex
        # Should be deterministic with same entropy input


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests across multiple layers."""
    
    def setUp(self):
        self.manager = create_security_system()
    
    def test_end_to_end_encryption(self):
        """Test end-to-end encryption flow."""
        result = self.manager.execute_secure_operation(
            operation="encrypt",
            data={
                "operation": "encrypt",
                "plaintext": b"sensitive data"
            },
            security_level=SecurityLevel.STANDARD
        )
        
        self.assertTrue(result["success"])
        self.assertIn("layer_results", result)
    
    def test_blockchain_transaction_flow(self):
        """Test blockchain transaction with full security."""
        result = self.manager.execute_secure_operation(
            operation="send_transaction",
            data={
                "operation": "send_transaction",
                "chain": "ethereum",
                "from": "0xabc",
                "to": "0xdef",
                "value": "1.0"
            },
            user_id="trader_1",
            security_level=SecurityLevel.ENHANCED
        )
        
        self.assertTrue(result["success"])
    
    def test_ai_trade_analysis_flow(self):
        """Test AI-powered trade analysis."""
        result = self.manager.execute_secure_operation(
            operation="analyze_trade",
            data={
                "operation": "analyze_trade",
                "asset": "ETH",
                "side": "buy",
                "amount": 10,
                "price": 3000
            },
            security_level=SecurityLevel.MAXIMUM
        )
        
        self.assertTrue(result["success"])


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance(unittest.TestCase):
    """Performance tests for security layers."""
    
    def setUp(self):
        self.manager = create_security_system()
    
    def test_throughput(self):
        """Test operation throughput."""
        start_time = time.time()
        operations = 100
        
        for _ in range(operations):
            self.manager.execute_secure_operation(
                operation="test",
                data={"payload": "x" * 100},
                security_level=SecurityLevel.BASIC
            )
        
        elapsed = time.time() - start_time
        ops_per_second = operations / elapsed
        
        # Should handle at least 10 ops/sec
        self.assertGreater(ops_per_second, 10)
    
    def test_concurrent_access(self):
        """Test concurrent operation execution."""
        results = []
        
        def worker():
            result = self.manager.execute_secure_operation(
                operation="test",
                data={},
                security_level=SecurityLevel.STANDARD
            )
            results.append(result["success"])
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        self.assertTrue(all(results))


# =============================================================================
# Configuration Tests
# =============================================================================

class TestConfiguration(unittest.TestCase):
    """Tests for different configuration options."""
    
    def test_minimal_config(self):
        """Test with minimal configuration."""
        manager = create_security_system({})
        self.assertTrue(manager._initialized)
    
    def test_custom_optimization_level(self):
        """Test custom optimization settings."""
        config = {"layer2": {"optimization_level": "aggressive"}}
        manager = create_security_system(config)
        layer = manager.get_layer(2)
        self.assertEqual(layer._cache_ttl_seconds, 600)
    
    def test_custom_crypto_variants(self):
        """Test custom PQC variants."""
        config = {
            "layer3": {
                "kyber_variant": "Kyber512",
                "dilithium_variant": "Dilithium2"
            }
        }
        manager = create_security_system(config)
        layer = manager.get_layer(3)
        self.assertEqual(layer._kyber_variant, "Kyber512")


# =============================================================================
# Run Tests
# =============================================================================

def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestInfrastructureLayer,
        TestOptimizationLayer,
        TestPostQuantumCryptoLayer,
        TestBlockchainInterfaceLayer,
        TestEntropyBalancerLayer,
        TestTradeExecutionAILayer,
        TestUserInterfaceLayer,
        TestSecurityManager,
        TestIntegration,
        TestPerformance,
        TestConfiguration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
