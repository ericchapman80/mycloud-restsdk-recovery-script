# Emoji Support - Quick Fix

If you see: `'utf-8' codec can't encode characters in position X: surrogates not allowed`

## Instant Fix

```bash
# Add to your shell config
echo 'export PYTHONIOENCODING=utf-8' >> ~/.zshrc
source ~/.zshrc

# Or run inline
export PYTHONIOENCODING=utf-8
```

## Permanent Setup

Run the setup script (already does this for you):
```bash
./setup.sh
source ~/.zshrc
```

## Verify It Works

```bash
# Should print emojis correctly
python3 -c "print('✅ 📋 🎉')"

# Should show utf-8
python3 -c "import sys; print(sys.stdout.encoding)"
```

That's it! ✅
