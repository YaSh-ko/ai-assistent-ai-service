#!/usr/bin/env python3
"""
Stress testing script for the AI service.
Tests various endpoints under different load conditions.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import httpx
import argparse
from datetime import datetime
import json


@dataclass
class TestConfig:
    """Configuration for stress test."""
    base_url: str = "http://localhost:8001"  # Changed from 8000 to avoid conflicts
    num_users: int = 10
    duration_seconds: int = 60
    rps_target: Optional[int] = None  # Requests per second target
    test_type: str = "simple"  # simple, rag, reasoning, streaming
    
    
@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    start_time: float
    end_time: float
    status_code: int
    error: Optional[str] = None
    ttfb: Optional[float] = None  # Time to first byte (for streaming)
    response_size: int = 0
    
    @property
    def latency(self) -> float:
        """Request latency in milliseconds."""
        return (self.end_time - self.start_time) * 1000
    
    @property
    def success(self) -> bool:
        """Whether request was successful."""
        return 200 <= self.status_code < 300 and self.error is None


@dataclass
class TestResults:
    """Aggregated test results."""
    config: TestConfig
    metrics: List[RequestMetrics] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0
    
    @property
    def duration(self) -> float:
        """Total test duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def total_requests(self) -> int:
        """Total number of requests."""
        return len(self.metrics)
    
    @property
    def successful_requests(self) -> int:
        """Number of successful requests."""
        return sum(1 for m in self.metrics if m.success)
    
    @property
    def failed_requests(self) -> int:
        """Number of failed requests."""
        return self.total_requests - self.successful_requests
    
    @property
    def error_rate(self) -> float:
        """Error rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    @property
    def throughput(self) -> float:
        """Requests per second."""
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration
    
    def get_latency_percentile(self, percentile: float) -> float:
        """Get latency percentile in milliseconds."""
        if not self.metrics:
            return 0.0
        latencies = [m.latency for m in self.metrics if m.success]
        if not latencies:
            return 0.0
        latencies.sort()
        index = int(len(latencies) * percentile / 100)
        return latencies[min(index, len(latencies) - 1)]
    
    def get_average_latency(self) -> float:
        """Get average latency in milliseconds."""
        latencies = [m.latency for m in self.metrics if m.success]
        if not latencies:
            return 0.0
        return statistics.mean(latencies)
    
    def get_ttfb_stats(self) -> Dict[str, float]:
        """Get TTFB statistics for streaming requests."""
        ttfbs = [m.ttfb for m in self.metrics if m.ttfb is not None]
        if not ttfbs:
            return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        
        ttfbs.sort()
        return {
            "min": min(ttfbs) * 1000,
            "max": max(ttfbs) * 1000,
            "avg": statistics.mean(ttfbs) * 1000,
            "p50": ttfbs[int(len(ttfbs) * 0.5)] * 1000,
            "p95": ttfbs[int(len(ttfbs) * 0.95)] * 1000,
            "p99": ttfbs[int(len(ttfbs) * 0.99)] * 1000,
        }


class StressTestRunner:
    """Runner for stress tests."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results = TestResults(config=config)
        self.session_ids: List[str] = []
        
    async def setup(self):
        """Setup test environment."""
        print(f"Setting up {self.config.num_users} test sessions...")
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=30.0) as client:
            # First check if service is available
            try:
                health_response = await client.get("/health")
                if health_response.status_code != 200:
                    print(f"Warning: Service health check returned {health_response.status_code}")
            except Exception as e:
                print(f"Error: Cannot connect to service at {self.config.base_url}")
                print(f"Details: {e}")
                print("\nPlease ensure the service is running:")
                print("  python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001")
                return
            
            for i in range(self.config.num_users):
                try:
                    response = await client.post(
                        "/api/v1/chat/sessions",
                        json={"user_id": f"stress_test_user_{i}"}
                    )
                    if response.status_code == 200:
                        session_id = response.json()["session_id"]
                        self.session_ids.append(session_id)
                    else:
                        print(f"Failed to create session {i}: HTTP {response.status_code}")
                        print(f"Response: {response.text}")
                except Exception as e:
                    print(f"Failed to create session {i}: {e}")
        
        print(f"Created {len(self.session_ids)} sessions")
        
        if len(self.session_ids) == 0:
            print("\nError: No sessions were created. Common issues:")
            print("  1. Service is not running")
            print("  2. Database connection failed")
            print("  3. Authentication/authorization issues")
            print("\nCheck service logs for more details.")
    
    async def cleanup(self):
        """Cleanup test environment."""
        print("Cleaning up test sessions...")
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=30.0) as client:
            for session_id in self.session_ids:
                try:
                    await client.post(f"/api/v1/chat/sessions/{session_id}/close")
                except Exception:
                    pass
    
    async def make_simple_request(self, client: httpx.AsyncClient, session_id: str) -> RequestMetrics:
        """Make a simple chat request."""
        start_time = time.time()
        try:
            response = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"content": "Привет!"}
            )
            end_time = time.time()
            
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=response.status_code,
                response_size=len(response.content)
            )
        except Exception as e:
            end_time = time.time()
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=0,
                error=str(e)
            )
    
    async def make_rag_request(self, client: httpx.AsyncClient, session_id: str) -> RequestMetrics:
        """Make a RAG request."""
        start_time = time.time()
        try:
            response = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"content": "Что я писал вчера про философию?"}
            )
            end_time = time.time()
            
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=response.status_code,
                response_size=len(response.content)
            )
        except Exception as e:
            end_time = time.time()
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=0,
                error=str(e)
            )
    
    async def make_reasoning_request(self, client: httpx.AsyncClient, session_id: str) -> RequestMetrics:
        """Make a complex reasoning request."""
        start_time = time.time()
        try:
            response = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"content": "Проанализируй мои последние записи и найди связи между концепциями."}
            )
            end_time = time.time()
            
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=response.status_code,
                response_size=len(response.content)
            )
        except Exception as e:
            end_time = time.time()
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=0,
                error=str(e)
            )
    
    async def make_streaming_request(self, client: httpx.AsyncClient, session_id: str) -> RequestMetrics:
        """Make a streaming request."""
        start_time = time.time()
        ttfb = None
        response_size = 0
        
        try:
            async with client.stream(
                "POST",
                f"/api/v1/chat/sessions/{session_id}/stream",
                json={"content": "Расскажи длинную историю."}
            ) as response:
                if ttfb is None:
                    ttfb = time.time() - start_time
                
                async for line in response.aiter_lines():
                    response_size += len(line)
                
                end_time = time.time()
                
                return RequestMetrics(
                    start_time=start_time,
                    end_time=end_time,
                    status_code=response.status_code,
                    ttfb=ttfb,
                    response_size=response_size
                )
        except Exception as e:
            end_time = time.time()
            return RequestMetrics(
                start_time=start_time,
                end_time=end_time,
                status_code=0,
                error=str(e),
                ttfb=ttfb
            )
    
    async def worker(self, worker_id: int, client: httpx.AsyncClient):
        """Worker coroutine that makes requests."""
        session_id = self.session_ids[worker_id % len(self.session_ids)]
        
        request_func = {
            "simple": self.make_simple_request,
            "rag": self.make_rag_request,
            "reasoning": self.make_reasoning_request,
            "streaming": self.make_streaming_request,
        }[self.config.test_type]
        
        while time.time() < self.results.end_time:
            metrics = await request_func(client, session_id)
            self.results.metrics.append(metrics)
            
            # Rate limiting
            if self.config.rps_target:
                await asyncio.sleep(1.0 / self.config.rps_target)
    
    async def run(self):
        """Run the stress test."""
        await self.setup()
        
        if not self.session_ids:
            print("No sessions created, aborting test")
            return
        
        print("\nStarting stress test:")
        print(f"  Type: {self.config.test_type}")
        print(f"  Users: {self.config.num_users}")
        print(f"  Duration: {self.config.duration_seconds}s")
        if self.config.rps_target:
            print(f"  Target RPS: {self.config.rps_target}")
        print()
        
        self.results.start_time = time.time()
        self.results.end_time = self.results.start_time + self.config.duration_seconds
        
        async with httpx.AsyncClient(base_url=self.config.base_url, timeout=60.0) as client:
            workers = [
                self.worker(i, client)
                for i in range(self.config.num_users)
            ]
            await asyncio.gather(*workers)
        
        self.results.end_time = time.time()
        
        await self.cleanup()
    
    def print_results(self):
        """Print test results."""
        print("\n" + "="*80)
        print("STRESS TEST RESULTS")
        print("="*80)
        print("\nTest Configuration:")
        print(f"  Type: {self.config.test_type}")
        print(f"  Concurrent Users: {self.config.num_users}")
        print(f"  Duration: {self.results.duration:.2f}s")
        if self.config.rps_target:
            print(f"  Target RPS: {self.config.rps_target}")
        
        print("\nRequest Statistics:")
        print(f"  Total Requests: {self.results.total_requests}")
        print(f"  Successful: {self.results.successful_requests}")
        print(f"  Failed: {self.results.failed_requests}")
        print(f"  Error Rate: {self.results.error_rate:.2f}%")
        
        print("\nThroughput:")
        print(f"  Actual RPS: {self.results.throughput:.2f}")
        
        print("\nLatency (ms):")
        print(f"  Average: {self.results.get_average_latency():.2f}")
        print(f"  p50: {self.results.get_latency_percentile(50):.2f}")
        print(f"  p95: {self.results.get_latency_percentile(95):.2f}")
        print(f"  p99: {self.results.get_latency_percentile(99):.2f}")
        
        if self.config.test_type == "streaming":
            ttfb_stats = self.results.get_ttfb_stats()
            print("\nTime to First Byte (ms):")
            print(f"  Min: {ttfb_stats['min']:.2f}")
            print(f"  Max: {ttfb_stats['max']:.2f}")
            print(f"  Average: {ttfb_stats['avg']:.2f}")
            print(f"  p50: {ttfb_stats['p50']:.2f}")
            print(f"  p95: {ttfb_stats['p95']:.2f}")
            print(f"  p99: {ttfb_stats['p99']:.2f}")
        
        print("\n" + "="*80)
    
    def save_results(self, filename: str):
        """Save results to JSON file."""
        data = {
            "config": {
                "base_url": self.config.base_url,
                "num_users": self.config.num_users,
                "duration_seconds": self.config.duration_seconds,
                "rps_target": self.config.rps_target,
                "test_type": self.config.test_type,
            },
            "summary": {
                "duration": self.results.duration,
                "total_requests": self.results.total_requests,
                "successful_requests": self.results.successful_requests,
                "failed_requests": self.results.failed_requests,
                "error_rate": self.results.error_rate,
                "throughput": self.results.throughput,
                "latency": {
                    "avg": self.results.get_average_latency(),
                    "p50": self.results.get_latency_percentile(50),
                    "p95": self.results.get_latency_percentile(95),
                    "p99": self.results.get_latency_percentile(99),
                }
            },
            "timestamp": datetime.now().isoformat(),
        }
        
        if self.config.test_type == "streaming":
            data["summary"]["ttfb"] = self.results.get_ttfb_stats()
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nResults saved to {filename}")


