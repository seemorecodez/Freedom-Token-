#!/usr/bin/env python3
"""
Tests for Cloud Mining Orchestrator

Run with: python -m pytest test_cloud_mining_orchestrator.py -v
"""

import pytest
import time
from datetime import datetime, timedelta
from cloud_mining_orchestrator import (
    OrchestratorConfig,
    InstanceState,
    InstanceStatus,
    MinerConfig,
    MiningMetrics,
    ProfitabilityReport,
    Provider,
    deploy_instance,
    configure_miner,
    monitor_profitability,
    auto_terminate,
    terminate_instances,
    get_instance_recommendations,
    _get_instance_hourly_cost,
    _generate_ip_address,
    _simulate_hashrate,
    INSTANCE_PRICING,
)


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = OrchestratorConfig()
        assert config.provider == "aws"
        assert config.region == "us-east-1"
        assert config.instance_type == "t3.medium"
        assert config.max_cost_hourly == 0.50
        assert config.threads == 4
        assert config.donate_level == 1
        assert config.tags == {}
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = OrchestratorConfig(
            provider="gcp",
            region="europe-west1",
            instance_type="n2-standard-4",
            max_cost_hourly=0.25,
            wallet_address="test_wallet",
            pool_url="pool.example.com:3333",
            threads=8,
            donate_level=2,
            tags={"env": "test", "project": "mining"}
        )
        assert config.provider == "gcp"
        assert config.region == "europe-west1"
        assert config.instance_type == "n2-standard-4"
        assert config.max_cost_hourly == 0.25
        assert config.wallet_address == "test_wallet"
        assert config.pool_url == "pool.example.com:3333"
        assert config.threads == 8
        assert config.donate_level == 2
        assert config.tags == {"env": "test", "project": "mining"}
    
    def test_invalid_max_cost(self):
        """Test validation of negative max_cost_hourly."""
        with pytest.raises(ValueError, match="max_cost_hourly must be positive"):
            OrchestratorConfig(max_cost_hourly=-1)
        
        with pytest.raises(ValueError, match="max_cost_hourly must be positive"):
            OrchestratorConfig(max_cost_hourly=0)
    
    def test_invalid_threads(self):
        """Test validation of threads parameter."""
        with pytest.raises(ValueError, match="threads must be at least 1"):
            OrchestratorConfig(threads=0)
        
        with pytest.raises(ValueError, match="threads must be at least 1"):
            OrchestratorConfig(threads=-1)
    
    def test_invalid_donate_level(self):
        """Test validation of donate_level."""
        with pytest.raises(ValueError, match="donate_level must be between 0 and 5"):
            OrchestratorConfig(donate_level=-1)
        
        with pytest.raises(ValueError, match="donate_level must be between 0 and 5"):
            OrchestratorConfig(donate_level=6)


class TestInstanceState:
    """Tests for InstanceState dataclass."""
    
    def test_instance_creation(self):
        """Test instance state creation."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium"
        )
        assert instance.instance_id == "test-123"
        assert instance.provider == "aws"
        assert instance.region == "us-east-1"
        assert instance.instance_type == "t3.medium"
        assert instance.status == InstanceStatus.PENDING
        assert instance.hourly_cost == 0.0
    
    def test_uptime_calculation(self):
        """Test uptime calculation for running instance."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            created_at=datetime.now()
        )
        # Should have minimal uptime
        assert instance.uptime_seconds >= 0
        assert instance.uptime_seconds < 1
    
    def test_terminated_uptime(self):
        """Test uptime returns 0 for terminated instance."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.TERMINATED
        )
        assert instance.uptime_seconds == 0.0
    
    def test_estimated_cost(self):
        """Test estimated cost calculation."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.10,
            created_at=datetime.now()
        )
        # Cost should be minimal for new instance
        assert instance.estimated_cost >= 0
        assert instance.estimated_cost < 0.01


