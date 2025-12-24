# MyCloud Recovery Tools

Recover and transfer files from a Western Digital (WD) MyCloud device to another location (like a Synology NAS).

> **📢 This project is a fork of [springfielddatarecovery/mycloud-restsdk-recovery-script](https://github.com/springfielddatarecovery/mycloud-restsdk-recovery-script)** with significant enhancements including multi-threading, memory optimization, resume capability, and a new rsync-based approach.

---

## 🏗️ Repository Structure (Phase 0: Pre-Split)

This repository is being reorganized into two distinct approaches:

### 📂 [`modern/`](modern/) - **Recommended** ✨

**Modern rsync-based recovery** (actively maintained)
- Lower memory usage (~50 MB vs 2-10 GB)
- Automatic timestamp preservation
- Built-in resume capability
- Real-time progress tracking
- Cleanup mode for orphaned files

👉 **[Start here for new recoveries →](modern/README.md)**

### 📂 [`legacy/`](legacy/) - Maintenance Mode ⚠️

**Python-based recovery** (critical fixes only)
- Original restsdk_public.py approach
- Requires manual timestamp sync (sync_mtime.py)
- Works in constrained environments
- Established, well-tested codebase

👉 **[See legacy documentation →](legacy/README.md)**

### 📂 [`shared/`](shared/)

Common resources:
- Database schema documentation

---

## 🚀 Quick Start

**macOS users (recommended):**
```bash
# Install system dependencies
brew bundle

# Choose your approach below
```

**For new users (recommended):**
```bash
cd modern
./setup.sh          # Installs Poetry and dependencies
poetry shell        # Activate environment
python preflight.py /path/to/source /path/to/dest
python rsync_restore.py --db index.db --source-root /source --dest-root /dest
```

**For legacy approach:**
```bash
cd legacy
./setup.sh
python preflight.py /path/to/source /path/to/dest
python restsdk_public.py --db index.db --filedir /source --dumpdir /dest
```

---

## 📋 Repository Roadmap

**✅ Phase 0 Complete** - Internal Reorganization & Testing Infrastructure
- ✅ Created `legacy/` and `modern/` subdirectories
- ✅ Duplicated shared tools (preflight, setup, tests)
- ✅ Both approaches tested independently and validated
- ✅ Testing infrastructure: create_test_dataset.py, validate_results.py, --limit flag
- ✅ Manual recovery validation: Both tools produce identical outputs (36 files, 430.54 MB)
- ✅ Bug fixes: Database schema, rsync compatibility, symlink paths, UTF-8 encoding
- ✅ User experience improvements: Emoji support with fallbacks, interactive setup

**Next Phase:** Repository Split
- Split into two separate repos:
  - `mycloud-python-recovery` (legacy, maintenance mode)
  - `mycloud-rsync-restore` (modern, active development)

See [PHASE0_STATUS.md](PHASE0_STATUS.md) and [CHANGELOG.md](CHANGELOG.md) for complete details.

---

## ☕ Support This Project

If this tool saved your data, consider supporting continued development:

- **GitHub Sponsors:** [Sponsor @ericchapman80](https://github.com/sponsors/ericchapman80)
- **Buy Me a Coffee:** Coming soon

---

## 📖 Documentation

- **Modern Approach:** [modern/README.md](modern/README.md)
- **Legacy Approach:** [legacy/README.md](legacy/README.md)
- **Symlink Farm Guide:** [README-SYMLINK-FARM.md](README-SYMLINK-FARM.md)
- **Repository Split Plan:** [REPO_SPLIT_PLAN.md](REPO_SPLIT_PLAN.md)
- **Manual Testing:** [docs/MANUAL_TESTING.md](docs/MANUAL_TESTING.md)
- **Performance Analysis:** [docs/PERFORMANCE_ANALYSIS.md](docs/PERFORMANCE_ANALYSIS.md)

---

## 🧪 Testing

Each subdirectory has its own test suite:

```bash
# Test legacy approach
cd legacy && ./run_tests.sh

# Test modern approach
cd modern && ./run_tests.sh
```

---

## 🤝 Contributing

- **Modern approach** (`modern/`): New features and improvements welcome!
- **Legacy approach** (`legacy/`): Critical bug fixes only

---

## 📜 License

See [LICENSE](LICENSE) file.

---

## 🙏 Credits

Original script by [springfielddatarecovery](https://github.com/springfielddatarecovery/mycloud-restsdk-recovery-script)

Enhancements and rsync approach by [@ericchapman80](https://github.com/ericchapman80)
