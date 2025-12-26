# Repository Split Plan

## Executive Summary

Split the current monorepo into two focused repositories to improve maintainability, clarity, and user experience.

## Current State (Monorepo)

**Repository:** `mycloud-restsdk-recovery-script`
- Mixed legacy (restsdk_public.py) and modern (rsync_restore.py) approaches
- Confusing for new users which tool to use
- Different dependencies and use cases
- Maintenance burden tracking both codebases

## Proposed State (Two Repos)

### Repo 1: mycloud-python-recovery (Legacy)
**Purpose:** Archived/maintenance-only Python-based recovery tool

**What stays:**
- `restsdk_public.py` - Core legacy script
- `sync_mtime.py` - Post-recovery mtime sync for --low-memory runs
- `preflight.py` - System analysis & thread recommendations (shared with modern)
- `create_symlink_farm.py` - Symlink-based deduplication
- `mtime_check.py` - Metadata utilities
- `setup.sh` - Environment setup script (shared with modern)
- `run_tests.sh` - Test runner (adapted for legacy tests)
- `tests/test_restsdk_public.py` - Python tool tests
- `tests/test_restsdk_high_value.py` - High-value function tests
- `tests/test_db_flows.py` - Database workflow tests
- `tests/test_symlink_farm.py` - Symlink tests
- Legacy documentation sections from README.md

**README focus:**
- "⚠️ This tool is in maintenance mode - use mycloud-rsync-restore for new projects"
- Python-based approach documentation
- Troubleshooting for existing users
- Migration guide to rsync tool

**Branch strategy:**
- `main` - frozen at last stable release
- `maintenance` - critical bug fixes only

---

### Repo 2: mycloud-rsync-restore (Modern - Recommended)
**Purpose:** Active development, rsync-based recovery with cleanup features

**What moves here:**
- `rsync_restore.py` - Core rsync wrapper
- `preflight.py` - System analysis & thread recommendations (shared with legacy)
- `monitor.sh` - Progress monitoring for rsync operations
- `setup.sh` - Environment setup script (shared with legacy)
- `run_tests.sh` - Test runner (adapted for modern tests)
- `tests/test_perf_regen_log.py` - Performance tests
- `README-SYMLINK-FARM.md` → becomes main README.md
- New cleanup feature and config

**README focus:**
- Recommended approach for all users
- Wizard mode walkthrough
- Cleanup feature documentation
- Performance comparison vs Python tool
- Advanced rsync options

**Branch strategy:**
- `main` - stable releases
- `develop` - active development
- Feature branches for new capabilities

---

## Shared Components

