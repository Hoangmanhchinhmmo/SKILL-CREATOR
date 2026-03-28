# Review & Test Plan — SKILL-CREATOR

## Goal
Fix critical issues found in multi-agent code review, then build a test suite for the two Python projects.

---

## Part A: Critical Code Fixes (from Code Review)

- [ ] **A1: Rotate leaked API keys** — `.env` is tracked in Git with live Gemini keys. Rotate all keys immediately, `git rm --cached` the file, add to `.gitignore` properly. → Verify: `git log --all -- "*.env"` shows removal, old keys no longer work.
- [ ] **A2: Fix `genai.configure()` race condition** — `agents.py:58` and `supervisor.py:87` set global API key. Refactor to use per-agent `GenerativeModel(api_key=...)` instances. → Verify: two agents can run with different keys without cross-contamination.
- [ ] **A3: Remove `importlib.reload()` from pipeline_runner** — `pipeline_runner.py:231-238` reloads modules in daemon thread. Pass config as parameters instead. → Verify: no `importlib.reload` calls remain in pipeline_runner.py.
- [ ] **A4: Stop injecting secrets into `os.environ`** — `pipeline_runner.py:44-91` writes decrypted keys to process env. Pass directly to agent functions. → Verify: `os.environ` not modified by pipeline runner.
- [ ] **A5: Fix machine_id fallback to "UNKNOWN"** — `machine_id.py:34-37` returns `"UNKNOWN"` on failure, creating universal machine code. Fail activation instead. → Verify: `get_machine_code()` raises error when hardware ID unavailable.
- [ ] **A6: Add pipeline error recovery UI** — `pipeline.py:234-242` shows error with no action buttons. Add "Retry" and "Back to Dashboard" buttons on failure state. → Verify: pipeline failure screen shows actionable buttons.
- [ ] **A7: Fix dead "Buy here" link** — `license.py:79-82` has no `on_click` handler. Wire to purchase URL. → Verify: clicking "Mua tai day" opens browser.
- [ ] **A8: Add SQLite `busy_timeout`** — `database.py:33-36` has no busy_timeout PRAGMA. Add `PRAGMA busy_timeout=5000`. → Verify: concurrent read/write doesn't throw "database is locked".
- [ ] **A9: Fix `write_with_review` feedback ignored** — `pipeline_v2.py:59` retries with original args, never passes supervisor feedback. Pass `feedback_prompt` to writer. → Verify: retry call includes feedback in prompt.
- [ ] **A10: Fix `if status:` bug in models.py** — `models.py:165,220` uses truthy check, empty string silently skipped. Change to `if status is not None:`. → Verify: `update_pipeline_run(run_id, status="")` actually updates.

---

## Part B: Test Infrastructure Prerequisites

- [ ] **B1: Refactor `config.py` import side effects** — Move `load_dotenv()` (line 9) and `os.makedirs()` (line 50) into `init_config()` function. → Verify: `import config` alone creates no dirs, loads no .env.
- [ ] **B2: Refactor `pipeline_v2.py` stdout rewrite** — Move `sys.stdout`/`sys.stderr` `TextIOWrapper` (lines 18-19) into `main()`. → Verify: importing pipeline_v2 doesn't touch sys.stdout.
- [ ] **B3: Guard `machine_id.py` for cross-platform** — Wrap Windows subprocess constants (lines 12-17) in `if sys.platform == "win32"`. → Verify: `import machine_id` works on Linux without error.
- [ ] **B4: Create `requirements-dev.txt`** — Add `pytest`, `pytest-mock`, `freezegun`. → Verify: `pip install -r requirements-dev.txt && pytest --version` works.
- [ ] **B5: Create test scaffolding** — Create `tests/` dirs, `conftest.py` with DB fixture (temp-file SQLite, patched `get_connection`, global cache resets). → Verify: `pytest --collect-only` finds test files.

---

## Part C: Write Tests (priority order)

- [ ] **C1: Test `crypto.py`** — Round-trip encrypt/decrypt, wrong key returns empty, key derivation deterministic. Pure functions, no mocks needed. → Verify: `pytest tests/test_crypto.py` passes.
- [ ] **C2: Test `detect_format()` and `post_process()`** — Input/output pairs for all 8 format keywords + Japanese text cleanup. → Verify: `pytest tests/test_pipeline_v2.py` passes.
- [ ] **C3: Test `database.py` + `models.py`** — Schema init, all CRUD operations on temp-file SQLite. Patch `get_connection`. Test `delete_article` transaction safety. → Verify: `pytest tests/test_models.py` passes.
- [ ] **C4: Test `supervisor.py` review parsing** — Mock `_call_supervisor`, test PASS/FAIL detection, empty response handling, unicode colon variants. → Verify: `pytest tests/test_supervisor.py` passes.
- [ ] **C5: Test `license_service.py`** — Mock `requests.post`, `db.models`, `machine_id`, `crypto`. Test activate/verify/grace period with `freezegun`. → Verify: `pytest tests/test_license_service.py` passes.
- [ ] **C6: Test `machine_id.py`** (Windows only) — Mock `subprocess.check_output`, test PowerShell/wmic fallback, cache behavior. `@pytest.mark.skipif` on Linux. → Verify: `pytest tests/test_machine_id.py` passes (or skips on Linux).

---

## Done When
- [ ] All API keys rotated, `.env` removed from Git tracking
- [ ] No import-time side effects in `config.py`, `pipeline_v2.py`, `machine_id.py`
- [ ] `pytest` runs clean with 6+ test files passing
- [ ] Critical bugs (A9, A10) fixed with regression tests

## Notes
- Mock targets must be at the **importing module's namespace** (e.g., `section_writers._call_gemini`, not `agents._call_gemini`)
- Use temp-file SQLite (not `:memory:`) — in-memory creates new DB per connection
- `conftest.py` must reset `machine_id._cached_machine_code = None` and `database._db_path = None` after each test
- `pipeline_runner` tests must call `_run()` directly, never through `start()` (daemon thread swallows assertions)
- 27/28 CRUD functions in models.py hardcode `get_connection()` — must patch at `db.database.get_connection`