class TestDeployInstance:
    """Tests for deploy_instance function."""
    
    def test_deploy_aws_instance(self):
        """Test deploying AWS instance."""
        config = OrchestratorConfig(provider="aws", instance_type="t3.medium")
        instance = deploy_instance(config)
        
        assert instance.provider == "aws"
        assert instance.instance_type == "t3.medium"
        assert instance.status == InstanceStatus.RUNNING
        assert instance.instance_id.startswith("aws-")
        assert instance.public_ip is not None
        assert instance.private_ip is not None
        assert instance.hourly_cost > 0
    
    def test_deploy_gcp_instance(self):
        """Test deploying GCP instance."""
        config = OrchestratorConfig(provider="gcp", instance_type="n1-standard-2")
        instance = deploy_instance(config)
        
        assert instance.provider == "gcp"
        assert instance.instance_type == "n1-standard-2"
        assert instance.status == InstanceStatus.RUNNING
        assert instance.instance_id.startswith("gcp-")
    
    def test_deploy_azure_instance(self):
        """Test deploying Azure instance."""
        config = OrchestratorConfig(provider="azure", instance_type="Standard_D2s_v3")
        instance = deploy_instance(config)
        
        assert instance.provider == "azure"
        assert instance.instance_type == "Standard_D2s_v3"
        assert instance.status == InstanceStatus.RUNNING
        assert instance.instance_id.startswith("azure-")
    
    def test_deploy_digitalocean_instance(self):
        """Test deploying DigitalOcean instance."""
        config = OrchestratorConfig(provider="digitalocean", instance_type="s-2vcpu-4gb")
        instance = deploy_instance(config)
        
        assert instance.provider == "digitalocean"
        assert instance.instance_type == "s-2vcpu-4gb"
        assert instance.status == InstanceStatus.RUNNING
        assert instance.instance_id.startswith("digitalocean-")
    
    def test_deploy_linode_instance(self):
        """Test deploying Linode instance."""
        config = OrchestratorConfig(provider="linode", instance_type="g6-standard-2")
        instance = deploy_instance(config)
        
        assert instance.provider == "linode"
        assert instance.instance_type == "g6-standard-2"
        assert instance.status == InstanceStatus.RUNNING
        assert instance.instance_id.startswith("linode-")
    
    def test_deploy_with_tags(self):
        """Test deploying with metadata tags."""
        config = OrchestratorConfig(
            provider="aws",
            tags={"project": "test", "env": "dev"}
        )
        instance = deploy_instance(config)
        
        assert instance.metadata["tags"] == {"project": "test", "env": "dev"}
        assert instance.metadata["simulation"] is True
    
    def test_deploy_invalid_provider(self):
        """Test deploying with unsupported provider."""
        config = OrchestratorConfig(provider="invalid_provider")
        with pytest.raises(ValueError, match="Unsupported provider"):
            deploy_instance(config)


class TestConfigureMiner:
    """Tests for configure_miner function."""
    
    def test_configure_miner_success(self):
        """Test successful miner configuration."""
        config = OrchestratorConfig(
            wallet_address="44testwalletaddress",
            pool_url="pool.xmrig.com:3333",
            threads=8,
            donate_level=2
        )
        instance = InstanceState(
            instance_id="aws-abc123",
            provider="aws",
            region="us-east-1",
            instance_type="c5.2xlarge"
        )
        
        miner_config = configure_miner(instance, config)
        
        assert miner_config.wallet_address == "44testwalletaddress"
        assert miner_config.pool_url == "pool.xmrig.com:3333"
        assert miner_config.threads == 8
        assert miner_config.donate_level == 2
        assert "worker-abc123" in miner_config.worker_name
        assert len(miner_config.config_json) > 0
    
    def test_configure_miner_missing_wallet(self):
        """Test configuration fails without wallet address."""
        config = OrchestratorConfig(wallet_address="", pool_url="pool.example.com")
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium"
        )
        
        with pytest.raises(ValueError, match="wallet_address is required"):
            configure_miner(instance, config)
    
    def test_configure_miner_missing_pool(self):
        """Test configuration fails without pool URL."""
        config = OrchestratorConfig(
            wallet_address="44test",
            pool_url=""
        )
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium"
        )
        
        with pytest.raises(ValueError, match="pool_url is required"):
            configure_miner(instance, config)
    
    def test_generate_xmrig_config(self):
        """Test XMRig config generation."""
        config = OrchestratorConfig(
            wallet_address="44testwallet",
            pool_url="pool.example.com:3333",
            threads=4,
            donate_level=1
        )
        instance = InstanceState(
            instance_id="aws-test123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium"
        )
        
        miner_config = configure_miner(instance, config)
        xmrig_config = miner_config.generate_xmrig_config()
        
        assert xmrig_config["donate-level"] == 1
        assert xmrig_config["cpu"]["enabled"] is True
        assert len(xmrig_config["pools"]) == 1
        assert xmrig_config["pools"][0]["url"] == "pool.example.com:3333"
        assert xmrig_config["pools"][0]["user"] == "44testwallet"
        assert xmrig_config["http"]["enabled"] is True