### What goes in BOTH repos:
- `preflight.py` - System analysis tool (useful for both recovery approaches)
- `setup.sh` - Python venv setup (both repos need Python environment)
- `run_tests.sh` - Test runner (adapted for each repo's test suite)
- Database schema documentation (`sql-data.info`)
- Link to sister repo in README

### Duplication strategy:
- **Option B:** Duplicate and let them diverge (simpler, more maintainable)
- **Recommendation:** Option B - repos serve different audiences and shared files will evolve independently

### File Placement Rationale:

| File | Legacy Repo | Modern Repo | Reasoning |
|------|:-----------:|:-----------:|-----------|
| `sync_mtime.py` | ✅ | ❌ | Fixes `--low-memory` limitation in restsdk_public.py; rsync preserves timestamps automatically |
| `preflight.py` | ✅ | ✅ | Universal system analysis—provides thread recommendations for both approaches |
| `setup.sh` | ✅ | ✅ | Both repos need Python virtual environment setup |
| `run_tests.sh` | ✅ | ✅ | Both repos have test suites; script will be adapted for each |
| `create_symlink_farm.py` | ✅ | ❌ | Legacy Python deduplication strategy |
| `mtime_check.py` | ✅ | ❌ | Validation utility specific to Python recovery workflow |
| `monitor.sh` | ❌ | ✅ | Rsync-specific progress monitoring |
| `tests/test_db_flows.py` | ✅ | ❌ | Database tests for Python workflow |
| `tests/test_symlink_farm.py` | ✅ | ❌ | Tests legacy deduplication |
| `tests/test_perf_regen_log.py` | ❌ | ✅ | Performance tests for rsync approach |
- **Option A:** Git submodule for shared code
- **Option B:** Duplicate and let them diverge (simpler, more maintainable)
- **Recommendation:** Option B - repos serve different audiences and `preflight.py` may diverge over time to add tool-specific checks

### File Placement Rationale:

| File | Legacy Repo | Modern Repo | Reasoning |
|------|:-----------:|:-----------:|-----------|
| `sync_mtime.py` | ✅ | ❌ | Fixes `--low-memory` limitation in restsdk_public.py; rsync preserves timestamps automatically |
| `preflight.py` | ✅ | ✅ | Universal system analysis—provides thread recommendations for both approaches |
| `create_symlink_farm.py` | ✅ | ❌ | Legacy Python deduplication strategy |
| `mtime_check.py` | ✅ | ❌ | Validation utility specific to Python recovery workflow |
| `monitor.sh` | ❌ | ✅ | Rsync-specific progress monitoring |
| `tests/test_db_flows.py` | ✅ | ❌ | Database tests for Python workflow |
| `tests/test_symlink_farm.py` | ✅ | ❌ | Tests legacy deduplication |
| `tests/test_perf_regen_log.py` | ❌ | ✅ | Performance tests for rsync approach |
---

## Migration Timeline

### ✅ Phase 0: Internal Reorganization & Test Coverage (COMPLETE)
**Goal:** Restructure monorepo into subdirectories to validate the split + Achieve adequate test coverage

**Status:** ✅ **COMPLETE** - Tagged as `v2.0.0-monorepo-phase0`

**Completed Tasks:**
- ✅ Created `legacy/` and `modern/` subdirectories
- ✅ Moved files to appropriate subdirectories (per table above)
- ✅ Duplicated shared files (`preflight.py`, `setup.sh`, `run_tests.sh`)
- ✅ Updated import paths in test files
- ✅ Verified both subdirectories work independently
- ✅ Updated root README.md to explain dual structure
- ✅ Tested actual recovery operations from each subdirectory
- ✅ Both tools produce identical outputs (36 files, 430.54 MB)
- ✅ **Test Coverage Improvements (Modern Tool):**
  - ✅ Phase 1: Added 202 unit tests (symlink farm, preflight, cleanup, user interaction)
  - ✅ Phase 2: Added 127 integration tests (end-to-end workflows)
  - ✅ Additional: 60+ progress monitoring and utility tests
  - ✅ **Total: 389+ new tests, 5,722 lines of test code**
  - ✅ **Coverage: 10% → 70-76%** (approaching legacy's 63% baseline)
  - ✅ All Priority 1 gaps addressed (symlink farm, preflight.py, cleanup, user interaction)

**Test Coverage Summary:**
- **Legacy Tool:** 63% coverage (stable, well-tested)
- **Modern Tool:** 70-76% coverage (now comprehensive, ready for split)
- **Combined Project:** ~66-69% coverage

**Benefits Achieved:**
- ✅ Low-risk validation of the split completed
- ✅ File placement validated through testing
- ✅ Both repos work independently in subdirectories
- ✅ Clear path to Phase 1 confirmed
- ✅ Modern tool now has quality test coverage matching legacy standards

### 🚀 Phase 1: Repository Creation (Ready to Execute)
**Goal:** Create two separate repositories from validated subdirectories

**Prerequisites:** ✅ All complete
- ✅ Phase 0 validation complete
- ✅ Both subdirectories tested independently
- ✅ Test coverage meets quality standards (70-76% modern, 63% legacy)
- ✅ Tagged as `v2.0.0-monorepo-phase0`

**Tasks:**
- [ ] Tag current monorepo: `v2.0.0-monorepo-final`
- [ ] Create `MIGRATION.md` guide for users
- [ ] Create two new repositories on GitHub:

**Repository 1: `mycloud-python-recovery` (Legacy)**
- [ ] Extract from `legacy/` subdirectory
- [ ] Move files to repo root
- [ ] Update README with maintenance mode notice
- [ ] Set up basic CI for critical bugs
- [ ] Configure branch protection (main = frozen)
- [ ] Add cross-reference to modern repo
- [ ] Tag initial release: `v2.0.0`

**Repository 2: `mycloud-rsync-restore` (Modern)**
- [ ] Extract from `modern/` subdirectory
- [ ] Move files to repo root
- [ ] Promote modern README to root
- [ ] Set up full CI/CD pipeline
- [ ] Configure branch protection (main + develop)
- [ ] Add cross-reference to legacy repo
- [ ] Tag initial release: `v2.0.0`
- [ ] Enable GitHub Discussions
- [ ] Set up issue templates

**Estimated Time:** 1-2 days

### Phase 2: Transition & Communication (Post-Split)
**Goal:** Ensure smooth transition for existing users

**Tasks:**
- [ ] Archive monorepo with redirect README pointing to both new repos
- [ ] Update all external links/documentation
- [ ] Announce split on GitHub (both repos)
- [ ] Update package metadata if applicable
- [ ] Monitor issues and provide migration support
- [ ] Update GitHub sponsors/support links

**Communication:**
- [ ] Create announcement in monorepo README
- [ ] Post in GitHub Discussions (if enabled)
- [ ] Update any external documentation/wikis
- [ ] Notify any known production users

**Estimated Time:** 1 week for transition, ongoing monitoring

### Phase 3: Post-Split (Ongoing)
- [ ] Legacy repo: Maintenance mode only
- [ ] Modern repo: Active feature development
- [ ] Cross-reference in READMEs

---

## User Impact & Communication

### For Existing Users

**Currently using restsdk_public.py:**
```
⚠️ IMPORTANT NOTICE

The Python-based recovery tool has moved to:
https://github.com/ericchapman80/mycloud-python-recovery

This tool is now in MAINTENANCE MODE.
For new recoveries, we recommend: mycloud-rsync-restore
```

**Currently using rsync_restore.py:**
```
✨ GOOD NEWS

The rsync-based tool now has its own repo:
https://github.com/ericchapman80/mycloud-rsync-restore

This is the actively maintained, recommended solution.
```

### Migration Checklist for Users
- [ ] Note which tool you're currently using
- [ ] Bookmark new repository URL
- [ ] Update any automation/scripts
- [ ] Review new features in rsync tool
- [ ] Consider migrating if on Python tool

---

## Technical Details

### Dependencies Split

**Python Recovery (Legacy):**
- Python 3.9+
- SQLite3
- Minimal dependencies (maintenance)

**Rsync Restore (Modern):**
- Python 3.9+
- rsync 3.0+
- PyYAML (optional for cleanup config)
- Active dependency updates

### Testing Strategy

**Phase 0 Testing (Pre-Split Validation):**

**Automated Tests:**
```bash
# Test legacy subdirectory
cd legacy
./setup.sh
./run_tests.sh
./run_tests.sh html

# Test modern subdirectory
cd ../modern
./setup.sh
./run_tests.sh

# Verify all tests pass in both subdirectories
```

**Manual Testing Checklist:**

*Legacy Subdirectory (`legacy/`):*
- [ ] Run preflight analysis: `python preflight.py <source> <dest>`
- [ ] Test restsdk_public.py basic recovery (small test dataset):
  ```bash
  python restsdk_public.py --db test.db --filedir /test/source --dumpdir /test/dest
  ```
- [ ] Test --low-memory mode
- [ ] Run sync_mtime.py on test recovery (verify timestamps sync)
- [ ] Test create_symlink_farm.py deduplication
- [ ] Run mtime_check.py validation
- [ ] Verify all imports resolve correctly from subdirectory
- [ ] Check that tests discover and run properly

*Modern Subdirectory (`modern/`):*
- [ ] Run preflight analysis: `python preflight.py <source> <dest>`
- [ ] Test rsync_restore.py basic recovery (small test dataset)
- [ ] Test monitor.sh progress tracking
- [ ] Verify rsync preserves timestamps (no sync_mtime.py needed)
- [ ] Verify all imports resolve correctly from subdirectory
- [ ] Check that tests discover and run properly

*Cross-Validation:*
- [ ] Recover same test dataset with both approaches
- [ ] Compare file counts, sizes, timestamps
- [ ] Verify modern approach doesn't need sync_mtime.py
- [ ] Confirm preflight.py works identically in both subdirectories

**Post-Split Testing:**

**Legacy Repo:**
- Existing test suite maintained
- Run on critical paths only
- No new test development
- CI runs on: Pull requests to `maintenance` branch

**Modern Repo:**
- Expand test coverage
- Performance benchmarks
- Integration tests with cleanup
- CI runs on: All PRs, nightly performance tests

---

## ✅ Phase 0 Validation Checklist (COMPLETE)

Before proceeding to Phase 1 (actual repo split), verify:

**Functional:**
- ✅ All automated tests pass in both `legacy/` and `modern/`
- ✅ Manual recovery works from both subdirectories
- ✅ Import paths are correct (no references to parent directory)
- ✅ Documentation updated (READMEs reflect subdirectory structure)

**Structural:**
- ✅ No shared files between subdirectories (duplicates are intentional)
- ✅ Each subdirectory is self-contained
- ✅ requirements.txt accurate for each subdirectory
- ✅ pytest.ini configured correctly for each test suite

**Operational:**
- ✅ setup.sh works in both subdirectories
- ✅ run_tests.sh adapted for each test suite
- ✅ preflight.py works identically in both contexts
- ✅ Both approaches successfully recover test dataset

**Test Coverage:**
- ✅ Legacy tool: 63% coverage (stable baseline)
- ✅ Modern tool: 70-76% coverage (389+ new tests)
- ✅ Modern tool coverage now matches legacy quality standards

**Sign-off:**
- ✅ Code owner review complete
- ✅ At least one successful production recovery from each subdirectory
- ✅ Documentation peer review complete
- ✅ **READY TO PROCEED TO PHASE 1** 🚀

---

## GitHub Configuration

### Repo Settings

**mycloud-python-recovery:**
- Topics: `mycloud`, `data-recovery`, `python`, `legacy`, `maintenance`
- Archive: No (allow critical bug reports)
- Issues: Enabled (redirect to modern repo)
- Wiki: Disabled
- Discussions: Disabled

**mycloud-rsync-restore:**
- Topics: `mycloud`, `data-recovery`, `rsync`, `python`, `backup`, `restore`
- Archive: No
- Issues: Enabled with templates
- Wiki: Enabled for advanced guides
- Discussions: Enabled for Q&A

### Cross-Linking

Both repos should have prominent links:
```markdown
## Related Projects

- **mycloud-python-recovery** - Legacy Python-based recovery tool (maintenance mode)
- **mycloud-rsync-restore** - Modern rsync-based tool (recommended)
```

---

## Benefits of Split

### For Users
✅ Clear which tool to use (recommended vs legacy)
✅ Focused documentation per approach
✅ Easier to find relevant issues/discussions
✅ Cleaner dependency management

### For Maintainers
✅ Separate issue trackers reduce noise
✅ Independent release cycles
✅ Legacy code archived without active burden
✅ Modern features don't break legacy users

### For the Project
✅ Professional presentation
✅ Better SEO (two focused repos vs one mixed)
✅ Easier onboarding for contributors
✅ Clear upgrade path for users

---

## Rollback Plan

If split causes issues:
1. Keep monorepo as `v2.0.0-unified` tag
2. Redirect users back temporarily
3. Merge improvements back to monorepo
4. Re-evaluate split approach

**Risk Assessment:** LOW
- Both tools already function independently
- No shared runtime dependencies
- Clear separation of concerns

---

## Next Steps

1. **Review this plan** - Get feedback/approval
2. **Run split simulation** - Test locally first
3. **Execute Phase 1** - Tag and prepare
4. **Communicate** - Announce to users/watchers
5. **Execute split** - Create new repos
6. **Monitor** - Track issues and smooth transition

---

## Questions to Answer

- [ ] Keep same GitHub org or create new for modern tool?
- [ ] Transfer existing issues or start fresh?
- [ ] What happens to existing stars/watchers?
- [ ] Archive monorepo or keep as redirect?
- [ ] Sponsor links - split or unified?

---

## Success Metrics

**After 30 days:**
- [ ] >80% of new issues in correct repo
- [ ] No confusion about which tool to use
- [ ] Positive user feedback on clarity
- [ ] Active development in modern repo
- [ ] Minimal/zero activity in legacy repo

**After 90 days:**
- [ ] Legacy repo clearly marked as archived
- [ ] Modern repo has ≥50% of monorepo stars
- [ ] Documentation highly rated
- [ ] Feature velocity increased (modern repo)
