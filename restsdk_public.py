import sqlite3
import pprint
import copy
import os
from shutil import copyfile
import argparse
import sys
import multiprocessing
import logging
from multiprocessing import Lock
from multiprocessing import Value
import time
from concurrent.futures import ThreadPoolExecutor

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
    #finds the next parent db item in a chain
    for key,value in fileDIC.items():
        if key==fileID:
            return value['Parent']
        
def hasAnotherParent(fileID):
    #checks to see if a db item has another parent
    if fileDIC[fileID]['Parent']!=None:
        return True
    else:
        return False
    
def findTree(fileID,name,parent):
    #turn a file ID into an original path
    path=fileDIC[parent]['Name']+"/"+name
    while hasAnotherParent(fileID)==True:
        fileID=findNextParent(fileID)
        path=fileDIC[fileID]['Name']+'/'+path
    return path

def idToPath2(fileID):
    #turn a file ID into an original path
    value=fileDIC[fileID]
    if value['Parent']!=None:
        print("idToPath2 - Found file " + value['Name'] + 'searching for parents')
        print('idToPath2 - Totalpath is ' + path)
        path=findTree(fileID,value['Name'],value['Parent'])
    else:
        print("idToPath2 - Found file " + value['Name'] + 'no parent search needed')
        path=fileDIC[fileID]['Name']
    return path

def filenameToID(filename):
    #turn a filename from filesystem into a db id
    for keys,values in fileDIC.items():
        if values['contentID']==filename:
            print('filenameToID Function - Found filename ' + filename + ' in DBkey ' + str(keys) +' with name ' + values['Name'])
            return str(keys)
    print('filenameToID Function - Unable to find filename ' + filename)
    return None

def getRootDirs():
    #quick function to find annoying "auth folder" name for filtering purposes
    for keys,values in fileDIC.items():
        if 'auth' in values['Name'] and '|' in values['Name']:
            return str(values['Name'])
        
def copy_file(root, file, skipnames, dumpdir, dry_run, log_file):
    #root, file, skipnames, dumpdir, dry_run, log_file = args
    
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
        if fullpath in copied_files:
            print('File ' + fullpath + ' exists in ' + log_file + ', thus copied in a previous run to avoid duplication, skipping')
            logging.info(f'File {fullpath} exists in {log_file}, thus copied in a previous run to avoid duplication, skipping')
            with skipped_files_counter.get_lock():
                skipped_files_counter.value += 1
            with processed_files_counter.get_lock():
                processed_files_counter.value += 1
            progress = (processed_files_counter.value / total_files) * 100
            print(f'Progress: {progress:.2f}%')
            return
        elif os.path.exists(newpath):  # Check if the file already exists in dumpdir skip to avoid duplication
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
                with skipped_files_counter.get_lock():
                    skipped_files_counter.value += 1
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
                    
def create_log_file(root_dir, log_file):
                        with open(log_file, 'w') as f:
                            for root, dirs, files in os.walk(root_dir):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    f.write(file_path + '\n')

def get_dir_size(start_path='.'):
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
    filedir_size= 1804.2066087452695
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
    #SQlite has a table named "FILES", the filename in the file structure is found in ContentID, with the parent directory being called ParentID
    fileDIC={}

    for file in files:
        fileID=file[0]
        fileName=file[1]
        fileParent=file[2]
        mimeType=file[3]
        contentID=file[4]
        fileDIC[fileID]={'Name':fileName,'Parent':fileParent,'contentID':contentID,'Type':mimeType,'fileContentID':''}

    skipnames.append(getRootDirs()) #remove obnoxious root dir names

    total_files = sum([len(files) for _, _, files in os.walk(filedir)])  # total number of files to be processed
    
    # Create a Value to hold processed_files, copied_files, and skipped_files
    # Since we are using multi-threading we need to use a multiprocessing.Value to share the counter between processes
    processed_files_counter = Value('i', 0)
    copied_files_counter = Value('i', 0)
    skipped_files_counter = Value('i', 0)

    print('Total files to copy ' + str(total_files))
    logging.info('Total files to copy ' + str(total_files))

    # Check if the log file exists
    if os.path.exists(log_file):
        print('Log file found - opening file ' + log_file + ' to check for previously copied files')
        logging.info('Log file found - opening file ' + log_file + ' to check for previously copied files')
        copied_files = set()
        with open(log_file, 'r') as f:
            copied_files = set(f.read().splitlines())
    else:
        copied_files = []

    # In the main part of your code
    with ThreadPoolExecutor(max_workers=1) as executor:
        for root,dirs,files in os.walk(filedir): #find all files in original directory structure
            for file in files:
                executor.submit(copy_file, root, file, skipnames, dumpdir, dry_run, log_file)

    print("Did this script help you recover your data? Save you a few hundred bucks? Or make you some money recovering somebody else's data?")
    print("Consider sending us some bitcoin/crypto as a way of saying thanks!")
    print("Bitcoin: 1DqSLNR8kTgwq5rvveUFDSbYQnJp9D5gfR")
    print("ETH: 0x9e765052283Ce6521E40069Ac52ffA5B277bD8AB")
    print("Zcash: t1RetUQktuUBL2kbX72taERb6QcuAiDsvC4")

    # Get the size of dumpdir in GB
    dumpdir_size = get_dir_size(dumpdir) / (1024 * 1024 * 1024)
    print(f'The size of the source directory {filedir} is {str(filedir_size):.2f} GB')
    print(f'The size of the destination directory {dumpdir} is {str(dumpdir_size):.2f} GB')
    print(f'Total files copied: {str(copied_files_counter.value)}')
    print(f'Total files skipped: {str(skipped_files_counter.value)}')
    print(f'Total files in the source directory: {str(total_files)}')
    print(f'Total files in the destination directory: {str(len(os.listdir(dumpdir)))}')

    logging.info(f'The size of the source directory {filedir} is {str(filedir_size):.2f} GB')
    logging.info(f'The size of the destination directory {dumpdir} is {str(dumpdir_size):.2f} GB')
    logging.info(f'Total files copied: {str(copied_files_counter.value)}')
    logging.info(f'Total files skipped: {str(skipped_files_counter.value)}')
    logging.info(f'Total files in the source directory: {str(total_files)}')
    logging.info(f'Total files in the destination directory: {str(len(os.listdir(dumpdir)))}')

    # Log the end of your script
    end_time = time.time()
    logging.info(f'End time: {time.ctime(end_time)}')
    logging.info(f'Total execution time: {end_time - start_time} seconds')
