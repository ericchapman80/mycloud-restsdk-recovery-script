# MyCloud REST SDK Recovery Script

This script helps you recover and transfer files from a Western Digital (WD) MyCloud device or similar storage to another location (like a Synology NAS), with features for performance, safety, and resumability.

## ✨ Recent Improvements (v2.0)

- **O(1) Filename Lookups**: Replaced O(n) loops with dictionary lookups - copying 3.5M files now takes hours instead of days
- **Accurate Resume**: Resume now matches files by **full path**, not just filename - handles duplicate filenames correctly
- **Smart Thread Recommendations**: Preflight now considers disk I/O speed and network filesystems (NFS/CIFS) for optimal thread count
- **Better Error Tracking**: Copy errors are now recorded to `skipped_files` table to prevent infinite retry loops
- **Resource Safety**: All SQLite connections use context managers to prevent "Too many open files" errors

**Problem:**
MyCloud devices don't use a simple, flat filesystem like other external drives, they store files with random-seeming names and directory structures. If your MyCloud is not functioning, you will need to read the SQLite database on the device to determine the original file structure.

### 🚀 Quick Setup (Recommended)
1. Run the setup script:
   ```sh
   bash setup.sh
   ```
2. To activate the environment in the future:
   ```sh
   source venv/bin/activate
   ```
3. Then run all project commands as usual (e.g., python restsdk_public.py ...)

### 1. Requirements
- Python 3.6+
- Alternatively, install dependencies manually:
  ```sh
  pip install -r requirements.txt
  ```

**Solution:**
This script reads the database and a dump of the filesystem and copies the data to another location with the correct filenames and structures. This script is intended for a Linux machine where you already have the file structure and database extracted. This won't work on Windows. I know it's ugly and inefficient, I am new to python. This is tested and working with **Python 3.6 on Linux**.

---

## 🚦 Resumable & Accurate Transfers

This script is designed to be safely interrupted and resumed at any time, ensuring no files are duplicated or missed. It uses a log file (e.g., `copied_file.log`) to track files that have been successfully copied. This log is automatically regenerated from the destination directory at the start of a resume (unless you specify otherwise), ensuring the log always reflects the true state of the destination.

## 🧭 Preflight Checks (optional)
There are two quick utilities to sanity-check hardware, filesystems, and filenames before a long copy:

- `preflight.py` (used by `restsdk_public.py --preflight`): collects CPU/RAM, disk free space and I/O speed (writes/reads a temp file on the destination), file stats (counts/sizes and how many filenames contain `|`), estimates duration, suggests thread count, and warns if your destination filesystem (NTFS/FAT/SMB, etc.) may reject `|` in filenames—suggesting `--sanitize-pipes` when needed.
- `preflight_check.py`: a standalone CLI (not wired into the main script) that prints similar hardware/disk info and a duration estimate. Run it directly if you want a lightweight, separate report.

How to run:
```sh
# Recommended: integrated preflight via the main CLI
python restsdk_public.py --preflight --filedir /path/to/source --dumpdir /path/to/dest

# Standalone preflight_check
python preflight_check.py --source /path/to/source --dest /path/to/dest
```

### Key CLI Options
- `--resume` : Resume a previous run. By default, regenerates the log file from the destination before resuming, ensuring accuracy.
- `--regen-log` : Only regenerate the log file from the destination directory, then exit (no copying performed).
- `--no-regen-log` : (Advanced) Use with `--resume` to skip regenerating the log and use the existing log file as-is.
- `--log_file` : Path to the log file tracking copied files (required for resume/regenerate).
- `--preserve-mtime` / `--no-preserve-mtime` : Enabled by default. Controls whether destination mtime is set from DB timestamps (imageDate/videoDate/cTime/birthTime) so restored photos sort by original capture time.
- `--thread-count` : Number of threads to use (defaults to CPU count).
- `--refresh-mtime-existing` : If the destination file already exists, refresh its mtime from DB timestamps without recopying the data.
- `--sanitize-pipes` : Replace `|` with `-` in destination paths; use for Windows/NTFS/FAT/SMB targets that reject the pipe character.
- `--io-buffer-size` : Optional buffer size in bytes for manual buffered copies (default 0 uses `shutil.copy2`); use only if you need to tune NAS/disk throughput.
- `--io-max-concurrency` : Optional semaphore cap for concurrent disk I/O (default 0 = no cap); useful to limit I/O pressure on spinning disks/NAS.