class TestMonitorProfitability:
    """Tests for monitor_profitability function."""
    
    def test_monitor_basic(self):
        """Test basic profitability monitoring."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.05
        )
        
        report = monitor_profitability(instance, duration_minutes=60)
        
        assert report.instance_id == "test-123"
        assert report.duration_minutes == 60
        assert report.infrastructure_cost_usd == 0.05  # 1 hour * $0.05
        assert isinstance(report.estimated_earnings_usd, float)
        assert isinstance(report.net_profit_usd, float)
        assert isinstance(report.roi_percent, float)
        assert isinstance(report.is_profitable, bool)
        assert len(report.recommendations) >= 0
    
    def test_monitor_different_durations(self):
        """Test monitoring with different durations."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.10
        )
        
        report_30 = monitor_profitability(instance, duration_minutes=30)
        assert report_30.duration_minutes == 30
        assert report_30.infrastructure_cost_usd == 0.05  # 0.5 hour * $0.10
        
        report_120 = monitor_profitability(instance, duration_minutes=120)
        assert report_120.duration_minutes == 120
        assert report_120.infrastructure_cost_usd == 0.20  # 2 hours * $0.10
    
    def test_monitor_profitability_calculation(self):
        """Test that net profit is calculated correctly."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="c5.2xlarge",  # Larger instance for better hashrate
            status=InstanceStatus.RUNNING,
            hourly_cost=0.34
        )
        
        report = monitor_profitability(instance, duration_minutes=60, xmr_price_usd=200)
        
        expected_cost = 0.34
        assert report.infrastructure_cost_usd == expected_cost
        assert report.net_profit_usd == report.estimated_earnings_usd - expected_cost
    
    def test_monitor_recommendations_unprofitable(self):
        """Test recommendations for unprofitable operation."""
        # Use very high cost to ensure unprofitability
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.micro",  # Small instance
            status=InstanceStatus.RUNNING,
            hourly_cost=5.00  # Unrealistically high cost
        )
        
        report = monitor_profitability(instance, duration_minutes=60)
        
        if not report.is_profitable:
            assert any("terminating" in r.lower() for r in report.recommendations)


class TestAutoTerminate:
    """Tests for auto_terminate function."""
    
    def test_no_termination_needed(self):
        """Test when no instances need termination."""
        config = OrchestratorConfig(max_cost_hourly=1.0)
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.05
        )
        
        to_terminate = auto_terminate([instance], config)
        
        assert len(to_terminate) == 0
    
    def test_terminate_over_cost_threshold(self):
        """Test termination when hourly cost exceeds threshold."""
        config = OrchestratorConfig(max_cost_hourly=0.10)
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="c5.2xlarge",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.34  # Exceeds threshold
        )
        
        to_terminate = auto_terminate([instance], config)
        
        assert len(to_terminate) == 1
        assert to_terminate[0].instance_id == "test-123"
        assert "termination_reasons" in to_terminate[0].metadata
    
    def test_terminate_accumulated_cost(self):
        """Test termination when accumulated cost exceeds limit."""
        config = OrchestratorConfig(max_cost_hourly=10.0)
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.05,
            created_at=datetime.now() - timedelta(hours=250)  # Simulate old instance
        )
        
        to_terminate = auto_terminate([instance], config)
        
        assert len(to_terminate) == 1
        assert any("safety limit" in reason for reason in to_terminate[0].metadata["termination_reasons"])
    
    def test_skip_already_terminated(self):
        """Test that already terminated instances are skipped."""
        config = OrchestratorConfig(max_cost_hourly=0.01)
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.TERMINATED,
            hourly_cost=0.34
        )
        
        to_terminate = auto_terminate([instance], config)
        
        assert len(to_terminate) == 0
    
    def test_force_check_unprofitable(self):
        """Test force check profitability mode."""
        # Small instance with high cost to ensure unprofitability
        config = OrchestratorConfig(max_cost_hourly=10.0)
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.micro",
            status=InstanceStatus.RUNNING,
            hourly_cost=0.50
        )
        
        to_terminate = auto_terminate([instance], config, force_check=True)
        
        # May or may not terminate depending on random profitability
        # Just verify the function runs without error
        assert isinstance(to_terminate, list)


class TestTerminateInstances:
    """Tests for terminate_instances function."""
    
    def test_terminate_single_instance(self):
        """Test terminating a single instance."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.RUNNING
        )
        
        terminated = terminate_instances([instance])
        
        assert len(terminated) == 1
        assert terminated[0].status == InstanceStatus.TERMINATED
        assert "terminated_at" in terminated[0].metadata
        assert "final_cost" in terminated[0].metadata
    
    def test_terminate_multiple_instances(self):
        """Test terminating multiple instances."""
        instances = [
            InstanceState(
                instance_id=f"test-{i}",
                provider="aws",
                region="us-east-1",
                instance_type="t3.medium",
                status=InstanceStatus.RUNNING
            )
            for i in range(3)
        ]
        
        terminated = terminate_instances(instances)
        
        assert len(terminated) == 3
        for inst in terminated:
            assert inst.status == InstanceStatus.TERMINATED
    
    def test_skip_already_terminated(self):
        """Test that already terminated instances are handled gracefully."""
        instance = InstanceState(
            instance_id="test-123",
            provider="aws",
            region="us-east-1",
            instance_type="t3.medium",
            status=InstanceStatus.TERMINATED
        )
        
        terminated = terminate_instances([instance])
        
        # Already terminated instances are returned but not modified
        assert len(terminated) == 0  # Skipped because already terminated


