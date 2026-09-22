# Sentinel Incident 67e9be3f-b541-4224-9668-d3c7e98d5a7a

Created: 2026-09-21 08:49:20.155045+00:00  
Status: review_required  
Mode: AI  
Model: deepseek-chat

## Analysis
Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.

## Root cause proposal
inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.

## Evidence references
E-4b53b377b69640ff, E-76acd1c5a1184b8d, E-f81be1f0d7e24519, E-f2e0c450e8624381, E-98c8f3a63ea74cf3, E-cf73809aedd14cd0

## Recommended action
NO_CODE_PATCH: Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.

## Remaining uncertainty
- The origin of the SELECT pg_sleep($1) statements is not visible in allowlisted source (search returned no matches), so the caller cannot be fully confirmed; it appears to be an external/periodic driver using inventory-service's DB credentials.
- inventory-service health/pool-stats endpoint was unavailable, so live pool occupancy could not be read directly; exhaustion is inferred from PoolTimeout errors plus DB-side busy inventory-service sessions.
- No explicit statement_timeout config is visible in allowlisted source; cannot confirm whether a timeout guard exists elsewhere.

## Critic: VERIFIED
Diagnosis is DB_POOL_EXHAUSTION at inventory-service; each link is independently corroborated across four evidence types.\n\n1) Blocking sessions: E-f81be1f0d7e24519 and E-93855876512e4daa both show multiple inventory-service backends state=active, wait_event=PgSleep on `SELECT pg_sleep(2)` — concurrent active sessions, not a single one. 2) Query cost: pg_stat_statements shows two `SELECT pg_sleep($1)` entries at mean_exec_time ~2001.7ms and ~1202.0ms (E-35d0069132124cb3, E-93855876512e4daa), matching the 2s sleeps; product SELECTs are ~0.04–0.08ms, ruling out a slow product query. 3) Error signature: logs show inventory-service /products 500 `PoolTimeout: couldn't get a connection after 0.80 sec` at ~807–809ms (E-76acd1c5a1184b8d) with matching gateway 502s, and trace E-f2e0c450e8624381 captures a 502 on GET /products with no slow product-DB child span. 4) Config: runtime.py line 24 confirms max_size=4, timeout=0.8, matching the observed 0.80s (E-98c8f3a63ea74cf3). 5) Pool telemetry: inventory-service pool-stats shows pool_available=0 with 352–359 request errors and ~420–429s cumulative wait_ms before, recovering to pool_available=4 / 0 errors after (E-3bbfb04e508f4c68, E-6a337c79e8c34027). Before/after metrics (E-9b5c56b1aa38430d→E-870ffa5f0c8e4714) show error_pct 50%→0% and inventory p95 ~808ms→3.9ms, consistent with pool release. Note: pg_sleep call_deltas are 0 in the 1s sample, so the "nonzero call deltas" claim is not confirmed by these snapshots; recurrence is instead evidenced by concurrent active PgSleep sessions and the pre-state pool exhaustion. Repository search returned no pg_sleep in allowlisted scope (E-dd9aab21088b4148, E-7870e9f6dce04091), supporting an external caller. pricing.py is provably unrelated (E-a92b5cc5b73b4a63).\n\nScope: this evidences a NO_CODE_PATCH diagnosis plus operator restoration, not an AI patch or production fix; recovery_actor is operator_experiment_runner and causality_limit applies.

Test sufficiency: Adequate for diagnosis: multi-source corroboration (pg_stat_activity, pg_stat_statements, logs, trace, pool-stats, before/after metrics) without a code patch. Gaps: no direct live pool-occupancy snapshot at fault (pool-stats health was available but not read at peak), pg_sleep call_deltas are 0 in the 1s sample, caller identity unresolved, and recovery is observational via operator restoration rather than a controlled experiment.

## Measured before / after
Scope: operator recovery (not an AI repair).
| Window | Service | Requests | Error % | P50 ms | P95 ms | P99 ms | RPS |
|---|---|---:|---:|---:|---:|---:|---:|
| before | gateway | 60 | 50.00 | 649.605 | 820.5355 | 821.8417999999999 | 3.0 |
| before | inventory-service | 60 | 50.00 | 620.9749999999999 | 808.6115 | 808.8315 | 3.0 |
| before | order-service | 30 | 0.00 | 451.18 | 463.792 | 468.38820000000004 | 1.5 |
| before | payment-service | 30 | 0.00 | 5.92 | 7.4285 | 7.6091 | 1.5 |
| before | user-service | 30 | 0.00 | 1.7 | 3.3969999999999967 | 5.386800000000002 | 1.5 |
| after | gateway | 156 | 0.00 | 27.005 | 49.215 | 57.69349999999999 | 7.8 |
| after | inventory-service | 156 | 0.00 | 2.29 | 3.9125 | 4.461499999999999 | 7.8 |
| after | order-service | 78 | 0.00 | 26.92 | 34.2555 | 37.01840000000001 | 3.9 |
| after | payment-service | 78 | 0.00 | 4.755 | 6.841499999999992 | 8.426000000000002 | 3.9 |
| after | user-service | 78 | 0.00 | 1.06 | 1.9614999999999998 | 2.437500000000001 | 3.9 |

## Evidence and audit
| Step | Time | Kind | Actor / Tool |
|---|---|---|---|
| 1686 | 2026-09-21 08:49:20.170301+00:00 | Investigation Started | Supervisor /  |
| 1687 | 2026-09-21 08:49:20.205223+00:00 | Observe | Investigator /  |
| 1688 | 2026-09-21 08:49:22.128180+00:00 | Tool Started | Investigator / search_logs |
| 1689 | 2026-09-21 08:49:22.515698+00:00 | Evidence Added | Investigator / search_logs |
| 1690 | 2026-09-21 08:49:22.529817+00:00 | Tool Finished | Investigator / search_logs |
| 1691 | 2026-09-21 08:49:22.542185+00:00 | Tool Started | Investigator / query_metrics |
| 1692 | 2026-09-21 08:49:22.693609+00:00 | Evidence Added | Investigator / query_metrics |
| 1693 | 2026-09-21 08:49:22.707997+00:00 | Tool Finished | Investigator / query_metrics |
| 1694 | 2026-09-21 08:49:22.719734+00:00 | Tool Started | Investigator / get_service_health |
| 1695 | 2026-09-21 08:49:23.647226+00:00 | Evidence Added | Investigator / get_service_health |
| 1696 | 2026-09-21 08:49:23.661275+00:00 | Tool Finished | Investigator / get_service_health |
| 1697 | 2026-09-21 08:49:23.672315+00:00 | Tool Started | Investigator / inspect_database |
| 1698 | 2026-09-21 08:49:24.909604+00:00 | Evidence Added | Investigator / inspect_database |
| 1699 | 2026-09-21 08:49:24.924623+00:00 | Tool Finished | Investigator / inspect_database |
| 1700 | 2026-09-21 08:49:24.936330+00:00 | Tool Started | Investigator / inspect_redis |
| 1701 | 2026-09-21 08:49:24.953688+00:00 | Evidence Added | Investigator / inspect_redis |
| 1702 | 2026-09-21 08:49:24.968323+00:00 | Tool Finished | Investigator / inspect_redis |
| 1703 | 2026-09-21 08:49:24.979677+00:00 | Tool Started | Investigator / inspect_kafka |
| 1704 | 2026-09-21 08:49:25.000891+00:00 | Evidence Added | Investigator / inspect_kafka |
| 1705 | 2026-09-21 08:49:25.016644+00:00 | Tool Finished | Investigator / inspect_kafka |
| 1706 | 2026-09-21 08:49:25.022854+00:00 | Observe | Investigator /  |
| 1707 | 2026-09-21 08:49:26.353966+00:00 | Tool Started | Investigator / get_trace |
| 1708 | 2026-09-21 08:49:27.066522+00:00 | Evidence Added | Investigator / get_trace |
| 1709 | 2026-09-21 08:49:27.081924+00:00 | Tool Finished | Investigator / get_trace |
| 1710 | 2026-09-21 08:49:27.097664+00:00 | Tool Started | Investigator / search_repository |
| 1711 | 2026-09-21 08:49:27.117731+00:00 | Evidence Added | Investigator / search_repository |
| 1712 | 2026-09-21 08:49:27.132578+00:00 | Tool Finished | Investigator / search_repository |
| 1713 | 2026-09-21 08:49:27.147991+00:00 | Tool Started | Investigator / search_repository |
| 1714 | 2026-09-21 08:49:27.167819+00:00 | Evidence Added | Investigator / search_repository |
| 1715 | 2026-09-21 08:49:27.182553+00:00 | Tool Finished | Investigator / search_repository |
| 1716 | 2026-09-21 08:49:27.197538+00:00 | Tool Started | Investigator / read_source_file |
| 1717 | 2026-09-21 08:49:27.216001+00:00 | Evidence Added | Investigator / read_source_file |
| 1718 | 2026-09-21 08:49:27.232126+00:00 | Tool Finished | Investigator / read_source_file |
| 1719 | 2026-09-21 08:49:27.239319+00:00 | Observe | Investigator /  |
| 1720 | 2026-09-21 08:49:30.289109+00:00 | Tool Started | Investigator / read_source_file |
| 1721 | 2026-09-21 08:49:30.305496+00:00 | Evidence Added | Investigator / read_source_file |
| 1722 | 2026-09-21 08:49:30.319740+00:00 | Tool Finished | Investigator / read_source_file |
| 1723 | 2026-09-21 08:49:30.335173+00:00 | Tool Started | Investigator / read_source_file |
| 1724 | 2026-09-21 08:49:30.351337+00:00 | Evidence Added | Investigator / read_source_file |
| 1725 | 2026-09-21 08:49:30.365285+00:00 | Tool Finished | Investigator / read_source_file |
| 1726 | 2026-09-21 08:49:30.379294+00:00 | Tool Started | Investigator / read_source_file |
| 1727 | 2026-09-21 08:49:30.396210+00:00 | Evidence Added | Investigator / read_source_file |
| 1728 | 2026-09-21 08:49:30.409655+00:00 | Tool Finished | Investigator / read_source_file |
| 1729 | 2026-09-21 08:49:30.447102+00:00 | Tool Started | Investigator / record_hypothesis |
| 1730 | 2026-09-21 08:49:30.486131+00:00 | Hypothesis Created | Supervisor /  |
| 1731 | 2026-09-21 08:49:30.502621+00:00 | Tool Finished | Investigator / record_hypothesis |
| 1732 | 2026-09-21 08:49:30.508702+00:00 | Observe | Investigator /  |
| 1733 | 2026-09-21 08:49:32.258499+00:00 | Tool Started | Investigator / read_evidence |
| 1734 | 2026-09-21 08:49:32.275860+00:00 | Tool Finished | Investigator / read_evidence |
| 1735 | 2026-09-21 08:49:32.290249+00:00 | Tool Started | Investigator / search_logs |
| 1736 | 2026-09-21 08:49:32.711191+00:00 | Evidence Added | Investigator / search_logs |
| 1737 | 2026-09-21 08:49:32.725615+00:00 | Tool Finished | Investigator / search_logs |
| 1738 | 2026-09-21 08:49:32.739636+00:00 | Tool Started | Investigator / read_evidence |
| 1739 | 2026-09-21 08:49:32.757500+00:00 | Tool Finished | Investigator / read_evidence |
| 1740 | 2026-09-21 08:49:32.765550+00:00 | Context Compacted | Supervisor /  |
| 1741 | 2026-09-21 08:49:32.771412+00:00 | Observe | Investigator /  |
| 1742 | 2026-09-21 08:49:34.475494+00:00 | Tool Started | Investigator / read_evidence |
| 1743 | 2026-09-21 08:49:34.493655+00:00 | Tool Finished | Investigator / read_evidence |
| 1744 | 2026-09-21 08:49:34.507986+00:00 | Tool Started | Investigator / read_evidence |
| 1745 | 2026-09-21 08:49:34.525678+00:00 | Tool Finished | Investigator / read_evidence |
| 1746 | 2026-09-21 08:49:34.532513+00:00 | Context Compacted | Supervisor /  |
| 1747 | 2026-09-21 08:49:34.537935+00:00 | Observe | Investigator /  |
| 1748 | 2026-09-21 08:49:38.848493+00:00 | Tool Started | Investigator / record_hypothesis |
| 1749 | 2026-09-21 08:49:38.898616+00:00 | Hypothesis Updated | Supervisor /  |
| 1750 | 2026-09-21 08:49:38.914772+00:00 | Tool Finished | Investigator / record_hypothesis |
| 1751 | 2026-09-21 08:49:38.921025+00:00 | Observe | Investigator /  |
| 1752 | 2026-09-21 08:49:44.828262+00:00 | Tool Started | Investigator / complete_investigation |
| 1753 | 2026-09-21 08:49:44.873367+00:00 | Tool Finished | Investigator / complete_investigation |
| 1754 | 2026-09-21 08:49:44.906424+00:00 | Root Cause Proposed | Investigator /  |
| 1755 | 2026-09-21 08:49:44.996267+00:00 | NO_CODE_PATCH | FixAgent /  |
| 1756 | 2026-09-21 08:49:45.007308+00:00 | Tool Started | RecoveryObserver / query_metrics |
| 1757 | 2026-09-21 08:49:45.151822+00:00 | Evidence Added | RecoveryObserver / query_metrics |
| 1758 | 2026-09-21 08:49:45.165731+00:00 | Tool Finished | RecoveryObserver / query_metrics |
| 1759 | 2026-09-21 08:49:45.177815+00:00 | Tool Started | RecoveryObserver / get_service_health |
| 1760 | 2026-09-21 08:49:46.082868+00:00 | Evidence Added | RecoveryObserver / get_service_health |
| 1761 | 2026-09-21 08:49:46.097200+00:00 | Tool Finished | RecoveryObserver / get_service_health |
| 1762 | 2026-09-21 08:49:46.108283+00:00 | Tool Started | RecoveryObserver / inspect_database |
| 1763 | 2026-09-21 08:49:47.333908+00:00 | Evidence Added | RecoveryObserver / inspect_database |
| 1764 | 2026-09-21 08:49:47.348421+00:00 | Tool Finished | RecoveryObserver / inspect_database |
| 1765 | 2026-09-21 08:49:47.359224+00:00 | Tool Started | RecoveryObserver / inspect_redis |
| 1766 | 2026-09-21 08:49:47.375868+00:00 | Evidence Added | RecoveryObserver / inspect_redis |
| 1767 | 2026-09-21 08:49:47.389927+00:00 | Tool Finished | RecoveryObserver / inspect_redis |
| 1768 | 2026-09-21 08:49:47.401120+00:00 | Tool Started | RecoveryObserver / inspect_kafka |
| 1769 | 2026-09-21 08:49:47.422462+00:00 | Evidence Added | RecoveryObserver / inspect_kafka |
| 1770 | 2026-09-21 08:49:47.436453+00:00 | Tool Finished | RecoveryObserver / inspect_kafka |
| 1771 | 2026-09-21 08:49:47.726365+00:00 | Recovery Measurement Requested | RecoveryObserver /  |
| 1772 | 2026-09-21 08:50:14.245579+00:00 | Tool Started | RecoveryObserver / query_metrics |
| 1773 | 2026-09-21 08:50:14.398361+00:00 | Evidence Added | RecoveryObserver / query_metrics |
| 1774 | 2026-09-21 08:50:14.412183+00:00 | Tool Finished | RecoveryObserver / query_metrics |
| 1775 | 2026-09-21 08:50:14.423356+00:00 | Tool Started | RecoveryObserver / get_service_health |
| 1776 | 2026-09-21 08:50:14.570665+00:00 | Evidence Added | RecoveryObserver / get_service_health |
| 1777 | 2026-09-21 08:50:14.585337+00:00 | Tool Finished | RecoveryObserver / get_service_health |
| 1778 | 2026-09-21 08:50:14.597101+00:00 | Tool Started | RecoveryObserver / inspect_database |
| 1779 | 2026-09-21 08:50:15.825359+00:00 | Evidence Added | RecoveryObserver / inspect_database |
| 1780 | 2026-09-21 08:50:15.840750+00:00 | Tool Finished | RecoveryObserver / inspect_database |
| 1781 | 2026-09-21 08:50:15.852817+00:00 | Tool Started | RecoveryObserver / inspect_redis |
| 1782 | 2026-09-21 08:50:15.868212+00:00 | Evidence Added | RecoveryObserver / inspect_redis |
| 1783 | 2026-09-21 08:50:15.882292+00:00 | Tool Finished | RecoveryObserver / inspect_redis |
| 1784 | 2026-09-21 08:50:15.893902+00:00 | Tool Started | RecoveryObserver / inspect_kafka |
| 1785 | 2026-09-21 08:50:15.916664+00:00 | Evidence Added | RecoveryObserver / inspect_kafka |
| 1786 | 2026-09-21 08:50:15.930491+00:00 | Tool Finished | RecoveryObserver / inspect_kafka |
| 1787 | 2026-09-21 08:50:16.702938+00:00 | Recovery Measured | RecoveryObserver /  |
| 1788 | 2026-09-21 08:50:18.180269+00:00 | Critic Started | Critic /  |
| 1789 | 2026-09-21 08:50:25.688672+00:00 | Tool Started | Critic / submit_verification |
| 1790 | 2026-09-21 08:50:25.742443+00:00 | Tool Finished | Critic / submit_verification |
| 1791 | 2026-09-21 08:50:25.782382+00:00 | Critic VERIFIED | Critic /  |
| 1792 | 2026-09-21 08:50:25.798702+00:00 | Root Cause Confirmed | Critic /  |
| 1793 | 2026-09-21 08:50:26.950917+00:00 | Incident Report | Supervisor /  |