### When to use the I/O tuning flags
- If your NAS/spinning disk thrashes with many threads, set `--io-max-concurrency` to a small number (e.g., 4–8) to limit concurrent copies.
- If you want to experiment with larger copy chunks, set `--io-buffer-size` (e.g., 4_194_304 for 4MB, 16_777_216 for 16MB). Leave it at 0 to stick with `shutil.copy2` (default and safest).
- Defaults require no tuning; only change these if you have measured slowdowns or want to test throughput improvements.

### When to use `--sanitize-pipes`
- Needed for destinations that disallow `|` in filenames (Windows NTFS/FAT and many SMB shares backed by those filesystems).
- Leave it off for Linux/macOS/EXT4/APFS targets to preserve exact names from the database.

### Usage Examples
```sh
# Resume a transfer (recommended: always up-to-date log)
python restsdk_public.py --resume --dumpdir=/mnt/nfs-media --log_file=copied_file.log ...

# Resume a transfer, but skip log regeneration (advanced)
python restsdk_public.py --resume --no-regen-log --dumpdir=/mnt/nfs-media --log_file=copied_file.log ...

# Only regenerate the log file (no file copying)
python restsdk_public.py --regen-log --dumpdir=/mnt/nfs-media --log_file=copied_file.log

# Preserve original mtimes on destination (default on; disable with --no-preserve-mtime)
python restsdk_public.py --resume --dumpdir=/mnt/nfs-media --log_file=copied_file.log ...
```

### How It Works
- On `--resume`, the script scans the destination directory and rebuilds the log file before resuming, so the log always matches the actual files present.
- **Path-based matching**: Files are matched by their full relative path (e.g., `Photos/2020/vacation/photo.jpg`), not just filename. This correctly handles multiple files with the same name in different directories.
- The script always checks both the log and the destination before copying any file.
- Files are only added to the log after a successful copy (atomic update).
- **Error tracking**: Files that fail to copy are recorded in the `skipped_files` table with a reason, preventing infinite retry loops on permanent errors.
- You can safely interrupt and rerun the script as many times as needed.

---

## 🧭 Preflight Check (optional)
Use the integrated preflight to sanity-check hardware, filesystems, and filenames before a long copy. It collects CPU/RAM, disk free space and I/O speed (writes/reads a temp file on the destination), file stats (counts/sizes and how many filenames contain `|`), estimates duration, suggests thread count, and warns if your destination filesystem (NTFS/FAT/SMB, etc.) may reject `|` in filenames—suggesting `--sanitize-pipes` when needed.

How to run:
```sh
python restsdk_public.py --preflight --filedir /path/to/source --dumpdir /path/to/dest
# Optional: include --db /path/to/index.db to auto-verify/create copy-tracking tables (copied_files/skipped_files)
```
Notes:
- Preflight reports your current open-file limit and suggests a thread count that stays under that limit (2 FDs per copy, with headroom). If you see a low FD limit, consider running `ulimit -n 65535` before starting, or use a lower `--thread-count`.
- To raise the open-file limit for your session: `ulimit -n 65535` (run this in the shell before starting the script).

Sample preflight output:
```
✅ Verified copy tracking tables in /mnt/backupdrive/restsdk/data/db/index.db
🚀  ===== Pre-flight Hardware & File System Check ===== 🚀

🖥️  CPU: x86_64 | Cores: 6 | Freq: 803.7 MHz
💾 RAM: 11 GB total | 9 GB available
📂 Source: /mnt/backupdrive/restsdk/data/files
  - Size: 1804.21 GB | Files: 3583981
  - Filenames containing '|': 0
  - Small: 3258153 | Medium: 324156 | Large: 1672
💽 Dest: /mnt/nfs-media
  - Free: 4841 GB | Total: 7143 GB | FS: nfs
⚡ Disk Speed (dest): Write: 105.9 MB/s | Read: 1804.5 MB/s
⏱️  Estimated Duration: 290.8 minutes (best case)
🔢 Recommended Threads: 6 (limited by: network filesystem)
   ├─ CPU-based: 12 (many small files (2x CPU cores, max 32))
   ├─ I/O-based: 6 (106 MB/s write speed)
   └─ FS-based:  6 (nfs (network filesystem, capped at CPU count))

✨ Recommended Command:
📝 python restsdk_public.py --db /mnt/backupdrive/restsdk/data/db/index.db --filedir /mnt/backupdrive/restsdk/data/files --dumpdir /mnt/nfs-media --log_file copied_file.log --thread-count 6
```

### Thread Recommendation Logic

The preflight analyzes your system and recommends threads based on the **most limiting factor**:

