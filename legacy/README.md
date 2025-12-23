# MyCloud Python Recovery (Legacy)

⚠️ **This is the legacy Python-based recovery approach. For new projects, consider the [modern rsync-based approach](../modern/).**

## Overview

Python-based file recovery tool for MyCloud NAS devices. Reads from SQLite database and reconstructs file hierarchy.

## Features

- Direct Python file copying from database metadata
- Multi-threaded recovery
- `--low-memory` mode for constrained environments
- Symlink-based deduplication
- Metadata timestamp synchronization

## Quick Start

```bash
# Setup environment
./setup.sh

# Run preflight analysis
python preflight.py /path/to/source /path/to/dest

# Run recovery
python restsdk_public.py --db index.db --filedir /source --dumpdir /dest --thread-count 4

# If you used --low-memory, sync timestamps
python sync_mtime.py --db index.db --root-dir /dest
```

## Tools

- **restsdk_public.py** - Main recovery script
- **sync_mtime.py** - Post-recovery timestamp sync (for --low-memory mode)
- **preflight.py** - System analysis and thread recommendations
- **create_symlink_farm.py** - Deduplication via symlinks
- **mtime_check.py** - Metadata validation utility

## Testing

```bash
# Run all legacy tests
./run_tests.sh

# Generate coverage report
./run_tests.sh html
```

## Migration Guide

For better performance and simpler operation, consider migrating to the [modern rsync-based approach](../modern/).

## Maintenance Mode

This codebase is in **maintenance mode**:
- Critical bug fixes only
- No new feature development
- See modern approach for active development