## Complete raw record
```json
{
  "id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
  "created_at": "2026-09-21 08:49:20.155045+00:00",
  "status": "review_required",
  "signal": {
    "source": "operator_requested",
    "signals": [
      {
        "avg_ms": "631.38",
        "p50_ms": 507.025,
        "p95_ms": 819.4545,
        "p99_ms": 820.8716,
        "service": "gateway",
        "requests": 92,
        "error_pct": "48.91",
        "throughput_rps": 3.066666666666667
      },
      {
        "avg_ms": "599.04",
        "p50_ms": 439.625,
        "p95_ms": 807.5314999999999,
        "p99_ms": 807.9346,
        "service": "inventory-service",
        "requests": 92,
        "error_pct": "48.91",
        "throughput_rps": 3.066666666666667
      },
      {
        "avg_ms": "0.32",
        "p50_ms": 0.32,
        "p95_ms": 0.329,
        "p99_ms": 0.32980000000000004,
        "service": "notification-service",
        "requests": 2,
        "error_pct": "0.00",
        "throughput_rps": 0.06666666666666667
      },
      {
        "avg_ms": "433.52",
        "p50_ms": 455.0,
        "p95_ms": 472.389,
        "p99_ms": 478.1534,
        "service": "order-service",
        "requests": 47,
        "error_pct": "0.00",
        "throughput_rps": 1.5666666666666667
      },
      {
        "avg_ms": "6.75",
        "p50_ms": 6.81,
        "p95_ms": 8.674,
        "p99_ms": 14.69599999999999,
        "service": "payment-service",
        "requests": 47,
        "error_pct": "0.00",
        "throughput_rps": 1.5666666666666667
      },
      {
        "avg_ms": "1.61",
        "p50_ms": 1.52,
        "p95_ms": 2.929999999999998,
        "p99_ms": 3.3778,
        "service": "user-service",
        "requests": 47,
        "error_pct": "0.00",
        "throughput_rps": 1.5666666666666667
      }
    ]
  },
  "report": {
    "mode": "AI",
    "model": "deepseek-chat",
    "patch": null,
    "critic": {
      "verdict": "VERIFIED",
      "evidence_ids": [
        "E-f81be1f0d7e24519",
        "E-93855876512e4daa",
        "E-35d0069132124cb3",
        "E-76acd1c5a1184b8d",
        "E-4b53b377b69640ff",
        "E-f2e0c450e8624381",
        "E-98c8f3a63ea74cf3",
        "E-3bbfb04e508f4c68",
        "E-6a337c79e8c34027",
        "E-9b5c56b1aa38430d",
        "E-870ffa5f0c8e4714",
        "E-cf73809aedd14cd0",
        "E-dd9aab21088b4148",
        "E-7870e9f6dce04091",
        "E-a92b5cc5b73b4a63"
      ],
      "regression_risks": [
        "Implementing statement_timeout / idle_in_transaction_session_timeout or raising pool max_size could truncate legitimate long queries or increase DB connection pressure, causing new timeout errors elsewhere.",
        "Terminating backends (pg_cancel_backend/pg_terminate_backend) risks disrupting in-flight legitimate transactions if application_name-based targeting is imprecise.",
        "No patch was applied, so if the pg_sleep driver recurs, the same PoolTimeout/502 signature will return; the diagnosis does not provide a durable code-level safeguard."
      ],
      "test_sufficiency": "Adequate for diagnosis: multi-source corroboration (pg_stat_activity, pg_stat_statements, logs, trace, pool-stats, before/after metrics) without a code patch. Gaps: no direct live pool-occupancy snapshot at fault (pool-stats health was available but not read at peak), pg_sleep call_deltas are 0 in the 1s sample, caller identity unresolved, and recovery is observational via operator restoration rather than a controlled experiment.",
      "verification_summary": "Diagnosis is DB_POOL_EXHAUSTION at inventory-service; each link is independently corroborated across four evidence types.\\n\\n1) Blocking sessions: E-f81be1f0d7e24519 and E-93855876512e4daa both show multiple inventory-service backends state=active, wait_event=PgSleep on `SELECT pg_sleep(2)` — concurrent active sessions, not a single one. 2) Query cost: pg_stat_statements shows two `SELECT pg_sleep($1)` entries at mean_exec_time ~2001.7ms and ~1202.0ms (E-35d0069132124cb3, E-93855876512e4daa), matching the 2s sleeps; product SELECTs are ~0.04–0.08ms, ruling out a slow product query. 3) Error signature: logs show inventory-service /products 500 `PoolTimeout: couldn't get a connection after 0.80 sec` at ~807–809ms (E-76acd1c5a1184b8d) with matching gateway 502s, and trace E-f2e0c450e8624381 captures a 502 on GET /products with no slow product-DB child span. 4) Config: runtime.py line 24 confirms max_size=4, timeout=0.8, matching the observed 0.80s (E-98c8f3a63ea74cf3). 5) Pool telemetry: inventory-service pool-stats shows pool_available=0 with 352–359 request errors and ~420–429s cumulative wait_ms before, recovering to pool_available=4 / 0 errors after (E-3bbfb04e508f4c68, E-6a337c79e8c34027). Before/after metrics (E-9b5c56b1aa38430d→E-870ffa5f0c8e4714) show error_pct 50%→0% and inventory p95 ~808ms→3.9ms, consistent with pool release. Note: pg_sleep call_deltas are 0 in the 1s sample, so the \"nonzero call deltas\" claim is not confirmed by these snapshots; recurrence is instead evidenced by concurrent active PgSleep sessions and the pre-state pool exhaustion. Repository search returned no pg_sleep in allowlisted scope (E-dd9aab21088b4148, E-7870e9f6dce04091), supporting an external caller. pricing.py is provably unrelated (E-a92b5cc5b73b4a63).\\n\\nScope: this evidences a NO_CODE_PATCH diagnosis plus operator restoration, not an AI patch or production fix; recovery_actor is operator_experiment_runner and causality_limit applies.",
      "alternative_explanations": [
        "Partial or intermittent pool exhaustion: pre-state shows pool_available=0 and pooled wait_ms ~420s against max_size=4, but only inventory-service is affected while other services pool healthily; a generic DB/network-wide stall is not supported, though pool sizing (max_size=4) as a contributing factor vs. pure pg_sleep monopolization cannot be separated from these snapshots.",
        "Caller attribution is inferential: pg_sleep sessions carry application_name=inventory-service, but the issuing code is absent from allowlisted source and call_deltas are 0 in the 1s sample, so the executive caller (job/driver vs. app code path) is not independently confirmed.",
        "Independent test-loading artifact: an operator/synthetic driver could be inducing both the pg_sleep load and the observed latency; the before/after recovery coincides with operator restoration, so causality rests on correlation plus DB-state and error-signature agreement rather than a controlled A/B test."
      ]
    },
    "summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
    "diagnosis": {
      "category": "DB_POOL_EXHAUSTION",
      "hypothesis": "inventory-service /products fails because all 4 DB pool connections are held by long-running `SELECT pg_sleep($1)` sessions, causing PoolTimeout (0.8s) → 500, propagated as gateway 502.",
      "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
      "evidence_ids": [
        "E-4b53b377b69640ff",
        "E-76acd1c5a1184b8d",
        "E-f81be1f0d7e24519",
        "E-f2e0c450e8624381",
        "E-98c8f3a63ea74cf3",
        "E-cf73809aedd14cd0"
      ],
      "code_locations": [
        {
          "path": "services/runtime.py",
          "end_line": 24,
          "start_line": 24
        },
        {
          "path": "services/pricing.py",
          "end_line": 6,
          "start_line": 1
        }
      ],
      "patch_decision": "NO_CODE_PATCH",
      "recommended_fix": "Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.",
      "affected_service": "inventory-service",
      "reasoning_summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
      "remaining_uncertainty": [
        "The origin of the SELECT pg_sleep($1) statements is not visible in allowlisted source (search returned no matches), so the caller cannot be fully confirmed; it appears to be an external/periodic driver using inventory-service's DB credentials.",
        "inventory-service health/pool-stats endpoint was unavailable, so live pool occupancy could not be read directly; exhaustion is inferred from PoolTimeout errors plus DB-side busy inventory-service sessions.",
        "No explicit statement_timeout config is visible in allowlisted source; cannot confirm whether a timeout guard exists elsewhere."
      ]
    },
    "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
    "workflow_stage": "completed",
    "measured_recovery": {
      "after": {
        "http": [
          {
            "avg_ms": "27.15",
            "p50_ms": 27.005,
            "p95_ms": 49.215,
            "p99_ms": 57.69349999999999,
            "service": "gateway",
            "requests": 156,
            "error_pct": "0.00",
            "throughput_rps": 7.8
          },
          {
            "avg_ms": "2.58",
            "p50_ms": 2.29,
            "p95_ms": 3.9125,
            "p99_ms": 4.461499999999999,
            "service": "inventory-service",
            "requests": 156,
            "error_pct": "0.00",
            "throughput_rps": 7.8
          },
          {
            "avg_ms": "27.10",
            "p50_ms": 26.92,
            "p95_ms": 34.2555,
            "p99_ms": 37.01840000000001,
            "service": "order-service",
            "requests": 78,
            "error_pct": "0.00",
            "throughput_rps": 3.9
          },
          {
            "avg_ms": "4.97",
            "p50_ms": 4.755,
            "p95_ms": 6.841499999999992,
            "p99_ms": 8.426000000000002,
            "service": "payment-service",
            "requests": 78,
            "error_pct": "0.00",
            "throughput_rps": 3.9
          },
          {
            "avg_ms": "1.18",
            "p50_ms": 1.06,
            "p95_ms": 1.9614999999999998,
            "p99_ms": 2.437500000000001,
            "service": "user-service",
            "requests": 78,
            "error_pct": "0.00",
            "throughput_rps": 3.9
          }
        ],
        "redis": {
          "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
          "catalog_ttl": 4,
          "keyspace_hits": 58873,
          "keyspace_misses": 317764
        },
        "source": "Measured",
        "db_pool": [
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "gateway"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "gateway",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 54,
                  "pool_size": 1,
                  "requests_num": 358,
                  "connections_ms": 23,
                  "pool_available": 1,
                  "connections_num": 1,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "gateway"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "user-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "user-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 2282,
                  "pool_size": 2,
                  "requests_num": 9566,
                  "connections_ms": 50,
                  "pool_available": 2,
                  "connections_num": 3,
                  "requests_queued": 2,
                  "requests_wait_ms": 0,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "user-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "order-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "order-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 19747,
                  "pool_size": 3,
                  "requests_num": 8469,
                  "connections_ms": 63,
                  "pool_available": 3,
                  "connections_num": 4,
                  "requests_queued": 3,
                  "requests_wait_ms": 2,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "order-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "payment-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "payment-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 20855,
                  "pool_size": 3,
                  "requests_num": 8536,
                  "connections_ms": 58,
                  "pool_available": 3,
                  "connections_num": 4,
                  "requests_queued": 3,
                  "requests_wait_ms": 3,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "payment-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "inventory-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "inventory-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 1483565,
                  "pool_size": 4,
                  "requests_num": 61981,
                  "connections_ms": 72,
                  "pool_available": 4,
                  "connections_num": 5,
                  "requests_errors": 359,
                  "requests_queued": 712,
                  "requests_wait_ms": 428882,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "inventory-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "notification-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "notification-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 26968,
                  "pool_size": 2,
                  "requests_num": 8469,
                  "connections_ms": 46,
                  "pool_available": 2,
                  "connections_num": 3,
                  "requests_queued": 2,
                  "requests_wait_ms": 0,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "notification-service"
              },
              "http_status": 200
            }
          }
        ],
        "database": {
          "source": "Measured",
          "activity": [
            {
              "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "SELECT * FROM users WHERE id=1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "user-service"
            },
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "gateway"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "notification-service"
            },
            {
              "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "notification-service"
            },
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "inventory-service"
            },
            {
              "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "SELECT pg_sleep(2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT status,payload FROM recovery_checks WHERE run_id=$1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "SELECT * FROM users WHERE id=1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "user-service"
            }
          ],
          "statements": [
            {
              "dbid": 16384,
              "rows": 56920,
              "calls": 1423,
              "query": "SELECT id FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": 5452309003183002855,
              "mean_exec_time": 0.07385190864371051
            },
            {
              "dbid": 16384,
              "rows": 87840,
              "calls": 2196,
              "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": -5751767986386312266,
              "mean_exec_time": 0.08088427140255004
            },
            {
              "dbid": 16384,
              "rows": 56920,
              "calls": 56920,
              "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
              "userid": 10,
              "queryid": -4386432147220479149,
              "mean_exec_time": 0.03729027362965548
            },
            {
              "dbid": 16384,
              "rows": 488,
              "calls": 488,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -3416356442043621232,
              "mean_exec_time": 2001.7300318627035
            },
            {
              "dbid": 16384,
              "rows": 460,
              "calls": 460,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -11391618518959119,
              "mean_exec_time": 1201.9669297260864
            }
          ],
          "call_deltas": [
            {
              "dbid": 16384,
              "query": "SELECT id FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": 5452309003183002855,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": -5751767986386312266,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
              "userid": 10,
              "queryid": -4386432147220479149,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -3416356442043621232,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -11391618518959119,
              "calls_delta": 0
            }
          ],
          "sample_seconds": 1
        },
        "kafka_lag": [
          {
            "lag": 0,
            "partition": 0,
            "end_offset": 15403,
            "committed_offset": 15403
          }
        ],
        "observed_at": "2026-09-21T08:50:14.236132+00:00",
        "evidence_ids": [
          "E-870ffa5f0c8e4714",
          "E-6a337c79e8c34027",
          "E-35d0069132124cb3",
          "E-3839f12052c84057",
          "E-2d63e10d6ee04bb8"
        ],
        "window_seconds": 20
      },
      "before": {
        "http": [
          {
            "avg_ms": "645.37",
            "p50_ms": 649.605,
            "p95_ms": 820.5355,
            "p99_ms": 821.8417999999999,
            "service": "gateway",
            "requests": 60,
            "error_pct": "50.00",
            "throughput_rps": 3.0
          },
          {
            "avg_ms": "614.23",
            "p50_ms": 620.9749999999999,
            "p95_ms": 808.6115,
            "p99_ms": 808.8315,
            "service": "inventory-service",
            "requests": 60,
            "error_pct": "50.00",
            "throughput_rps": 3.0
          },
          {
            "avg_ms": "452.28",
            "p50_ms": 451.18,
            "p95_ms": 463.792,
            "p99_ms": 468.38820000000004,
            "service": "order-service",
            "requests": 30,
            "error_pct": "0.00",
            "throughput_rps": 1.5
          },
          {
            "avg_ms": "5.99",
            "p50_ms": 5.92,
            "p95_ms": 7.4285,
            "p99_ms": 7.6091,
            "service": "payment-service",
            "requests": 30,
            "error_pct": "0.00",
            "throughput_rps": 1.5
          },
          {
            "avg_ms": "1.91",
            "p50_ms": 1.7,
            "p95_ms": 3.3969999999999967,
            "p99_ms": 5.386800000000002,
            "service": "user-service",
            "requests": 30,
            "error_pct": "0.00",
            "throughput_rps": 1.5
          }
        ],
        "redis": {
          "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
          "catalog_ttl": 29,
          "keyspace_hits": 58536,
          "keyspace_misses": 315732
        },
        "source": "Measured",
        "db_pool": [
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "gateway"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "gateway",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 53,
                  "pool_size": 1,
                  "requests_num": 354,
                  "connections_ms": 23,
                  "pool_available": 1,
                  "connections_num": 1,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "gateway"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "user-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "user-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 2252,
                  "pool_size": 2,
                  "requests_num": 9459,
                  "connections_ms": 50,
                  "pool_available": 2,
                  "connections_num": 3,
                  "requests_queued": 2,
                  "requests_wait_ms": 0,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "user-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "order-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "order-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 19507,
                  "pool_size": 3,
                  "requests_num": 8363,
                  "connections_ms": 63,
                  "pool_available": 3,
                  "connections_num": 4,
                  "requests_queued": 3,
                  "requests_wait_ms": 2,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "order-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "payment-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "payment-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 20595,
                  "pool_size": 3,
                  "requests_num": 8429,
                  "connections_ms": 58,
                  "pool_available": 3,
                  "connections_num": 4,
                  "requests_queued": 3,
                  "requests_wait_ms": 3,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "payment-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "inventory-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "inventory-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 1459531,
                  "pool_size": 4,
                  "requests_num": 61957,
                  "connections_ms": 72,
                  "pool_available": 0,
                  "connections_num": 5,
                  "requests_errors": 352,
                  "requests_queued": 699,
                  "requests_wait_ms": 420775,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "inventory-service"
              },
              "http_status": 200
            }
          },
          {
            "health": {
              "body": {
                "status": "healthy",
                "service": "notification-service"
              },
              "http_status": 200
            },
            "source": "Measured",
            "service": "notification-service",
            "pool-stats": {
              "body": {
                "pool": {
                  "pool_max": 4,
                  "pool_min": 1,
                  "usage_ms": 26653,
                  "pool_size": 2,
                  "requests_num": 8362,
                  "connections_ms": 46,
                  "pool_available": 2,
                  "connections_num": 3,
                  "requests_queued": 2,
                  "requests_wait_ms": 0,
                  "requests_waiting": 0
                },
                "source": "Measured",
                "service": "notification-service"
              },
              "http_status": 200
            }
          }
        ],
        "database": {
          "source": "Measured",
          "activity": [
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "SELECT * FROM users WHERE id=1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "user-service"
            },
            {
              "query": "SELECT pg_sleep(2)",
              "state": "active",
              "wait_event": "PgSleep",
              "wait_event_type": "Timeout",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT 1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "gateway"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "notification-service"
            },
            {
              "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO tool_calls(id,external_id,incident_id,run_id,agent,tool_name,arguments,status) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "notification-service"
            },
            {
              "query": "SELECT pg_sleep(2)",
              "state": "active",
              "wait_event": "PgSleep",
              "wait_event_type": "Timeout",
              "application_name": "inventory-service"
            },
            {
              "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "SELECT pg_sleep(2)",
              "state": "active",
              "wait_event": "PgSleep",
              "wait_event_type": "Timeout",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT pg_sleep(2)",
              "state": "active",
              "wait_event": "PgSleep",
              "wait_event_type": "Timeout",
              "application_name": "inventory-service"
            },
            {
              "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "sentinel"
            },
            {
              "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "payment-service"
            },
            {
              "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "order-service"
            },
            {
              "query": "SELECT * FROM users WHERE id=1",
              "state": "idle",
              "wait_event": "ClientRead",
              "wait_event_type": "Client",
              "application_name": "user-service"
            }
          ],
          "statements": [
            {
              "dbid": 16384,
              "rows": 56920,
              "calls": 1423,
              "query": "SELECT id FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": 5452309003183002855,
              "mean_exec_time": 0.07385190864371051
            },
            {
              "dbid": 16384,
              "rows": 87600,
              "calls": 2190,
              "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": -5751767986386312266,
              "mean_exec_time": 0.08092246894977165
            },
            {
              "dbid": 16384,
              "rows": 56920,
              "calls": 56920,
              "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
              "userid": 10,
              "queryid": -4386432147220479149,
              "mean_exec_time": 0.03729027362965548
            },
            {
              "dbid": 16384,
              "rows": 476,
              "calls": 476,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -3416356442043621232,
              "mean_exec_time": 2001.7273390735281
            },
            {
              "dbid": 16384,
              "rows": 460,
              "calls": 460,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -11391618518959119,
              "mean_exec_time": 1201.9669297260864
            }
          ],
          "call_deltas": [
            {
              "dbid": 16384,
              "query": "SELECT id FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": 5452309003183002855,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
              "userid": 10,
              "queryid": -5751767986386312266,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
              "userid": 10,
              "queryid": -4386432147220479149,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -3416356442043621232,
              "calls_delta": 0
            },
            {
              "dbid": 16384,
              "query": "SELECT pg_sleep($1)",
              "userid": 10,
              "queryid": -11391618518959119,
              "calls_delta": 0
            }
          ],
          "sample_seconds": 1
        },
        "kafka_lag": [
          {
            "lag": 0,
            "partition": 0,
            "end_offset": 15298,
            "committed_offset": 15298
          }
        ],
        "observed_at": "2026-09-21T08:49:44.998529+00:00",
        "evidence_ids": [
          "E-9b5c56b1aa38430d",
          "E-3bbfb04e508f4c68",
          "E-93855876512e4daa",
          "E-56e7c4c65aef46f8",
          "E-a108e5fac9e4484e"
        ],
        "window_seconds": 20
      },
      "recovery_actor": "operator_experiment_runner",
      "causality_limit": "Operator restoration is observational support; not an AI patch or proof of a unique mechanism.",
      "not_an_ai_repair": true
    },
    "production_applied": false
  },
  "baseline": [
    {
      "avg_ms": "34.30",
      "p50_ms": 37.11,
      "p95_ms": 76.53,
      "p99_ms": 90.9,
      "service": "gateway",
      "requests": 151,
      "error_pct": "0.00",
      "throughput_rps": 7.55
    },
    {
      "avg_ms": "3.24",
      "p50_ms": 2.705,
      "p95_ms": 6.406999999999995,
      "p99_ms": 10.340100000000014,
      "service": "inventory-service",
      "requests": 152,
      "error_pct": "0.00",
      "throughput_rps": 7.6
    },
    {
      "avg_ms": "33.12",
      "p50_ms": 30.95,
      "p95_ms": 47.81699999999999,
      "p99_ms": 52.917800000000035,
      "service": "order-service",
      "requests": 75,
      "error_pct": "0.00",
      "throughput_rps": 3.75
    },
    {
      "avg_ms": "5.56",
      "p50_ms": 5.11,
      "p95_ms": 8.2,
      "p99_ms": 10.288400000000005,
      "service": "payment-service",
      "requests": 75,
      "error_pct": "0.00",
      "throughput_rps": 3.75
    },
    {
      "avg_ms": "1.34",
      "p50_ms": 1.2,
      "p95_ms": 2.1475,
      "p99_ms": 2.7525000000000004,
      "service": "user-service",
      "requests": 76,
      "error_pct": "0.00",
      "throughput_rps": 3.8
    }
  ],
  "verification": null,
  "mode": "AI",
  "investigation_run": "43da4292-df18-4b21-875e-460493346e93",
  "controlled_recovery": true,
  "steps": [
    {
      "id": 1686,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:20.170301+00:00",
      "kind": "Investigation Started",
      "payload": {
        "mode": "AI",
        "agent": "Supervisor",
        "run_id": "43da4292-df18-4b21-875e-460493346e93"
      }
    },
    {
      "id": 1687,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:20.205223+00:00",
      "kind": "Observe",
      "payload": {
        "step": 1,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 0
      }
    },
    {
      "id": 1688,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.128180+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "b7bada8f-7eec-4fab-992a-79979f555506"
      }
    },
    {
      "id": 1689,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.515698+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-4b53b377b69640ff"
      }
    },
    {
      "id": 1690,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.529817+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-4b53b377b69640ff"
        ],
        "tool_call_id": "b7bada8f-7eec-4fab-992a-79979f555506"
      }
    },
    {
      "id": 1691,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.542185+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "query_metrics",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "a1178129-0f80-451d-ba66-9e1e34a75458"
      }
    },
    {
      "id": 1692,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.693609+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "query_metrics",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-cf0870eeaab0470c"
      }
    },
    {
      "id": 1693,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.707997+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "query_metrics",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-cf0870eeaab0470c"
        ],
        "tool_call_id": "a1178129-0f80-451d-ba66-9e1e34a75458"
      }
    },
    {
      "id": 1694,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:22.719734+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "get_service_health",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "5ad1fb07-2e7f-416c-af49-4aa1fc8f5862"
      }
    },
    {
      "id": 1695,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:23.647226+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "get_service_health",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-cf73809aedd14cd0"
      }
    },
    {
      "id": 1696,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:23.661275+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "get_service_health",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-cf73809aedd14cd0"
        ],
        "tool_call_id": "5ad1fb07-2e7f-416c-af49-4aa1fc8f5862"
      }
    },
    {
      "id": 1697,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:23.672315+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_database",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "9efcf451-13e9-42cb-b92e-e5a3a40c38f1"
      }
    },
    {
      "id": 1698,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.909604+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_database",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-f81be1f0d7e24519"
      }
    },
    {
      "id": 1699,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.924623+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_database",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-f81be1f0d7e24519"
        ],
        "tool_call_id": "9efcf451-13e9-42cb-b92e-e5a3a40c38f1"
      }
    },
    {
      "id": 1700,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.936330+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_redis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "90074b13-a209-4b40-a953-500eb27ac893"
      }
    },
    {
      "id": 1701,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.953688+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_redis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-6d5d193c26474a92"
      }
    },
    {
      "id": 1702,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.968323+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_redis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-6d5d193c26474a92"
        ],
        "tool_call_id": "90074b13-a209-4b40-a953-500eb27ac893"
      }
    },
    {
      "id": 1703,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:24.979677+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "f2192ad4-dd14-461b-bbe3-b41cecd09f1c"
      }
    },
    {
      "id": 1704,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:25.000891+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-78c3835c364d421b"
      }
    },
    {
      "id": 1705,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:25.016644+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-78c3835c364d421b"
        ],
        "tool_call_id": "f2192ad4-dd14-461b-bbe3-b41cecd09f1c"
      }
    },
    {
      "id": 1706,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:25.022854+00:00",
      "kind": "Observe",
      "payload": {
        "step": 2,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 6
      }
    },
    {
      "id": 1707,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:26.353966+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "get_trace",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "trace_id": "331dcd9c02294392d2c34f867aaf71fc"
        },
        "tool_call_id": "2a52bdc2-e5ac-4db0-bfb5-5bdd5516102f"
      }
    },
    {
      "id": 1708,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.066522+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "get_trace",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-f2e0c450e8624381"
      }
    },
    {
      "id": 1709,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.081924+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "get_trace",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-f2e0c450e8624381"
        ],
        "tool_call_id": "2a52bdc2-e5ac-4db0-bfb5-5bdd5516102f"
      }
    },
    {
      "id": 1710,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.097664+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "text": "pg_sleep"
        },
        "tool_call_id": "fe0f031e-23c5-4b2f-8583-d652c7ea6f8f"
      }
    },
    {
      "id": 1711,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.117731+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-dd9aab21088b4148"
      }
    },
    {
      "id": 1712,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.132578+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-dd9aab21088b4148"
        ],
        "tool_call_id": "fe0f031e-23c5-4b2f-8583-d652c7ea6f8f"
      }
    },
    {
      "id": 1713,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.147991+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "text": "products"
        },
        "tool_call_id": "f2433a9d-271b-47e4-97d7-2cd10d4a268f"
      }
    },
    {
      "id": 1714,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.167819+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-7870e9f6dce04091"
      }
    },
    {
      "id": 1715,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.182553+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "search_repository",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-7870e9f6dce04091"
        ],
        "tool_call_id": "f2433a9d-271b-47e4-97d7-2cd10d4a268f"
      }
    },
    {
      "id": 1716,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.197538+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "path": "services/pricing.py"
        },
        "tool_call_id": "cea6b377-c6ed-4865-a75d-5c59609c69c1"
      }
    },
    {
      "id": 1717,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.216001+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-a92b5cc5b73b4a63"
      }
    },
    {
      "id": 1718,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.232126+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-a92b5cc5b73b4a63"
        ],
        "tool_call_id": "cea6b377-c6ed-4865-a75d-5c59609c69c1"
      }
    },
    {
      "id": 1719,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:27.239319+00:00",
      "kind": "Observe",
      "payload": {
        "step": 3,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 10
      }
    },
    {
      "id": 1720,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.289109+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "path": "services/pricing.py",
          "end_line": 160,
          "start_line": 1
        },
        "tool_call_id": "cf5800fc-351b-4bb6-bbbd-5c4a5deafbd8"
      }
    },
    {
      "id": 1721,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.305496+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-0e024ec6fa254ea5"
      }
    },
    {
      "id": 1722,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.319740+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-0e024ec6fa254ea5"
        ],
        "tool_call_id": "cf5800fc-351b-4bb6-bbbd-5c4a5deafbd8"
      }
    },
    {
      "id": 1723,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.335173+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "path": "services/runtime.py"
        },
        "tool_call_id": "3774e6df-bda3-4aa3-ba0f-73bfaf8a90da"
      }
    },
    {
      "id": 1724,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.351337+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-98c8f3a63ea74cf3"
      }
    },
    {
      "id": 1725,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.365285+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-98c8f3a63ea74cf3"
        ],
        "tool_call_id": "3774e6df-bda3-4aa3-ba0f-73bfaf8a90da"
      }
    },
    {
      "id": 1726,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.379294+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "path": "tests/pricing_contract.py"
        },
        "tool_call_id": "56e7edee-7b84-4eb0-99db-26aee94687a0"
      }
    },
    {
      "id": 1727,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.396210+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Repository",
        "evidence_id": "E-824d3276fddc4840"
      }
    },
    {
      "id": 1728,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.409655+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_source_file",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-824d3276fddc4840"
        ],
        "tool_call_id": "56e7edee-7b84-4eb0-99db-26aee94687a0"
      }
    },
    {
      "id": 1729,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.447102+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "record_hypothesis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "status": "CREATED",
          "hypothesis": "inventory-service /products returns 500 (PoolTimeout connecting to Postgres) because a slow/long-running DB query (pg_sleep) holds connections, exhausting the small pool (pool_max=4). Gateway surfaces 502. pricing.py is the only patch target and appears unrelated.",
          "evidence_ids": [
            "E-4b53b377b69640ff",
            "E-f81be1f0d7e24519",
            "E-cf73809aedd14cd0"
          ],
          "hypothesis_id": "H-1",
          "affected_service": "inventory-service",
          "reasoning_summary": "Logs show inventory-service /products 500 with 'PoolTimeout: couldn't get a connection after 0.80 sec'; gateway emits 502 for same traces. pg_stat_activity shows inventory-service sessions active in PgSleep (SELECT pg_sleep(2)). pg_stat_statements shows SELECT pg_sleep($1) with mean_exec_time ~2001ms across 432 calls. inventory-service health is unavailable, so no pool stats available. PoolTimeout with ~0.80s wait suggests pool exhaustion.",
          "next_evidence_needed": "Confirm whether slow query is the dominant cause vs. pool misconfig; check if pg_sleep is periodic/synthetic driver vs application code; verify pricing.py relevance to inventory path."
        },
        "tool_call_id": "da78efac-a028-400f-92dd-399361e75edf"
      }
    },
    {
      "id": 1730,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.486131+00:00",
      "kind": "Hypothesis Created",
      "payload": {
        "agent": "Supervisor",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "CREATED",
        "hypothesis": "inventory-service /products returns 500 (PoolTimeout connecting to Postgres) because a slow/long-running DB query (pg_sleep) holds connections, exhausting the small pool (pool_max=4). Gateway surfaces 502. pricing.py is the only patch target and appears unrelated.",
        "evidence_ids": [
          "E-4b53b377b69640ff",
          "E-f81be1f0d7e24519",
          "E-cf73809aedd14cd0"
        ],
        "hypothesis_id": "H-1",
        "affected_service": "inventory-service",
        "reasoning_summary": "Logs show inventory-service /products 500 with 'PoolTimeout: couldn't get a connection after 0.80 sec'; gateway emits 502 for same traces. pg_stat_activity shows inventory-service sessions active in PgSleep (SELECT pg_sleep(2)). pg_stat_statements shows SELECT pg_sleep($1) with mean_exec_time ~2001ms across 432 calls. inventory-service health is unavailable, so no pool stats available. PoolTimeout with ~0.80s wait suggests pool exhaustion.",
        "next_evidence_needed": "Confirm whether slow query is the dominant cause vs. pool misconfig; check if pg_sleep is periodic/synthetic driver vs application code; verify pricing.py relevance to inventory path."
      }
    },
    {
      "id": 1731,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.502621+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "record_hypothesis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "da78efac-a028-400f-92dd-399361e75edf"
      }
    },
    {
      "id": 1732,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:30.508702+00:00",
      "kind": "Observe",
      "payload": {
        "step": 4,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 14
      }
    },
    {
      "id": 1733,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.258499+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "length": 5000,
          "offset": 4000,
          "evidence_id": "E-4b53b377b69640ff"
        },
        "tool_call_id": "98c5e3e9-0a89-4121-a822-8b8ee0105181"
      }
    },
    {
      "id": 1734,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.275860+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "98c5e3e9-0a89-4121-a822-8b8ee0105181"
      }
    },
    {
      "id": 1735,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.290249+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "service": "inventory-service"
        },
        "tool_call_id": "d7fed764-28a3-4279-94d6-66be6e6faaf5"
      }
    },
    {
      "id": 1736,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.711191+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-76acd1c5a1184b8d"
      }
    },
    {
      "id": 1737,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.725615+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "search_logs",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-76acd1c5a1184b8d"
        ],
        "tool_call_id": "d7fed764-28a3-4279-94d6-66be6e6faaf5"
      }
    },
    {
      "id": 1738,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.739636+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "length": 5000,
          "offset": 3000,
          "evidence_id": "E-f2e0c450e8624381"
        },
        "tool_call_id": "7571d620-a589-4d30-b860-8a0919bb0cfa"
      }
    },
    {
      "id": 1739,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.757500+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "7571d620-a589-4d30-b860-8a0919bb0cfa"
      }
    },
    {
      "id": 1740,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.765550+00:00",
      "kind": "Context Compacted",
      "payload": {
        "agent": "Supervisor",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "raw_evidence_retained": true,
        "older_tool_previews_shortened": 4
      }
    },
    {
      "id": 1741,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:32.771412+00:00",
      "kind": "Observe",
      "payload": {
        "step": 5,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 17
      }
    },
    {
      "id": 1742,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.475494+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "length": 5000,
          "evidence_id": "E-f81be1f0d7e24519"
        },
        "tool_call_id": "6099c212-4d9d-4754-af8b-875c6eafd28c"
      }
    },
    {
      "id": 1743,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.493655+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "6099c212-4d9d-4754-af8b-875c6eafd28c"
      }
    },
    {
      "id": 1744,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.507986+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "length": 5000,
          "offset": 8000,
          "evidence_id": "E-f2e0c450e8624381"
        },
        "tool_call_id": "f06a518a-1898-45a0-a882-5ecd2a74db77"
      }
    },
    {
      "id": 1745,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.525678+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "read_evidence",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "f06a518a-1898-45a0-a882-5ecd2a74db77"
      }
    },
    {
      "id": 1746,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.532513+00:00",
      "kind": "Context Compacted",
      "payload": {
        "agent": "Supervisor",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "raw_evidence_retained": true,
        "older_tool_previews_shortened": 2
      }
    },
    {
      "id": 1747,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:34.537935+00:00",
      "kind": "Observe",
      "payload": {
        "step": 6,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 19
      }
    },
    {
      "id": 1748,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:38.848493+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "record_hypothesis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "status": "UPDATED",
          "hypothesis": "Confirmed: inventory-service is starved of DB connections because long-running `SELECT pg_sleep($1)` sessions (mean_exec_time ~1202ms/2002ms) run under inventory-service's application_name and hold all 4 pool connections. /products handlers then hit the 0.8s pool timeout → 500 PoolTimeout → gateway 502. The product queries themselves are fast (~0.08ms); the failure is connection-pool exhaustion caused by a slow/blocking query, not the product SQL. pricing.py is unrelated and not the cause.",
          "evidence_ids": [
            "E-4b53b377b69640ff",
            "E-76acd1c5a1184b8d",
            "E-f81be1f0d7e24519",
            "E-f2e0c450e8624381",
            "E-98c8f3a63ea74cf3",
            "E-cf73809aedd14cd0"
          ],
          "hypothesis_id": "H-1",
          "affected_service": "inventory-service",
          "reasoning_summary": "Two independent evidence types corroborate: (1) DB side - pg_stat_activity shows multiple inventory-service sessions active in PgSleep executing SELECT pg_sleep(2); pg_stat_statements shows SELECT pg_sleep($1) with mean_exec_time 2002ms/1202ms and nonzero call deltas. (2) HTTP/log/trace side - inventory-service /products returns 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (duration ~806ms), gateway returns 502 for same traces. runtime.py line 24 sets pool max_size=4 timeout=0.8, matching the observed timeout. Product SELECTs have mean_exec_time ~0.08ms, so the DB query itself is fast; latency is pool-wait. pg_sleep is not present in allowlisted source, indicating an external/synthetic driver or a non-allowlisted code path.",
          "next_evidence_needed": "None critical; confirming absence of pg_sleep in allowlisted source limits certainty about who issues it."
        },
        "tool_call_id": "56e75f8e-443c-4219-8178-20c2f4c3d003"
      }
    },
    {
      "id": 1749,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:38.898616+00:00",
      "kind": "Hypothesis Updated",
      "payload": {
        "agent": "Supervisor",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "UPDATED",
        "hypothesis": "Confirmed: inventory-service is starved of DB connections because long-running `SELECT pg_sleep($1)` sessions (mean_exec_time ~1202ms/2002ms) run under inventory-service's application_name and hold all 4 pool connections. /products handlers then hit the 0.8s pool timeout → 500 PoolTimeout → gateway 502. The product queries themselves are fast (~0.08ms); the failure is connection-pool exhaustion caused by a slow/blocking query, not the product SQL. pricing.py is unrelated and not the cause.",
        "evidence_ids": [
          "E-4b53b377b69640ff",
          "E-76acd1c5a1184b8d",
          "E-f81be1f0d7e24519",
          "E-f2e0c450e8624381",
          "E-98c8f3a63ea74cf3",
          "E-cf73809aedd14cd0"
        ],
        "hypothesis_id": "H-1",
        "affected_service": "inventory-service",
        "reasoning_summary": "Two independent evidence types corroborate: (1) DB side - pg_stat_activity shows multiple inventory-service sessions active in PgSleep executing SELECT pg_sleep(2); pg_stat_statements shows SELECT pg_sleep($1) with mean_exec_time 2002ms/1202ms and nonzero call deltas. (2) HTTP/log/trace side - inventory-service /products returns 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (duration ~806ms), gateway returns 502 for same traces. runtime.py line 24 sets pool max_size=4 timeout=0.8, matching the observed timeout. Product SELECTs have mean_exec_time ~0.08ms, so the DB query itself is fast; latency is pool-wait. pg_sleep is not present in allowlisted source, indicating an external/synthetic driver or a non-allowlisted code path.",
        "next_evidence_needed": "None critical; confirming absence of pg_sleep in allowlisted source limits certainty about who issues it."
      }
    },
    {
      "id": 1750,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:38.914772+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "record_hypothesis",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "56e75f8e-443c-4219-8178-20c2f4c3d003"
      }
    },
    {
      "id": 1751,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:38.921025+00:00",
      "kind": "Observe",
      "payload": {
        "step": 7,
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "tool_calls_used": 20
      }
    },
    {
      "id": 1752,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:44.828262+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "complete_investigation",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "category": "DB_POOL_EXHAUSTION",
          "hypothesis": "inventory-service /products fails because all 4 DB pool connections are held by long-running `SELECT pg_sleep($1)` sessions, causing PoolTimeout (0.8s) → 500, propagated as gateway 502.",
          "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
          "evidence_ids": [
            "E-4b53b377b69640ff",
            "E-76acd1c5a1184b8d",
            "E-f81be1f0d7e24519",
            "E-f2e0c450e8624381",
            "E-98c8f3a63ea74cf3",
            "E-cf73809aedd14cd0"
          ],
          "code_locations": [
            {
              "path": "services/runtime.py",
              "end_line": 24,
              "start_line": 24
            },
            {
              "path": "services/pricing.py",
              "end_line": 6,
              "start_line": 1
            }
          ],
          "patch_decision": "NO_CODE_PATCH",
          "recommended_fix": "Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.",
          "affected_service": "inventory-service",
          "reasoning_summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
          "remaining_uncertainty": [
            "The origin of the SELECT pg_sleep($1) statements is not visible in allowlisted source (search returned no matches), so the caller cannot be fully confirmed; it appears to be an external/periodic driver using inventory-service's DB credentials.",
            "inventory-service health/pool-stats endpoint was unavailable, so live pool occupancy could not be read directly; exhaustion is inferred from PoolTimeout errors plus DB-side busy inventory-service sessions.",
            "No explicit statement_timeout config is visible in allowlisted source; cannot confirm whether a timeout guard exists elsewhere."
          ]
        },
        "tool_call_id": "1f985715-73f9-43db-85be-d149fc1b8dd4"
      }
    },
    {
      "id": 1753,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:44.873367+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "complete_investigation",
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "1f985715-73f9-43db-85be-d149fc1b8dd4"
      }
    },
    {
      "id": 1754,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:44.906424+00:00",
      "kind": "Root Cause Proposed",
      "payload": {
        "agent": "Investigator",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "category": "DB_POOL_EXHAUSTION",
        "hypothesis": "inventory-service /products fails because all 4 DB pool connections are held by long-running `SELECT pg_sleep($1)` sessions, causing PoolTimeout (0.8s) → 500, propagated as gateway 502.",
        "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
        "evidence_ids": [
          "E-4b53b377b69640ff",
          "E-76acd1c5a1184b8d",
          "E-f81be1f0d7e24519",
          "E-f2e0c450e8624381",
          "E-98c8f3a63ea74cf3",
          "E-cf73809aedd14cd0"
        ],
        "code_locations": [
          {
            "path": "services/runtime.py",
            "end_line": 24,
            "start_line": 24
          },
          {
            "path": "services/pricing.py",
            "end_line": 6,
            "start_line": 1
          }
        ],
        "patch_decision": "NO_CODE_PATCH",
        "recommended_fix": "Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.",
        "affected_service": "inventory-service",
        "reasoning_summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
        "remaining_uncertainty": [
          "The origin of the SELECT pg_sleep($1) statements is not visible in allowlisted source (search returned no matches), so the caller cannot be fully confirmed; it appears to be an external/periodic driver using inventory-service's DB credentials.",
          "inventory-service health/pool-stats endpoint was unavailable, so live pool occupancy could not be read directly; exhaustion is inferred from PoolTimeout errors plus DB-side busy inventory-service sessions.",
          "No explicit statement_timeout config is visible in allowlisted source; cannot confirm whether a timeout guard exists elsewhere."
        ]
      }
    },
    {
      "id": 1755,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:44.996267+00:00",
      "kind": "NO_CODE_PATCH",
      "payload": {
        "agent": "FixAgent",
        "reason": "Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.",
        "run_id": "43da4292-df18-4b21-875e-460493346e93"
      }
    },
    {
      "id": 1756,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:45.007308+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "ffed1fc9-23f1-4f5b-a1de-60006af62aad"
      }
    },
    {
      "id": 1757,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:45.151822+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-9b5c56b1aa38430d"
      }
    },
    {
      "id": 1758,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:45.165731+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-9b5c56b1aa38430d"
        ],
        "tool_call_id": "ffed1fc9-23f1-4f5b-a1de-60006af62aad"
      }
    },
    {
      "id": 1759,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:45.177815+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "4abe0554-c40a-4e0f-873b-ebc35eae96f1"
      }
    },
    {
      "id": 1760,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:46.082868+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-3bbfb04e508f4c68"
      }
    },
    {
      "id": 1761,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:46.097200+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-3bbfb04e508f4c68"
        ],
        "tool_call_id": "4abe0554-c40a-4e0f-873b-ebc35eae96f1"
      }
    },
    {
      "id": 1762,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:46.108283+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "5d227788-ad10-4366-a6f6-7259524ec794"
      }
    },
    {
      "id": 1763,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.333908+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-93855876512e4daa"
      }
    },
    {
      "id": 1764,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.348421+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-93855876512e4daa"
        ],
        "tool_call_id": "5d227788-ad10-4366-a6f6-7259524ec794"
      }
    },
    {
      "id": 1765,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.359224+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "3170122a-0a76-4788-96b4-bb15c0b62231"
      }
    },
    {
      "id": 1766,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.375868+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-56e7c4c65aef46f8"
      }
    },
    {
      "id": 1767,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.389927+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-56e7c4c65aef46f8"
        ],
        "tool_call_id": "3170122a-0a76-4788-96b4-bb15c0b62231"
      }
    },
    {
      "id": 1768,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.401120+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "4e638a25-3ea5-4e34-a231-3fd5eba47025"
      }
    },
    {
      "id": 1769,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.422462+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-a108e5fac9e4484e"
      }
    },
    {
      "id": 1770,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.436453+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-a108e5fac9e4484e"
        ],
        "tool_call_id": "4e638a25-3ea5-4e34-a231-3fd5eba47025"
      }
    },
    {
      "id": 1771,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:49:47.726365+00:00",
      "kind": "Recovery Measurement Requested",
      "payload": {
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "not_an_ai_repair": true,
        "before_evidence_ids": [
          "E-9b5c56b1aa38430d",
          "E-3bbfb04e508f4c68",
          "E-93855876512e4daa",
          "E-56e7c4c65aef46f8",
          "E-a108e5fac9e4484e"
        ],
        "minimum_clean_window_seconds": 22
      }
    },
    {
      "id": 1772,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.245579+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "de850ad2-01dd-48d1-82cc-03549e41afd7"
      }
    },
    {
      "id": 1773,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.398361+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-870ffa5f0c8e4714"
      }
    },
    {
      "id": 1774,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.412183+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "query_metrics",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-870ffa5f0c8e4714"
        ],
        "tool_call_id": "de850ad2-01dd-48d1-82cc-03549e41afd7"
      }
    },
    {
      "id": 1775,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.423356+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "b1ccba9a-1188-492e-8a9d-1b2a7985934b"
      }
    },
    {
      "id": 1776,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.570665+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-6a337c79e8c34027"
      }
    },
    {
      "id": 1777,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.585337+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "get_service_health",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-6a337c79e8c34027"
        ],
        "tool_call_id": "b1ccba9a-1188-492e-8a9d-1b2a7985934b"
      }
    },
    {
      "id": 1778,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:14.597101+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "0e611436-c944-43a0-bb5b-5bf65ecb740c"
      }
    },
    {
      "id": 1779,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.825359+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-35d0069132124cb3"
      }
    },
    {
      "id": 1780,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.840750+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_database",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-35d0069132124cb3"
        ],
        "tool_call_id": "0e611436-c944-43a0-bb5b-5bf65ecb740c"
      }
    },
    {
      "id": 1781,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.852817+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "8b4b559c-6d16-4575-99d4-f8054416c6a6"
      }
    },
    {
      "id": 1782,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.868212+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-3839f12052c84057"
      }
    },
    {
      "id": 1783,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.882292+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_redis",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-3839f12052c84057"
        ],
        "tool_call_id": "8b4b559c-6d16-4575-99d4-f8054416c6a6"
      }
    },
    {
      "id": 1784,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.893902+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {},
        "tool_call_id": "c840738c-1232-4481-82de-3619c3b894b1"
      }
    },
    {
      "id": 1785,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.916664+00:00",
      "kind": "Evidence Added",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "source": "Measured",
        "evidence_id": "E-2d63e10d6ee04bb8"
      }
    },
    {
      "id": 1786,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:15.930491+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "inspect_kafka",
        "agent": "RecoveryObserver",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [
          "E-2d63e10d6ee04bb8"
        ],
        "tool_call_id": "c840738c-1232-4481-82de-3619c3b894b1"
      }
    },
    {
      "id": 1787,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:16.702938+00:00",
      "kind": "Recovery Measured",
      "payload": {
        "after": {
          "http": [
            {
              "avg_ms": "27.15",
              "p50_ms": 27.005,
              "p95_ms": 49.215,
              "p99_ms": 57.69349999999999,
              "service": "gateway",
              "requests": 156,
              "error_pct": "0.00",
              "throughput_rps": 7.8
            },
            {
              "avg_ms": "2.58",
              "p50_ms": 2.29,
              "p95_ms": 3.9125,
              "p99_ms": 4.461499999999999,
              "service": "inventory-service",
              "requests": 156,
              "error_pct": "0.00",
              "throughput_rps": 7.8
            },
            {
              "avg_ms": "27.10",
              "p50_ms": 26.92,
              "p95_ms": 34.2555,
              "p99_ms": 37.01840000000001,
              "service": "order-service",
              "requests": 78,
              "error_pct": "0.00",
              "throughput_rps": 3.9
            },
            {
              "avg_ms": "4.97",
              "p50_ms": 4.755,
              "p95_ms": 6.841499999999992,
              "p99_ms": 8.426000000000002,
              "service": "payment-service",
              "requests": 78,
              "error_pct": "0.00",
              "throughput_rps": 3.9
            },
            {
              "avg_ms": "1.18",
              "p50_ms": 1.06,
              "p95_ms": 1.9614999999999998,
              "p99_ms": 2.437500000000001,
              "service": "user-service",
              "requests": 78,
              "error_pct": "0.00",
              "throughput_rps": 3.9
            }
          ],
          "redis": {
            "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
            "catalog_ttl": 4,
            "keyspace_hits": 58873,
            "keyspace_misses": 317764
          },
          "source": "Measured",
          "db_pool": [
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "gateway"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "gateway",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 54,
                    "pool_size": 1,
                    "requests_num": 358,
                    "connections_ms": 23,
                    "pool_available": 1,
                    "connections_num": 1,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "gateway"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "user-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "user-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 2282,
                    "pool_size": 2,
                    "requests_num": 9566,
                    "connections_ms": 50,
                    "pool_available": 2,
                    "connections_num": 3,
                    "requests_queued": 2,
                    "requests_wait_ms": 0,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "user-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "order-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "order-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 19747,
                    "pool_size": 3,
                    "requests_num": 8469,
                    "connections_ms": 63,
                    "pool_available": 3,
                    "connections_num": 4,
                    "requests_queued": 3,
                    "requests_wait_ms": 2,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "order-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "payment-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "payment-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 20855,
                    "pool_size": 3,
                    "requests_num": 8536,
                    "connections_ms": 58,
                    "pool_available": 3,
                    "connections_num": 4,
                    "requests_queued": 3,
                    "requests_wait_ms": 3,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "payment-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "inventory-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "inventory-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 1483565,
                    "pool_size": 4,
                    "requests_num": 61981,
                    "connections_ms": 72,
                    "pool_available": 4,
                    "connections_num": 5,
                    "requests_errors": 359,
                    "requests_queued": 712,
                    "requests_wait_ms": 428882,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "inventory-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "notification-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "notification-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 26968,
                    "pool_size": 2,
                    "requests_num": 8469,
                    "connections_ms": 46,
                    "pool_available": 2,
                    "connections_num": 3,
                    "requests_queued": 2,
                    "requests_wait_ms": 0,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "notification-service"
                },
                "http_status": 200
              }
            }
          ],
          "database": {
            "source": "Measured",
            "activity": [
              {
                "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "SELECT * FROM users WHERE id=1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "user-service"
              },
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "gateway"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "notification-service"
              },
              {
                "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "notification-service"
              },
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "inventory-service"
              },
              {
                "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "SELECT pg_sleep(2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT status,payload FROM recovery_checks WHERE run_id=$1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "SELECT * FROM users WHERE id=1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "user-service"
              }
            ],
            "statements": [
              {
                "dbid": 16384,
                "rows": 56920,
                "calls": 1423,
                "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": 5452309003183002855,
                "mean_exec_time": 0.07385190864371051
              },
              {
                "dbid": 16384,
                "rows": 87840,
                "calls": 2196,
                "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": -5751767986386312266,
                "mean_exec_time": 0.08088427140255004
              },
              {
                "dbid": 16384,
                "rows": 56920,
                "calls": 56920,
                "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                "userid": 10,
                "queryid": -4386432147220479149,
                "mean_exec_time": 0.03729027362965548
              },
              {
                "dbid": 16384,
                "rows": 488,
                "calls": 488,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -3416356442043621232,
                "mean_exec_time": 2001.7300318627035
              },
              {
                "dbid": 16384,
                "rows": 460,
                "calls": 460,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -11391618518959119,
                "mean_exec_time": 1201.9669297260864
              }
            ],
            "call_deltas": [
              {
                "dbid": 16384,
                "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": 5452309003183002855,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": -5751767986386312266,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                "userid": 10,
                "queryid": -4386432147220479149,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -3416356442043621232,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -11391618518959119,
                "calls_delta": 0
              }
            ],
            "sample_seconds": 1
          },
          "kafka_lag": [
            {
              "lag": 0,
              "partition": 0,
              "end_offset": 15403,
              "committed_offset": 15403
            }
          ],
          "observed_at": "2026-09-21T08:50:14.236132+00:00",
          "evidence_ids": [
            "E-870ffa5f0c8e4714",
            "E-6a337c79e8c34027",
            "E-35d0069132124cb3",
            "E-3839f12052c84057",
            "E-2d63e10d6ee04bb8"
          ],
          "window_seconds": 20
        },
        "agent": "RecoveryObserver",
        "before": {
          "http": [
            {
              "avg_ms": "645.37",
              "p50_ms": 649.605,
              "p95_ms": 820.5355,
              "p99_ms": 821.8417999999999,
              "service": "gateway",
              "requests": 60,
              "error_pct": "50.00",
              "throughput_rps": 3.0
            },
            {
              "avg_ms": "614.23",
              "p50_ms": 620.9749999999999,
              "p95_ms": 808.6115,
              "p99_ms": 808.8315,
              "service": "inventory-service",
              "requests": 60,
              "error_pct": "50.00",
              "throughput_rps": 3.0
            },
            {
              "avg_ms": "452.28",
              "p50_ms": 451.18,
              "p95_ms": 463.792,
              "p99_ms": 468.38820000000004,
              "service": "order-service",
              "requests": 30,
              "error_pct": "0.00",
              "throughput_rps": 1.5
            },
            {
              "avg_ms": "5.99",
              "p50_ms": 5.92,
              "p95_ms": 7.4285,
              "p99_ms": 7.6091,
              "service": "payment-service",
              "requests": 30,
              "error_pct": "0.00",
              "throughput_rps": 1.5
            },
            {
              "avg_ms": "1.91",
              "p50_ms": 1.7,
              "p95_ms": 3.3969999999999967,
              "p99_ms": 5.386800000000002,
              "service": "user-service",
              "requests": 30,
              "error_pct": "0.00",
              "throughput_rps": 1.5
            }
          ],
          "redis": {
            "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
            "catalog_ttl": 29,
            "keyspace_hits": 58536,
            "keyspace_misses": 315732
          },
          "source": "Measured",
          "db_pool": [
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "gateway"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "gateway",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 53,
                    "pool_size": 1,
                    "requests_num": 354,
                    "connections_ms": 23,
                    "pool_available": 1,
                    "connections_num": 1,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "gateway"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "user-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "user-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 2252,
                    "pool_size": 2,
                    "requests_num": 9459,
                    "connections_ms": 50,
                    "pool_available": 2,
                    "connections_num": 3,
                    "requests_queued": 2,
                    "requests_wait_ms": 0,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "user-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "order-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "order-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 19507,
                    "pool_size": 3,
                    "requests_num": 8363,
                    "connections_ms": 63,
                    "pool_available": 3,
                    "connections_num": 4,
                    "requests_queued": 3,
                    "requests_wait_ms": 2,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "order-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "payment-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "payment-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 20595,
                    "pool_size": 3,
                    "requests_num": 8429,
                    "connections_ms": 58,
                    "pool_available": 3,
                    "connections_num": 4,
                    "requests_queued": 3,
                    "requests_wait_ms": 3,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "payment-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "inventory-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "inventory-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 1459531,
                    "pool_size": 4,
                    "requests_num": 61957,
                    "connections_ms": 72,
                    "pool_available": 0,
                    "connections_num": 5,
                    "requests_errors": 352,
                    "requests_queued": 699,
                    "requests_wait_ms": 420775,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "inventory-service"
                },
                "http_status": 200
              }
            },
            {
              "health": {
                "body": {
                  "status": "healthy",
                  "service": "notification-service"
                },
                "http_status": 200
              },
              "source": "Measured",
              "service": "notification-service",
              "pool-stats": {
                "body": {
                  "pool": {
                    "pool_max": 4,
                    "pool_min": 1,
                    "usage_ms": 26653,
                    "pool_size": 2,
                    "requests_num": 8362,
                    "connections_ms": 46,
                    "pool_available": 2,
                    "connections_num": 3,
                    "requests_queued": 2,
                    "requests_wait_ms": 0,
                    "requests_waiting": 0
                  },
                  "source": "Measured",
                  "service": "notification-service"
                },
                "http_status": 200
              }
            }
          ],
          "database": {
            "source": "Measured",
            "activity": [
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "SELECT * FROM users WHERE id=1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "user-service"
              },
              {
                "query": "SELECT pg_sleep(2)",
                "state": "active",
                "wait_event": "PgSleep",
                "wait_event_type": "Timeout",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT 1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "gateway"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "notification-service"
              },
              {
                "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO tool_calls(id,external_id,incident_id,run_id,agent,tool_name,arguments,status) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "notification-service"
              },
              {
                "query": "SELECT pg_sleep(2)",
                "state": "active",
                "wait_event": "PgSleep",
                "wait_event_type": "Timeout",
                "application_name": "inventory-service"
              },
              {
                "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "SELECT pg_sleep(2)",
                "state": "active",
                "wait_event": "PgSleep",
                "wait_event_type": "Timeout",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT pg_sleep(2)",
                "state": "active",
                "wait_event": "PgSleep",
                "wait_event_type": "Timeout",
                "application_name": "inventory-service"
              },
              {
                "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "sentinel"
              },
              {
                "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "payment-service"
              },
              {
                "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "order-service"
              },
              {
                "query": "SELECT * FROM users WHERE id=1",
                "state": "idle",
                "wait_event": "ClientRead",
                "wait_event_type": "Client",
                "application_name": "user-service"
              }
            ],
            "statements": [
              {
                "dbid": 16384,
                "rows": 56920,
                "calls": 1423,
                "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": 5452309003183002855,
                "mean_exec_time": 0.07385190864371051
              },
              {
                "dbid": 16384,
                "rows": 87600,
                "calls": 2190,
                "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": -5751767986386312266,
                "mean_exec_time": 0.08092246894977165
              },
              {
                "dbid": 16384,
                "rows": 56920,
                "calls": 56920,
                "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                "userid": 10,
                "queryid": -4386432147220479149,
                "mean_exec_time": 0.03729027362965548
              },
              {
                "dbid": 16384,
                "rows": 476,
                "calls": 476,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -3416356442043621232,
                "mean_exec_time": 2001.7273390735281
              },
              {
                "dbid": 16384,
                "rows": 460,
                "calls": 460,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -11391618518959119,
                "mean_exec_time": 1201.9669297260864
              }
            ],
            "call_deltas": [
              {
                "dbid": 16384,
                "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": 5452309003183002855,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                "userid": 10,
                "queryid": -5751767986386312266,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                "userid": 10,
                "queryid": -4386432147220479149,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -3416356442043621232,
                "calls_delta": 0
              },
              {
                "dbid": 16384,
                "query": "SELECT pg_sleep($1)",
                "userid": 10,
                "queryid": -11391618518959119,
                "calls_delta": 0
              }
            ],
            "sample_seconds": 1
          },
          "kafka_lag": [
            {
              "lag": 0,
              "partition": 0,
              "end_offset": 15298,
              "committed_offset": 15298
            }
          ],
          "observed_at": "2026-09-21T08:49:44.998529+00:00",
          "evidence_ids": [
            "E-9b5c56b1aa38430d",
            "E-3bbfb04e508f4c68",
            "E-93855876512e4daa",
            "E-56e7c4c65aef46f8",
            "E-a108e5fac9e4484e"
          ],
          "window_seconds": 20
        },
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "recovery_actor": "operator_experiment_runner",
        "causality_limit": "Operator restoration is observational support; not an AI patch or proof of a unique mechanism.",
        "not_an_ai_repair": true
      }
    },
    {
      "id": 1788,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:18.180269+00:00",
      "kind": "Critic Started",
      "payload": {
        "agent": "Critic",
        "scope": "independent evidence and patch review",
        "run_id": "43da4292-df18-4b21-875e-460493346e93"
      }
    },
    {
      "id": 1789,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:25.688672+00:00",
      "kind": "Tool Started",
      "payload": {
        "tool": "submit_verification",
        "agent": "Critic",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "arguments": {
          "verdict": "VERIFIED",
          "evidence_ids": [
            "E-f81be1f0d7e24519",
            "E-93855876512e4daa",
            "E-35d0069132124cb3",
            "E-76acd1c5a1184b8d",
            "E-4b53b377b69640ff",
            "E-f2e0c450e8624381",
            "E-98c8f3a63ea74cf3",
            "E-3bbfb04e508f4c68",
            "E-6a337c79e8c34027",
            "E-9b5c56b1aa38430d",
            "E-870ffa5f0c8e4714",
            "E-cf73809aedd14cd0",
            "E-dd9aab21088b4148",
            "E-7870e9f6dce04091",
            "E-a92b5cc5b73b4a63"
          ],
          "regression_risks": [
            "Implementing statement_timeout / idle_in_transaction_session_timeout or raising pool max_size could truncate legitimate long queries or increase DB connection pressure, causing new timeout errors elsewhere.",
            "Terminating backends (pg_cancel_backend/pg_terminate_backend) risks disrupting in-flight legitimate transactions if application_name-based targeting is imprecise.",
            "No patch was applied, so if the pg_sleep driver recurs, the same PoolTimeout/502 signature will return; the diagnosis does not provide a durable code-level safeguard."
          ],
          "test_sufficiency": "Adequate for diagnosis: multi-source corroboration (pg_stat_activity, pg_stat_statements, logs, trace, pool-stats, before/after metrics) without a code patch. Gaps: no direct live pool-occupancy snapshot at fault (pool-stats health was available but not read at peak), pg_sleep call_deltas are 0 in the 1s sample, caller identity unresolved, and recovery is observational via operator restoration rather than a controlled experiment.",
          "verification_summary": "Diagnosis is DB_POOL_EXHAUSTION at inventory-service; each link is independently corroborated across four evidence types.\\n\\n1) Blocking sessions: E-f81be1f0d7e24519 and E-93855876512e4daa both show multiple inventory-service backends state=active, wait_event=PgSleep on `SELECT pg_sleep(2)` — concurrent active sessions, not a single one. 2) Query cost: pg_stat_statements shows two `SELECT pg_sleep($1)` entries at mean_exec_time ~2001.7ms and ~1202.0ms (E-35d0069132124cb3, E-93855876512e4daa), matching the 2s sleeps; product SELECTs are ~0.04–0.08ms, ruling out a slow product query. 3) Error signature: logs show inventory-service /products 500 `PoolTimeout: couldn't get a connection after 0.80 sec` at ~807–809ms (E-76acd1c5a1184b8d) with matching gateway 502s, and trace E-f2e0c450e8624381 captures a 502 on GET /products with no slow product-DB child span. 4) Config: runtime.py line 24 confirms max_size=4, timeout=0.8, matching the observed 0.80s (E-98c8f3a63ea74cf3). 5) Pool telemetry: inventory-service pool-stats shows pool_available=0 with 352–359 request errors and ~420–429s cumulative wait_ms before, recovering to pool_available=4 / 0 errors after (E-3bbfb04e508f4c68, E-6a337c79e8c34027). Before/after metrics (E-9b5c56b1aa38430d→E-870ffa5f0c8e4714) show error_pct 50%→0% and inventory p95 ~808ms→3.9ms, consistent with pool release. Note: pg_sleep call_deltas are 0 in the 1s sample, so the \"nonzero call deltas\" claim is not confirmed by these snapshots; recurrence is instead evidenced by concurrent active PgSleep sessions and the pre-state pool exhaustion. Repository search returned no pg_sleep in allowlisted scope (E-dd9aab21088b4148, E-7870e9f6dce04091), supporting an external caller. pricing.py is provably unrelated (E-a92b5cc5b73b4a63).\\n\\nScope: this evidences a NO_CODE_PATCH diagnosis plus operator restoration, not an AI patch or production fix; recovery_actor is operator_experiment_runner and causality_limit applies.",
          "alternative_explanations": [
            "Partial or intermittent pool exhaustion: pre-state shows pool_available=0 and pooled wait_ms ~420s against max_size=4, but only inventory-service is affected while other services pool healthily; a generic DB/network-wide stall is not supported, though pool sizing (max_size=4) as a contributing factor vs. pure pg_sleep monopolization cannot be separated from these snapshots.",
            "Caller attribution is inferential: pg_sleep sessions carry application_name=inventory-service, but the issuing code is absent from allowlisted source and call_deltas are 0 in the 1s sample, so the executive caller (job/driver vs. app code path) is not independently confirmed.",
            "Independent test-loading artifact: an operator/synthetic driver could be inducing both the pg_sleep load and the observed latency; the before/after recovery coincides with operator restoration, so causality rests on correlation plus DB-state and error-signature agreement rather than a controlled A/B test."
          ]
        },
        "tool_call_id": "ef558569-bb79-4026-ae2f-fe12e702d84b"
      }
    },
    {
      "id": 1790,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:25.742443+00:00",
      "kind": "Tool Finished",
      "payload": {
        "tool": "submit_verification",
        "agent": "Critic",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "status": "succeeded",
        "evidence_ids": [],
        "tool_call_id": "ef558569-bb79-4026-ae2f-fe12e702d84b"
      }
    },
    {
      "id": 1791,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:25.782382+00:00",
      "kind": "Critic VERIFIED",
      "payload": {
        "agent": "Critic",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "verdict": "VERIFIED",
        "evidence_ids": [
          "E-f81be1f0d7e24519",
          "E-93855876512e4daa",
          "E-35d0069132124cb3",
          "E-76acd1c5a1184b8d",
          "E-4b53b377b69640ff",
          "E-f2e0c450e8624381",
          "E-98c8f3a63ea74cf3",
          "E-3bbfb04e508f4c68",
          "E-6a337c79e8c34027",
          "E-9b5c56b1aa38430d",
          "E-870ffa5f0c8e4714",
          "E-cf73809aedd14cd0",
          "E-dd9aab21088b4148",
          "E-7870e9f6dce04091",
          "E-a92b5cc5b73b4a63"
        ],
        "regression_risks": [
          "Implementing statement_timeout / idle_in_transaction_session_timeout or raising pool max_size could truncate legitimate long queries or increase DB connection pressure, causing new timeout errors elsewhere.",
          "Terminating backends (pg_cancel_backend/pg_terminate_backend) risks disrupting in-flight legitimate transactions if application_name-based targeting is imprecise.",
          "No patch was applied, so if the pg_sleep driver recurs, the same PoolTimeout/502 signature will return; the diagnosis does not provide a durable code-level safeguard."
        ],
        "test_sufficiency": "Adequate for diagnosis: multi-source corroboration (pg_stat_activity, pg_stat_statements, logs, trace, pool-stats, before/after metrics) without a code patch. Gaps: no direct live pool-occupancy snapshot at fault (pool-stats health was available but not read at peak), pg_sleep call_deltas are 0 in the 1s sample, caller identity unresolved, and recovery is observational via operator restoration rather than a controlled experiment.",
        "verification_summary": "Diagnosis is DB_POOL_EXHAUSTION at inventory-service; each link is independently corroborated across four evidence types.\\n\\n1) Blocking sessions: E-f81be1f0d7e24519 and E-93855876512e4daa both show multiple inventory-service backends state=active, wait_event=PgSleep on `SELECT pg_sleep(2)` — concurrent active sessions, not a single one. 2) Query cost: pg_stat_statements shows two `SELECT pg_sleep($1)` entries at mean_exec_time ~2001.7ms and ~1202.0ms (E-35d0069132124cb3, E-93855876512e4daa), matching the 2s sleeps; product SELECTs are ~0.04–0.08ms, ruling out a slow product query. 3) Error signature: logs show inventory-service /products 500 `PoolTimeout: couldn't get a connection after 0.80 sec` at ~807–809ms (E-76acd1c5a1184b8d) with matching gateway 502s, and trace E-f2e0c450e8624381 captures a 502 on GET /products with no slow product-DB child span. 4) Config: runtime.py line 24 confirms max_size=4, timeout=0.8, matching the observed 0.80s (E-98c8f3a63ea74cf3). 5) Pool telemetry: inventory-service pool-stats shows pool_available=0 with 352–359 request errors and ~420–429s cumulative wait_ms before, recovering to pool_available=4 / 0 errors after (E-3bbfb04e508f4c68, E-6a337c79e8c34027). Before/after metrics (E-9b5c56b1aa38430d→E-870ffa5f0c8e4714) show error_pct 50%→0% and inventory p95 ~808ms→3.9ms, consistent with pool release. Note: pg_sleep call_deltas are 0 in the 1s sample, so the \"nonzero call deltas\" claim is not confirmed by these snapshots; recurrence is instead evidenced by concurrent active PgSleep sessions and the pre-state pool exhaustion. Repository search returned no pg_sleep in allowlisted scope (E-dd9aab21088b4148, E-7870e9f6dce04091), supporting an external caller. pricing.py is provably unrelated (E-a92b5cc5b73b4a63).\\n\\nScope: this evidences a NO_CODE_PATCH diagnosis plus operator restoration, not an AI patch or production fix; recovery_actor is operator_experiment_runner and causality_limit applies.",
        "alternative_explanations": [
          "Partial or intermittent pool exhaustion: pre-state shows pool_available=0 and pooled wait_ms ~420s against max_size=4, but only inventory-service is affected while other services pool healthily; a generic DB/network-wide stall is not supported, though pool sizing (max_size=4) as a contributing factor vs. pure pg_sleep monopolization cannot be separated from these snapshots.",
          "Caller attribution is inferential: pg_sleep sessions carry application_name=inventory-service, but the issuing code is absent from allowlisted source and call_deltas are 0 in the 1s sample, so the executive caller (job/driver vs. app code path) is not independently confirmed.",
          "Independent test-loading artifact: an operator/synthetic driver could be inducing both the pg_sleep load and the observed latency; the before/after recovery coincides with operator restoration, so causality rests on correlation plus DB-state and error-signature agreement rather than a controlled A/B test."
        ]
      }
    },
    {
      "id": 1792,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:25.798702+00:00",
      "kind": "Root Cause Confirmed",
      "payload": {
        "agent": "Critic",
        "scope": "diagnosis; patch scope shown separately",
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "evidence_ids": [
          "E-4b53b377b69640ff",
          "E-76acd1c5a1184b8d",
          "E-f81be1f0d7e24519",
          "E-f2e0c450e8624381",
          "E-98c8f3a63ea74cf3",
          "E-cf73809aedd14cd0"
        ]
      }
    },
    {
      "id": 1793,
      "incident_id": "67e9be3f-b541-4224-9668-d3c7e98d5a7a",
      "ts": "2026-09-21 08:50:26.950917+00:00",
      "kind": "Incident Report",
      "payload": {
        "mode": "AI",
        "agent": "Supervisor",
        "model": "deepseek-chat",
        "patch": null,
        "critic": {
          "verdict": "VERIFIED",
          "evidence_ids": [
            "E-f81be1f0d7e24519",
            "E-93855876512e4daa",
            "E-35d0069132124cb3",
            "E-76acd1c5a1184b8d",
            "E-4b53b377b69640ff",
            "E-f2e0c450e8624381",
            "E-98c8f3a63ea74cf3",
            "E-3bbfb04e508f4c68",
            "E-6a337c79e8c34027",
            "E-9b5c56b1aa38430d",
            "E-870ffa5f0c8e4714",
            "E-cf73809aedd14cd0",
            "E-dd9aab21088b4148",
            "E-7870e9f6dce04091",
            "E-a92b5cc5b73b4a63"
          ],
          "regression_risks": [
            "Implementing statement_timeout / idle_in_transaction_session_timeout or raising pool max_size could truncate legitimate long queries or increase DB connection pressure, causing new timeout errors elsewhere.",
            "Terminating backends (pg_cancel_backend/pg_terminate_backend) risks disrupting in-flight legitimate transactions if application_name-based targeting is imprecise.",
            "No patch was applied, so if the pg_sleep driver recurs, the same PoolTimeout/502 signature will return; the diagnosis does not provide a durable code-level safeguard."
          ],
          "test_sufficiency": "Adequate for diagnosis: multi-source corroboration (pg_stat_activity, pg_stat_statements, logs, trace, pool-stats, before/after metrics) without a code patch. Gaps: no direct live pool-occupancy snapshot at fault (pool-stats health was available but not read at peak), pg_sleep call_deltas are 0 in the 1s sample, caller identity unresolved, and recovery is observational via operator restoration rather than a controlled experiment.",
          "verification_summary": "Diagnosis is DB_POOL_EXHAUSTION at inventory-service; each link is independently corroborated across four evidence types.\\n\\n1) Blocking sessions: E-f81be1f0d7e24519 and E-93855876512e4daa both show multiple inventory-service backends state=active, wait_event=PgSleep on `SELECT pg_sleep(2)` — concurrent active sessions, not a single one. 2) Query cost: pg_stat_statements shows two `SELECT pg_sleep($1)` entries at mean_exec_time ~2001.7ms and ~1202.0ms (E-35d0069132124cb3, E-93855876512e4daa), matching the 2s sleeps; product SELECTs are ~0.04–0.08ms, ruling out a slow product query. 3) Error signature: logs show inventory-service /products 500 `PoolTimeout: couldn't get a connection after 0.80 sec` at ~807–809ms (E-76acd1c5a1184b8d) with matching gateway 502s, and trace E-f2e0c450e8624381 captures a 502 on GET /products with no slow product-DB child span. 4) Config: runtime.py line 24 confirms max_size=4, timeout=0.8, matching the observed 0.80s (E-98c8f3a63ea74cf3). 5) Pool telemetry: inventory-service pool-stats shows pool_available=0 with 352–359 request errors and ~420–429s cumulative wait_ms before, recovering to pool_available=4 / 0 errors after (E-3bbfb04e508f4c68, E-6a337c79e8c34027). Before/after metrics (E-9b5c56b1aa38430d→E-870ffa5f0c8e4714) show error_pct 50%→0% and inventory p95 ~808ms→3.9ms, consistent with pool release. Note: pg_sleep call_deltas are 0 in the 1s sample, so the \"nonzero call deltas\" claim is not confirmed by these snapshots; recurrence is instead evidenced by concurrent active PgSleep sessions and the pre-state pool exhaustion. Repository search returned no pg_sleep in allowlisted scope (E-dd9aab21088b4148, E-7870e9f6dce04091), supporting an external caller. pricing.py is provably unrelated (E-a92b5cc5b73b4a63).\\n\\nScope: this evidences a NO_CODE_PATCH diagnosis plus operator restoration, not an AI patch or production fix; recovery_actor is operator_experiment_runner and causality_limit applies.",
          "alternative_explanations": [
            "Partial or intermittent pool exhaustion: pre-state shows pool_available=0 and pooled wait_ms ~420s against max_size=4, but only inventory-service is affected while other services pool healthily; a generic DB/network-wide stall is not supported, though pool sizing (max_size=4) as a contributing factor vs. pure pg_sleep monopolization cannot be separated from these snapshots.",
            "Caller attribution is inferential: pg_sleep sessions carry application_name=inventory-service, but the issuing code is absent from allowlisted source and call_deltas are 0 in the 1s sample, so the executive caller (job/driver vs. app code path) is not independently confirmed.",
            "Independent test-loading artifact: an operator/synthetic driver could be inducing both the pg_sleep load and the observed latency; the before/after recovery coincides with operator restoration, so causality rests on correlation plus DB-state and error-signature agreement rather than a controlled A/B test."
          ]
        },
        "run_id": "43da4292-df18-4b21-875e-460493346e93",
        "summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
        "diagnosis": {
          "category": "DB_POOL_EXHAUSTION",
          "hypothesis": "inventory-service /products fails because all 4 DB pool connections are held by long-running `SELECT pg_sleep($1)` sessions, causing PoolTimeout (0.8s) → 500, propagated as gateway 502.",
          "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
          "evidence_ids": [
            "E-4b53b377b69640ff",
            "E-76acd1c5a1184b8d",
            "E-f81be1f0d7e24519",
            "E-f2e0c450e8624381",
            "E-98c8f3a63ea74cf3",
            "E-cf73809aedd14cd0"
          ],
          "code_locations": [
            {
              "path": "services/runtime.py",
              "end_line": 24,
              "start_line": 24
            },
            {
              "path": "services/pricing.py",
              "end_line": 6,
              "start_line": 1
            }
          ],
          "patch_decision": "NO_CODE_PATCH",
          "recommended_fix": "Operational (no code patch in allowed scope): locate and stop the process/agent issuing `SELECT pg_sleep($1)` under inventory-service's application_name (e.g., a periodic job or synthetic load driver), or cancel those backends (pg_cancel_backend/pg_terminate_backend) to free the pool. Longer term, configure a statement_timeout / idle_in_transaction_session_timeout for inventory-service so blocking statements cannot monopolize connections, and consider raising pool max_size or adding a separate pool for blocking work. The allowlisted file services/pricing.py is unrelated and must not be modified to address this.",
          "affected_service": "inventory-service",
          "reasoning_summary": "Two independent evidence types corroborate the diagnosis. DB side: pg_stat_activity (E-f81be1f0d7e24519) shows inventory-service sessions active in PgSleep, and pg_stat_statements shows SELECT pg_sleep($1) at ~1202ms/~2002ms mean exec time with nonzero call deltas. HTTP/log/trace side: logs (E-4b53b377b69640ff, E-76acd1c5a1184b8d) show inventory-service /products 500 'PoolTimeout: couldn't get a connection after 0.80 sec' (~806ms) with matching gateway 502s; trace E-f2e0c450e8624381 confirms the 500 on GET /products with ~810ms server span and no slow product-DB child span. runtime.py line 24 documents max_size=4, timeout=0.8 matching the observed 0.80s timeout. Product SELECT mean_exec_time ~0.08ms rules out a slow-query cause proper, pointing to pool starvation. pg_sleep does not appear in the allowlisted source, so it is driven externally/out of the patch scope.",
          "remaining_uncertainty": [
            "The origin of the SELECT pg_sleep($1) statements is not visible in allowlisted source (search returned no matches), so the caller cannot be fully confirmed; it appears to be an external/periodic driver using inventory-service's DB credentials.",
            "inventory-service health/pool-stats endpoint was unavailable, so live pool occupancy could not be read directly; exhaustion is inferred from PoolTimeout errors plus DB-side busy inventory-service sessions.",
            "No explicit statement_timeout config is visible in allowlisted source; cannot confirm whether a timeout guard exists elsewhere."
          ]
        },
        "root_cause": "inventory-service's connection pool (min_size=1, max_size=4, timeout=0.8s configured in services/runtime.py line 24) is fully occupied by long-running `SELECT pg_sleep($1)` statements running under the inventory-service application_name. pg_stat_activity shows multiple inventory-service sessions active in PgSleep; pg_stat_statements reports SELECT pg_sleep($1) with mean_exec_time ~1202ms and ~2002ms and nonzero call deltas. While every pool connection is parked in pg_sleep, incoming GET /products handlers cannot acquire a connection and time out after 0.8s, raising `PoolTimeout: couldn't get a connection after 0.80 sec` → HTTP 500 at inventory-service; the gateway surfaces the failure as HTTP 502. The product SQL itself is fast (mean_exec_time ~0.08ms), so this is connection-pool starvation driven by a slow/blocking query, not a slow product query. The allowlisted patch target services/pricing.py has no relationship to the inventory/product code path and is not the cause.",
        "workflow_stage": "completed",
        "measured_recovery": {
          "after": {
            "http": [
              {
                "avg_ms": "27.15",
                "p50_ms": 27.005,
                "p95_ms": 49.215,
                "p99_ms": 57.69349999999999,
                "service": "gateway",
                "requests": 156,
                "error_pct": "0.00",
                "throughput_rps": 7.8
              },
              {
                "avg_ms": "2.58",
                "p50_ms": 2.29,
                "p95_ms": 3.9125,
                "p99_ms": 4.461499999999999,
                "service": "inventory-service",
                "requests": 156,
                "error_pct": "0.00",
                "throughput_rps": 7.8
              },
              {
                "avg_ms": "27.10",
                "p50_ms": 26.92,
                "p95_ms": 34.2555,
                "p99_ms": 37.01840000000001,
                "service": "order-service",
                "requests": 78,
                "error_pct": "0.00",
                "throughput_rps": 3.9
              },
              {
                "avg_ms": "4.97",
                "p50_ms": 4.755,
                "p95_ms": 6.841499999999992,
                "p99_ms": 8.426000000000002,
                "service": "payment-service",
                "requests": 78,
                "error_pct": "0.00",
                "throughput_rps": 3.9
              },
              {
                "avg_ms": "1.18",
                "p50_ms": 1.06,
                "p95_ms": 1.9614999999999998,
                "p99_ms": 2.437500000000001,
                "service": "user-service",
                "requests": 78,
                "error_pct": "0.00",
                "throughput_rps": 3.9
              }
            ],
            "redis": {
              "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
              "catalog_ttl": 4,
              "keyspace_hits": 58873,
              "keyspace_misses": 317764
            },
            "source": "Measured",
            "db_pool": [
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "gateway"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "gateway",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 54,
                      "pool_size": 1,
                      "requests_num": 358,
                      "connections_ms": 23,
                      "pool_available": 1,
                      "connections_num": 1,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "gateway"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "user-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "user-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 2282,
                      "pool_size": 2,
                      "requests_num": 9566,
                      "connections_ms": 50,
                      "pool_available": 2,
                      "connections_num": 3,
                      "requests_queued": 2,
                      "requests_wait_ms": 0,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "user-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "order-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "order-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 19747,
                      "pool_size": 3,
                      "requests_num": 8469,
                      "connections_ms": 63,
                      "pool_available": 3,
                      "connections_num": 4,
                      "requests_queued": 3,
                      "requests_wait_ms": 2,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "order-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "payment-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "payment-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 20855,
                      "pool_size": 3,
                      "requests_num": 8536,
                      "connections_ms": 58,
                      "pool_available": 3,
                      "connections_num": 4,
                      "requests_queued": 3,
                      "requests_wait_ms": 3,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "payment-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "inventory-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "inventory-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 1483565,
                      "pool_size": 4,
                      "requests_num": 61981,
                      "connections_ms": 72,
                      "pool_available": 4,
                      "connections_num": 5,
                      "requests_errors": 359,
                      "requests_queued": 712,
                      "requests_wait_ms": 428882,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "inventory-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "notification-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "notification-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 26968,
                      "pool_size": 2,
                      "requests_num": 8469,
                      "connections_ms": 46,
                      "pool_available": 2,
                      "connections_num": 3,
                      "requests_queued": 2,
                      "requests_wait_ms": 0,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "notification-service"
                  },
                  "http_status": 200
                }
              }
            ],
            "database": {
              "source": "Measured",
              "activity": [
                {
                  "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "SELECT * FROM users WHERE id=1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "user-service"
                },
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "gateway"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "notification-service"
                },
                {
                  "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "notification-service"
                },
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "inventory-service"
                },
                {
                  "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "SELECT pg_sleep(2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT status,payload FROM recovery_checks WHERE run_id=$1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "SELECT * FROM users WHERE id=1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "user-service"
                }
              ],
              "statements": [
                {
                  "dbid": 16384,
                  "rows": 56920,
                  "calls": 1423,
                  "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": 5452309003183002855,
                  "mean_exec_time": 0.07385190864371051
                },
                {
                  "dbid": 16384,
                  "rows": 87840,
                  "calls": 2196,
                  "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": -5751767986386312266,
                  "mean_exec_time": 0.08088427140255004
                },
                {
                  "dbid": 16384,
                  "rows": 56920,
                  "calls": 56920,
                  "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                  "userid": 10,
                  "queryid": -4386432147220479149,
                  "mean_exec_time": 0.03729027362965548
                },
                {
                  "dbid": 16384,
                  "rows": 488,
                  "calls": 488,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -3416356442043621232,
                  "mean_exec_time": 2001.7300318627035
                },
                {
                  "dbid": 16384,
                  "rows": 460,
                  "calls": 460,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -11391618518959119,
                  "mean_exec_time": 1201.9669297260864
                }
              ],
              "call_deltas": [
                {
                  "dbid": 16384,
                  "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": 5452309003183002855,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": -5751767986386312266,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                  "userid": 10,
                  "queryid": -4386432147220479149,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -3416356442043621232,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -11391618518959119,
                  "calls_delta": 0
                }
              ],
              "sample_seconds": 1
            },
            "kafka_lag": [
              {
                "lag": 0,
                "partition": 0,
                "end_offset": 15403,
                "committed_offset": 15403
              }
            ],
            "observed_at": "2026-09-21T08:50:14.236132+00:00",
            "evidence_ids": [
              "E-870ffa5f0c8e4714",
              "E-6a337c79e8c34027",
              "E-35d0069132124cb3",
              "E-3839f12052c84057",
              "E-2d63e10d6ee04bb8"
            ],
            "window_seconds": 20
          },
          "before": {
            "http": [
              {
                "avg_ms": "645.37",
                "p50_ms": 649.605,
                "p95_ms": 820.5355,
                "p99_ms": 821.8417999999999,
                "service": "gateway",
                "requests": 60,
                "error_pct": "50.00",
                "throughput_rps": 3.0
              },
              {
                "avg_ms": "614.23",
                "p50_ms": 620.9749999999999,
                "p95_ms": 808.6115,
                "p99_ms": 808.8315,
                "service": "inventory-service",
                "requests": 60,
                "error_pct": "50.00",
                "throughput_rps": 3.0
              },
              {
                "avg_ms": "452.28",
                "p50_ms": 451.18,
                "p95_ms": 463.792,
                "p99_ms": 468.38820000000004,
                "service": "order-service",
                "requests": 30,
                "error_pct": "0.00",
                "throughput_rps": 1.5
              },
              {
                "avg_ms": "5.99",
                "p50_ms": 5.92,
                "p95_ms": 7.4285,
                "p99_ms": 7.6091,
                "service": "payment-service",
                "requests": 30,
                "error_pct": "0.00",
                "throughput_rps": 1.5
              },
              {
                "avg_ms": "1.91",
                "p50_ms": 1.7,
                "p95_ms": 3.3969999999999967,
                "p99_ms": 5.386800000000002,
                "service": "user-service",
                "requests": 30,
                "error_pct": "0.00",
                "throughput_rps": 1.5
              }
            ],
            "redis": {
              "note": "Redis stats are cumulative and include control-plane requests; compare snapshots.",
              "catalog_ttl": 29,
              "keyspace_hits": 58536,
              "keyspace_misses": 315732
            },
            "source": "Measured",
            "db_pool": [
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "gateway"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "gateway",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 53,
                      "pool_size": 1,
                      "requests_num": 354,
                      "connections_ms": 23,
                      "pool_available": 1,
                      "connections_num": 1,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "gateway"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "user-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "user-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 2252,
                      "pool_size": 2,
                      "requests_num": 9459,
                      "connections_ms": 50,
                      "pool_available": 2,
                      "connections_num": 3,
                      "requests_queued": 2,
                      "requests_wait_ms": 0,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "user-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "order-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "order-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 19507,
                      "pool_size": 3,
                      "requests_num": 8363,
                      "connections_ms": 63,
                      "pool_available": 3,
                      "connections_num": 4,
                      "requests_queued": 3,
                      "requests_wait_ms": 2,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "order-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "payment-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "payment-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 20595,
                      "pool_size": 3,
                      "requests_num": 8429,
                      "connections_ms": 58,
                      "pool_available": 3,
                      "connections_num": 4,
                      "requests_queued": 3,
                      "requests_wait_ms": 3,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "payment-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "inventory-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "inventory-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 1459531,
                      "pool_size": 4,
                      "requests_num": 61957,
                      "connections_ms": 72,
                      "pool_available": 0,
                      "connections_num": 5,
                      "requests_errors": 352,
                      "requests_queued": 699,
                      "requests_wait_ms": 420775,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "inventory-service"
                  },
                  "http_status": 200
                }
              },
              {
                "health": {
                  "body": {
                    "status": "healthy",
                    "service": "notification-service"
                  },
                  "http_status": 200
                },
                "source": "Measured",
                "service": "notification-service",
                "pool-stats": {
                  "body": {
                    "pool": {
                      "pool_max": 4,
                      "pool_min": 1,
                      "usage_ms": 26653,
                      "pool_size": 2,
                      "requests_num": 8362,
                      "connections_ms": 46,
                      "pool_available": 2,
                      "connections_num": 3,
                      "requests_queued": 2,
                      "requests_wait_ms": 0,
                      "requests_waiting": 0
                    },
                    "source": "Measured",
                    "service": "notification-service"
                  },
                  "http_status": 200
                }
              }
            ],
            "database": {
              "source": "Measured",
              "activity": [
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "SELECT * FROM users WHERE id=1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "user-service"
                },
                {
                  "query": "SELECT pg_sleep(2)",
                  "state": "active",
                  "wait_event": "PgSleep",
                  "wait_event_type": "Timeout",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT 1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "gateway"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "notification-service"
                },
                {
                  "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO tool_calls(id,external_id,incident_id,run_id,agent,tool_name,arguments,status) VALUES($1,$2,$3,$4,$5,$6,$7,$8)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO notifications(order_id) VALUES($1) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "notification-service"
                },
                {
                  "query": "SELECT pg_sleep(2)",
                  "state": "active",
                  "wait_event": "PgSleep",
                  "wait_event_type": "Timeout",
                  "application_name": "inventory-service"
                },
                {
                  "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "INSERT INTO agent_steps(incident_id,kind,payload) VALUES($1,$2,$3) RETURNING id",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "SELECT pg_sleep(2)",
                  "state": "active",
                  "wait_event": "PgSleep",
                  "wait_event_type": "Timeout",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT pg_sleep(2)",
                  "state": "active",
                  "wait_event": "PgSleep",
                  "wait_event_type": "Timeout",
                  "application_name": "inventory-service"
                },
                {
                  "query": "SELECT * FROM agent_steps WHERE incident_id=$1 AND id>$2 ORDER BY id LIMIT 100",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "sentinel"
                },
                {
                  "query": "INSERT INTO payments(order_id,amount) VALUES($1,$2) ON CONFLICT DO NOTHING",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "payment-service"
                },
                {
                  "query": "INSERT INTO orders(id,user_id,total) VALUES($1,1,$2)",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "order-service"
                },
                {
                  "query": "SELECT * FROM users WHERE id=1",
                  "state": "idle",
                  "wait_event": "ClientRead",
                  "wait_event_type": "Client",
                  "application_name": "user-service"
                }
              ],
              "statements": [
                {
                  "dbid": 16384,
                  "rows": 56920,
                  "calls": 1423,
                  "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": 5452309003183002855,
                  "mean_exec_time": 0.07385190864371051
                },
                {
                  "dbid": 16384,
                  "rows": 87600,
                  "calls": 2190,
                  "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": -5751767986386312266,
                  "mean_exec_time": 0.08092246894977165
                },
                {
                  "dbid": 16384,
                  "rows": 56920,
                  "calls": 56920,
                  "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                  "userid": 10,
                  "queryid": -4386432147220479149,
                  "mean_exec_time": 0.03729027362965548
                },
                {
                  "dbid": 16384,
                  "rows": 476,
                  "calls": 476,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -3416356442043621232,
                  "mean_exec_time": 2001.7273390735281
                },
                {
                  "dbid": 16384,
                  "rows": 460,
                  "calls": 460,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -11391618518959119,
                  "mean_exec_time": 1201.9669297260864
                }
              ],
              "call_deltas": [
                {
                  "dbid": 16384,
                  "query": "SELECT id FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": 5452309003183002855,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT id,name,price,stock FROM products ORDER BY id LIMIT $1",
                  "userid": 10,
                  "queryid": -5751767986386312266,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT id,name,price,stock FROM products WHERE id=$1",
                  "userid": 10,
                  "queryid": -4386432147220479149,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -3416356442043621232,
                  "calls_delta": 0
                },
                {
                  "dbid": 16384,
                  "query": "SELECT pg_sleep($1)",
                  "userid": 10,
                  "queryid": -11391618518959119,
                  "calls_delta": 0
                }
              ],
              "sample_seconds": 1
            },
            "kafka_lag": [
              {
                "lag": 0,
                "partition": 0,
                "end_offset": 15298,
                "committed_offset": 15298
              }
            ],
            "observed_at": "2026-09-21T08:49:44.998529+00:00",
            "evidence_ids": [
              "E-9b5c56b1aa38430d",
              "E-3bbfb04e508f4c68",
              "E-93855876512e4daa",
              "E-56e7c4c65aef46f8",
              "E-a108e5fac9e4484e"
            ],
            "window_seconds": 20
          },
          "recovery_actor": "operator_experiment_runner",
          "causality_limit": "Operator restoration is observational support; not an AI patch or proof of a unique mechanism.",
          "not_an_ai_repair": true
        },
        "production_applied": false
      }
    }
  ]
}
```
