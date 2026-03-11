"""
Wealth Distributor - Automated Treasury Management and Payout Distribution
Handles automated fund distribution with multiple strategies and scheduling.
"""

import re
import time
import uuid
import hashlib
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WealthDistributor")


class DistributionStrategy(Enum):
    EQUAL = "equal"
    WEIGHTED = "weighted"
    PERFORMANCE = "performance"


class DistributionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DistributionConfig:
    """Configuration for automated wealth distribution"""
    strategy: DistributionStrategy = DistributionStrategy.EQUAL
    threshold: float = 0.0  # Minimum treasury balance to trigger distribution
    interval: str = "0 0 * * *"  # Cron-like schedule expression
    auto_reinvest_percent: float = 0.0  # Percentage to compound back
    max_payout: Optional[float] = None  # Maximum per recipient
    min_payout: float = 0.01  # Minimum to include
    timezone: str = "UTC"
    enabled: bool = True


@dataclass
class Recipient:
    """A distribution recipient"""
    id: str
    name: str
    address: str
    weight: float = 1.0
    performance_score: float = 1.0  # For performance-based strategy
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class DistributionRecord:
    """Record of a single distribution"""
    id: str
    timestamp: float
    treasury_balance: float
    total_distributed: float
    reinvested_amount: float
    recipients: Dict[str, float]  # recipient_id -> amount
    status: DistributionStatus
    strategy: str
    error_message: Optional[str] = None
    completed_at: Optional[float] = None
    tx_hash: Optional[str] = None


@dataclass
class ScheduledDistribution:
    """A scheduled distribution job"""
    id: str
    next_run: float
    config: DistributionConfig
    last_run: Optional[float] = None
    run_count: int = 0


