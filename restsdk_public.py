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

##Intended for python3.6 on linux, probably won't work on Windows
##This software is distributed without any warranty. It will probably brick your computer.
#--db=/media/chapman/4be9fddb-873d-4dd9-852b-bb9556560ff1/restsdk/data/db/index.db --filedir=/media/chapman/4be9fddb-873d-4dd9-852b-bb9556560ff1/restsdk/data/files --dumpdir=/mnt/nfs-media --dry_run --log_file=/home/chapman/projects/mycloud-restsdk-recovery-script/copied_file.log

# Set up logging
log_filename = 'summary.log'
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s %(message)s')


def print_help():
    print("Usage: python restsdk_public.py [options]")
    print("Options:")
    print("  --dry_run     Perform a dry run (do not copy files)")
    print("  --help        Show this help message")
    print("  --db          Path to the file DB (example: /restsdk/data/db/index.db)")
    print("  --filedir     Path to the files directory (example: /restsdk/data/files)")
    print("  --dumpdir     Path to the directory to dump files (example: /location/to/dump/files/to)")
    print("  --log_file    Path to the log file (example: /location/to/log/file.log)")
    print("  --create_log  Create a log file from an existing run where logging was not in place.")

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
                    
def create_log_file(root_dir, log_file):
    """
    Creates a log file and writes the absolute paths of all files in the given root directory.
    This is useful for creating a log file from an existing run where logging was not in place.
    Args:
        root_dir (str): The root directory to start searching for files.
        log_file (str): The path to the log file to be created.
    Returns: None
    """
    with open(log_file, 'w') as f:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(root, file)
                f.write(file_path + '\n')

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
    parser.add_argument('--log_file', help='Path to the log file')
    parser.add_argument('--create_log', action='store_true', default=False, help='Create a log file from an existing run where logging was not in place')
    args = parser.parse_args()

    if "--help" in sys.argv:
        print_help()
        sys.exit(0)

    db = args.db
    filedir = args.filedir
    dumpdir = args.dumpdir
    dry_run = args.dry_run
    log_file = args.log_file

    logging.info(f'Parameters: db={db}, filedir={filedir}, dumpdir={dumpdir}, dry_run={dry_run}, log_file={log_file}, create_log={args.create_log}')

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
    cur.execute("SELECT id,name,parentID,mimeType,contentID FROM files")
    files = cur.fetchall()
    #Retrieve the number of DB records
    num_db_rows = len(files)
    #SQlite has a table named "FILES", the filename in the file structure is found in ContentID, with the parent directory being called ParentID
    fileDIC={}

    for file in files:
        fileID=file[0]
        fileName=file[1]
        fileParent=file[2]
        mimeType=file[3]
        contentID=file[4]
        fileDIC[fileID]={'Name':fileName,'Parent':fileParent,'contentID':contentID,'Type':mimeType,'fileContentID':''}

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

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as executor:
        for root,dirs,files in os.walk(filedir): #find all files in original directory structure
            for file in files:
                executor.submit(copy_file, root, file, skipnames, dumpdir, dry_run, log_file)

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
    print('There are ' + str(total_files) + 'files to copy from ' + filedir + ' to ' + dumpdir).end("\n")
    print('There are ' + str(num_db_rows) + ' rows in the database to process').end("\n")
    print('The size of file data dictionary is ' + str(fileDIC_size) + ' elements')
    print('There are ' + str(len(copied_files)) + ' files copied on previous runs of this script, pulled from ' + log_file)
    if dry_run:
        print(f'Dry run - No files were actually copied: Total files that would have been copied: {str(copied_files_counter.value)}')
    else:
        print(f'Total files copied: {str(copied_files_counter.value)}')
    print(f'Total files skipped: {str(skipped_files_counter.value)}')
    print(f'Total files in the source directory: {str(total_files)}')
    print(f'Total files in the destination directory: {str(len(os.listdir(dumpdir)))}')

    #Output file logging
    logging.info(f'The size of the source directory {filedir} is {str(filedir_size):.2f} GB')
    logging.info(f'The size of the destination directory {dumpdir} is {str(dumpdir_size):.2f} GB') 
    logging.info('There are ' + str(total_files) + 'files to copy from ' + filedir + ' to ' + dumpdir)
    logging.info('There are ' + str(num_db_rows) + ' rows in the database to process')
    logging.info('The size of file data dictionary is ' + str(fileDIC_size) + ' elements')
    logging.info('There are ' + str(len(copied_files)) + ' files copied on previous runs of this script, pulled from ' + log_file)
    if dry_run:
        logging.info(f'Dry run - No files were actually copied: Total files that would have been copied: {str(copied_files_counter.value)}')
    else:
        logging.info(f'Total files copied: {str(copied_files_counter.value)}')
    logging.info(f'Total files skipped: {str(skipped_files_counter.value)}')
    logging.info(f'Total files in the source directory: {str(total_files)}')
    logging.info(f'Total files in the destination directory: {str(len(os.listdir(dumpdir)))}')

    # Log the end of your script
    end_time = time.time()
    logging.info(f'Start time: {time.ctime(start_time)}')
    logging.info(f'End time: {time.ctime(end_time)}')
    logging.info(f'Total execution time: {end_time - start_time} seconds')
