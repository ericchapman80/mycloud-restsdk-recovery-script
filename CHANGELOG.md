# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0-monorepo-phase0] - 2024-12-24

### Phase 0: Monorepo Organization & Testing Infrastructure

This release completes Phase 0 of the repository reorganization, establishing a solid foundation for future development and repository splitting.

### Added

**Testing Infrastructure:**
- `shared/create_test_dataset.py` - Smart test dataset creation tool (410 lines)
  - Multiple sampling strategies: diverse, edge_cases, quick
  - Automatic schema copy excluding SQLite internal tables
  - File sharding support (single-char, two-char, flat)
  - Progress tracking and validation
- `shared/validate_results.py` - Output comparison and validation tool (244 lines)
  - File count and size verification
  - SHA256 content integrity checks
  - Directory structure comparison
  - Detailed diff reporting
- `--limit` flag for both recovery tools
  - Enables rapid development iteration
  - Tests with small subsets (10-100 files)
  - Available in both legacy and modern tools

**Documentation:**
- `modern/UTF8-EMOJI-SUPPORT.md` - Technical emoji encoding documentation
- `modern/EMOJI-QUICK-FIX.md` - Quick troubleshooting guide
- `PHASE0_STATUS.md` - Complete Phase 0 implementation tracking
- Updated all README files with new tooling and workflow instructions

**User Experience:**
- Interactive setup script with opt-in shell configuration
- `./setup.sh --no-shell-config` flag for security-conscious users  
- Graceful emoji fallback system (✅ → [OK], 📋 → [TRANSFER])
- UTF-8 encoding auto-detection and configuration

### Fixed

**Database & Schema Issues:**
- Schema copy now excludes SQLite internal tables (sqlite_sequence, etc.)
- Fixed FTS (Full-Text Search) shadow table handling
- Corrected table name case sensitivity (Files vs files)
- Added all required NOT NULL columns to INSERT statements
- Fixed content path resolution for single-char sharding

**rsync Compatibility:**
- Removed `--info=progress2` flag (not supported by macOS openrsync)
- Added Homebrew rsync 3.4.1 installation via Brewfile
- Updated to use `--progress` for universal compatibility

**Symlink Farm:**
- Changed symlinks from relative to absolute paths
- Fixed broken symlinks preventing rsync transfers
- Symlinks now resolve correctly from /tmp/farm location

**Progress Monitoring:**
- Updated parser for standard rsync `-v --progress` output
- Fixed file transfer counter (was counting directories)
- Parse rsync summary for accurate byte counts
- Real-time progress updates every 5 files

**UTF-8/Emoji Encoding:**
- Added UTF-8 wrapper for stdout/stderr
- Implemented emoji detection and fallback system
- Fixed "surrogates not allowed" errors under sudo
- Automatic encoding configuration in setup.sh

### Changed

**Modern Tool Improvements:**
- Simplified database stats (removed misleading "Already copied" message)
- Enhanced summary output with source/destination comparison
- Better error reporting and retry logic
- Comprehensive validation reporting

**Setup Process:**
- Setup script now asks permission before modifying shell config
- Added `PYTHONIOENCODING=utf-8` environment variable configuration
- Improved user guidance for emoji support
- Clear instructions for minimal/no-modification setup

### Validated

**Manual Testing Results:**
- Test dataset: 36 files (430.54 MB), 130 database rows
- Legacy recovery: 36/36 files, 0 errors, 225.31 files/sec ✅
- Modern recovery: 36/36 files, 0 errors, 74.93 MB/s ✅
- Validation: 100% identical outputs ✅
- Multiple test iterations: All successful ✅

### Technical Improvements

- Proper error handling with UTF-8 encoding fallbacks
- Better subprocess management with encoding configuration
- Improved progress parsing for rsync compatibility
- Enhanced real-time monitoring with accurate metrics
- Comprehensive emoji support with graceful degradation

### Repository Structure

Maintained clean separation of concerns:
```
mycloud-restsdk-recovery-script/
├── legacy/           # Python-based recovery (maintenance mode)
├── modern/           # Rsync-based recovery (active development)
└── shared/           # Common tools and test fixtures
```

### Known Issues

None - Phase 0 complete and validated for production use.

### Migration Guide

For existing users:
1. Run `./setup.sh` in your desired subdirectory (legacy/ or modern/)
2. Choose whether to configure shell for emoji support (optional)
3. Test with `--limit 10` flag before full recovery
4. Use validation tool to verify results

### Next Steps

Phase 1: Repository split into separate repos for legacy and modern approaches.

---

## [1.x.x] - Historical Releases

See git history for previous versions before Phase 0 reorganization.
