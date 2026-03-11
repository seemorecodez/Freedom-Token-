#!/usr/bin/env python3
"""
Cloud Mining Orchestrator - Simulation Framework

A framework for simulating cloud-based cryptocurrency mining operations.
This is for educational and simulation purposes only - no actual mining occurs.

DISCLAIMER: This framework simulates mining operations for educational purposes.
It does not perform actual cryptocurrency mining or cloud deployments.
"""

import uuid
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum


class Provider(str, Enum):
    """Supported cloud providers."""
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    DIGITALOCEAN = "digitalocean"
    LINODE = "linode"


class InstanceStatus(str, Enum):
    """Instance lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class OrchestratorConfig:
    """Configuration for cloud mining orchestration.
    
    Attributes:
        provider: Cloud provider (aws, gcp, azure, etc.)
        region: Deployment region
        instance_type: VM instance type
        max_cost_hourly: Maximum acceptable cost per hour ($)
        wallet_address: Cryptocurrency wallet address for mining payouts
        pool_url: Mining pool URL with port
        threads: Number of CPU threads to use for mining
        donate_level: XMRig donation level (0-5%)
        tags: Optional metadata tags
    """
    provider: str = "aws"
    region: str = "us-east-1"
    instance_type: str = "t3.medium"
    max_cost_hourly: float = 0.50
    wallet_address: str = ""
    pool_url: str = ""
    threads: int = 4
    donate_level: int = 1
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration values."""
        if self.max_cost_hourly <= 0:
            raise ValueError("max_cost_hourly must be positive")
        if self.threads < 1:
            raise ValueError("threads must be at least 1")
        if self.donate_level < 0 or self.donate_level > 5:
            raise ValueError("donate_level must be between 0 and 5")


@dataclass
class InstanceState:
    """Represents a cloud instance state.
    
    Attributes:
        instance_id: Unique instance identifier
        provider: Cloud provider name
        region: Deployment region
        instance_type: VM instance type
        public_ip: Public IP address
        private_ip: Private IP address
        status: Current instance status
        created_at: Creation timestamp
        hourly_cost: Estimated hourly cost ($)
        metadata: Additional instance metadata
    """
    instance_id: str
    provider: str
    region: str
    instance_type: str
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    status: InstanceStatus = InstanceStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    hourly_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def uptime_seconds(self) -> float:
        """Calculate instance uptime in seconds."""
        if self.status == InstanceStatus.TERMINATED:
            return 0.0
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def estimated_cost(self) -> float:
        """Calculate estimated total cost so far."""
        hours = self.uptime_seconds / 3600
        return hours * self.hourly_cost


@dataclass
class MinerConfig:
    """XMRig miner configuration.
    
    Attributes:
        pool_url: Mining pool URL
        wallet_address: Wallet address for payouts
        worker_name: Worker identifier
        threads: CPU threads to use
        donate_level: Donation percentage
        config_json: Full XMRig config as dict
    """
    pool_url: str
    wallet_address: str
    worker_name: str
    threads: int = 4
    donate_level: int = 1
    config_json: Dict[str, Any] = field(default_factory=dict)
    
    def generate_xmrig_config(self) -> Dict[str, Any]:
        """Generate a complete XMRig configuration dictionary."""
        config = {
            "api": {
                "id": None,
                "worker-id": self.worker_name
            },
            "http": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8080,
                "access-token": None,
                "restricted": True
            },
            "autosave": True,
            "background": False,
            "colors": True,
            "title": True,
            "randomx": {
                "init": -1,
                "init-avx2": -1,
                "mode": "auto",
                "1gb-pages": False,
                "rdmsr": True,
                "wrmsr": True,
                "cache_qos": False,
                "numa": True,
                "scratchpad_prefetch_mode": 1
            },
            "cpu": {
                "enabled": True,
                "huge-pages": True,
                "huge-pages-jit": False,
                "hw-aes": None,
                "priority": None,
                "memory-pool": False,
                "yield": True,
                "max-threads-hint": 100,
                "asm": True,
                "argon2-impl": None,
                "astrobwt-max-size": 550,
                "astrobwt-avx2": False,
                "cn/0": False,
                "cn-lite/0": False
            },
            "opencl": {
                "enabled": False
            },
            "cuda": {
                "enabled": False
            },
            "donate-level": self.donate_level,
            "donate-over-proxy": 1,
            "log-file": None,
            "pools": [
                {
                    "algo": None,
                    "coin": None,
                    "url": self.pool_url,
                    "user": self.wallet_address,
                    "pass": self.worker_name,
                    "rig-id": None,
                    "nicehash": False,
                    "keepalive": True,
                    "enabled": True,
                    "tls": False,
                    "tls-fingerprint": None,
                    "daemon": False,
                    "socks5": None,
                    "self-select": None,
                    "submit-to-origin": False
                }
            ],
            "print-time": 60,
            "health-print-time": 60,
            "dmi": True,
            "retries": 5,
            "retry-pause": 5,
            "syslog": False,
            "tls": {
                "enabled": False,
                "protocols": None,
                "cert": None,
                "cert_key": None,
                "ciphers": None,
                "ciphersuites": None,
                "dhparam": None
            },
            "dns": {
                "ipv6": False,
                "ttl": 30
            },
            "user-agent": None,
            "verbose": 0,
            "watch": True,
            "pause-on-battery": False,
            "pause-on-active": False
        }
        return config


