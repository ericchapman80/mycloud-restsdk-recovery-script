#!/bin/bash
# Extract modern repository structure for wd-mycloud-rsync-recovery

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/../wd-mycloud-rsync-recovery"

echo "🔧 Creating wd-mycloud-rsync-recovery repository structure..."
echo "Target: $TARGET_DIR"

# Create target directory
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

# Initialize git repo
git init
git branch -m main
echo "✅ Initialized git repository"

# Copy core files from modern/
echo "📦 Copying files from modern/..."
cp "$SCRIPT_DIR/modern/rsync_restore.py" .
cp "$SCRIPT_DIR/modern/preflight.py" .
cp "$SCRIPT_DIR/modern/monitor.sh" .
cp "$SCRIPT_DIR/modern/setup.sh" .
cp "$SCRIPT_DIR/modern/run_tests.sh" .
cp "$SCRIPT_DIR/modern/requirements.txt" .
cp "$SCRIPT_DIR/modern/pytest.ini" .

# Copy tests directory
echo "📦 Copying tests/..."
cp -r "$SCRIPT_DIR/modern/tests" .

# Copy shared files
echo "📦 Copying shared files..."
cp "$SCRIPT_DIR/shared/sql-data.info" .

# Copy LICENSE from root
echo "📦 Copying LICENSE..."
cp "$SCRIPT_DIR/LICENSE" .

# Create .gitignore
echo "📝 Creating .gitignore..."
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Poetry
poetry.lock

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Log files
*.log

# Database files
*.db
*.db-journal

# Symlink farms
symlink_farm/

# Cleanup config
cleanup_config.yaml
EOF

# Create README.md
echo "📝 Creating README.md..."
cat > README.md << 'EOF'
# WD MyCloud Rsync Recovery

Modern rsync-based recovery toolkit for Western Digital MyCloud NAS devices. Uses battle-tested rsync with intelligent path reconstruction from SQLite database.

> **🚀 Recommended approach** for MyCloud recovery. Simpler, faster, and more reliable than SDK-based methods.

---

## Why Rsync?

- **Automatic timestamp preservation** - No separate mtime sync needed
- **Native resume capability** - Interrupted recoveries continue seamlessly  
- **Battle-tested reliability** - Decades of proven rsync stability
- **Better performance** - Optimized I/O patterns
- **Lower memory usage** - ~50 MB vs 2-10 GB (SDK approach)
- **Simpler operation** - Fewer manual steps

## Alternative: SDK Toolkit

For users who need Python API access or prefer REST SDK approach, see **[wd-mycloud-python-recovery](https://github.com/ericchapman80/wd-mycloud-python-recovery)**.

---

## Quick Start

**macOS users (install system dependencies first):**
```bash
# From repository root
brew install rsync python@3.12
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

## Features

### Core Recovery
- **Multi-threaded rsync operations** for optimal performance
- **Progress monitoring** with real-time statistics
- **Automatic timestamp preservation** (no manual sync needed)
- **Resume capability** for interrupted transfers
- **Path reconstruction** from SQLite database

### Cleanup Mode
- **Orphan detection** - Find files in destination not in database
- **Pattern-based protection** - Exclude specific paths from cleanup
- **Dry-run mode** - Preview changes before deleting
- **Interactive wizard** - Guided cleanup with prompts
- **Config persistence** - Save cleanup settings

### Monitoring & Analysis
- **Preflight checks** - System analysis and recommendations
- **Thread optimization** - Automatic thread count tuning
- **Disk space warnings** - Proactive space management
- **Transfer statistics** - Detailed progress reporting

## Tools

- **rsync_restore.py** - Main recovery script (rsync wrapper with intelligent path handling)
- **preflight.py** - System analysis and thread recommendations
- **monitor.sh** - Real-time progress monitoring

## Testing

**Test Coverage:** 70-76% (467+ tests, 5,722 lines of test code)

```bash
# Run all tests
./run_tests.sh

# Run with coverage report
./run_tests.sh html

# Run specific test suites
poetry run pytest tests/test_symlink_farm.py -v          # Symlink farm tests
poetry run pytest tests/test_preflight_integration.py -v  # Integration tests
poetry run pytest tests/test_cleanup_integration.py -v    # Cleanup workflows
```

**Test Suite:**
- **Unit Tests (202 tests):** Symlink farm, preflight, cleanup, user interaction
- **Integration Tests (127 tests):** End-to-end workflows, component interaction
- **Additional Tests (60+ tests):** Progress monitoring, database operations, error handling

## Comparison: Rsync vs SDK Toolkit

| Feature | Rsync Toolkit (This) | SDK Toolkit |
|---------|---------------------|-------------|
| Timestamp Preservation | Automatic | Requires sync_mtime.py |
| Resume | Native rsync support | Limited |
| Memory Usage | ~50 MB | 2-10 GB |
| Performance | Optimized I/O | Good |
| Complexity | Lower | Higher |
| Development | Active | Open source |
| Test Coverage | 70-76% | 63% |
| API Access | No | Yes (REST SDK) |

## When to Use Which Toolkit

**Use this rsync toolkit when:**
- Starting a new recovery project (recommended)
- Want simplest operation with automatic features
- Need reliable resume capability
- Prefer battle-tested tools (rsync)
- Want active development and new features

**Use SDK toolkit when:**
- Need Python API access to MyCloud device
- Working where rsync is unavailable
- Require programmatic control over recovery
- Need symlink deduplication feature
- Prefer REST API approach

## Documentation

- **Database Schema:** [sql-data.info](sql-data.info)
- **Legacy Python Tool:** [wd-mycloud-python-recovery](https://github.com/ericchapman80/wd-mycloud-python-recovery)
- **Symlink Farm Guide:** See repository docs

## Development Status

✅ **Active Development**
- Comprehensive test suite with 70-76% coverage
- All critical workflows tested and validated
- Integration tests ensure components work together
- Regular updates and new features

## Support & Contributing

- **Issues:** Report bugs or request features via GitHub issues
- **Pull Requests:** Contributions welcome!
- **Discussions:** Use GitHub Discussions for questions
- **SDK Alternative:** [wd-mycloud-python-recovery](https://github.com/ericchapman80/wd-mycloud-python-recovery)

## License

See [LICENSE](LICENSE) file.

## Credits

Original mycloud-restsdk concept by [springfielddatarecovery](https://github.com/springfielddatarecovery/mycloud-restsdk-recovery-script)

Rsync approach, testing, and toolkit development by [@ericchapman80](https://github.com/ericchapman80)

Legacy Python tool: [wd-mycloud-python-recovery](https://github.com/ericchapman80/wd-mycloud-python-recovery)
EOF

echo ""
echo "✅ Repository structure created successfully!"
echo ""
echo "📊 Summary:"
echo "  - Core script: rsync_restore.py"
echo "  - Utilities: preflight.py, monitor.sh"
echo "  - Setup: setup.sh, run_tests.sh"
echo "  - Tests: $(find tests -name '*.py' 2>/dev/null | wc -l | xargs) test files"
echo "  - Documentation: README.md, sql-data.info, LICENSE"
echo "  - Git: Initialized on main branch (not committed yet)"
echo ""
echo "📍 Location: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the extracted files"
echo "  2. cd $TARGET_DIR"
echo "  3. git add ."
echo "  4. git commit -m 'Initial commit: Rsync recovery toolkit (v2.0.0)'"
echo "  5. Create GitHub repo and push"
echo ""
