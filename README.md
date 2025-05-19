# MyCloud REST SDK Recovery Script

This script helps you recover and transfer files from a Western Digital (WD) MyCloud device or similar storage to another location (like a Synology NAS), with features for performance, safety, and resumability.

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

### Key CLI Options
- `--resume` : Resume a previous run. By default, regenerates the log file from the destination before resuming, ensuring accuracy.
- `--regen-log` : Only regenerate the log file from the destination directory, then exit (no copying performed).
- `--no-regen-log` : (Advanced) Use with `--resume` to skip regenerating the log and use the existing log file as-is.
- `--log_file` : Path to the log file tracking copied files (required for resume/regenerate).

### Usage Examples
```sh
# Resume a transfer (recommended: always up-to-date log)
python restsdk_public.py --resume --dumpdir=/mnt/nfs-media --log_file=copied_file.log ...

# Resume a transfer, but skip log regeneration (advanced)
python restsdk_public.py --resume --no-regen-log --dumpdir=/mnt/nfs-media --log_file=copied_file.log ...

# Only regenerate the log file (no file copying)
python restsdk_public.py --regen-log --dumpdir=/mnt/nfs-media --log_file=copied_file.log
```

### How It Works
- On `--resume`, the script scans the destination directory and rebuilds the log file before resuming, so the log always matches the actual files present.
- The script always checks both the log and the destination before copying any file.
- Files are only added to the log after a successful copy (atomic update).
- You can safely interrupt and rerun the script as many times as needed.

---

**More:**
Need more help than this script can offer? We offer affordable flat-rate data recovery at [our website](https://springfielddatarecovery.com)

## If this script has helped you recover your data, please consider saying thanks with a crypto/Bitcoin donation

* Bitcoin: 1DqSLNR8kTgwq5rvveUFDSbYQnJp9D5gfR
* ETH: 0x9e765052283Ce6521E40069Ac52ffA5B277bD8AB
* Zcash: t1RetUQktuUBL2kbX72taERb6QcuAiDsvC4

Don't have any crypto? Buy some at [Coinbase](https://www.coinbase.com/join/calltheninja)

**FUTURE DEVELOPMENT:**
This code will not be receiving any updates, feel free to fork it if you want to make improvements.

**Notes:**
SQLite database is stored in /restsdk/data/db/index.db. Inside the DB two main tables appear to be of interest, FILES and ImageTrans. FILES lists each file with a unique ID (primary key) and a ContentID (the name of the file when stored on the filesystem) along with the file name "My important picture.jpg" and some other metadata. I believe ImageTrans is only for thumbnailing purposes but I could be wrong about that. Importantly, the entries in FILES have a "parent" attribute which places each file in a directory structure. This script totally ignores ImageTrans.

**FAQ:**

**Why do I see "File not found in database" errors?**
* Files may be missing from the database due to corruption or interrupted operations on the MyCloud device
* The script searches for matches between filenames and ContentIDs, returning None when no match exists
* Some files in the filesystem dump may be temporary or system files without database entries
* These unmatched files are reported but not counted in the percentage complete calculation