@dataclass
class MiningMetrics:
    """Simulated mining performance metrics.
    
    Attributes:
        hashrate_10s: 10-second average hashrate (H/s)
        hashrate_1m: 1-minute average hashrate (H/s)
        hashrate_15m: 15-minute average hashrate (H/s)
        shares_good: Accepted shares count
        shares_total: Total shares submitted
        uptime_minutes: Mining uptime in minutes
        difficulty: Current mining difficulty
    """
    hashrate_10s: float = 0.0
    hashrate_1m: float = 0.0
    hashrate_15m: float = 0.0
    shares_good: int = 0
    shares_total: int = 0
    uptime_minutes: float = 0.0
    difficulty: int = 0


@dataclass
class ProfitabilityReport:
    """Mining profitability analysis.
    
    Attributes:
        instance_id: Instance identifier
        duration_minutes: Monitoring duration
        estimated_earnings_usd: Estimated mining earnings in USD
        infrastructure_cost_usd: Cloud infrastructure cost in USD
        net_profit_usd: Net profit (earnings - costs)
        roi_percent: Return on investment percentage
        is_profitable: Whether operation is profitable
        recommendations: List of recommendations
    """
    instance_id: str
    duration_minutes: int
    estimated_earnings_usd: float
    infrastructure_cost_usd: float
    net_profit_usd: float
    roi_percent: float
    is_profitable: bool
    recommendations: List[str] = field(default_factory=list)


# Simulated instance pricing (USD per hour)
INSTANCE_PRICING = {
    "aws": {
        "t3.micro": 0.0104,
        "t3.small": 0.0208,
        "t3.medium": 0.0416,
        "t3.large": 0.0832,
        "c5.large": 0.085,
        "c5.xlarge": 0.17,
        "c5.2xlarge": 0.34,
        "c5.4xlarge": 0.68,
        "m5.large": 0.096,
        "m5.xlarge": 0.192,
    },
    "gcp": {
        "n1-standard-1": 0.0475,
        "n1-standard-2": 0.0950,
        "n1-standard-4": 0.1900,
        "n1-standard-8": 0.3800,
        "n2-standard-2": 0.0971,
        "n2-standard-4": 0.1942,
        "e2-medium": 0.0336,
        "e2-standard-2": 0.0671,
    },
    "azure": {
        "Standard_B1s": 0.0104,
        "Standard_B2s": 0.0416,
        "Standard_D2s_v3": 0.096,
        "Standard_D4s_v3": 0.192,
        "Standard_F2s_v2": 0.085,
        "Standard_F4s_v2": 0.169,
    },
    "digitalocean": {
        "s-1vcpu-1gb": 0.00744,
        "s-1vcpu-2gb": 0.01488,
        "s-2vcpu-2gb": 0.02232,
        "s-2vcpu-4gb": 0.04464,
        "s-4vcpu-8gb": 0.08928,
    },
    "linode": {
        "g6-nanode-1": 0.0075,
        "g6-standard-1": 0.015,
        "g6-standard-2": 0.03,
        "g6-standard-4": 0.06,
        "g6-standard-6": 0.12,
    }
}


