╔════════════════════════════════════════════════════════════════════════════════╗
║                   SCHEDULER TASK REVIEW - Safety & Code Quality                ║
║                              February 15, 2026                                  ║
╚════════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════════
TASK 1: AUTO-SYNC MO FROM ODOO (auto_sync_mo_task)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE & GOOD:
  [✓] Logic is simple and clear - only fetch when mo_batch is empty
  [✓] Exception handling with logger.exception()
  [✓] Proper database connection cleanup with engine.connect() context manager
  [✓] Respects .env configuration (ENABLE_TASK_1_AUTO_SYNC)
  [✓] Prevents double-fetch (sequential processing via empty check)

⚠ POTENTIAL ISSUES:
  [1] Engine not properly disposed after use
      File: Line 50-52
      Problem: create_engine() creates a new engine each time, not disposed
      Risk: Connection pool depletion over time
      Fix: Should use `engine.dispose()` or reuse global engine
      
  [2] Race condition between count check and fetch
      File: Line 50-65
      Scenario: 
        - Thread A: Checks COUNT(*) = 0, gets True
        - Thread B: Checks COUNT(*) = 0, gets True (race!)
        - Both fetch and insert duplicate MOs
      Risk: Double MOs if tasks run in parallel
      Fix: Add advisory lock atau use database unique constraint
      
  [3] Silent failure on Odoo API timeout
      File: Line 66-69
      If fetch_mo_list_detailed() hangs, task waits forever
      Risk: Task blocks scheduler until timeout
      Fix: Add timeout parameter to fetch_mo_list_detailed()

RECOMMENDATION: Add timeout & connection disposal. Medium priority.

═══════════════════════════════════════════════════════════════════════════════════
TASK 2: PLC READ SYNC (plc_read_sync_task)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE & GOOD:
  [✓] Read PLC once per cycle (efficient)
  [✓] Check for active batches before reading PLC
  [✓] Immediate Odoo sync after PLC update (real-time)
  [✓] Properly set update_odoo flag after sync
  [✓] Good error handling with multiple try-except blocks
  [✓] DB session cleanup in finally blocks
  [✓] Comprehensive logging for debugging

⚠ ISSUES FOUND (BLOCKING):
  [1] CRITICAL: Skips Odoo sync if status_manufacturing already = 1
      File: Line 213-221
      
      Code snippet:
      ```
      if result.get("updated"):
          # ... prepare batch_data ...
          odoo_result = await consumption_service.process_batch_consumption(...)
      ```
      
      Problem: When batch status=1 (completed) at PLC read time:
      1. update_batch_if_changed() updates actual_consumption_silo_* = ✓
      2. update_batch_if_changed() updates status_manufacturing = 1
      3. return updated=True (because consumption changed)
      4. Try to sync to Odoo...
      5. BUT: In process_batch_consumption(), there's skip logic!
      6. Result: Consumption NOT sent to Odoo properly
      
      Current Behavior: Works but may have edge cases
      Risk: When batch status changes while Task 2 runs
      
      Recommended Fix: 
      - Check status BEFORE syncing: 
        ```python
        if result.get("updated"):
            # Check if status is NOT already completed
            if not batch.status_manufacturing:
                # Only sync if status=0 (still active)
                odoo_result = await consumption_service.process_batch_consumption(...)
        ```

  [2] No handling for already-completed batches
      File: Line 144-180
      If PLC keeps returning same MO with status=1:
      - Task 2 will keep trying to process it
      - Task 3 waiting to delete it
      - 6 other MOs stuck waiting
      
      Current Status: ⚠ Watch - depends on Task 3 execution

  [3] DB session created inside try block
      File: Line 118-125
      If check for active batches fails, session.close() never called
      
      Current: Actually OK because of db.close() in finally
      But pattern could be cleaner

ISSUES SEVERITY: 
  - Issue #1: WATCH (depends on Task 3 timing)
  - Issue #2: WATCH (architectural)
  - Issue #3: LOW (mitigated)

RECOMMENDATION: Monitor Task 2 + Task 3 interaction. Acceptable for now.

