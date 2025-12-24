# MyCloud Rsync Restore (Modern - Recommended)

✨ **This is the actively maintained, recommended approach for MyCloud recovery.**

## Overview

Modern rsync-based file recovery tool for MyCloud NAS devices. Uses battle-tested rsync for file operations with intelligent path reconstruction from SQLite database.

## Why Rsync?

- **Automatic timestamp preservation** - No separate mtime sync needed
- **Resume capability** - Interrupted recoveries can continue
- **Proven reliability** - rsync is battle-tested for decades
- **Better performance** - Optimized I/O patterns
- **Simpler operation** - Fewer manual steps

## Quick Start

**macOS users (install system dependencies first):**
```bash
# From repository root
brew bundle

# Then continue with setup below
```

**Setup with Poetry (recommended):**
```bash
# Standard setup (asks permission to modify shell config)
./setup.sh

# Minimal setup (no shell config modification)
./setup.sh --no-shell-config

# Reload your shell to apply UTF-8 settings (if you chose to modify)
source ~/.zshrc  # or ~/.bashrc

# Activate Poetry shell
poetry shell

# Run preflight analysis
python preflight.py /path/to/source /path/to/dest

# Run recovery
python rsync_restore.py --db index.db --source-root /source --dest-root /dest

# Monitor progress (in another terminal)
./monitor.sh
```

**Alternative: Direct commands with Poetry:**
```bash
poetry run python preflight.py /path/to/source /path/to/dest
poetry run python rsync_restore.py --db index.db --source-root /source --dest-root /dest
```

**Note on Emoji Support:**  
The tool uses emoji characters (✅ 📋 🎉) for better visual output. The setup script will ask if you want to configure `PYTHONIOENCODING=utf-8` for emoji support.

**Options:**
- Standard: `./setup.sh` - Asks permission before modifying shell config
- Minimal: `./setup.sh --no-shell-config` - Skips shell modifications, uses plain text fallbacks
- Manual: Export `PYTHONIOENCODING=utf-8` yourself

The tool gracefully falls back to plain text (✅ → [OK], 📋 → [TRANSFER]) if emoji support is unavailable. See [UTF8-EMOJI-SUPPORT.md](./UTF8-EMOJI-SUPPORT.md) for details.

## Features

- Generate HTML coverage report
./run_tests.sh html

# Or use Poetry directly
poetry run pytest tests/(no mtime sync needed)
- Multi-threaded operations
- Progress monitoring
- Cleanup mode (remove orphaned files)

## Tools

- **rsync_restore.py** - Main recovery script (rsync wrapper)
- **preflight.py** - System analysis and thread recommendations
- **monitor.sh** - Real-time progress monitoring

## Testing

```bash
# Run all modern tests
./run_tests.sh

# Run performance tests
pytest tests/test_perf_regen_log.py -v
```

## Comparison to Legacy

| Feature | Legacy (Python) | Modern (Rsync) |
|---------|----------------|----------------|
| Timestamp Preservation | Requires sync_mtime.py | Automatic |
| Resume | Limited | Native support |
| Performance | Good | Better |
| Complexity | Higher | Lower |
| Maintenance | Frozen | Active |

## Development

This is the actively maintained codebase. New features and improvements welcome!

See the [legacy approach](../legacy/) for the Python-based alternative (maintenance mode).