- **CPU-based**: 2x CPU cores for many small files, 1x for large files
- **I/O-based**: ~1 thread per 20 MB/s of write throughput (more threads don't help if disk is the bottleneck)
- **Filesystem-based**: Capped at CPU count for network filesystems (NFS/CIFS/SMB) to avoid contention

---

## 🗄️ SQL Migration & Integration Points

To enable hybrid log + database resumable logic, add the following tables to your SQLite database (the script will create them if missing):

```sql
CREATE TABLE IF NOT EXISTS copied_files (
    file_id TEXT PRIMARY KEY,
    filename TEXT,
    copied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    mtime_refreshed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skipped_files (
    filename TEXT PRIMARY KEY,
    reason TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Example: Query for Files to Copy

```sql
SELECT f.*
FROM Files f
LEFT JOIN copied_files c ON f.id = c.file_id
LEFT JOIN skipped_files s ON f.contentID = s.filename
WHERE c.file_id IS NULL AND s.filename IS NULL;
```
- This query returns only files that have not been copied and are not permanently skipped.

### Integration Points in Script
- On `--resume` or `--create-log`, scan the destination and update both `copied_file.log` and the `copied_files` table.
- After each successful copy, insert into `copied_files` and append to the log; `mtime_refreshed` is set when mtimes are refreshed on existing files.
- For skipped/problem files, insert into `skipped_files`.
- Always filter files to process using the SQL join above, not by loading all copied/skipped files into memory.

---

**More:**
Need more help than this script can offer? We offer affordable flat-rate data recovery at [our website](https://springfielddatarecovery.com)

## If this script has helped you recover your data, please consider saying thanks with a crypto/Bitcoin donation

* Bitcoin: 1DqSLNR8kTgwq5rvveUFDSbYQnJp9D5gfR
* ETH: 0x9e765052283Ce6521E40069Ac52ffA5B277bD8AB
* Zcash: t1RetUQktuUBL2kbX72taERb6QcuAiDsvC4

Don't have any crypto? Buy some at [Coinbase](https://www.coinbase.com/join/calltheninja)

**FUTURE DEVELOPMENT:**
This fork is actively maintained. Contributions welcome!

**Notes:**
SQLite database is stored in /restsdk/data/db/index.db. Inside the DB two main tables appear to be of interest, FILES and ImageTrans. FILES lists each file with a unique ID (primary key) and a ContentID (the name of the file when stored on the filesystem) along with the file name "My important picture.jpg" and some other metadata. I believe ImageTrans is only for thumbnailing purposes but I could be wrong about that. Importantly, the entries in FILES have a "parent" attribute which places each file in a directory structure. This script totally ignores ImageTrans.

**FAQ:**

**Why do I see "File not found in database" errors?**
* Files may be missing from the database due to corruption or interrupted operations on the MyCloud device
* The script searches for matches between on-disk filenames (`contentID` column) and database entries. If no match exists, the file is skipped and reported.
* Some files in the filesystem dump may be temporary or system files without database entries
* These unmatched files are reported but not counted in the percentage complete calculation

**How is the database structured? What columns matter?**
* The main table is typically called `Files`.
- Key columns:
  - `id`: The primary key for each file record.
  - `contentID`: The unique identifier for the file as stored on disk (e.g., `a22236cwsmelmd4on2qs2jdf`).
  - `name`: The original human-readable file name (e.g., `IMG_7524.HEIC`).
  - `parentID`: Reference to parent directory for path reconstruction.
- Source files are stored in sharded directories by first character: `/files/a/a22236...`, `/files/b/b12345...`
- The script reconstructs original paths using the `parentID` chain and copies files with their original `name`.

**How can I safely inspect or query the database?**
> ⚠️ **Warning:** Always make a backup of your database before running queries that modify data. Read-only queries are generally safe, but proceed with caution.

To inspect the schema or sample data, use the following commands:

```sh
# Start the SQLite shell
sqlite3 index.db
```

```sql
-- Show table names
.tables

-- Show the schema for the Files table
.schema Files

-- See a sample of file records
SELECT id, name, contentID FROM Files LIMIT 10;

-- Count all files
SELECT COUNT(*) FROM Files;
```

**If you see errors about missing columns:**
- Double-check the actual schema using `.schema Files`.
- The script expects `contentID` to match on-disk filenames.
- If your database uses different column names, adjust the script and queries accordingly.

**Best Practices:**
- Always work on a copy of your database when experimenting or debugging.
- Never run destructive queries unless you are certain of their effect.
- If in doubt, ask for help or clarification before proceeding.
