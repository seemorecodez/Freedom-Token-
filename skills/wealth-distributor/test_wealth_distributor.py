"""
Unit tests for the Wealth Distributor skill
"""

import unittest
import time
from wealth_distributor import (
    WealthDistributor, DistributionConfig, DistributionStrategy,
    DistributionStatus, DistributionRecord, Recipient,
    RecipientManager, DistributionCalculator, AutoReinvestment,
    Scheduler, DistributionTracker
)


class TestRecipientManager(unittest.TestCase):
    """Test recipient management functionality"""
    
    def setUp(self):
        self.manager = RecipientManager()
    
    def test_add_recipient(self):
        """Test adding a recipient"""
        recipient = self.manager.add_recipient(
            name="test_user",
            address="0x123...",
            weight=50.0
        )
        
        self.assertIsNotNone(recipient.id)
        self.assertEqual(recipient.name, "test_user")
        self.assertEqual(recipient.address, "0x123...")
        self.assertEqual(recipient.weight, 50.0)
    
    def test_remove_recipient(self):
        """Test removing a recipient"""
        recipient = self.manager.add_recipient("to_remove", "0xabc...")
        result = self.manager.remove_recipient(recipient.id)
        
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_recipient(recipient.id))
    
    def test_remove_nonexistent(self):
        """Test removing a non-existent recipient"""
        result = self.manager.remove_recipient("fake_id")
        self.assertFalse(result)
    
    def test_update_recipient(self):
        """Test updating recipient properties"""
        recipient = self.manager.add_recipient("update_me", "0xdef...", weight=10.0)
        
        updated = self.manager.update_recipient(
            recipient.id,
            weight=20.0,
            active=False
        )
        
        self.assertIsNotNone(updated)
        self.assertEqual(updated.weight, 20.0)
        self.assertEqual(updated.active, False)
    
    def test_get_active_recipients(self):
        """Test filtering active recipients"""
        r1 = self.manager.add_recipient("active1", "0x1...")
        r2 = self.manager.add_recipient("inactive", "0x2...")
        r3 = self.manager.add_recipient("active2", "0x3...")
        
        # Deactivate r2
        self.manager.update_recipient(r2.id, active=False)
        
        active = self.manager.get_active_recipients()
        
        self.assertEqual(len(active), 2)
        self.assertIn(r1, active)
        self.assertIn(r3, active)
        self.assertNotIn(r2, active)


class TestDistributionCalculator(unittest.TestCase):
    """Test distribution calculation functionality"""
    
    def setUp(self):
        self.config = DistributionConfig(strategy=DistributionStrategy.EQUAL)
        self.calculator = DistributionCalculator(self.config)
        self.recipients = [
            Recipient(id="r1", name="a", address="0x1...", weight=1.0),
            Recipient(id="r2", name="b", address="0x2...", weight=1.0),
            Recipient(id="r3", name="c", address="0x3...", weight=1.0)
        ]
    
    def test_equal_distribution(self):
        """Test equal distribution strategy"""
        amounts = self.calculator.calculate_distribution(300.0, self.recipients)
        
        self.assertEqual(len(amounts), 3)
        self.assertAlmostEqual(amounts["r1"], 100.0, places=2)
        self.assertAlmostEqual(amounts["r2"], 100.0, places=2)
        self.assertAlmostEqual(amounts["r3"], 100.0, places=2)
    
    def test_weighted_distribution(self):
        """Test weighted distribution strategy"""
        self.config.strategy = DistributionStrategy.WEIGHTED
        self.calculator = DistributionCalculator(self.config)
        
        recipients = [
            Recipient(id="r1", name="a", address="0x1...", weight=50.0),
            Recipient(id="r2", name="b", address="0x2...", weight=30.0),
            Recipient(id="r3", name="c", address="0x3...", weight=20.0)
        ]
        
        amounts = self.calculator.calculate_distribution(1000.0, recipients)
        
        self.assertAlmostEqual(amounts["r1"], 500.0, places=2)
        self.assertAlmostEqual(amounts["r2"], 300.0, places=2)
        self.assertAlmostEqual(amounts["r3"], 200.0, places=2)
    
    def test_performance_distribution(self):
        """Test performance-based distribution"""
        self.config.strategy = DistributionStrategy.PERFORMANCE
        self.calculator = DistributionCalculator(self.config)
        
        recipients = [
            Recipient(id="r1", name="a", address="0x1...", weight=50.0, performance_score=2.0),
            Recipient(id="r2", name="b", address="0x2...", weight=50.0, performance_score=1.0)
        ]
        
        amounts = self.calculator.calculate_distribution(900.0, recipients)
        
        # r1: 50 * 2 = 100, r2: 50 * 1 = 50, total score = 150
        # r1 gets (100/150) * 900 = 600
        # r2 gets (50/150) * 900 = 300
        self.assertAlmostEqual(amounts["r1"], 600.0, places=2)
        self.assertAlmostEqual(amounts["r2"], 300.0, places=2)
    
    def test_threshold_check(self):
        """Test that distribution respects threshold"""
        self.config.threshold = 500.0
        self.calculator = DistributionCalculator(self.config)
        
        amounts = self.calculator.calculate_distribution(400.0, self.recipients)
        
        self.assertEqual(len(amounts), 0)
    
    def test_max_payout_constraint(self):
        """Test max payout constraint"""
        self.config.max_payout = 50.0
        self.calculator = DistributionCalculator(self.config)
        
        amounts = self.calculator.calculate_distribution(300.0, self.recipients)
        
        for amount in amounts.values():
            self.assertLessEqual(amount, 50.0)
    
    def test_min_payout_constraint(self):
        """Test min payout constraint filters small amounts"""
        self.config.min_payout = 10.0
        self.calculator = DistributionCalculator(self.config)
        
        recipients = [
            Recipient(id="r1", name="a", address="0x1..."),
            Recipient(id="r2", name="b", address="0x2..."),
            Recipient(id="r3", name="c", address="0x3...")
        ]
        
        # With 15.0 and min_payout=10, none should qualify (5 each, below 10)
        amounts = self.calculator.calculate_distribution(15.0, recipients)
        
        # All recipients get 5.0 which is below min_payout of 10.0
        self.assertEqual(len(amounts), 0)
    
    def test_auto_reinvest_calculation(self):
        """Test that auto-reinvest reduces distribution"""
        self.config.auto_reinvest_percent = 10.0
        self.calculator = DistributionCalculator(self.config)
        
        amounts = self.calculator.calculate_distribution(1000.0, self.recipients)
        total = sum(amounts.values())
        
        # 10% reinvested = 900 distributed
        self.assertAlmostEqual(total, 900.0, places=2)


