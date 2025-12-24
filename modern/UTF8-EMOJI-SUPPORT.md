# UTF-8 and Emoji Support

## Overview

The rsync restore tool uses emoji characters for better visual output. This requires proper UTF-8 encoding support.

## Already Configured

The tool automatically handles UTF-8 encoding by wrapping `stdout` and `stderr` at startup:

```python
# In rsync_restore.py - lines 45-49
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

## Running Under sudo

When running with `sudo`, the environment changes and UTF-8 might not be preserved. The code above handles this automatically.

### Optional: Set Environment Variable

If you encounter encoding issues (rare), you can explicitly set the encoding:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PYTHONIOENCODING=utf-8

# Or use inline when running under sudo
sudo PYTHONIOENCODING=utf-8 poetry run python rsync_restore.py ...
```

## Troubleshooting

**Symptom:** `'utf-8' codec can't encode characters in position X: surrogates not allowed`

**Cause:** The Python source file contains corrupted UTF-16 surrogates instead of proper UTF-8 emoji characters.

**Fix:** Re-save the file with proper UTF-8 encoding:
```bash
# Verify file encoding
file -I rsync_restore.py
# Should show: charset=utf-8

# If corrupted, the emoji removal script will fix it
python3 remove_emoji.py
```

## Testing Emoji Support

```bash
# Quick test
sudo poetry run python -c "import sys; print(f'Encoding: {sys.stdout.encoding}'); print('✅ 📋 🎉')"
```

Should output:
```
Encoding: utf-8
✅ 📋 🎉
```