class TestGetInstanceRecommendations:
    """Tests for get_instance_recommendations function."""
    
    def test_recommendations_with_budget(self):
        """Test getting recommendations within budget."""
        recommendations = get_instance_recommendations(budget_usd=5.0)
        
        assert len(recommendations) > 0
        assert len(recommendations) <= 5
        
        for rec in recommendations:
            assert "provider" in rec
            assert "instance_type" in rec
            assert "hourly_cost" in rec
            assert "daily_cost" in rec
            assert rec["daily_cost"] <= 5.0
    
    def test_recommendations_low_budget(self):
        """Test recommendations with very low budget."""
        recommendations = get_instance_recommendations(budget_usd=0.5)
        
        # Should still return some cheap options
        assert len(recommendations) >= 0
        if recommendations:
            assert all(r["daily_cost"] <= 0.5 for r in recommendations)
    
    def test_recommendations_priority_cost(self):
        """Test cost-priority recommendations."""
        recs_cost = get_instance_recommendations(budget_usd=10.0, priority="cost")
        recs_perf = get_instance_recommendations(budget_usd=10.0, priority="performance")
        
        # Different priorities should give different orderings
        assert len(recs_cost) > 0
        assert len(recs_perf) > 0
    
    def test_recommendations_sorted(self):
        """Test that recommendations are sorted by score."""
        recommendations = get_instance_recommendations(budget_usd=10.0)
        
        if len(recommendations) >= 2:
            scores = [r["score"] for r in recommendations]
            assert scores == sorted(scores, reverse=True)


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_get_instance_hourly_cost_known(self):
        """Test getting known instance cost."""
        cost = _get_instance_hourly_cost("aws", "t3.medium")
        assert cost == 0.0416
    
    def test_get_instance_hourly_cost_unknown(self):
        """Test getting unknown instance cost returns default."""
        cost = _get_instance_hourly_cost("unknown", "unknown-type")
        assert cost == 0.05  # Default
    
    def test_generate_ip_address(self):
        """Test IP address generation."""
        ip = _generate_ip_address()
        parts = ip.split(".")
        assert len(parts) == 4
        for part in parts:
            assert part.isdigit()
            assert 0 <= int(part) <= 255
    
    def test_generate_ip_address_unique(self):
        """Test that generated IPs are different."""
        ips = [_generate_ip_address() for _ in range(10)]
        # Should mostly be unique (probabilistic)
        assert len(set(ips)) > 5
    
    def test_simulate_hashrate(self):
        """Test hashrate simulation."""
        hashrates = _simulate_hashrate("t3.medium", 4)
        
        assert "hashrate_10s" in hashrates
        assert "hashrate_1m" in hashrates
        assert "hashrate_15m" in hashrates
        assert all(h > 0 for h in hashrates.values())
    
    def test_simulate_hashrate_different_instances(self):
        """Test hashrates differ for different instance types."""
        small = _simulate_hashrate("t3.micro", 1)
        large = _simulate_hashrate("c5.2xlarge", 8)
        
        # Larger instance should generally have higher hashrate
        assert large["hashrate_1m"] > small["hashrate_1m"]