class TestAutoReinvestment(unittest.TestCase):
    """Test auto-reinvestment functionality"""
    
    def setUp(self):
        self.config = DistributionConfig(auto_reinvest_percent=10.0)
        self.reinvestment = AutoReinvestment(self.config)
    
    def test_calculate_reinvestment(self):
        """Test reinvestment calculation"""
        amount = self.reinvestment.calculate_reinvestment(1000.0)
        self.assertEqual(amount, 100.0)
    
    def test_apply_compounding(self):
        """Test compounding logic"""
        distribution_amounts = {"r1": 300.0, "r2": 200.0}
        
        result = self.reinvestment.apply_compounding(1000.0, distribution_amounts)
        
        self.assertEqual(result["original_balance"], 1000.0)
        self.assertEqual(result["reinvested_amount"], 100.0)
        self.assertEqual(result["total_distributed"], 500.0)
        self.assertEqual(result["new_treasury_balance"], 500.0)
    
    def test_projected_growth(self):
        """Test growth projection"""
        projections = self.reinvestment.get_projected_growth(
            initial_balance=1000.0,
            periods=3,
            avg_yield_per_period=0.05
        )
        
        self.assertEqual(len(projections), 3)
        # Each period should grow
        self.assertGreater(
            projections[1]["ending_balance"],
            projections[0]["ending_balance"]
        )


class TestScheduler(unittest.TestCase):
    """Test scheduling functionality"""
    
    def setUp(self):
        self.scheduler = Scheduler()
        self.config = DistributionConfig(interval="@daily")
    
    def test_schedule_distribution(self):
        """Test scheduling a distribution"""
        job_id = self.scheduler.schedule_distribution(self.config)
        
        self.assertIsNotNone(job_id)
        self.assertIn(job_id, self.scheduler.scheduled_jobs)
    
    def test_cancel_schedule(self):
        """Test cancelling a scheduled job"""
        job_id = self.scheduler.schedule_distribution(self.config)
        result = self.scheduler.cancel_schedule(job_id)
        
        self.assertTrue(result)
        self.assertNotIn(job_id, self.scheduler.scheduled_jobs)
    
    def test_cancel_nonexistent(self):
        """Test cancelling non-existent job"""
        result = self.scheduler.cancel_schedule("fake_job")
        self.assertFalse(result)
    
    def test_calculate_next_run(self):
        """Test next run calculation"""
        next_run = self.scheduler._calculate_next_run("*/5 * * * *")
        
        # Should be in the future
        self.assertGreater(next_run, time.time())
    
    def test_list_schedules(self):
        """Test listing scheduled jobs"""
        self.scheduler.schedule_distribution(self.config, "job1")
        self.scheduler.schedule_distribution(self.config, "job2")
        
        schedules = self.scheduler.list_schedules()
        
        self.assertEqual(len(schedules), 2)


