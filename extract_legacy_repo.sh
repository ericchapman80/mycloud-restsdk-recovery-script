#!/bin/bash
# Extract legacy repository structure for wd-mycloud-python-recovery

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/../wd-mycloud-python-recovery"

echo "🔧 Creating wd-mycloud-python-recovery repository structure..."
echo "Target: $TARGET_DIR"

# Create target directory
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

# Initialize git repo
git init
echo "✅ Initialized git repository"

# Copy core files from legacy/
echo "📦 Copying files from legacy/..."
cp "$SCRIPT_DIR/legacy/restsdk_public.py" .
cp "$SCRIPT_DIR/legacy/sync_mtime.py" .
cp "$SCRIPT_DIR/legacy/create_symlink_farm.py" .
cp "$SCRIPT_DIR/legacy/mtime_check.py" .
cp "$SCRIPT_DIR/legacy/preflight.py" .
cp "$SCRIPT_DIR/legacy/setup.sh" .
cp "$SCRIPT_DIR/legacy/run_tests.sh" .
cp "$SCRIPT_DIR/legacy/requirements.txt" .
cp "$SCRIPT_DIR/legacy/pytest.ini" .

# Copy tests directory
echo "📦 Copying tests/..."
cp -r "$SCRIPT_DIR/legacy/tests" .

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

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

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
EOF

# Create README.md with maintenance notice
echo "📝 Creating README.md..."
cat > README.md << 'EOF'
# WD MyCloud Python Recovery (Legacy - Maintenance Mode)

⚠️ **This tool is in maintenance mode. For new projects, use [wd-mycloud-rsync-recovery](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)**

Recover and transfer files from a Western Digital (WD) MyCloud device using Python-based REST SDK approach.

> **📢 This is the legacy Python-based recovery tool.** It remains available for existing users but is no longer actively developed. Critical bug fixes only.

---

## 🚨 Migration Notice

**Recommended:** Switch to the modern rsync-based tool for:
- ✅ Automatic timestamp preservation (no sync_mtime.py needed)
- ✅ Better resume capability
- ✅ Lower memory usage (~50 MB vs 2-10 GB)
- ✅ Real-time progress tracking
- ✅ Active development and new features

👉 **[Get the modern tool →](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)**

---

## Quick Start (Legacy Tool)

**macOS users (install dependencies first):**
```bash
brew install python@3.12
```

**Setup:**
```bash
# Standard setup
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Run preflight analysis
python preflight.py /path/to/source /path/to/dest

# Run recovery
python restsdk_public.py --db index.db --filedir /source --dumpdir /dest

# For --low-memory mode, sync timestamps afterward
python sync_mtime.py --db index.db --filedir /source --dumpdir /dest
```

## Features

- Multi-threaded file recovery via WD MyCloud REST SDK
- Memory-optimized mode (`--low-memory`)
- Resume capability
- Symlink-based deduplication
- Metadata validation tools

## Tools

- **restsdk_public.py** - Main recovery script (Python/REST SDK)
- **sync_mtime.py** - Post-recovery timestamp sync (required for --low-memory)
- **preflight.py** - System analysis and thread recommendations
- **create_symlink_farm.py** - Symlink-based deduplication
- **mtime_check.py** - Metadata validation utility

## Testing

```bash
# Run all legacy tests
./run_tests.sh

# Run with coverage
./run_tests.sh html
```

**Test Coverage:** 63% (stable baseline)

## Why Maintenance Mode?

The modern rsync-based approach (`wd-mycloud-rsync-recovery`) offers:
- Simpler operation (fewer manual steps)
- No separate timestamp sync needed
- Better performance and reliability
- Lower resource usage
- Active feature development

This Python tool remains available for:
- Existing users with established workflows
- Environments where rsync is not available
- Specific use cases requiring Python API access

## Support

- **Active Development:** [wd-mycloud-rsync-recovery](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)
- **Critical Bugs:** Open issues in this repository
- **Questions:** See modern tool documentation

## Documentation

- **Database Schema:** [sql-data.info](sql-data.info)
- **Modern Tool:** [wd-mycloud-rsync-recovery](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)

## License

See [LICENSE](LICENSE) file.

## Credits

Original script by [springfielddatarecovery](https://github.com/springfielddatarecovery/mycloud-restsdk-recovery-script)

Legacy Python approach maintained by [@ericchapman80](https://github.com/ericchapman80)

Modern rsync approach: [wd-mycloud-rsync-recovery](https://github.com/ericchapman80/wd-mycloud-rsync-recovery)
EOF

echo ""
echo "✅ Repository structure created successfully!"
echo ""
echo "📊 Summary:"
echo "  - Core scripts: restsdk_public.py, sync_mtime.py, create_symlink_farm.py, mtime_check.py"
echo "  - Shared utilities: preflight.py, setup.sh, run_tests.sh"
echo "  - Tests: $(find tests -name '*.py' | wc -l | xargs) test files"
echo "  - Documentation: README.md, sql-data.info, LICENSE"
echo "  - Git: Initialized (not committed yet)"
echo ""
echo "📍 Location: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the extracted files"
echo "  2. cd $TARGET_DIR"
echo "  3. git add ."
echo "  4. git commit -m 'Initial commit: Legacy Python recovery tool (v2.0.0)'"
echo "  5. Create GitHub repo and push"
echo ""