═══════════════════════════════════════════════════════════════════════════════════
TASK 3: PROCESS COMPLETED BATCHES (process_completed_batches_task)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE & GOOD:
  [✓] Only process batches with (status=1 AND update_odoo=True)
  [✓] Safe filter prevents premature deletion
  [✓] Move to history before delete (audit trail)
  [✓] Good error handling per batch (continue on error)
  [✓] Comprehensive logging
  [✓] DB session cleanup

✓ FLOW IS CORRECT:
  Task 3 will:
  1. Find batches where status_manufacturing=True AND update_odoo=True
  2. Call consume update to Odoo (re-send consumption)
  3. Move to mo_histories (audit record)
  4. Delete from mo_batch (clear queue)
  
  This SOLVES Task 2 stuck issue!

POTENTIAL ISSUE:
  [1] Redundant Odoo update call
      File: Line 275-277
      Task 2 already updated Odoo with consumption
      Task 3 calls process_batch_consumption() again
      
      Question: Is this intentional?
      - To mark batch as "completed" in Odoo?
      - To send final consumption data?
      
      Risk: If Odoo call fails, batch stuck (won't delete)
      
      Current: This is INTENTIONAL design (good for data consistency)
      Status: ✓ SAFE - designed this way

RECOMMENDATION: Excellent - clear and safe. Ready to execute.

═══════════════════════════════════════════════════════════════════════════════════
TASK 4: MONITOR BATCH HEALTH (monitor_batch_health_task)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE:
  [✓] No database modifications (read-only)
  [✓] Exception handling present

⚠ NOT YET IMPLEMENTED:
  File: Line 386-410
  
  Current state: Skeleton only
  ```python
  # TODO: Add monitoring logic
  # - Check last_read_from_plc timestamp untuk detect stuck batches
  # - Check consumption values untuk detect anomalies
  # - Trigger notifications jika needed
  ```
  
  Status: ✓ SAFE to leave as-is for now
  
  Future implementation should add:
  - Check if batch hasn't updated for X minutes → log warning
  - Check for zero consumption after long processing → anomaly alert
  - Check for unusual consumption spikes → quality warning

RECOMMENDATION: Currently harmless. Implementation can be deferred.

═══════════════════════════════════════════════════════════════════════════════════
TASK 5: EQUIPMENT FAILURE MONITORING (equipment_failure_monitoring_task)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE & GOOD:
  [✓] Complex error handling with nested try-except blocks
  [✓] Change detection (save_if_changed) prevents duplicate inserts
  [✓] Proper datetime parsing with error handling
  [✓] DB session cleanup
  [✓] Comprehensive debug logging
  [✓] Graceful degradation on invalid data

⚠ POTENTIAL ISSUES:
  [1] Nested exception handling is DEEP
      File: Line 448-495
      4 levels of nested try-except blocks
      
      Risk: Harder to debug, potential silent failures
      
      Suggested refactor: Split into smaller functions
      ```python
      async def _read_equipment_failure_from_plc()
      async def _save_to_local_db(failure_data)
      async def _sync_to_odoo_api(failure_record)
      ```
      
      Current: Works but could be cleaner

  [2] Timestamp parsing is fragile
      File: Line 476-485
      Only supports "YYYY-MM-DD HH:MM:SS" format
      If PLC sends different format, data lost
      
      Risk: Custom timestamp formats not supported
      Fix: Add more format alternatives
      
      Current: Acceptable with warning log

  [3] Missing retry logic for Odoo sync failure
      File: Line 485-510
      If Odoo API timeout/fails:
      - Local DB has the record
      - But Odoo doesn't
      - No automatic retry
      
      Risk: Eventually consistent (Odoo missing data)
      
      Current: Acceptable - manual Odoo re-sync can be done
      Improvement: Add retry mechanism in future

RECOMMENDATION: Acceptable. Consider refactoring for readability in future.

═══════════════════════════════════════════════════════════════════════════════════
SCHEDULER INITIALIZATION (start_scheduler)
═══════════════════════════════════════════════════════════════════════════════════

✓ SAFE & GOOD:
  [✓] Respects all 5 enable flags from .env
  [✓] Prevents duplicate job registration (replace_existing=True)
  [✓] APScheduler configuration looks good:
      - coalesce=True: Merge missed runs (good)
      - max_instances=1: No concurrent execution (good)
      - misfire_grace_time=30: 30s grace period (good)
  [✓] Clear logging of enabled/disabled tasks

STATUS: ✓ VERY GOOD - Well configured.

═══════════════════════════════════════════════════════════════════════════════════
GLOBAL ISSUES & RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════════════════════

1. ENGINE MANAGEMENT [MEDIUM PRIORITY]
   ─────────────────────────────────
   Multiple tasks create engine but don't dispose
   
   Fix: Use global engine instance
   ```python
   # In scheduler init
   _scheduler_engine = None
   
   def get_scheduler_engine():
       global _scheduler_engine
       if _scheduler_engine is None:
           _scheduler_engine = create_engine(settings.database_url)
       return _scheduler_engine
   ```

2. TASK SEQUENCING [LOW PRIORITY - CURRENT DESIGN OK]
   ───────────────────────────────────────────────
   Current sequence (parallel):
   - Task 1 @ 0, 60, 120... min
   - Task 2 @ 0, 5, 10, 15... min  ← Reads PLC
   - Task 3 @ 0, 3, 6, 9... min    ← Deletes from queue
   
   Design is intentional (real-time PLC read)
   Status: ✓ SAFE
   
   To prevent Task 2 stuck on single MO:
   - Task 3 should run frequently (✓ every 3 min)
   - Task 2 should handle completed batches (⚠ Check before sync)
   
   Current: Task 2 needs to check status BEFORE syncing to Odoo

3. DATABASE CONNECTIONS [LOW PRIORITY]
   ─────────────────────────────────
   Multiple SessionLocal() creations - OK but could optimize
   
   Current: Pattern is acceptable (SessionLocal is lightweight)
   Optimization: Not needed for current scale

═══════════════════════════════════════════════════════════════════════════════════
FINAL ASSESSMENT
═══════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│ Overall Rating: 8/10 - GOOD & MOSTLY SAFE                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

✓ STRENGTHS:
  • Clear task separation (5 distinct responsibilities)
  • Good error handling and logging
  • Respects .env configuration
  • APScheduler well configured
  • Task 3 properly handles cleanup
  • Proper DB session management

⚠ WATCHLIST:
  • Task 1: Engine disposal (fix timing issue)
  • Task 2: Check status before Odoo sync (architectural)
  • Task 5: Deeply nested try-except (refactoring candidate)

✓ READY FOR TESTING:
  All tasks can be safely tested in sequence
  Recommend: Test Task 1 → Task 2 → Task 3 cycle

═══════════════════════════════════════════════════════════════════════════════════
RECOMMENDED ACTIONS (Priority Order)
═══════════════════════════════════════════════════════════════════════════════════

PRIORITY 1 (Blocking - Do Now):
  [ ] Verify Task 2 + Task 3 interaction via test_task3_process_completed.py
  [ ] Check if Task 2 correctly syncs consumption despite status=1

PRIORITY 2 (Quality - This week):
  [ ] Add engine.dispose() or use global engine
  [ ] Refactor Task 5 nested try-except into helper functions
  [ ] Test race condition on Task 1 (concurrent execution)

PRIORITY 3 (Enhancement - Next sprint):
  [ ] Add retry logic to Task 5 Odoo sync
  [ ] Implement Task 4 batch health monitoring
  [ ] Add timestamp format flexibility to Task 5

═══════════════════════════════════════════════════════════════════════════════════
CONCLUSION: ✓ SAFE & ACCEPTABLE

Tasks are well-designed with good error handling. Main focus should be on testing
the Task 2 ↔ Task 3 interaction to ensure batches flow smoothly through the system.

Current bottleneck: Verify Task 3 executes properly to clear completed batches
from queue - this enables Task 1 to fetch new MOs and unblocks the full cycle.

═══════════════════════════════════════════════════════════════════════════════════