class TestDistributionTracker(unittest.TestCase):
    """Test distribution tracking functionality"""
    
    def setUp(self):
        self.tracker = DistributionTracker()
    
    def test_create_record(self):
        """Test creating a distribution record"""
        record = self.tracker.create_record(
            treasury_balance=1000.0,
            amounts={"r1": 300.0, "r2": 200.0},
            strategy="weighted",
            reinvested=100.0
        )
        
        self.assertIsNotNone(record.id)
        self.assertEqual(record.treasury_balance, 1000.0)
        self.assertEqual(record.total_distributed, 500.0)
        self.assertEqual(record.reinvested_amount, 100.0)
        self.assertEqual(record.status, DistributionStatus.PENDING)
    
    def test_update_status(self):
        """Test updating record status"""
        record = self.tracker.create_record(
            treasury_balance=1000.0,
            amounts={"r1": 100.0},
            strategy="equal"
        )
        
        updated = self.tracker.update_status(
            record.id,
            DistributionStatus.COMPLETED,
            tx_hash="0xabc123"
        )
        
        self.assertEqual(updated.status, DistributionStatus.COMPLETED)
        self.assertEqual(updated.tx_hash, "0xabc123")
        self.assertIsNotNone(updated.completed_at)
    
    def test_get_pending(self):
        """Test getting pending distributions"""
        r1 = self.tracker.create_record(1000.0, {"r1": 100.0}, "equal")
        r2 = self.tracker.create_record(2000.0, {"r2": 200.0}, "weighted")
        
        self.tracker.update_status(r2.id, DistributionStatus.COMPLETED)
        
        pending = self.tracker.get_pending()
        
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].id, r1.id)
    
    def test_get_completed(self):
        """Test getting completed distributions"""
        for i in range(5):
            record = self.tracker.create_record(
                1000.0 + i * 100,
                {"r1": 100.0},
                "equal"
            )
            if i % 2 == 0:
                self.tracker.update_status(record.id, DistributionStatus.COMPLETED)
        
        completed = self.tracker.get_completed()
        
        self.assertEqual(len(completed), 3)
    
    def test_get_stats(self):
        """Test getting statistics"""
        # Create some records
        r1 = self.tracker.create_record(1000.0, {"r1": 300.0, "r2": 200.0}, "equal")
        r2 = self.tracker.create_record(2000.0, {"r1": 400.0, "r3": 100.0}, "weighted")
        
        self.tracker.update_status(r1.id, DistributionStatus.COMPLETED)
        self.tracker.update_status(r2.id, DistributionStatus.FAILED)
        
        stats = self.tracker.get_stats()
        
        self.assertEqual(stats["total_records"], 2)
        self.assertEqual(stats["completed_count"], 1)
        self.assertEqual(stats["failed_count"], 1)
        self.assertEqual(stats["total_distributed"], 500.0)  # Only completed


class TestWealthDistributor(unittest.TestCase):
    """Integration tests for WealthDistributor"""
    
    def setUp(self):
        self.config = DistributionConfig(
            strategy=DistributionStrategy.WEIGHTED,
            threshold=500.0,
            auto_reinvest_percent=10.0
        )
        self.distributor = WealthDistributor(self.config)
    
    def test_add_and_list_recipients(self):
        """Test full recipient workflow"""
        r1 = self.distributor.add_recipient("alice", "0x1...", weight=50.0)
        r2 = self.distributor.add_recipient("bob", "0x2...", weight=50.0)
        
        recipients = self.distributor.list_recipients()
        
        self.assertEqual(len(recipients), 2)
        self.assertIn(r1, recipients)
        self.assertIn(r2, recipients)
    
    def test_calculate_distribution(self):
        """Test distribution calculation"""
        self.distributor.add_recipient("a", "0x1...", weight=60.0)
        self.distributor.add_recipient("b", "0x2...", weight=40.0)
        
        amounts = self.distributor.calculate_distribution(1000.0)
        
        self.assertEqual(len(amounts), 2)
        self.assertAlmostEqual(sum(amounts.values()), 900.0, places=2)  # After reinvest
    
    def test_distribute_execution(self):
        """Test full distribution execution"""
        self.distributor.add_recipient("a", "0x1...", weight=50.0)
        self.distributor.add_recipient("b", "0x2...", weight=50.0)
        
        result = self.distributor.distribute(1000.0)
        
        self.assertEqual(result["status"], "completed")
        self.assertIn("record_id", result)
        self.assertIn("amounts", result)
    
    def test_distribute_below_threshold(self):
        """Test distribution below threshold"""
        result = self.distributor.distribute(100.0)
        
        self.assertEqual(result["status"], "skipped")
    
    def test_schedule_distributions(self):
        """Test scheduling"""
        job_id = self.distributor.schedule_distributions("test_job")
        
        self.assertEqual(job_id, "test_job")
        
        result = self.distributor.cancel_schedule(job_id)
        self.assertTrue(result)
    
    def test_project_growth(self):
        """Test growth projection"""
        projections = self.distributor.project_growth(1000.0, 6, 0.03)
        
        self.assertEqual(len(projections), 6)
        # Should be increasing
        for i in range(1, len(projections)):
            self.assertGreater(
                projections[i]["ending_balance"],
                projections[i-1]["ending_balance"]
            )
    
    def test_get_stats(self):
        """Test statistics"""
        self.distributor.add_recipient("a", "0x1...")
        self.distributor.distribute(1000.0)
        
        stats = self.distributor.get_stats()
        
        self.assertEqual(stats["completed_count"], 1)
        self.assertGreater(stats["total_distributed"], 0)
    
    def test_auto_reinvest(self):
        """Test auto reinvest calculation"""
        amount = self.distributor.auto_reinvest(1000.0)
        
        self.assertEqual(amount, 100.0)  # 10% of 1000


if __name__ == "__main__":
    unittest.main()