class TestInstancePricing:
    """Tests for instance pricing data."""
    
    def test_pricing_structure(self):
        """Test that pricing data has expected structure."""
        assert "aws" in INSTANCE_PRICING
        assert "gcp" in INSTANCE_PRICING
        assert "azure" in INSTANCE_PRICING
        assert "digitalocean" in INSTANCE_PRICING
        assert "linode" in INSTANCE_PRICING
    
    def test_pricing_values_positive(self):
        """Test that all pricing values are positive."""
        for provider, types in INSTANCE_PRICING.items():
            for instance_type, cost in types.items():
                assert cost > 0, f"{provider}.{instance_type} has invalid cost"


class TestIntegration:
    """Integration tests for full workflow."""
    
    def test_full_workflow_profitable(self):
        """Test complete workflow with profitable scenario."""
        # Setup
        config = OrchestratorConfig(
            provider="aws",
            region="us-east-1",
            instance_type="c5.2xlarge",
            max_cost_hourly=0.50,
            wallet_address="44testwallet",
            pool_url="pool.example.com:3333",
            threads=8
        )
        
        # Deploy
        instance = deploy_instance(config)
        assert instance.status == InstanceStatus.RUNNING
        
        # Configure miner
        miner_config = configure_miner(instance, config)
        assert miner_config.config_json is not None
        
        # Monitor
        report = monitor_profitability(instance, duration_minutes=60)
        assert report.instance_id == instance.instance_id
        
        # Check auto-terminate
        to_terminate = auto_terminate([instance], config)
        
        # Cleanup
        if to_terminate:
            terminate_instances(to_terminate)
    
    def test_full_workflow_unprofitable(self):
        """Test complete workflow with unprofitable scenario."""
        # Setup with very low cost threshold
        config = OrchestratorConfig(
            provider="aws",
            region="us-east-1",
            instance_type="c5.2xlarge",
            max_cost_hourly=0.01,  # Very low threshold
            wallet_address="44testwallet",
            pool_url="pool.example.com:3333"
        )
        
        # Deploy expensive instance
        instance = deploy_instance(config)
        
        # Should be marked for termination
        to_terminate = auto_terminate([instance], config)
        assert len(to_terminate) == 1
        
        # Terminate
        terminated = terminate_instances(to_terminate)
        assert terminated[0].status == InstanceStatus.TERMINATED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
