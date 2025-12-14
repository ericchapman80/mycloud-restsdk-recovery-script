Manual testing checklist
========================

Use these commands as a lightweight script to verify the recovery workflow manually. Run from the repository root.

1) Environment setup
- `bash setup.sh`
- `source venv/bin/activate`

2) Fast sanity checks
- `python -m pytest`
- `python restsdk_public.py --help` (parses once and exits)

3) Preflight hardware/file check
- `python restsdk_public.py --preflight --filedir /path/to/source/files --dumpdir /path/to/destination`

4) Standard dry run (no writes)
- `python restsdk_public.py --db /path/to/index.db --filedir /path/to/source/files --dumpdir /path/to/destination --log_file copied_file.log --dry_run --thread-count 4`
  - Add `--preserve-mtime` to verify timestamp preservation logic (still dry-run, so no writes).

5) Resume with log regeneration (recommended)
- `python restsdk_public.py --resume --db /path/to/index.db --filedir /path/to/source/files --dumpdir /path/to/destination --log_file copied_file.log --thread-count 4`
  - Mtime preservation is on by default; use `--no-preserve-mtime` to disable if needed.
  - Use `--refresh-mtime-existing` to refresh mtimes on already-present files without recopying.

6) Resume without regeneration (advanced)
- `python restsdk_public.py --resume --no-regen-log --db /path/to/index.db --filedir /path/to/source/files --dumpdir /path/to/destination --log_file copied_file.log`

7) Regenerate log only (no copying)
- `python restsdk_public.py --regen-log --db /path/to/index.db --dumpdir /path/to/destination --log_file copied_file.log`

Notes
- Replace `/path/to/...` with your actual paths.
- The log file is required for resume and standard runs to avoid duplicate copies.
- Dry-run mode still walks the source but does not write to the destination.

Performance sanity (optional)
- Set an env var to control perf test size, then run pytest:
  - `export PERF_TEST_ROWS=20000` (for example)
  - `python -m pytest -m perf`
- On success you should see the perf test run; unset the env var to skip it.
