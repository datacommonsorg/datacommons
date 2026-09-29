# PR #290: Deferred Tasks & Follow-up Design Topics

This document tracks items discussed during the review of PR #290 (`cliInitDb`) that were intentionally deferred to keep the initial database initialization and migration tooling PR scoped, safe, and focused.

---

## 1. Spanner Emulator Schema Dump Investigation (PR Review Comment 16)
- **Topic**: Investigate using the Spanner emulator's `database.get_schema_ddl()` to dump a true engine-collapsed schema artifact (e.g. for generating an entity-relationship diagram or a standalone target DDL).
- **Key Consideration**: The Spanner emulator does not currently support several production DDL statements (notably `CREATE MODEL ... REMOTE OPTIONS (...)`).
- **Comparison**: Weigh the benefits of an engine-collapsed DDL against maintaining the current sequential execution transcript in `tests/snapshots/schema_snapshot.sql`, which accurately reflects how migrations are applied in real environments (baseline first, then sequential migration steps) and provides clear PR diff visibility.

---

## 2. Snapshot / Generated Schema Location & Package Boundaries (PR Review Comment 18)
- **Topic**: Decide whether `schema_snapshot.sql` should live in `tests/snapshots/` (assertion fixture for regression tests and PR diff guardrails) vs. `packages/datacommons-db/datacommons_db/schema/generated/` (exported contract).
- **Encapsulation**: Consider having `datacommons-db` own writing its own schema artifact via `write_compiled_schema()` or `write_target_schema()`. This would simplify `datacommons-devtools` by removing filesystem boilerplate.

---

## 3. Schema Directory Reorganization & Renaming (PR Review Comments 2, 3, 5)
- **Topic**: Move `schema.sql` into the standardized package source hierarchy (e.g. `packages/datacommons-db/src/datacommons_db/...`).
- **Naming**: Rename `schema.sql` $\to$ `baseline_schema.sql` (or similar) to make its role as the initial DB baseline explicit and distinguish it from compiled or migrated states.

---

## 4. `schema/loader.py` Refactor & `init_schema()` Simplification (PR Review Comment 12)
- **Topic**: Introduce a dedicated `datacommons_db.schema.loader` utility module to encapsulate path resolution, file reading, and environment variable templating (`PROJECT_ID`, `REGION`).
- **Impact**: Allows `SpannerClient.init_schema()` to collapse into a concise two-line method delegating directly to the schema loader.

---

## 5. Spanner Emulator Parity & Remote ML Model Isolation (E2E Integration Test)
- **Topic**: The Cloud Spanner emulator fails on `CREATE MODEL NodeEmbeddingModel REMOTE OPTIONS (...)` with a syntax error on `REMOTE`.
- **Resolution**: Move `NodeEmbeddingModel` out of the baseline schema into a migration flagged with `emulator_supported = False` (as drafted in the `emulatorFix` branch). This allows hermetic e2e tests in `test_e2e_spanner.py` to run seamlessly on developer machines and in CI emulator workflows.

---

## 6. Generalizing Migration / DDL Execution Engine (PR Review Comment 8)
- **Topic**: Evaluate unifying synchronous batch polling (`_execute_ddl_sync`) into a broader asynchronous Long Running Operation (LRO) helper shared across the database client layer.

---

## 7. Granular Multi-Writer Locking (PR Review Comments 9, 11)
- **Topic**: Re-evaluate whether to expose fine-grained lock IDs (e.g., per-dataset, per-provenance) or additional `LockState` types when multi-writer ingestion pipelines require concurrent non-interfering locks, rather than relying solely on `GLOBAL_INGESTION_LOCK_ID`.

---

## 8. Historical SQL Formatting & Legacy Comment Cleanups (PR Review Comment 4)
- **Topic**: Clean up inherited formatting, whitespace, and historical schema comments in SQL files during a dedicated schema maintenance pass to avoid polluting git blame in functional PRs.
