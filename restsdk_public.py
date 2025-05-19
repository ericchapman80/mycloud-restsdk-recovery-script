import argparse
import copy
import logging
import multiprocessing
import os
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
    print("  --preflight         Run hardware and file system pre-flight check (requires --filedir and --dumpdir)")
    print("  --dry_run           Perform a dry run (do not copy files)")
    print("  --help              Show this help message")
    print("  --db                Path to the file DB (example: /restsdk/data/db/index.db)")
    print("  --filedir           Path to the files directory (example: /restsdk/data/files)")
    print("  --dumpdir           Path to the directory to dump files (example: /location/to/dump/files/to)")
    print("  --log_file          Path to the log file (example: /location/to/log/file.log)")
    print("  --create_log        Create a log file from an existing run where logging was not in place.")
    print("  --resume            Resume a previous run, regenerating the log from the destination before resuming (default)")
    print("  --regen-log         Regenerate the log file from the destination directory only, then exit")
    print("  --no-regen-log      (Advanced) Use with --resume to skip regenerating the log and use the existing log file as-is")
    print("  --thread-count      Number of threads to use")

# --- SQL DDL/DML and Hybrid Copy Logic ---
import sqlite3

def init_copy_tracking_tables(db_path):
    """
    Ensure the copied_files and skipped_files tables exist in the database.
    Uses TEXT for file_id and filename to match Files table schema.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS copied_files (
        file_id TEXT PRIMARY KEY,
        filename TEXT,
        copied_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
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
    c.execute('''INSERT OR IGNORE INTO copied_files (file_id, filename) VALUES (?, ?)''', (str(file_id), str(filename)))
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
                else:
                    print(f"  [NO MATCH] No DB entry found for destination file: {file}")
                total_files += 1
                if total_files % 100000 == 0:
                    print(f"  Processed {total_files} files so far...")
    print(f"Finished scanning. Total files processed: {total_files}")
    conn.commit()
    conn.close()
    os.replace(tmp_log, log_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WD MyCloud REST SDK Recovery Tool")
    parser.add_argument("--preflight", action="store_true", help="Run pre-flight hardware/file check and print recommendations")
    parser.add_argument("--db", type=str, help="Path to the file DB")
    parser.add_argument("--filedir", type=str, help="Path to the files directory")
    parser.add_argument("--dumpdir", type=str, help="Path to the directory to dump files")
    parser.add_argument("--log_file", type=str, help="Path to the log file")
    parser.add_argument("--thread-count", type=int, help="Number of threads to use")
    parser.add_argument("--dry_run", action="store_true", help="Perform a dry run (do not copy files)")
    parser.add_argument("--create_log", action="store_true", help="Create a log file from an existing run")
    parser.add_argument("--resume", action="store_true", help="Resume a previous run, regenerating the log from the destination before resuming (default)")
    parser.add_argument("--regen-log", action="store_true", help="Regenerate the log file from the destination directory only, then exit")
    parser.add_argument("--no-regen-log", action="store_true", help="When used with --resume, skip regenerating the log and use the existing log file as-is (advanced)")

    args = parser.parse_args()

    # Initialize tracking tables
    if args.db:
        init_copy_tracking_tables(args.db)

    # Handle preflight
    if args.preflight:
        if not args.filedir or not args.dumpdir:
            print("\n❗ Please provide both --filedir (source) and --dumpdir (destination) for pre-flight check.\n")
            print_help()
            sys.exit(1)
        summary = preflight_summary(args.filedir, args.dumpdir)
        print_preflight_report(summary, args.filedir, args.dumpdir)
        sys.exit(0)

    # Handle log regeneration only
    if args.regen_log or args.create_log:
        if not args.dumpdir or not args.log_file or not args.db:
            print("\n❗ Please provide --dumpdir, --log_file, and --db for log regeneration.\n")
            sys.exit(1)
        print(f"Regenerating log file {args.log_file} from destination {args.dumpdir} and updating copied_files table...")
        regenerate_copied_files_from_dest(args.db, args.dumpdir, args.log_file)
        print("Log file and copied_files table regeneration complete.")
        sys.exit(0)

    # Handle resume (default: always regen log unless --no-regen-log is set)
    if args.resume:
        if not args.dumpdir or not args.log_file or not args.db:
            print("\n❗ Please provide --dumpdir, --log_file, and --db for resume mode.\n")
            sys.exit(1)
        if not args.no_regen_log:
            print(f"Regenerating log file {args.log_file} from destination {args.dumpdir} before resuming and updating copied_files table...")
            regenerate_copied_files_from_dest(args.db, args.dumpdir, args.log_file)
            print("Log file and copied_files table regeneration complete. Resuming copy process...")
        else:
            print("Skipping log regeneration (using existing log file as-is). Resuming copy process...")
        # Query files to process using SQL join
        conn = sqlite3.connect(args.db)
        c = conn.cursor()
        # Use contentID for all joins and filtering
        c.execute('''SELECT f.* FROM Files f
                     LEFT JOIN copied_files c ON f.id = c.file_id
                     LEFT JOIN skipped_files s ON f.contentID = s.filename
                     WHERE c.file_id IS NULL AND s.filename IS NULL''')
        files_to_copy = c.fetchall()
        conn.close()
        print(f"Files to process: {len(files_to_copy)} (filtered by copied_files and skipped_files tables)")

        # Counters for summary
        copied_this_run = 0
        skipped_already = 0
        skipped_problem = 0
        errored = 0
        processed = 0
        skipped_files_list = []
        already_copied_files_list = []
        errored_files_list = []

        # Build quick lookup sets for skipped and already copied
        conn = sqlite3.connect(args.db)
        c = conn.cursor()
        c.execute('SELECT filename FROM copied_files')
        already_copied_set = set(row[0] for row in c.fetchall())
        c.execute('SELECT filename FROM skipped_files')
        skipped_set = set(row[0] for row in c.fetchall())
        conn.close()

        # --- Multithreaded file copy using ThreadPoolExecutor ---
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def copy_worker(f):
            # Files table order: id, parentID, contentID, version, name, ...
            file_id = f[0]         # id (TEXT)
            contentID = f[2]       # contentID (TEXT)
            name = f[4]            # name (TEXT)
            try:
                if contentID in already_copied_set:
                    return ("skipped_already", contentID)
                elif contentID in skipped_set:
                    return ("skipped_problem", contentID)
                else:
                    if args.dry_run:
                        print(f"[DRY RUN] Would copy: {contentID}")
                        logging.info(f"[DRY RUN] Would copy: {contentID}")
                        return ("dry_run", contentID)
                    else:
                        try:
                            rel_path = idToPath2(file_id)
                            for skip in skipnames:
                                rel_path = rel_path.replace(skip, '')
                            rel_path = rel_path.replace('|', '-')
                            dest_path = os.path.join(args.dumpdir, rel_path)
                            src_path = os.path.join(args.filedir, contentID)
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            shutil.copy2(src_path, dest_path)
                            insert_copied_file(args.db, file_id, contentID)
                            print(f"[COPIED] {rel_path}")
                            logging.info(f"Copied: {rel_path}")
                            return ("copied", rel_path)
                        except Exception as copy_err:
                            logging.error(f"Error copying {rel_path if 'rel_path' in locals() else name}: {copy_err}")
                            print(f"[ERROR] {rel_path if 'rel_path' in locals() else name}: {copy_err}")
                            return ("errored", rel_path if 'rel_path' in locals() else name)
            except Exception as e:
                logging.error(f"Error processing {contentID}: {e}")
                print(f"[ERROR] {contentID}: {e}")
                return ("errored", contentID)

        # Use user-specified thread count or default
        thread_count = args.thread_count if args.thread_count else os.cpu_count() or 4
        results = {"copied": 0, "skipped_already": 0, "skipped_problem": 0, "errored": 0, "dry_run": 0}
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            future_to_file = {executor.submit(copy_worker, f): f for f in files_to_copy}
            for future in as_completed(future_to_file):
                status, val = future.result()
                results[status] += 1
                # Optionally, collect lists for reporting
                if status == "skipped_already":
                    already_copied_files_list.append(val)
                elif status == "skipped_problem":
                    skipped_files_list.append(val)
                elif status == "errored":
                    errored_files_list.append(val)

        copied_this_run = results["copied"]
        skipped_already = results["skipped_already"]
        skipped_problem = results["skipped_problem"]
        errored = results["errored"]
        processed = sum(results.values())

        # End-of-run reconciliation summary
        conn = sqlite3.connect(args.db)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM copied_files')
        copied_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM skipped_files')
        skipped_count = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM Files')
        total_files = c.fetchone()[0]
        conn.close()
        dest_count = sum(len(files) for _, _, files in os.walk(args.dumpdir)) if args.dumpdir else 0

        print("\n===== SUMMARY =====")
        print(f"Total files in source (Files table): {total_files}")
        print(f"Total files copied (copied_files table): {copied_count}")
        print(f"Total files skipped (skipped_files table): {skipped_count}")
        print(f"Total files in destination directory: {dest_count}")
        print(f"Copied this run: {copied_this_run}")
        print(f"Skipped (already copied): {skipped_already}")
        print(f"Skipped (problem/skipped): {skipped_problem}")
        print(f"Errored: {errored}")
        print(f"Processed: {processed}")
        logging.info(f"SUMMARY: source={total_files}, copied={copied_count}, skipped={skipped_count}, dest={dest_count}, copied_this_run={copied_this_run}, skipped_already={skipped_already}, skipped_problem={skipped_problem}, errored={errored}, processed={processed}")
        print("===================\n")
        # Optionally, print lists of skipped/copied/errored files for review
        # print("Skipped files:", skipped_files_list)
        # print("Already copied files:", already_copied_files_list)
        # print("Errored files:", errored_files_list)
    # ... (rest of the script remains the same)

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
    while hasAnotherParent(fileID) == True:
        fileID = findNextParent(fileID)
        path = fileDIC[fileID]['Name'] + '/' + path
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
    """
    Copy a file from the source directory to the target directory, skipping duplicates.
    Args:
        root (str): The root directory of the file.
        file (str): The name of the file.
        skipnames (list): A list of paths to skip during the copy process.
        dumpdir (str): The target directory to copy the file to.
        dry_run (bool): If True, perform a dry run without actually copying the file.
        log_file (str): The path to the log file.
    Returns:
        None
    """
    # Function code...
def copy_file(root, file, skipnames, dumpdir, dry_run, log_file):
    filename = str(file)
    print('FOUND FILE ' + filename + ' SEARCHING......', end="\n")
    print('Processing ' + str(processed_files_counter.value) + ' of ' + str(total_files) + ' files', end="\n")
    fileID = filenameToID(str(file))
    fullpath = None
    if fileID != None:
        fullpath = idToPath2(fileID)
    if fullpath != None:
        newpath = None
        for paths in skipnames:
            newpath = fullpath.replace(paths, '')
        if newpath != None:
            newpath = dumpdir + newpath
        fullpath = str(os.path.join(root, file))

        # Check if the file has already been copied by comparing the full path to the copied_files set
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
        # Check if the file already exists in dumpdir skip to avoid duplication
        elif os.path.exists(newpath):  
            print('File ' + newpath + ' already exists in target destination, skipping')
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
                # Use .value to access the Value's underlying data
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
                    copyfile(fullpath, newpath)
                    # Use .value to access the Value's underlying data
                    with processed_files_counter.get_lock():
                        processed_files_counter.value += 1
                    progress = (processed_files_counter.value / total_files) * 100
                    with copied_files_counter.get_lock():
                        copied_files_counter.value += 1
                    print(f'Progress: {progress:.2f}%')
                    # Write the successfully copied file to the log file
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

    # Log start time
    start_time = time.time()
    logging.info(f'Start time: {time.ctime(start_time)}')

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry_run', action='store_true', default=False, help='Perform a dry run')
    parser.add_argument('--db', help='Path to the file DB')
    parser.add_argument('--filedir', help='Path to the files directory')
    parser.add_argument('--dumpdir', help='Path to the directory to dump files')
    parser.add_argument('--log_file', help='Path to the log file used to track successfully copied files to avoid duplication in future runs')
    parser.add_argument('--create_log', action='store_true', default=False, help='Create a log file from an existing run where logging was not in place')
    parser.add_argument('--thread-count', type=int, help='Number of threads to use')
    parser.add_argument('--log_level', type=str, choices=['DEBUG', 'INFO', 'WARNING'], default='INFO', help='Set the logging level (DEBUG, INFO, WARNING). Default is INFO.')
    args = parser.parse_args()

    # Assign log_file after args is defined
    log_file = args.log_file

    if "--help" in sys.argv:
        print_help()
        sys.exit(0)
    db = args.db
    filedir = args.filedir
    dumpdir = args.dumpdir
    dry_run = args.dry_run
    # log_file = args.log_file

    # Determine the number of threads to use
    thread_count = args.thread_count if args.thread_count else os.cpu_count() or 1

    # Set the logging level based on the argument
    log_level = args.log_level
    logging.getLogger().setLevel(getattr(logging, log_level))

    logging.info(f'Parameters: db={db}, filedir={filedir}, dumpdir={dumpdir}, dry_run={dry_run}, log_file={log_file}, create_log={args.create_log}, thread_count={thread_count}')

    lock = Lock()

    if args.create_log:
        if log_file is None or dumpdir is None:
            print("Error: Missing required arguments. Please provide values for --log_file and --dumpdir.")
            sys.exit(1)
        else:
            create_log_file(dumpdir, args.log_file)
            sys.exit(0)
    if db is None or filedir is None or dumpdir is None:
        print("Error: Missing required arguments. Please provide values for --db, --filedir, and --dumpdir.")
        sys.exit(1)
    
    skipnames=[filedir] #remove these strings from the final file/path name. Don't edit this.

    # Get the size of filedir in GB
    filedir_size = get_dir_size(filedir) / (1024 * 1024 * 1024)
    print(f'The size of the directory {filedir} is {filedir_size:.2f} GB')
    logging.info(f'The size of the directory {filedir} is {filedir_size:.2f} GB')

    #open the sqlite database
    print('Opening database...',end="\r")
    logging.info('Opening database...')
    try:
        con = sqlite3.connect(db)
    except:
        print('Error opening database at ' + db)
        logging.info('Error opening database at ' + db)
        quit()
    print('Querying database...',end="\r")
    logging.info('Querying database...')
    cur = con.cursor()
    # Optimize database query by adding indexes and fetching only required columns
    cur.execute("SELECT id, name, parentID, contentID FROM files")
    files = cur.fetchall()

    # Define num_db_rows based on the database query
    num_db_rows = len(files)  # Count the number of rows fetched from the database

    # Create an index on the database for faster lookups (if not already present)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contentID ON files (contentID)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parentID ON files (parentID)")
    con.commit()

    # Optimize file processing by reducing redundant checks and using efficient data structures
    copied_files = set()  # Use a set for faster lookups
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            copied_files.update(f.read().splitlines())

    # Use a dictionary to store file paths for quick access
    fileDIC = {file[0]: {'Name': file[1], 'Parent': file[2], 'contentID': file[3]} for file in files}

    # Get the size of fileDIC
    fileDIC_size = len(fileDIC)

    skipnames.append(getRootDirs()) #remove obnoxious root dir names

    total_files = sum([len(files) for _, _, files in os.walk(filedir)])  # total number of files to be processed
    
    # Since we are using multi-threading we need to use a multiprocessing.Value to share the counter between processes
    processed_files_counter = Value('i', 0)
    copied_files_counter = Value('i', 0)
    skipped_files_counter = Value('i', 0)

    #Pre-processing message Logging
    print('There are ' + str(total_files) + ' files to copy from ' + filedir + ' to ' + dumpdir)
    logging.info('There are ' + str(total_files) + ' files to copy from ' + filedir + ' to ' + dumpdir)
    print('There are ' + str(num_db_rows) + ' rows in the database to process')
    logging.info('There are ' + str(num_db_rows) + ' rows in the database to process')
    print('The size of file data dictionary is ' + str(fileDIC_size) + ' elements')
    logging.info('The size of file data dictionary is ' + str(fileDIC_size) + ' elements')
    print('The number of threads used in this run is ' + str(thread_count))
    logging.info('The number of threads used in this run is ' + str(thread_count))

    # Check if the log file exists
    if os.path.exists(log_file):
        print('Log file found - opening file ' + log_file + ' to check for previously copied files')
        logging.info('Log file found - opening file ' + log_file + ' to check for previously copied files')
        copied_files = set()
        with open(log_file, 'r') as f:
            copied_files = set(f.read().splitlines()) # read the log file and store the copied files in a set
            print('There are ' + str(len(copied_files)) + ' files copied on previous runs of this script, pulled from ' + log_file)
            logging.info('There are ' + str(len(copied_files)) + ' files copied on previous runs of this script, pulled from ' + log_file)
    else:
        copied_files = []

    # Set the queue size dynamically based on the number of processing threads
    queue_size = thread_count * 2  # Queue size is twice the number of threads

    # Initialize the logging queue with the dynamic size
    log_queue = Queue(maxsize=queue_size)

    # Progress tracking variables
    last_logged_percent = -1
    def log_progress():
        copied = copied_files_counter.value
        skipped = skipped_files_counter.value
        # For this implementation, missing and errored are counted as skipped (can be split if needed)
        missing = 0
        errored = 0
        processed = processed_files_counter.value
        percent = int((processed / total_files) * 100) if total_files else 100
        msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Progress: Copied={copied} Skipped={skipped} Missing={missing} Errored={errored} Total={total_files} Percent={percent}%"
        print(msg)
        logging.info(msg)

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for root,dirs,files in os.walk(filedir): #find all files in original directory structure
            for file in files:
                executor.submit(copy_file, root, file, skipnames, dumpdir, dry_run, log_file)
                # Efficient 1% progress logging
                processed = processed_files_counter.value
                percent = int((processed / total_files) * 100) if total_files else 100
                if percent > last_logged_percent:
                    last_logged_percent = percent
                    log_progress()

    print("Did this script help you recover your data? Save you a few hundred bucks? Or make you some money recovering somebody else's data?")
    print("Consider sending us some bitcoin/crypto as a way of saying thanks!")
    print("Bitcoin: 1DqSLNR8kTgwq5rvveUFDSbYQnJp9D5gfR")
    print("ETH: 0x9e765052283Ce6521E40069Ac52ffA5B277bD8AB")
    print("Zcash: t1RetUQktuUBL2kbX72taERb6QcuAiDsvC4")

    # Post-processing message logging
    dumpdir_size = get_dir_size(dumpdir) / (1024 * 1024 * 1024)

    #Console Logging
    print(f'The size of the source directory {filedir} is {str(filedir_size):.2f} GB')
    print(f'The size of the destination directory {dumpdir} is {str(dumpdir_size):.2f} GB')
    print('There are ' + str(total_files) + 'files to copy from ' + filedir + ' to ' + dumpdir)
    print('There are ' + str(num_db_rows) + ' rows in the database to process')
    print('The size of file data dictionary is ' + str(fileDIC_size) + ' elements')
    print('There are ' + str(len(copied_files)) + ' files copied on previous runs of this script, pulled from ' + log_file)
    if dry_run:
        print(f'Dry run - No files were actually copied: Total files that would have been copied: {str(copied_files_counter.value)}')
    else:
        print(f'Total files copied: {str(copied_files_counter.value)}')
    print(f'Total files skipped: {str(skipped_files_counter.value)}')
    print(f'Total files in the source directory: {str(total_files)}')
    print(f'Total files in the destination directory: {str(len(os.listdir(dumpdir)))}')
    print('The number of threads used in this run is ' + str(thread_count))
    
    # Consolidate reconciliation and logging to avoid duplication
    print("\nReconciliation Summary:")
    logging.info("\nReconciliation Summary:")

    summary_data = [
        ("The size of the source directory", f"{filedir_size:.2f} GB"),
        ("The size of the destination directory", f"{dumpdir_size:.2f} GB"),
        ("Total files to copy", total_files),
        ("Rows in the database to process", num_db_rows),
        ("The size of file data dictionary", fileDIC_size),
        ("Files copied on previous runs", len(copied_files)),
        ("Total files copied", copied_files_counter.value),
        ("Total files skipped", skipped_files_counter.value),
        ("Total files in the source directory", total_files),
        ("Total files in the destination directory", len(os.listdir(dumpdir)))
    ]

    for label, value in summary_data:
        print(f"{label}: {value}")
        logging.info(f"{label}: {value}")

    if dry_run:
        print(f"Dry run - No files were actually copied: Total files that would have been copied: {copied_files_counter.value}")
        logging.info(f"Dry run - No files were actually copied: Total files that would have been copied: {copied_files_counter.value}")

    if processed_files_counter.value != total_files:
        print("Warning: Not all files were processed. Check for errors or incomplete runs.")
        logging.warning("Not all files were processed. Check for errors or incomplete runs.")
    else:
        print("All files have been processed successfully.")
        logging.info("All files have been processed successfully.")

    # Ensure re-runnability by leveraging log_file
    if os.path.exists(log_file):
        print(f"Resuming from previous run. Log file found: {log_file}")
        logging.info(f"Resuming from previous run. Log file found: {log_file}")
    else:
        print("Starting a new run. No log file found.")
        logging.info("Starting a new run. No log file found.")

    # Stop the logging thread
    log_queue.put("STOP")
    log_thread.join()