class RecipientManager:
    """
    Component 1: Recipient Management
    Add, remove, and update distribution recipients
    """
    
    def __init__(self):
        self.recipients: Dict[str, Recipient] = {}
        self._lock = threading.Lock()
    
    def add_recipient(
        self,
        name: str,
        address: str,
        weight: float = 1.0,
        performance_score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Recipient:
        """
        Add a new recipient
        
        Args:
            name: Recipient identifier/name
            address: Wallet/destination address
            weight: Distribution weight (for weighted strategy)
            performance_score: Performance multiplier
            metadata: Additional recipient data
            
        Returns:
            Created Recipient object
        """
        with self._lock:
            recipient_id = self._generate_id(name, address)
            
            recipient = Recipient(
                id=recipient_id,
                name=name,
                address=address,
                weight=weight,
                performance_score=performance_score,
                metadata=metadata or {}
            )
            
            self.recipients[recipient_id] = recipient
            logger.info(f"Added recipient: {name} ({recipient_id[:8]}...)")
            return recipient
    
    def remove_recipient(self, recipient_id: str) -> bool:
        """
        Remove a recipient by ID
        
        Args:
            recipient_id: Recipient to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if recipient_id in self.recipients:
                del self.recipients[recipient_id]
                logger.info(f"Removed recipient: {recipient_id[:8]}...")
                return True
            return False
    
    def update_recipient(
        self,
        recipient_id: str,
        **kwargs
    ) -> Optional[Recipient]:
        """
        Update recipient properties
        
        Args:
            recipient_id: Recipient to update
            **kwargs: Fields to update
            
        Returns:
            Updated Recipient or None if not found
        """
        with self._lock:
            if recipient_id not in self.recipients:
                return None
            
            recipient = self.recipients[recipient_id]
            
            allowed_fields = {'name', 'address', 'weight', 
                            'performance_score', 'active', 'metadata'}
            
            for key, value in kwargs.items():
                if key in allowed_fields:
                    setattr(recipient, key, value)
            
            logger.info(f"Updated recipient: {recipient_id[:8]}...")
            return recipient
    
    def get_recipient(self, recipient_id: str) -> Optional[Recipient]:
        """Get a recipient by ID"""
        return self.recipients.get(recipient_id)
    
    def get_active_recipients(self) -> List[Recipient]:
        """Get all active recipients"""
        return [r for r in self.recipients.values() if r.active]
    
    def list_recipients(self) -> List[Recipient]:
        """List all recipients"""
        return list(self.recipients.values())
    
    def _generate_id(self, name: str, address: str) -> str:
        """Generate unique recipient ID"""
        data = f"{name}:{address}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class DistributionCalculator:
    """
    Component 2: Distribution Calculation
    Determines payouts per recipient based on strategy
    """
    
    def __init__(self, config: DistributionConfig):
        self.config = config
    
    def calculate_distribution(
        self,
        treasury_balance: float,
        recipients: List[Recipient]
    ) -> Dict[str, float]:
        """
        Calculate distribution amounts for each recipient
        
        Args:
            treasury_balance: Available funds
            recipients: List of active recipients
            
        Returns:
            Dict mapping recipient_id to amount
        """
        if not recipients or treasury_balance <= 0:
            return {}
        
        # Check threshold
        if treasury_balance < self.config.threshold:
            logger.info(f"Treasury (${treasury_balance}) below threshold (${self.config.threshold})")
            return {}
        
        # Calculate amount available for distribution
        reinvest_amount = treasury_balance * (self.config.auto_reinvest_percent / 100)
        available = treasury_balance - reinvest_amount
        
        # Apply strategy
        if self.config.strategy == DistributionStrategy.EQUAL:
            amounts = self._calculate_equal(available, recipients)
        elif self.config.strategy == DistributionStrategy.WEIGHTED:
            amounts = self._calculate_weighted(available, recipients)
        elif self.config.strategy == DistributionStrategy.PERFORMANCE:
            amounts = self._calculate_performance(available, recipients)
        else:
            amounts = self._calculate_equal(available, recipients)
        
        # Apply min/max constraints
        amounts = self._apply_constraints(amounts)
        
        return amounts
    
    def _calculate_equal(
        self,
        available: float,
        recipients: List[Recipient]
    ) -> Dict[str, float]:
        """Equal distribution among all recipients"""
        if not recipients:
            return {}
        
        per_recipient = available / len(recipients)
        return {r.id: per_recipient for r in recipients}
    
    def _calculate_weighted(
        self,
        available: float,
        recipients: List[Recipient]
    ) -> Dict[str, float]:
        """Weighted distribution based on recipient weights"""
        if not recipients:
            return {}
        
        total_weight = sum(r.weight for r in recipients)
        
        if total_weight == 0:
            return self._calculate_equal(available, recipients)
        
        return {
            r.id: (r.weight / total_weight) * available
            for r in recipients
        }
    
    def _calculate_performance(
        self,
        available: float,
        recipients: List[Recipient]
    ) -> Dict[str, float]:
        """Performance-based distribution"""
        if not recipients:
            return {}
        
        # Calculate performance-weighted scores
        total_score = sum(r.weight * r.performance_score for r in recipients)
        
        if total_score == 0:
            return self._calculate_equal(available, recipients)
        
        return {
            r.id: ((r.weight * r.performance_score) / total_score) * available
            for r in recipients
        }
    
    def _apply_constraints(self, amounts: Dict[str, float]) -> Dict[str, float]:
        """Apply min/max payout constraints"""
        result = {}
        
        for recipient_id, amount in amounts.items():
            # Apply max payout
            if self.config.max_payout is not None:
                amount = min(amount, self.config.max_payout)
            
            # Apply min payout (filter out if below)
            if amount >= self.config.min_payout:
                result[recipient_id] = round(amount, 8)
        
        return result


class AutoReinvestment:
    """
    Component 3: Auto Reinvestment
    Handles compounding logic for treasury growth
    """
    
    def __init__(self, config: DistributionConfig):
        self.config = config
        self.reinvestment_history: List[Dict] = []
    
    def calculate_reinvestment(self, treasury_balance: float) -> float:
        """
        Calculate amount to reinvest
        
        Args:
            treasury_balance: Current treasury balance
            
        Returns:
            Amount to reinvest
        """
        return treasury_balance * (self.config.auto_reinvest_percent / 100)
    
    def apply_compounding(
        self,
        treasury_balance: float,
        distribution_amounts: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Apply compounding to distribution
        
        Args:
            treasury_balance: Current balance
            distribution_amounts: Planned distributions
            
        Returns:
            Compounding result with new balances
        """
        reinvest_amount = self.calculate_reinvestment(treasury_balance)
        total_distribution = sum(distribution_amounts.values())
        
        new_treasury = treasury_balance - total_distribution
        # Reinvest amount stays in treasury
        
        result = {
            "original_balance": treasury_balance,
            "reinvested_amount": reinvest_amount,
            "total_distributed": total_distribution,
            "new_treasury_balance": new_treasury,
            "projected_growth": reinvest_amount
        }
        
        self.reinvestment_history.append({
            "timestamp": time.time(),
            **result
        })
        
        return result
    
    def get_projected_growth(
        self,
        initial_balance: float,
        periods: int,
        avg_yield_per_period: float = 0.0
    ) -> List[Dict[str, float]]:
        """
        Project treasury growth over multiple periods
        
        Args:
            initial_balance: Starting balance
            periods: Number of periods to project
            avg_yield_per_period: Expected yield per period (as decimal)
            
        Returns:
            List of projected balances per period
        """
        projections = []
        balance = initial_balance
        
        for period in range(periods):
            reinvest = balance * (self.config.auto_reinvest_percent / 100)
            yield_amount = balance * avg_yield_per_period
            
            balance = balance + yield_amount  # Assumes distributions are external
            
            projections.append({
                "period": period + 1,
                "starting_balance": balance - yield_amount,
                "yield": yield_amount,
                "reinvested": reinvest,
                "ending_balance": balance
            })
        
        return projections


class Scheduler:
    """
    Component 4: Distribution Scheduler
    Cron-like scheduling for automated distributions
    """
    
    def __init__(self):
        self.scheduled_jobs: Dict[str, ScheduledDistribution] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def schedule_distribution(
        self,
        config: DistributionConfig,
        job_id: Optional[str] = None
    ) -> str:
        """
        Schedule a recurring distribution
        
        Args:
            config: Distribution configuration
            job_id: Optional custom job ID
            
        Returns:
            Job ID
        """
        job_id = job_id or str(uuid.uuid4())[:8]
        
        with self._lock:
            next_run = self._calculate_next_run(config.interval)
            
            job = ScheduledDistribution(
                id=job_id,
                next_run=next_run,
                config=config
            )
            
            self.scheduled_jobs[job_id] = job
            logger.info(f"Scheduled distribution job: {job_id}")
            return job_id
    
    def cancel_schedule(self, job_id: str) -> bool:
        """Cancel a scheduled job"""
        with self._lock:
            if job_id in self.scheduled_jobs:
                del self.scheduled_jobs[job_id]
                logger.info(f"Cancelled scheduled job: {job_id}")
                return True
            return False
    
    def get_due_jobs(self) -> List[ScheduledDistribution]:
        """Get all jobs that are due to run"""
        now = time.time()
        with self._lock:
            return [
                job for job in self.scheduled_jobs.values()
                if job.next_run <= now and job.config.enabled
            ]
    
    def update_last_run(self, job_id: str):
        """Update the last run time and calculate next run"""
        with self._lock:
            if job_id in self.scheduled_jobs:
                job = self.scheduled_jobs[job_id]
                job.last_run = time.time()
                job.run_count += 1
                job.next_run = self._calculate_next_run(job.config.interval)
    
    def _calculate_next_run(self, interval: str) -> float:
        """
        Calculate next run time from cron-like expression
        
        Supports:
        - Standard cron: "0 0 * * *" (daily at midnight)
        - Intervals: "*/5 * * * *" (every 5 minutes)
        - Special: "@hourly", "@daily", "@weekly", "@monthly"
        """
        now = datetime.now()
        
        # Handle special strings
        special_intervals = {
            "@hourly": "0 * * * *",
            "@daily": "0 0 * * *",
            "@weekly": "0 0 * * 0",
            "@monthly": "0 0 1 * *"
        }
        
        interval = special_intervals.get(interval, interval)
        
        # Parse cron expression
        parts = interval.split()
        if len(parts) != 5:
            # Default to daily if invalid
            return (now + timedelta(days=1)).timestamp()
        
        minute, hour, day, month, weekday = parts
        
        # Simple interval calculation (every N minutes)
        if minute.startswith("*/"):
            try:
                interval_mins = int(minute[2:])
                next_run = now + timedelta(minutes=interval_mins)
                return next_run.timestamp()
            except ValueError:
                pass
        
        # Default: next day at specified time
        try:
            target_hour = int(hour) if hour != "*" else 0
            target_minute = int(minute) if minute != "*" else 0
            
            next_run = now.replace(hour=target_hour, minute=target_minute, second=0)
            
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run.timestamp()
        except (ValueError, TypeError):
            return (now + timedelta(days=1)).timestamp()
    
    def list_schedules(self) -> List[ScheduledDistribution]:
        """List all scheduled jobs"""
        return list(self.scheduled_jobs.values())


class DistributionTracker:
    """
    Component 5: Distribution Tracking
    Track history, pending, and completed distributions
    """
    
    def __init__(self):
        self.records: Dict[str, DistributionRecord] = {}
        self.pending: Dict[str, DistributionRecord] = {}
        self.completed: Dict[str, DistributionRecord] = {}
        self.failed: Dict[str, DistributionRecord] = {}
        self._lock = threading.Lock()
    
    def create_record(
        self,
        treasury_balance: float,
        amounts: Dict[str, float],
        strategy: str,
        reinvested: float = 0.0
    ) -> DistributionRecord:
        """
        Create a new distribution record
        
        Args:
            treasury_balance: Balance at time of distribution
            amounts: Amount per recipient
            strategy: Distribution strategy used
            reinvested: Amount reinvested
            
        Returns:
            Created record
        """
        record_id = str(uuid.uuid4())[:12]
        
        record = DistributionRecord(
            id=record_id,
            timestamp=time.time(),
            treasury_balance=treasury_balance,
            total_distributed=sum(amounts.values()),
            reinvested_amount=reinvested,
            recipients=amounts.copy(),
            status=DistributionStatus.PENDING,
            strategy=strategy
        )
        
        with self._lock:
            self.records[record_id] = record
            self.pending[record_id] = record
        
        logger.info(f"Created distribution record: {record_id}")
        return record
    
    def update_status(
        self,
        record_id: str,
        status: DistributionStatus,
        error_message: Optional[str] = None,
        tx_hash: Optional[str] = None
    ) -> Optional[DistributionRecord]:
        """Update the status of a distribution record"""
        with self._lock:
            if record_id not in self.records:
                return None
            
            record = self.records[record_id]
            record.status = status
            
            if error_message:
                record.error_message = error_message
            
            if tx_hash:
                record.tx_hash = tx_hash
            
            if status == DistributionStatus.COMPLETED:
                record.completed_at = time.time()
                self.pending.pop(record_id, None)
                self.failed.pop(record_id, None)
                self.completed[record_id] = record
            elif status == DistributionStatus.FAILED:
                self.pending.pop(record_id, None)
                self.failed[record_id] = record
            elif status == DistributionStatus.CANCELLED:
                self.pending.pop(record_id, None)
            
            return record
    
    def get_record(self, record_id: str) -> Optional[DistributionRecord]:
        """Get a record by ID"""
        return self.records.get(record_id)
    
    def get_pending(self) -> List[DistributionRecord]:
        """Get all pending distributions"""
        return list(self.pending.values())
    
    def get_completed(self, limit: int = 100) -> List[DistributionRecord]:
        """Get completed distributions (most recent first)"""
        sorted_records = sorted(
            self.completed.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )
        return sorted_records[:limit]
    
    def get_failed(self) -> List[DistributionRecord]:
        """Get failed distributions"""
        return list(self.failed.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get distribution statistics"""
        with self._lock:
            total_distributed = sum(r.total_distributed for r in self.completed.values())
            total_reinvested = sum(r.reinvested_amount for r in self.records.values())
            
            return {
                "total_records": len(self.records),
                "pending_count": len(self.pending),
                "completed_count": len(self.completed),
                "failed_count": len(self.failed),
                "total_distributed": total_distributed,
                "total_reinvested": total_reinvested,
                "unique_recipients": len(set(
                    rid for r in self.records.values() for rid in r.recipients.keys()
                ))
            }


class WealthDistributor:
    """
    Main Wealth Distributor orchestrator
    Combines all components for automated treasury management
    """
    
    def __init__(self, config: Optional[DistributionConfig] = None):
        self.config = config or DistributionConfig()
        
        # Initialize components
        self.recipients = RecipientManager()
        self.calculator = DistributionCalculator(self.config)
        self.reinvestment = AutoReinvestment(self.config)
        self.scheduler = Scheduler()
        self.tracker = DistributionTracker()
        
        self.execute_callback: Optional[Callable] = None
        self._running = False
    
    def add_recipient(
        self,
        name: str,
        address: str,
        weight: float = 1.0,
        performance_score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Recipient:
        """Add a recipient"""
        return self.recipients.add_recipient(
            name=name,
            address=address,
            weight=weight,
            performance_score=performance_score,
            metadata=metadata
        )
    
    def remove_recipient(self, recipient_id: str) -> bool:
        """Remove a recipient"""
        return self.recipients.remove_recipient(recipient_id)
    
    def update_recipient(self, recipient_id: str, **kwargs) -> Optional[Recipient]:
        """Update a recipient"""
        return self.recipients.update_recipient(recipient_id, **kwargs)
    
    def list_recipients(self) -> List[Recipient]:
        """List all recipients"""
        return self.recipients.list_recipients()
    
    def calculate_distribution(self, treasury_balance: float) -> Dict[str, float]:
        """
        Calculate distribution amounts without executing
        
        Args:
            treasury_balance: Current treasury balance
            
        Returns:
            Dict mapping recipient_id to amount
        """
        active = self.recipients.get_active_recipients()
        return self.calculator.calculate_distribution(treasury_balance, active)
    
    def distribute(
        self,
        treasury_balance: float,
        execute: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a distribution
        
        Args:
            treasury_balance: Available funds
            execute: If False, only calculate without recording
            
        Returns:
            Distribution result
        """
        # Calculate distribution
        amounts = self.calculate_distribution(treasury_balance)
        
        if not amounts:
            return {
                "status": "skipped",
                "reason": "No distribution calculated",
                "treasury_balance": treasury_balance,
                "threshold": self.config.threshold
            }
        
        # Calculate reinvestment
        reinvest_result = self.reinvestment.apply_compounding(
            treasury_balance, amounts
        )
        
        # Create record
        record = self.tracker.create_record(
            treasury_balance=treasury_balance,
            amounts=amounts,
            strategy=self.config.strategy.value,
            reinvested=reinvest_result["reinvested_amount"]
        )
        
        if not execute:
            return {
                "status": "calculated",
                "record_id": record.id,
                "amounts": amounts,
                "reinvestment": reinvest_result
            }
        
        # Execute distribution
        try:
            self.tracker.update_status(record.id, DistributionStatus.PROCESSING)
            
            # If callback provided, use it for execution
            if self.execute_callback:
                result = self.execute_callback(record)
                if result.get("success"):
                    self.tracker.update_status(
                        record.id,
                        DistributionStatus.COMPLETED,
                        tx_hash=result.get("tx_hash")
                    )
                else:
                    self.tracker.update_status(
                        record.id,
                        DistributionStatus.FAILED,
                        error_message=result.get("error")
                    )
            else:
                # Simulate execution
                self.tracker.update_status(record.id, DistributionStatus.COMPLETED)
            
            return {
                "status": "completed",
                "record_id": record.id,
                "amounts": amounts,
                "total_distributed": sum(amounts.values()),
                "reinvested": reinvest_result["reinvested_amount"],
                "new_treasury": reinvest_result["new_treasury_balance"]
            }
            
        except Exception as e:
            self.tracker.update_status(
                record.id,
                DistributionStatus.FAILED,
                error_message=str(e)
            )
            return {
                "status": "failed",
                "record_id": record.id,
                "error": str(e)
            }
    
    def schedule_distributions(self, job_id: Optional[str] = None) -> str:
        """
        Schedule automated distributions
        
        Args:
            job_id: Optional custom job ID
            
        Returns:
            Job ID
        """
        return self.scheduler.schedule_distribution(self.config, job_id)
    
    def cancel_schedule(self, job_id: str) -> bool:
        """Cancel a scheduled distribution"""
        return self.scheduler.cancel_schedule(job_id)
    
    def get_pending_distributions(self) -> List[DistributionRecord]:
        """Get all pending distributions"""
        return self.tracker.get_pending()
    
    def get_distribution_history(self, limit: int = 100) -> List[DistributionRecord]:
        """Get distribution history"""
        return self.tracker.get_completed(limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get distribution statistics"""
        return self.tracker.get_stats()
    
    def auto_reinvest(self, treasury_balance: float) -> float:
        """
        Calculate auto-reinvestment amount
        
        Args:
            treasury_balance: Current balance
            
        Returns:
            Amount to reinvest
        """
        return self.reinvestment.calculate_reinvestment(treasury_balance)
    
    def project_growth(
        self,
        initial_balance: float,
        periods: int,
        avg_yield: float = 0.0
    ) -> List[Dict[str, float]]:
        """
        Project treasury growth
        
        Args:
            initial_balance: Starting balance
            periods: Number of periods
            avg_yield: Expected yield per period (as decimal)
            
        Returns:
            Projected balances per period
        """
        return self.reinvestment.get_projected_growth(
            initial_balance, periods, avg_yield
        )
    
    def set_execute_callback(self, callback: Callable):
        """Set callback for actual execution"""
        self.execute_callback = callback


# Example usage
if __name__ == "__main__":
    # Create distributor with weighted strategy
    config = DistributionConfig(
        strategy=DistributionStrategy.WEIGHTED,
        threshold=1000.0,
        auto_reinvest_percent=10.0,
        max_payout=5000.0
    )
    
    distributor = WealthDistributor(config)
    
    # Add recipients with weights
    distributor.add_recipient("treasury_growth", "0x111...", weight=10.0)
    distributor.add_recipient("developer_fund", "0x222...", weight=30.0)
    distributor.add_recipient("community_rewards", "0x333...", weight=40.0)
    distributor.add_recipient("marketing", "0x444...", weight=20.0)
    
    # Calculate distribution
    print("=== DISTRIBUTION CALCULATION ===")
    treasury = 10000.0
    amounts = distributor.calculate_distribution(treasury)
    
    recipients = distributor.list_recipients()
    for rid, amount in amounts.items():
        rec = next((r for r in recipients if r.id == rid), None)
        print(f"{rec.name if rec else rid}: ${amount:.2f}")
    
    # Execute distribution
    print("\n=== EXECUTING DISTRIBUTION ===")
    result = distributor.distribute(treasury)
    print(f"Status: {result['status']}")
    print(f"Total distributed: ${result.get('total_distributed', 0):.2f}")
    print(f"Reinvested: ${result.get('reinvested', 0):.2f}")
    print(f"New treasury: ${result.get('new_treasury', 0):.2f}")
    
    # Project growth
    print("\n=== GROWTH PROJECTION (12 months, 2% monthly yield) ===")
    projections = distributor.project_growth(treasury, 12, 0.02)
    for p in projections[:5]:
        print(f"Month {p['period']}: ${p['ending_balance']:.2f}")
    print("...")
    
    # Stats
    print("\n=== STATISTICS ===")
    stats = distributor.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
