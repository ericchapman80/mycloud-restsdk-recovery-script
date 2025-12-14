import argparse
import copy
import logging
import multiprocessing
import os
import shutil
import pprint
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Lock, Value
from shutil import copyfile
import datetime
from queue import Queue
from threading import Thread

# Preflight import
try:
    from preflight import preflight_summary, print_preflight_report
except ImportError as e:
    print("❌ ERROR: Could not import preflight module. Make sure preflight.py is in the same directory.")
    print(f"Details: {e}")
    sys.exit(1)

##Intended for python3.6 on linux, probably won't work on Windows
##This software is distributed without any warranty. It will probably brick your computer.
#--db=/mnt/backupdrive/restsdk/data/db/index.db --filedir=/mnt/backupdrive/restsdk/data/files --dumpdir=/mnt/nfs-media --dry_run --log_file=/home/chapman/projects/mycloud-restsdk-recovery-script/copied_file.log
#sudo python3 restsdk_public.py --db=/mnt/backupdrive/restsdk/data/db/index.db --filedir=/mnt/backupdrive/restsdk/data/files --dumpdir=/mnt/nfs-media --dry_run --log_file=/home/chapman/projects/mycloud-restsdk-recovery-script/copied_file.log --thread-count=12

# Generate a timestamp for the log file
current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# log_filename is used to store run information, such as progress and errors, in a timestamped log file.
log_filename = f'summary_{current_time}.log'

# log_file is used to track the files that have been successfully copied to avoid duplication in future runs.
# log_file = args.log_file

# Set up a logging queue for asynchronous logging
log_queue = Queue()

# Define a custom logging handler to use the queue
class QueueHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        self.queue.put(self.format(record))

# Define a worker thread to process log messages asynchronously
def log_worker():
    with open(log_filename, 'a') as log_file:
        while True:
            message = log_queue.get()
            if message == "STOP":
                break
            log_file.write(message + '\n')
            log_file.flush()

# Start the logging worker thread
log_thread = Thread(target=log_worker, daemon=True)
log_thread.start()

# Set up the logging configuration
queue_handler = QueueHandler(log_queue)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
queue_handler.setFormatter(formatter)
logging.getLogger().addHandler(queue_handler)
logging.getLogger().setLevel(logging.INFO)  # Default level is INFO
def print_help():
    print("Usage: python restsdk_public.py [options]")
    print("Options:")
    print("  --preflight           Run hardware and file system pre-flight check (requires --filedir and --dumpdir)")
    print("  --dry_run             Perform a dry run (do not copy files)")
    print("  --db                  Path to the file DB (example: /restsdk/data/db/index.db)")
    print("  --filedir             Path to the files directory (example: /restsdk/data/files)")
    print("  --dumpdir             Path to the directory to dump files (example: /location/to/dump/files/to)")
    print("  --log_file            Path to the log file (example: /location/to/log/file.log)")
    print("  --create_log          Create a log file from an existing run where logging was not in place")
    print("  --regen-log           Regenerate the log file from the destination directory only, then exit")
    print("  --resume              Resume a previous run, regenerating the log before copying (default)")
    print("  --no-regen-log        Use with --resume to skip regenerating the log (advanced)")
    print("  --thread-count        Number of threads to use")
    print("  --log_level {DEBUG,INFO,WARNING}  Logging level (default INFO)")
    print("  --preserve-mtime      After copy, set destination mtime from DB timestamps (imageDate/videoDate/cTime/birthTime)")

# --- SQL DDL/DML and Hybrid Copy Logic ---
import sqlite3

