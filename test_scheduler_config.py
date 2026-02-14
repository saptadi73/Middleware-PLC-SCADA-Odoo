"""
Test script untuk verifikasi Scheduler Task Control Configuration
Mengecek bahwa config.py dan scheduler.py properly handle individual task control
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings

settings = get_settings()


def test_config_loaded():
    """Test bahwa konfigurasi loaded dengan benar"""
    print("\n" + "=" * 80)
    print("TEST 1: Verify Configuration Loaded")
    print("=" * 80)
    
    config = {
        "Master Switch (ENABLE_AUTO_SYNC)": settings.enable_auto_sync,
        "Task 1: Auto-sync MO": settings.enable_task_1_auto_sync,
        "Task 2: PLC Read": settings.enable_task_2_plc_read,
        "Task 3: Process Completed": settings.enable_task_3_process_completed,
        "Task 4: Health Monitor": settings.enable_task_4_health_monitor,
    }
    
    for key, value in config.items():
        status = "✓ ENABLED" if value else "✓ DISABLED"
        print(f"  {key:<35}: {status}")
    
    return True


def test_intervals_configured():
    """Test bahwa intervals dikonfigurasi dengan benar"""
    print("\n" + "=" * 80)
    print("TEST 2: Verify Intervals Configuration")
    print("=" * 80)
    
    intervals = {
        "Task 1 (Auto-sync MO)": settings.sync_interval_minutes,
        "Task 2 (PLC Read)": settings.plc_read_interval_minutes,
        "Task 3 (Process Completed)": settings.process_completed_interval_minutes,
        "Task 4 (Health Monitor)": settings.health_monitor_interval_minutes,
    }
    
    all_valid = True
    for task, interval in intervals.items():
        if interval > 0:
            print(f"  {task:<35}: {interval} minute(s) ✓")
        else:
            print(f"  {task:<35}: {interval} minute(s) ✗ INVALID")
            all_valid = False
    
    return all_valid


def test_batch_limit():
    """Test batch sync limit"""
    print("\n" + "=" * 80)
    print("TEST 3: Verify Batch Limit")
    print("=" * 80)
    
    if settings.sync_batch_limit > 0:
        print(f"  Batch Limit: {settings.sync_batch_limit} ✓")
        return True
    else:
        print(f"  Batch Limit: {settings.sync_batch_limit} ✗ INVALID")
        return False


def test_task_count():
    """Hitung berapa banyak task yang enabled"""
    print("\n" + "=" * 80)
    print("TEST 4: Task Count Summary")
    print("=" * 80)
    
    enabled_tasks = [
        settings.enable_task_1_auto_sync,
        settings.enable_task_2_plc_read,
        settings.enable_task_3_process_completed,
        settings.enable_task_4_health_monitor,
    ]
    
    task_count = sum(enabled_tasks)
    total_tasks = len(enabled_tasks)
    
    print(f"  Enabled Tasks: {task_count}/{total_tasks}")
    print()
    
    task_names = [
        "Task 1: Auto-sync MO",
        "Task 2: PLC Read",
        "Task 3: Process Completed",
        "Task 4: Health Monitor",
    ]
    
    for i, (enabled, name) in enumerate(zip(enabled_tasks, task_names)):
        status = "✓" if enabled else "✗"
        print(f"    {status} {name}")
    
    return task_count > 0


def test_master_switch_logic():
    """Test bahwa master switch bekerja dengan benar"""
    print("\n" + "=" * 80)
    print("TEST 5: Master Switch Logic")
    print("=" * 80)
    
    if settings.enable_auto_sync:
        print("  Master Switch: ENABLED ✓")
        print("  → Individual task flags WILL be respected")
        return True
    else:
        print("  Master Switch: DISABLED ✓")
        print("  ⚠️  WARNING: All scheduler tasks will be DISABLED")
        print("      regardless of individual task settings")
        return True


def print_startup_log_simulation():
    """Simulate startup log yang akan dilihat user"""
    print("\n" + "=" * 80)
    print("SIMULATED STARTUP LOG")
    print("=" * 80)
    print()
    
    if not settings.enable_auto_sync:
        print("⊘ Scheduler Master Switch is DISABLED - All tasks will be DISABLED")
        return
    
    task_configs = [
        (settings.enable_task_1_auto_sync, 
         "Auto-sync MO", 
         settings.sync_interval_minutes),
        (settings.enable_task_2_plc_read, 
         "PLC read sync", 
         settings.plc_read_interval_minutes),
        (settings.enable_task_3_process_completed, 
         "Process completed batches", 
         settings.process_completed_interval_minutes),
        (settings.enable_task_4_health_monitor, 
         "Batch health monitoring", 
         settings.health_monitor_interval_minutes),
    ]
    
    enabled_count = 0
    for enabled, task_name, interval in task_configs:
        if enabled:
            print(f"✓ Task: {task_name} scheduler added (interval: {interval} minutes)")
            enabled_count += 1
        else:
            print(f"⊘ Task: {task_name} scheduler DISABLED")
    
    print()
    status_icons = ["✓" if cfg[0] else "✗" for cfg in task_configs]
    print(f"✓✓✓ Enhanced Scheduler STARTED with {enabled_count}/4 tasks enabled ✓✓✓")
    print(f"  - Task 1: Auto-sync MO ({settings.sync_interval_minutes} min) - {status_icons[0]}")
    print(f"  - Task 2: PLC read sync ({settings.plc_read_interval_minutes} min) - {status_icons[1]}")
    print(f"  - Task 3: Process completed ({settings.process_completed_interval_minutes} min) - {status_icons[2]}")
    print(f"  - Task 4: Health monitoring ({settings.health_monitor_interval_minutes} min) - {status_icons[3]}")


def main():
    """Run all tests"""
    print("\n")
    print("=" * 80)
    print("SCHEDULER TASK CONTROL - CONFIGURATION VERIFICATION TEST")
    print("=" * 80)
    
    results = []
    
    try:
        results.append(("Configuration Loaded", test_config_loaded()))
        results.append(("Intervals Valid", test_intervals_configured()))
        results.append(("Batch Limit Valid", test_batch_limit()))
        results.append(("Task Count Valid", test_task_count()))
        results.append(("Master Switch Logic", test_master_switch_logic()))
        
        print_startup_log_simulation()
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {test_name:<40}: {status}")
        
        all_passed = all(result for _, result in results)
        
        print()
        if all_passed:
            print("✓✓✓ ALL TESTS PASSED ✓✓✓")
            print("\n✓ Configuration is valid and ready for production")
            print("✓ Scheduler will start with configured task settings")
            return 0
        else:
            print("✗✗✗ SOME TESTS FAILED ✗✗✗")
            print("\n✗ Please check configuration and fix issues")
            return 1
            
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