def _get_instance_hourly_cost(provider: str, instance_type: str) -> float:
    """Get the hourly cost for an instance type.
    
    Args:
        provider: Cloud provider name
        instance_type: Instance type
        
    Returns:
        Hourly cost in USD
    """
    provider_pricing = INSTANCE_PRICING.get(provider.lower(), {})
    return provider_pricing.get(instance_type, 0.05)  # Default to $0.05/hr


def _generate_ip_address() -> str:
    """Generate a random IP address for simulation."""
    return f"{random.randint(10, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def deploy_instance(config: OrchestratorConfig) -> InstanceState:
    """Simulate deploying a cloud instance.
    
    This function simulates the provisioning of a cloud instance
    with the specified configuration. No actual cloud resources are created.
    
    Args:
        config: Orchestrator configuration
        
    Returns:
        InstanceState representing the simulated instance
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Validate provider
    try:
        provider = Provider(config.provider.lower())
    except ValueError:
        raise ValueError(f"Unsupported provider: {config.provider}")
    
    # Generate instance ID
    instance_id = f"{provider.value}-{uuid.uuid4().hex[:8]}"
    
    # Get hourly cost
    hourly_cost = _get_instance_hourly_cost(provider.value, config.instance_type)
    
    # Simulate provisioning delay
    time.sleep(0.1)
    
    instance = InstanceState(
        instance_id=instance_id,
        provider=provider.value,
        region=config.region,
        instance_type=config.instance_type,
        public_ip=_generate_ip_address(),
        private_ip=_generate_ip_address(),
        status=InstanceStatus.RUNNING,
        hourly_cost=hourly_cost,
        metadata={
            "tags": config.tags,
            "launched_by": "cloud-mining-orchestrator",
            "simulation": True
        }
    )
    
    return instance


def configure_miner(instance: InstanceState, config: OrchestratorConfig) -> MinerConfig:
    """Generate XMRig configuration for an instance.
    
    Creates a complete XMRig configuration based on the instance
    specifications and orchestrator settings.
    
    Args:
        instance: The instance to configure miner for
        config: Orchestrator configuration
        
    Returns:
        MinerConfig with generated settings
        
    Raises:
        ValueError: If wallet address or pool URL is missing
    """
    if not config.wallet_address:
        raise ValueError("wallet_address is required for miner configuration")
    if not config.pool_url:
        raise ValueError("pool_url is required for miner configuration")
    
    worker_name = f"worker-{instance.instance_id.split('-')[-1]}"
    
    miner_config = MinerConfig(
        pool_url=config.pool_url,
        wallet_address=config.wallet_address,
        worker_name=worker_name,
        threads=config.threads,
        donate_level=config.donate_level
    )
    
    # Generate full XMRig config
    miner_config.config_json = miner_config.generate_xmrig_config()
    
    return miner_config


def _simulate_hashrate(instance_type: str, threads: int) -> Dict[str, float]:
    """Simulate hashrate based on instance specs.
    
    Args:
        instance_type: Instance type
        threads: Number of threads
        
    Returns:
        Dict with hashrate metrics
    """
    # Base hashrate per thread (simulated H/s)
    base_hashrate = random.uniform(800, 1200)
    
    # Adjust for instance type (rough simulation)
    instance_multiplier = 1.0
    if "xlarge" in instance_type or "standard-4" in instance_type:
        instance_multiplier = 1.5
    elif "2xlarge" in instance_type or "standard-8" in instance_type:
        instance_multiplier = 2.0
    elif "micro" in instance_type or "nanode" in instance_type:
        instance_multiplier = 0.5
    
    hashrate = base_hashrate * threads * instance_multiplier
    
    # Add some variance
    variance = random.uniform(0.95, 1.05)
    
    return {
        "hashrate_10s": hashrate * variance,
        "hashrate_1m": hashrate * random.uniform(0.98, 1.02),
        "hashrate_15m": hashrate * random.uniform(0.97, 1.03)
    }


def monitor_profitability(
    instance: InstanceState, 
    duration_minutes: int = 60,
    xmr_price_usd: float = 150.0
) -> ProfitabilityReport:
    """Monitor and calculate mining profitability.
    
    Simulates mining performance over a specified duration and
    calculates earnings vs infrastructure costs.
    
    Args:
        instance: The instance to monitor
        duration_minutes: Monitoring duration in minutes
        xmr_price_usd: XMR price in USD for earnings calculation
        
    Returns:
        ProfitabilityReport with analysis results
    """
    # Calculate infrastructure cost
    hours = duration_minutes / 60
    infrastructure_cost = instance.hourly_cost * hours
    
    # Simulate mining metrics based on instance specs
    hashrates = _simulate_hashrate(instance.instance_type, 4)
    avg_hashrate = hashrates["hashrate_1m"]
    
    # Simulate earnings (very rough approximation for simulation)
    # In reality this depends on network difficulty, luck, pool fees, etc.
    # Using a simplified model: ~1 XMR per 100 MH/s per month at current diff
    monthly_xmr_per_100mhs = 0.03  # Rough estimate
    hashrate_mhs = avg_hashrate / 1_000_000
    
    # Scale to monitoring duration
    duration_fraction = duration_minutes / (30 * 24 * 60)  # fraction of month
    estimated_xmr = monthly_xmr_per_100mhs * hashrate_mhs * 100 * duration_fraction
    estimated_earnings = estimated_xmr * xmr_price_usd
    
    # Calculate net profit
    net_profit = estimated_earnings - infrastructure_cost
    
    # Calculate ROI
    roi_percent = (net_profit / infrastructure_cost * 100) if infrastructure_cost > 0 else 0
    
    # Generate recommendations
    recommendations = []
    if net_profit < 0:
        recommendations.append("Consider terminating - operation is unprofitable")
        recommendations.append(f"Cost (${infrastructure_cost:.4f}) exceeds earnings (${estimated_earnings:.4f})")
        if instance.hourly_cost > 0.1:
            recommendations.append("Try a smaller instance type to reduce costs")
    else:
        recommendations.append("Operation is profitable")
        if roi_percent < 10:
            recommendations.append("Margin is thin - monitor closely for market changes")
    
    if instance.hourly_cost > 0.2:
        recommendations.append("Consider spot/preemptible instances for cost reduction")
    
    report = ProfitabilityReport(
        instance_id=instance.instance_id,
        duration_minutes=duration_minutes,
        estimated_earnings_usd=estimated_earnings,
        infrastructure_cost_usd=infrastructure_cost,
        net_profit_usd=net_profit,
        roi_percent=roi_percent,
        is_profitable=net_profit > 0,
        recommendations=recommendations
    )
    
    return report


def auto_terminate(
    instances: List[InstanceState], 
    config: OrchestratorConfig,
    force_check: bool = False
) -> List[InstanceState]:
    """Evaluate and mark instances for termination based on cost.
    
    Compares running instances against cost thresholds and returns
    those that should be terminated to control costs.
    
    Args:
        instances: List of instances to evaluate
        config: Orchestrator configuration with thresholds
        force_check: If True, ignore cost threshold and check all
        
    Returns:
        List of instances marked for termination
    """
    to_terminate = []
    
    for instance in instances:
        # Skip already terminated instances
        if instance.status == InstanceStatus.TERMINATED:
            continue
        
        should_terminate = False
        reasons = []
        
        # Check hourly cost threshold
        if instance.hourly_cost > config.max_cost_hourly:
            should_terminate = True
            reasons.append(f"Hourly cost (${instance.hourly_cost:.4f}) exceeds threshold (${config.max_cost_hourly:.4f})")
        
        # Check accumulated cost (terminate if > $10 accumulated in simulation)
        if instance.estimated_cost > 10.0:
            should_terminate = True
            reasons.append(f"Accumulated cost (${instance.estimated_cost:.4f}) exceeds safety limit")
        
        # Simulate profitability check if force_check is enabled
        if force_check and instance.status == InstanceStatus.RUNNING:
            report = monitor_profitability(instance, duration_minutes=30)
            if not report.is_profitable:
                should_terminate = True
                reasons.append("Instance is not profitable based on 30-min analysis")
        
        if should_terminate:
            instance.metadata["termination_reasons"] = reasons
            instance.metadata["marked_for_termination_at"] = datetime.now().isoformat()
            to_terminate.append(instance)
    
    return to_terminate


def terminate_instances(instances: List[InstanceState]) -> List[InstanceState]:
    """Simulate terminating cloud instances.
    
    Args:
        instances: List of instances to terminate
        
    Returns:
        List of terminated instances with updated status
    """
    terminated = []
    
    for instance in instances:
        if instance.status != InstanceStatus.TERMINATED:
            instance.status = InstanceStatus.TERMINATED
            instance.metadata["terminated_at"] = datetime.now().isoformat()
            instance.metadata["final_cost"] = instance.estimated_cost
            terminated.append(instance)
    
    return terminated


def get_instance_recommendations(
    budget_usd: float,
    priority: str = "balanced"  # "cost", "performance", "balanced"
) -> List[Dict[str, Any]]:
    """Get instance type recommendations based on budget.
    
    Args:
        budget_usd: Daily budget in USD
        priority: Optimization priority
        
    Returns:
        List of recommended instance configurations
    """
    recommendations = []
    
    for provider, types in INSTANCE_PRICING.items():
        for instance_type, hourly_cost in types.items():
            daily_cost = hourly_cost * 24
            
            if daily_cost <= budget_usd:
                # Estimate hashrate (simplified)
                threads = 2
                if "xlarge" in instance_type:
                    threads = 4
                elif "2xlarge" in instance_type:
                    threads = 8
                elif "micro" in instance_type or "nanode" in instance_type:
                    threads = 1
                
                estimated_hashrate = threads * 1000  # Rough estimate
                
                score = 0
                if priority == "cost":
                    score = 1 / daily_cost
                elif priority == "performance":
                    score = estimated_hashrate
                else:  # balanced
                    score = estimated_hashrate / daily_cost
                
                recommendations.append({
                    "provider": provider,
                    "instance_type": instance_type,
                    "hourly_cost": hourly_cost,
                    "daily_cost": daily_cost,
                    "estimated_hashrate_hps": estimated_hashrate,
                    "score": score
                })
    
    # Sort by score (descending)
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    
    return recommendations[:5]  # Top 5 recommendations


if __name__ == "__main__":
    # Demo usage
    print("Cloud Mining Orchestrator - Simulation Framework")
    print("=" * 50)
    
    # Create config
    config = OrchestratorConfig(
        provider="aws",
        region="us-east-1",
        instance_type="c5.2xlarge",
        max_cost_hourly=0.34,
        wallet_address="44...",
        pool_url="pool.xmrig.com:3333",
        threads=8
    )
    
    print(f"\nConfiguration:")
    print(f"  Provider: {config.provider}")
    print(f"  Instance: {config.instance_type}")
    print(f"  Max Cost/Hour: ${config.max_cost_hourly}")
    
    # Deploy instance
    instance = deploy_instance(config)
    print(f"\nDeployed Instance:")
    print(f"  ID: {instance.instance_id}")
    print(f"  Public IP: {instance.public_ip}")
    print(f"  Hourly Cost: ${instance.hourly_cost}")
    
    # Configure miner
    miner_config = configure_miner(instance, config)
    print(f"\nMiner Configuration:")
    print(f"  Worker: {miner_config.worker_name}")
    print(f"  Threads: {miner_config.threads}")
    print(f"  Pool: {miner_config.pool_url}")
    
    # Monitor profitability
    report = monitor_profitability(instance, duration_minutes=60)
    print(f"\nProfitability Report (1 hour):")
    print(f"  Earnings: ${report.estimated_earnings_usd:.6f}")
    print(f"  Cost: ${report.infrastructure_cost_usd:.4f}")
    print(f"  Net Profit: ${report.net_profit_usd:.6f}")
    print(f"  ROI: {report.roi_percent:.2f}%")
    print(f"  Profitable: {report.is_profitable}")
    
    # Check auto-terminate
    to_terminate = auto_terminate([instance], config)
    if to_terminate:
        print(f"\nInstances to Terminate: {len(to_terminate)}")
    else:
        print(f"\nNo instances require termination")
    
    # Get recommendations
    print(f"\nTop Recommendations for $5/day budget:")
    recs = get_instance_recommendations(budget_usd=5.0)
    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec['provider']} {rec['instance_type']} - ${rec['daily_cost']:.2f}/day")
