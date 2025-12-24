# Shared Testing Infrastructure

This directory contains testing utilities shared between legacy and modern subdirectories.

## 📋 Contents

- **create_test_dataset.py** - Create representative test datasets from production data
- **validate_results.py** - Compare legacy vs modern recovery outputs
- **sql-data.info** - Database schema documentation
- **test-fixtures/** - (git-ignored) Test datasets created by create_test_dataset.py

## 🧪 Testing Workflow

### 1. Create Test Dataset

Extract a small, representative sample from your production data:

```bash
python shared/create_test_dataset.py \
    --prod-db ~/MyCloudEX2Ultra/index.db \
    --prod-files ~/MyCloudEX2Ultra/files \
    --test-db shared/test-fixtures/test.db \
    --test-files shared/test-fixtures/files \
    --strategy diverse \
    --max-per-category 5
```

**Sampling Strategies:**
- `diverse` (default) - Balanced mix of file types, sizes, edge cases
- `edge_cases` - Focus on problematic filenames (pipes, unicode, spaces)
- `quick` - Random sample for fast testing

### 2. Run Recovery (Both Tools)

**Legacy:**
```bash
cd legacy
python restsdk_public.py \
    --db ../shared/test-fixtures/test.db \
    --filedir ../shared/test-fixtures/files \
    --dumpdir /tmp/legacy-test
cd ..
```

**Modern:**
```bash
cd modern
poetry run python rsync_restore.py \
    --db ../shared/test-fixtures/test.db \
    --source ../shared/test-fixtures/files \
    --dest /tmp/modern-test \
    --farm /tmp/farm
cd ..
```

### 3. Validate Results

Compare the outputs to ensure both tools produce identical results:

```bash
# Full validation with content hashes (thorough but slow)
python shared/validate_results.py /tmp/legacy-test /tmp/modern-test

# Quick validation - skip content hashes (fast)
python shared/validate_results.py /tmp/legacy-test /tmp/modern-test --no-hashes

# Verbose output with directory structure analysis
python shared/validate_results.py /tmp/legacy-test /tmp/modern-test -v
```

**Exit Codes:**
- `0` - Validation passed (outputs identical)
- `1` - Validation failed (differences found)

## ⚡ Quick Development Testing

For rapid iteration during development, use the `--limit` flag:

```bash
# Legacy - test with just 10 files
cd legacy && python restsdk_public.py \
    --db /path/to/index.db \
    --filedir /path/to/files \
    --dumpdir /tmp/test \
    --limit 10

# Modern - test with just 10 files
cd modern && poetry run python rsync_restore.py \
    --db /path/to/index.db \
    --source /path/to/files \
    --dest /tmp/test \
    --farm /tmp/farm \
    --limit 10
```

This processes only the first N files, allowing you to:
- Test changes quickly without waiting for full recovery
- Validate fixes on production data safely
- Iterate rapidly during development

## 📊 Validation Checks

The `validate_results.py` script performs comprehensive comparison:

1. **File Counts** - Ensures both tools recovered the same number of files
2. **Directory Structure** - Verifies folder hierarchy matches
3. **File Sizes** - Checks every file has identical size
4. **Timestamps** - Validates mtime preservation
5. **Content Integrity** - SHA256 checksums (when `--no-hashes` not used)
6. **Symlink Consistency** - Ensures symlinks handled correctly

## 🎯 Use Cases

### Phase 0 Validation
Before splitting the repository:
1. Create test dataset from production data
2. Run both legacy and modern tools
3. Validate outputs are identical
4. Sign off on Phase 0 completion

### Remote→Local Testing Workflow
When production data is on a remote server but you want to test locally:

**On Remote Server (has production data):**
```bash
# Create test dataset
python shared/create_test_dataset.py \
    --prod-db /path/to/index.db \
    --prod-files /mnt/nfs/files \
    --test-db /tmp/phase0-test.db \
    --test-files /tmp/phase0-files \
    --strategy diverse \
    --max-per-category 5

# Compress for transfer
cd /tmp
tar czf phase0-dataset.tar.gz phase0-test.db phase0-files/
```

**On Local Machine:**
```bash
# Transfer dataset
scp user@remote:/tmp/phase0-dataset.tar.gz ~/Downloads/

# Extract to test-fixtures
cd shared/test-fixtures/
tar xzf ~/Downloads/phase0-dataset.tar.gz
mv phase0-test.db test.db
mv phase0-files files

# Run legacy recovery
cd ../../legacy
python restsdk_public.py \
    --db ../shared/test-fixtures/test.db \
    --filedir ../shared/test-fixtures/files \
    --dumpdir /tmp/legacy-test

# Run modern recovery
cd ../modern
poetry run python rsync_restore.py \
    --db ../shared/test-fixtures/test.db \
    --source ../shared/test-fixtures/files \
    --dest /tmp/modern-test \
    --farm /tmp/farm

# Validate results
cd ..
python shared/validate_results.py /tmp/legacy-test /tmp/modern-test
```

**Alternative - Git LFS (for permanent test datasets):**
If you want versioned test datasets that multiple team members can access:
```bash
# One-time setup
git lfs install
git lfs track "shared/test-datasets/*.db"
git lfs track "shared/test-datasets/files/**"

# Create in test-datasets/ (not test-fixtures/)
python shared/create_test_dataset.py \
    --test-db shared/test-datasets/validation-v1.db \
    --test-files shared/test-datasets/files \
    ...

git add .gitattributes shared/test-datasets/
git commit -m "Add versioned test dataset"
git push
```

Note: `test-fixtures/` is gitignored (temporary), `test-datasets/` can be committed with Git LFS

### CI/CD Regression Testing
Automated testing in GitHub Actions:
```bash
# Use committed test fixtures
python shared/validate_results.py ./legacy-output ./modern-output
```

### Development Iteration
Quick testing during feature development:
```bash
# Use --limit flag for fast feedback
python rsync_restore.py --db test.db --source files --dest /tmp/test --farm /tmp/farm --limit 5
```

## 📝 Examples

**Create edge case test set:**
```bash
python shared/create_test_dataset.py \
    --prod-db index.db \
    --prod-files /files \
    --test-db edge-test.db \
    --test-files edge-files \
    --strategy edge_cases
```

**Quick validation (no content hashes):**
```bash
python shared/validate_results.py /tmp/leg /tmp/mod --no-hashes
```

**Verbose validation with structure analysis:**
```bash
python shared/validate_results.py /tmp/leg /tmp/mod -v
```

## 🚀 Next Steps

After validation passes:
1. Tag monorepo as `v2.0.0-monorepo-final`
2. Proceed to Phase 1 - Repository split
3. Use test datasets for regression testing in new repos