async def run_test_suite():
    """Run a suite of stress tests."""
    test_configs = [
        # Simple requests - different load levels
        TestConfig(num_users=10, duration_seconds=30, rps_target=10, test_type="simple"),
        TestConfig(num_users=50, duration_seconds=30, rps_target=50, test_type="simple"),
        TestConfig(num_users=100, duration_seconds=30, rps_target=100, test_type="simple"),
        
        # RAG requests
        TestConfig(num_users=10, duration_seconds=30, rps_target=10, test_type="rag"),
        TestConfig(num_users=50, duration_seconds=30, rps_target=50, test_type="rag"),
        
        # Reasoning requests
        TestConfig(num_users=10, duration_seconds=30, rps_target=5, test_type="reasoning"),
        TestConfig(num_users=20, duration_seconds=30, rps_target=10, test_type="reasoning"),
        
        # Streaming requests
        TestConfig(num_users=10, duration_seconds=30, rps_target=10, test_type="streaming"),
        TestConfig(num_users=50, duration_seconds=30, rps_target=50, test_type="streaming"),
    ]
    
    results_dir = "stress_test_results"
    import os
    os.makedirs(results_dir, exist_ok=True)
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{'='*80}")
        print(f"Running Test {i}/{len(test_configs)}")
        print(f"{'='*80}")
        
        runner = StressTestRunner(config)
        await runner.run()
        runner.print_results()
        
        filename = f"{results_dir}/test_{i}_{config.test_type}_{config.num_users}users_{config.rps_target}rps.json"
        runner.save_results(filename)
        
        # Cool down between tests
        print("\nCooling down for 10 seconds...")
        await asyncio.sleep(10)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Stress test the AI service")
    parser.add_argument("--url", default="http://localhost:8001", help="Base URL of the service")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--rps", type=int, help="Target requests per second")
    parser.add_argument("--type", choices=["simple", "rag", "reasoning", "streaming"], 
                       default="simple", help="Type of test to run")
    parser.add_argument("--suite", action="store_true", help="Run full test suite")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    if args.suite:
        asyncio.run(run_test_suite())
    else:
        config = TestConfig(
            base_url=args.url,
            num_users=args.users,
            duration_seconds=args.duration,
            rps_target=args.rps,
            test_type=args.type
        )
        
        runner = StressTestRunner(config)
        asyncio.run(runner.run())
        runner.print_results()
        
        if args.output:
            runner.save_results(args.output)


if __name__ == "__main__":
    main()