def init_copy_tracking_tables(db_path):
    """
    Ensure the copied_files and skipped_files tables exist in the database.
    Uses TEXT for file_id and filename to match Files table schema.
    Adds mtime_refreshed flag to track whether we applied DB timestamps to the dest file.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS copied_files (
        file_id TEXT PRIMARY KEY,
        filename TEXT,
        copied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        mtime_refreshed INTEGER DEFAULT 0
    )''')
    # Safe ALTER in case table already exists without the new column
    try:
        c.execute("ALTER TABLE copied_files ADD COLUMN mtime_refreshed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS skipped_files (
        filename TEXT PRIMARY KEY,
        reason TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def insert_copied_file(db_path, file_id, filename):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO copied_files (file_id, filename, mtime_refreshed) VALUES (?, ?, 0)''', (str(file_id), str(filename)))
    conn.commit()
    conn.close()

def insert_skipped_file(db_path, filename, reason):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Always use TEXT for filename and reason
    c.execute('''INSERT OR IGNORE INTO skipped_files (filename, reason) VALUES (?, ?)''', (str(filename), str(reason)))
    conn.commit()
    conn.close()

def regenerate_copied_files_from_dest(db_path, dumpdir, log_file):
    """
    Scan the destination directory, update copied_files table and regenerate log file.
    Uses contentID for matching, as this is the on-disk filename.
    Provides progress output for user feedback during long scans.
    """
    tmp_log = log_file + ".tmp"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    total_files = 0
    print("Scanning destination directory and regenerating log file (this may take a while for large datasets)...")
    with open(tmp_log, 'w') as f:
        for root, dirs, files in os.walk(dumpdir):
            for file in files:
                file_path = os.path.join(root, file)
                f.write(file_path + '\n')
                print(f"Checking destination file: {file}")
                c.execute('SELECT id FROM Files WHERE name = ?', (file,))
                row = c.fetchone()
                file_id = row[0] if row else None
                if file_id:
                    print(f"  [MATCH] DB id: {file_id} for file: {file} -- inserting into copied_files table.")
                    c.execute('INSERT OR IGNORE INTO copied_files (file_id, filename) VALUES (?, ?)', (file_id, file))
                    if c.rowcount == 1:
                        print(f"    [INSERTED] Inserted into copied_files: ({file_id}, {file})")
                    else:
                        print(f"    [SKIPPED] Entry already exists for: ({file_id}, {file})")
                else:
                    print(f"  [NO MATCH] No DB entry found for destination file: {file}")
                total_files += 1
                #TODO: add this batch size as a pareameter to the cli
                if total_files % 10000 == 0:
                    print(f"  Processed {total_files} files so far...")
                    conn.commit()
                    print(f"  [COMMIT] Database commit after {total_files} files.")
    print(f"Finished scanning. Total files processed: {total_files}")
    conn.commit()
    conn.close()
    os.replace(tmp_log, log_file)

def findNextParent(fileID):
    """
    Finds the next parent directory from the data dicstionary
    Args: fileID (str): The ID of the file to find the next parent for.
    Returns: str: The ID of the next parent db item in the chain.
    """
    for key, value in fileDIC.items():
        if key == fileID:
            return value['Parent']
        
def hasAnotherParent(fileID):
    """
    Checks if the data dictionary item has another parent.
    Args: fileID (str): The ID of the file to check.
    Returns: bool: True if the file has another parent, False otherwise.
    """
    if fileDIC[fileID]['Parent'] != None:
        return True
    else:
        return False
    
def findTree(fileID, name, parent):
    """
    Finds the original file path for a given file ID, name, and parent.
    Parameters:
        fileID (int): The ID of the file.
        name (str): The name of the file.
        parent (str): The parent directory of the file.
    Returns: str: The original file path.
    """
    path = fileDIC[parent]['Name'] + "/" + name
    current_parent = parent
    while current_parent is not None and hasAnotherParent(current_parent):
        current_parent = findNextParent(current_parent)
        path = fileDIC[current_parent]['Name'] + '/' + path
    return path

def idToPath2(fileID):
    """
    Converts a file ID into its original path by traversing the fileDIC dictionary and reconstructing the path.
    Args: fileID (int): The ID of the file.
    Returns: str: The original path of the file.
    """
    value = fileDIC[fileID]
    if value['Parent'] != None:
        path = findTree(fileID, value['Name'], value['Parent'])
    else:
        path = fileDIC[fileID]['Name']
    return path

def filenameToID(filename):
    """
    Search the data dictionary for an contentID that matches a corresponding filename from the filesystem return the identity key.
    Parameters: filename (str): The name of the file to search for.
    Returns: str or None: The key corresponding to the filename if found, or None if not found.
    """
    for keys, values in fileDIC.items():
        if values['contentID'] == filename:
            return str(keys)
    return None

def getRootDirs():
    """
    Returns the name of the root directory that contains the 'auth' folder with a '|' character in its name.
    Returns: str: The name of the root directory.
    """
    #quick function to find annoying "auth folder" name for filtering purposes
    for keys,values in fileDIC.items():
        if 'auth' in values['Name'] and '|' in values['Name']:
            return str(values['Name'])
        
def copy_file(root, file, skipnames, dumpdir, dry_run, log_file):
    filename = str(file)
    print('FOUND FILE ' + filename + ' SEARCHING......', end="\n")
    print('Processing ' + str(processed_files_counter.value) + ' of ' + str(total_files) + ' files', end="\n")
    fileID = filenameToID(str(file))
    fullpath = None
    if fileID is not None:
        fullpath = idToPath2(fileID)
    if fullpath is not None:
        newpath = None
        for paths in skipnames:
            newpath = fullpath.replace(paths, '')
        if newpath is not None:
            newpath = os.path.join(dumpdir, newpath.lstrip(os.sep))
        fullpath = str(os.path.join(root, file))

        if newpath in copied_files:
            print('File ' + fullpath + ' exists in ' + log_file + ', thus copied in a previous run to avoid duplication, skipping')
            logging.info(f'File {fullpath} exists in {log_file}, thus copied in a previous run to avoid duplication, skipping')
            with skipped_files_counter.get_lock():
                skipped_files_counter.value += 1
            with processed_files_counter.get_lock():
                processed_files_counter.value += 1
            progress = (processed_files_counter.value / total_files) * 100
            print(f'Progress: {progress:.2f}%')
            return
        elif os.path.exists(newpath):
            if args.refresh_mtime_existing and args.preserve_mtime:
                meta = fileDIC.get(fileID, {})
                ts = next(
                    (
                        t
                        for t in [
                            meta.get("imageDate"),
                            meta.get("videoDate"),
                            meta.get("cTime"),
                            meta.get("birthTime"),
                        ]
                        if isinstance(t, (int, float)) and t is not None
                    ),
                    None,
                )
                if ts:
                    os.utime(newpath, (ts / 1000, ts / 1000))
            with skipped_files_counter.get_lock():
                skipped_files_counter.value += 1
            with processed_files_counter.get_lock():
                processed_files_counter.value += 1
            progress = (processed_files_counter.value / total_files) * 100
            print(f'Progress: {progress:.2f}%')
            return
        else:
            if dry_run:
                print('Dry run: Skipping copying ' + fullpath + ' to ' + newpath)
                with processed_files_counter.get_lock():
                    processed_files_counter.value += 1
                progress = (processed_files_counter.value / total_files) * 100
                with copied_files_counter.get_lock():
                    copied_files_counter.value += 1
                print(f'Progress: {progress:.2f}%')
                return
            else:
                print('Copying ' + newpath)
                try:
                    os.makedirs(os.path.dirname(newpath), exist_ok=True)
                    shutil.copy2(fullpath, newpath)
                        if args.preserve_mtime:
                            meta = fileDIC.get(fileID, {})
                            ts = next(
                                (
                                    t
                                    for t in [
                                    meta.get("imageDate"),
                                    meta.get("videoDate"),
                                    meta.get("cTime"),
                                    meta.get("birthTime"),
                                ]
                                if isinstance(t, (int, float)) and t is not None
                            ),
                            None,
                        )
                            if ts:
                                os.utime(newpath, (ts / 1000, ts / 1000))
                                try:
                                    conn = sqlite3.connect(db)
                                    cur = conn.cursor()
                                    cur.execute("UPDATE copied_files SET mtime_refreshed=1 WHERE file_id=?", (fileID,))
                                    conn.commit()
                                    conn.close()
                                except sqlite3.Error:
                                    pass
                    with processed_files_counter.get_lock():
                        processed_files_counter.value += 1
                    progress = (processed_files_counter.value / total_files) * 100
                    with copied_files_counter.get_lock():
                        copied_files_counter.value += 1
                    print(f'Progress: {progress:.2f}%')
                    with lock:
                        with open(log_file, 'a') as f:
                            f.write(fullpath + '\n')
                except:
                    print('Error copying file ' + fullpath + ' to ' + newpath)
                    logging.info('Error copying file ' + fullpath + ' to ' + newpath)
    else:
        print('Error: Unable to find file ' + filename + ' in the database')
        logging.info('Error: Unable to find file ' + filename + ' in the database')
        with processed_files_counter.get_lock():
            processed_files_counter.value += 1
        progress = (processed_files_counter.value / total_files) * 100
        with skipped_files_counter.get_lock():
            skipped_files_counter.value += 1
        print(f'Progress: {progress:.2f}%')
                    
def create_log_file_from_dir(root_dir, log_file):
    """
    Regenerate the log file by scanning the destination directory and writing all found files to the log.
    Args:
        root_dir (str): The directory to scan (usually the destination/dumpdir).
        log_file (str): The path to the log file to be created.
    """
    tmp_log = log_file + ".tmp"
    with open(tmp_log, 'w') as f:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                f.write(file_path + '\n')
    os.replace(tmp_log, log_file)

def get_dir_size(start_path='.'):
    """
    Calculate the total size of a directory and its subdirectories.
    Args: start_path (str): The path of the directory to calculate the size of. Defaults to the current directory.
    Returns: int: The total size of the directory in bytes.
    """
    total_size = 0
    for dirpath, _, filenames in os.walk(start_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            # skip if it is symbolic link
            if not os.path.islink(filepath):
                try:
                    file_stat = os.stat(filepath)
                    total_size += file_stat.st_size
                except OSError:
                    pass

    return total_size

if __name__ == "__main__":

    start_time = time.time()
    logging.info(f"Start time: {time.ctime(start_time)}")

    parser = argparse.ArgumentParser(description="WD MyCloud REST SDK Recovery Tool")
    parser.add_argument("--preflight", action="store_true", help="Run pre-flight hardware/file check and print recommendations")
    parser.add_argument("--dry_run", action="store_true", default=False, help="Perform a dry run")
    parser.add_argument("--db", help="Path to the file DB")
    parser.add_argument("--filedir", help="Path to the files directory")
    parser.add_argument("--dumpdir", help="Path to the directory to dump files")
    parser.add_argument("--log_file", help="Path to the log file used to track successfully copied files to avoid duplication in future runs")
    parser.add_argument("--create_log", action="store_true", default=False, help="Create a log file from an existing run where logging was not in place")
    parser.add_argument("--resume", action="store_true", help="Resume a previous run, regenerating the log from the destination before resuming (default)")
    parser.add_argument("--regen-log", dest="regen_log", action="store_true", help="Regenerate the log file from the destination directory only, then exit")
    parser.add_argument("--no-regen-log", dest="no_regen_log", action="store_true", help="When used with --resume, skip regenerating the log and use the existing log file as-is (advanced)")
    parser.add_argument("--thread-count", type=int, help="Number of threads to use")
    parser.add_argument("--log_level", type=str, choices=["DEBUG", "INFO", "WARNING"], default="INFO", help="Set the logging level (DEBUG, INFO, WARNING). Default is INFO.")
    parser.add_argument(
        "--preserve-mtime",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After copy, set destination mtime to the best available timestamp from the DB (imageDate, videoDate, cTime). Enabled by default; use --no-preserve-mtime to disable.",
    )
    parser.add_argument(
        "--refresh-mtime-existing",
        action="store_true",
        help="If destination file already exists, refresh its mtime from DB timestamps without recopying.",
    )
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.db:
        init_copy_tracking_tables(args.db)

    if args.preflight:
        if not args.filedir or not args.dumpdir:
            print("\n❗ Please provide both --filedir (source) and --dumpdir (destination) for pre-flight check.\n")
            print_help()
            sys.exit(1)
        summary = preflight_summary(args.filedir, args.dumpdir)
        print_preflight_report(summary, args.filedir, args.dumpdir)
        sys.exit(0)

    if args.regen_log or args.create_log:
        if not args.dumpdir or not args.log_file or not args.db:
            print("\n❗ Please provide --dumpdir, --log_file, and --db for log regeneration.\n")
            sys.exit(1)
        print(f"Regenerating log file {args.log_file} from destination {args.dumpdir} and updating copied_files table...")
        regenerate_copied_files_from_dest(args.db, args.dumpdir, args.log_file)
        print("Log file and copied_files table regeneration complete.")
        sys.exit(0)

    if not args.db or not args.filedir or not args.dumpdir or not args.log_file:
        print("\n❗ Missing required arguments. Please provide --db, --filedir, --dumpdir, and --log_file.\n")
        sys.exit(1)

    # Expose globals for helper functions
    db = args.db
    filedir = args.filedir
    dumpdir = args.dumpdir
    dry_run = args.dry_run
    log_file = args.log_file
    thread_count = args.thread_count if args.thread_count else os.cpu_count() or 1

    lock = Lock()

    filedir_size = get_dir_size(filedir) / (1024 * 1024 * 1024)
    print(f"The size of the directory {filedir} is {filedir_size:.2f} GB")
    logging.info(f"The size of the directory {filedir} is {filedir_size:.2f} GB")

    try:
        con = sqlite3.connect(db)
    except sqlite3.Error:
        print(f"Error opening database at {db}")
        logging.exception("Error opening database")
        sys.exit(1)

    cur = con.cursor()
    cur.execute("SELECT id, name, parentID, contentID, imageDate, videoDate, cTime, birthTime FROM files")
    files = cur.fetchall()
    num_db_rows = len(files)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contentID ON files (contentID)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parentID ON files (parentID)")
    con.commit()
    con.close()

    fileDIC = {
        file[0]: {
            "Name": file[1],
            "Parent": file[2],
            "contentID": file[3],
            "imageDate": file[4],
            "videoDate": file[5],
            "cTime": file[6],
            "birthTime": file[7],
        }
        for file in files
    }
    skipnames = [filedir]
    root_dir_name = getRootDirs()
    if root_dir_name:
        skipnames.append(root_dir_name)

    total_files = sum([len(files) for _, _, files in os.walk(filedir)])
    processed_files_counter = Value("i", 0)
    copied_files_counter = Value("i", 0)
    skipped_files_counter = Value("i", 0)

    copied_files = set()
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            copied_files = set(f.read().splitlines())

    logging.info(f"Parameters: db={db}, filedir={filedir}, dumpdir={dumpdir}, dry_run={dry_run}, log_file={log_file}, create_log={args.create_log}, resume={args.resume}, thread_count={thread_count}")

    def run_standard_copy():
        print(f"There are {total_files} files to copy from {filedir} to {dumpdir}")
        logging.info(f"There are {total_files} files to copy from {filedir} to {dumpdir}")
        print(f"There are {num_db_rows} rows in the database to process")
        logging.info(f"There are {num_db_rows} rows in the database to process")
        print(f"The size of file data dictionary is {len(fileDIC)} elements")
        logging.info(f"The size of file data dictionary is {len(fileDIC)} elements")
        print(f"The number of threads used in this run is {thread_count}")
        logging.info(f"The number of threads used in this run is {thread_count}")
        perf_hint = max(1000, min(num_db_rows // 50, 50000))  # ~2% capped at 50k
        print(f"Tip: to run the perf sanity test, set PERF_TEST_ROWS={perf_hint} and run pytest tests/test_perf_regen_log.py")
        logging.info(f"Perf hint suggested rows: {perf_hint}")

        last_logged_percent = -1

        def log_progress():
            copied = copied_files_counter.value
            skipped = skipped_files_counter.value
            processed = processed_files_counter.value
            percent = int((processed / total_files) * 100) if total_files else 100
            msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Progress: Copied={copied} Skipped={skipped} Total={total_files} Percent={percent}%"
            print(msg)
            logging.info(msg)

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            for root, dirs, files in os.walk(filedir):
                for file in files:
                    executor.submit(copy_file, root, file, skipnames, dumpdir, dry_run, log_file)
                    processed = processed_files_counter.value
                    percent = int((processed / total_files) * 100) if total_files else 100
                    if percent > last_logged_percent:
                        last_logged_percent = percent
                        log_progress()

        dumpdir_size = get_dir_size(dumpdir) / (1024 * 1024 * 1024)
        print(f"The size of the source directory {filedir} is {filedir_size:.2f} GB")
        print(f"The size of the destination directory {dumpdir} is {dumpdir_size:.2f} GB")
        print(f"There are {total_files} files to copy from {filedir} to {dumpdir}")
        print(f"There are {num_db_rows} rows in the database to process")
        print(f"The size of file data dictionary is {len(fileDIC)} elements")
        print(f"There are {len(copied_files)} files copied on previous runs of this script, pulled from {log_file}")
        if dry_run:
            print(f"Dry run - No files were actually copied: Total files that would have been copied: {copied_files_counter.value}")
        else:
            print(f"Total files copied: {copied_files_counter.value}")
        print(f"Total files skipped: {skipped_files_counter.value}")
        print(f"Total files in the source directory: {total_files}")
        print(f"Total files in the destination directory: {len(os.listdir(dumpdir))}")
        print(f"The number of threads used in this run is {thread_count}")

        print("\nReconciliation Summary:")
        summary_data = [
            ("The size of the source directory", f"{filedir_size:.2f} GB"),
            ("The size of the destination directory", f"{dumpdir_size:.2f} GB"),
            ("Total files to copy", total_files),
            ("Rows in the database to process", num_db_rows),
            ("The size of file data dictionary", len(fileDIC)),
            ("Files copied on previous runs", len(copied_files)),
            ("Total files copied", copied_files_counter.value),
            ("Total files skipped", skipped_files_counter.value),
            ("Total files in the source directory", total_files),
            ("Total files in the destination directory", len(os.listdir(dumpdir))),
        ]
        for label, value in summary_data:
            print(f"{label}: {value}")
            logging.info(f"{label}: {value}")

        if processed_files_counter.value != total_files:
            print("Warning: Not all files were processed. Check for errors or incomplete runs.")
            logging.warning("Not all files were processed. Check for errors or incomplete runs.")
        else:
            print("All files have been processed successfully.")
            logging.info("All files have been processed successfully.")

        if os.path.exists(log_file):
            print(f"Resuming from previous run. Log file found: {log_file}")
            logging.info(f"Resuming from previous run. Log file found: {log_file}")
        else:
            print("Starting a new run. No log file found.")
            logging.info("Starting a new run. No log file found.")

    def run_resume_copy():
        if not args.no_regen_log:
            print(f"Regenerating log file {log_file} from destination {dumpdir} before resuming and updating copied_files table...")
            regenerate_copied_files_from_dest(db, dumpdir, log_file)
            print("Log file and copied_files table regeneration complete. Resuming copy process...")
        else:
            print("Skipping log regeneration (using existing log file as-is). Resuming copy process...")

        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute(
            """SELECT f.id, f.contentID, f.name, f.imageDate, f.videoDate, f.cTime, f.birthTime FROM files f
               LEFT JOIN copied_files c2 ON f.id = c2.file_id
               LEFT JOIN skipped_files s ON f.contentID = s.filename
               WHERE c2.file_id IS NULL AND s.filename IS NULL"""
        )
        files_to_copy = c.fetchall()
        c.execute("SELECT filename FROM copied_files")
        already_copied_set = set(row[0] for row in c.fetchall())
        c.execute("SELECT filename FROM skipped_files")
        skipped_set = set(row[0] for row in c.fetchall())
        conn.close()

        print(f"Files to process: {len(files_to_copy)} (filtered by copied_files and skipped_files tables)")
        logging.info(f"Files to process: {len(files_to_copy)}")

        results = {"copied": 0, "skipped_already": 0, "skipped_problem": 0, "errored": 0, "dry_run": 0}

        def copy_worker(file_row):
            file_id, content_id, name, image_date, video_date, c_time, birth_time = file_row
            try:
                if content_id in already_copied_set:
                    return ("skipped_already", content_id)
                if content_id in skipped_set:
                    return ("skipped_problem", content_id)
                if dry_run:
                    print(f"[DRY RUN] Would copy: {content_id}")
                    logging.info(f"[DRY RUN] Would copy: {content_id}")
                    return ("dry_run", content_id)
                rel_path = idToPath2(file_id)
                for skip in skipnames:
                    rel_path = rel_path.replace(skip, "")
                rel_path = rel_path.replace("|", "-")
                dest_path = os.path.join(dumpdir, rel_path)
                src_path = os.path.join(filedir, content_id)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                if os.path.exists(dest_path) and args.refresh_mtime_existing:
                    if args.preserve_mtime:
                        ts = next(
                            (
                                t
                                for t in [image_date, video_date, c_time, birth_time]
                                if isinstance(t, (int, float)) and t is not None
                            ),
                            None,
                        )
                        if ts:
                            os.utime(dest_path, (ts / 1000, ts / 1000))
                    return ("skipped_already", content_id)
                shutil.copy2(src_path, dest_path)
                if args.preserve_mtime:
                    ts = next(
                        (
                            t
                            for t in [image_date, video_date, c_time, birth_time]
                            if isinstance(t, (int, float)) and t is not None
                        ),
                        None,
                    )
                    if ts:
                        os.utime(dest_path, (ts / 1000, ts / 1000))  # convert ms to seconds
                insert_copied_file(db, file_id, content_id)
                print(f"[COPIED] {rel_path}")
                logging.info(f"Copied: {rel_path}")
                return ("copied", rel_path)
            except Exception as copy_err:
                logging.error(f"Error copying {name}: {copy_err}")
                print(f"[ERROR] {name}: {copy_err}")
                return ("errored", name)

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            for status, rel in executor.map(copy_worker, files_to_copy):
                results[status] += 1

        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM copied_files")
        copied_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM skipped_files")
        skipped_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM files")
        total_files_db = c.fetchone()[0]
        conn.close()
        dest_count = sum(len(files) for _, _, files in os.walk(dumpdir))

        print("\n===== SUMMARY =====")
        print(f"Total files in source (files table): {total_files_db}")
        print(f"Total files copied (copied_files table): {copied_count}")
        print(f"Total files skipped (skipped_files table): {skipped_count}")
        print(f"Total files in destination directory: {dest_count}")
        print(f"Copied this run: {results['copied']}")
        print(f"Skipped (already copied): {results['skipped_already']}")
        print(f"Skipped (problem/skipped): {results['skipped_problem']}")
        print(f"Errored: {results['errored']}")
        print(f"Processed: {sum(results.values())}")

    if args.resume:
        run_resume_copy()
    else:
        run_standard_copy()

    log_queue.put("STOP")
    log_thread.join()
