# MyCloud Recovery Tools (Archived Monorepo)

> **⚠️ THIS REPOSITORY HAS BEEN REFACTORED AND SPLIT**
>
> This monorepo has been reorganized into two focused, standalone repositories. Please use the new repos below for all future work.

---

## 🚀 New Repositories

### ✨ [wd-mycloud-rsync-recovery](https://github.com/ericchapman80/wd-mycloud-rsync-recovery) — **Recommended**

Modern rsync-based recovery toolkit for WD MyCloud NAS devices.

- Lower memory usage (~50 MB vs 2-10 GB)
- Automatic timestamp preservation
- Built-in resume capability
- Real-time progress tracking
- Cleanup mode for orphaned files
- **389+ tests, 70-76% coverage**

👉 **[Use this for all new recoveries →](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)**

---

### � [wd-mycloud-python-recovery](https://github.com/ericchapman80/wd-mycloud-python-recovery) — Maintenance Mode

Legacy Python-based recovery tool for WD MyCloud NAS devices.

- Original restsdk_public.py approach
- Works in constrained environments
- Established, well-tested codebase
- **127 tests, 63% coverage**

� **[Legacy tool (critical fixes only) →](https://github.com/ericchapman80/wd-mycloud-python-recovery)**

---

## 📜 About This Repository

This was the original monorepo containing both recovery approaches. It has been preserved for historical reference but is **no longer actively maintained**.

**What was accomplished here:**

- ✅ Multi-threading and memory optimization
- ✅ Resume capability and checkpoint system
- ✅ Pre-flight hardware analysis
- ✅ Comprehensive test coverage (389+ tests)
- ✅ Modern rsync-based alternative to Python approach
- ✅ Repository split into focused, standalone tools

See [PHASE0_STATUS.md](PHASE0_STATUS.md) and [REPO_SPLIT_PLAN.md](REPO_SPLIT_PLAN.md) for the complete development history.

---

## 🙏 Credits

Original script by [springfielddatarecovery](https://github.com/springfielddatarecovery/mycloud-restsdk-recovery-script)

Enhancements, rsync approach, and repository split by [@ericchapman80](https://github.com/ericchapman80)

---

## 📜 License

See [LICENSE](LICENSE) file.
