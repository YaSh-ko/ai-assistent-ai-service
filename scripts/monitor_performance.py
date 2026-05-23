#!/usr/bin/env python3
"""
Real-time performance monitoring script.
Monitors service metrics during stress tests.
"""

import asyncio
import time
import psutil
import httpx
from datetime import datetime
from typing import Dict, Any, List
import argparse


class PerformanceMonitor:
    """Monitor system and service performance."""
    
    def __init__(self, base_url: str, interval: int = 5):
        self.base_url = base_url
        self.interval = interval
        self.metrics_history: List[Dict[str, Any]] = []
        self.running = False
        
    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health metrics."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    return {"status": "healthy", "response_time": response.elapsed.total_seconds()}
                else:
                    return {"status": "unhealthy", "status_code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count(),
            },
            "memory": {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "percent": memory.percent,
                "available_gb": memory.available / (1024**3),
            },
            "disk": {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent_mb": net_io.bytes_sent / (1024**2),
                "bytes_recv_mb": net_io.bytes_recv / (1024**2),
            }
        }
    
    def get_process_metrics(self) -> Dict[str, Any]:
        """Get metrics for Python processes."""
        python_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cpu_percent": proc.info['cpu_percent'],
                        "memory_percent": proc.info['memory_percent'],
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return {"python_processes": python_processes}
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect all metrics."""
        timestamp = datetime.now().isoformat()
        
        service_health = await self.get_service_health()
        system_metrics = self.get_system_metrics()
        process_metrics = self.get_process_metrics()
        
        return {
            "timestamp": timestamp,
            "service": service_health,
            "system": system_metrics,
            "processes": process_metrics,
        }
    
    def print_metrics(self, metrics: Dict[str, Any]):
        """Print metrics to console."""
        print("\n" + "="*80)
        print(f"Timestamp: {metrics['timestamp']}")
        print("="*80)
        
        # Service health
        service = metrics['service']
        status_color = "\033[92m" if service['status'] == 'healthy' else "\033[91m"
        print(f"\nService Status: {status_color}{service['status']}\033[0m")
        if 'response_time' in service:
            print(f"Response Time: {service['response_time']*1000:.2f}ms")
        
        # System metrics
        system = metrics['system']
        print("\nSystem Resources:")
        print(f"  CPU: {system['cpu']['percent']:.1f}% ({system['cpu']['count']} cores)")
        print(f"  Memory: {system['memory']['used_gb']:.2f}GB / {system['memory']['total_gb']:.2f}GB "
              f"({system['memory']['percent']:.1f}%)")
        print(f"  Disk: {system['disk']['used_gb']:.2f}GB / {system['disk']['total_gb']:.2f}GB "
              f"({system['disk']['percent']:.1f}%)")
        print(f"  Network: ↑{system['network']['bytes_sent_mb']:.2f}MB ↓{system['network']['bytes_recv_mb']:.2f}MB")
        
        # Python processes
        processes = metrics['processes']['python_processes']
        if processes:
            print(f"\nPython Processes ({len(processes)}):")
            for proc in processes[:5]:  # Show top 5
                print(f"  PID {proc['pid']}: CPU {proc['cpu_percent']:.1f}%, "
                      f"Memory {proc['memory_percent']:.1f}%")
    
    def check_alerts(self, metrics: Dict[str, Any]) -> List[str]:
        """Check for alert conditions."""
        alerts = []
        
        system = metrics['system']
        
        # CPU alert
        if system['cpu']['percent'] > 80:
            alerts.append(f"⚠️  HIGH CPU: {system['cpu']['percent']:.1f}%")
        
        # Memory alert
        if system['memory']['percent'] > 85:
            alerts.append(f"⚠️  HIGH MEMORY: {system['memory']['percent']:.1f}%")
        
        # Disk alert
        if system['disk']['percent'] > 90:
            alerts.append(f"⚠️  HIGH DISK USAGE: {system['disk']['percent']:.1f}%")
        
        # Service health alert
        if metrics['service']['status'] != 'healthy':
            alerts.append(f"⚠️  SERVICE UNHEALTHY: {metrics['service']['status']}")
        
        return alerts
    
    async def monitor_loop(self):
        """Main monitoring loop."""
        print(f"Starting performance monitoring (interval: {self.interval}s)")
        print("Press Ctrl+C to stop\n")
        
        self.running = True
        
        try:
            while self.running:
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
                
                self.print_metrics(metrics)
                
                # Check for alerts
                alerts = self.check_alerts(metrics)
                if alerts:
                    print("\n🚨 ALERTS:")
                    for alert in alerts:
                        print(f"  {alert}")
                
                await asyncio.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\nStopping monitor...")
            self.running = False
    
    def save_history(self, filename: str):
        """Save metrics history to file."""
        import json
        
        with open(filename, 'w') as f:
            json.dump(self.metrics_history, f, indent=2)
        
        print(f"\nMetrics history saved to {filename}")
    
    def print_summary(self):
        """Print summary statistics."""
        if not self.metrics_history:
            return
        
        print("\n" + "="*80)
        print("MONITORING SUMMARY")
        print("="*80)
        
        # Calculate averages
        cpu_values = [m['system']['cpu']['percent'] for m in self.metrics_history]
        memory_values = [m['system']['memory']['percent'] for m in self.metrics_history]
        
        print(f"\nDuration: {len(self.metrics_history) * self.interval}s")
        print(f"Samples: {len(self.metrics_history)}")
        
        print("\nCPU Usage:")
        print(f"  Average: {sum(cpu_values)/len(cpu_values):.1f}%")
        print(f"  Min: {min(cpu_values):.1f}%")
        print(f"  Max: {max(cpu_values):.1f}%")
        
        print("\nMemory Usage:")
        print(f"  Average: {sum(memory_values)/len(memory_values):.1f}%")
        print(f"  Min: {min(memory_values):.1f}%")
        print(f"  Max: {max(memory_values):.1f}%")
        
        # Service health
        healthy_count = sum(1 for m in self.metrics_history if m['service']['status'] == 'healthy')
        print("\nService Health:")
        print(f"  Uptime: {healthy_count/len(self.metrics_history)*100:.1f}%")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor service performance")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the service")
    parser.add_argument("--interval", type=int, default=5, help="Monitoring interval in seconds")
    parser.add_argument("--output", help="Save metrics history to file")
    
    args = parser.parse_args()
    
    monitor = PerformanceMonitor(args.url, args.interval)
    
    try:
        await monitor.monitor_loop()
    finally:
        monitor.print_summary()
        
        if args.output:
            monitor.save_history(args.output)


if __name__ == "__main__":
    asyncio.run(main())
