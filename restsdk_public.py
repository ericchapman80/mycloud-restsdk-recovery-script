##Intended for python3.6 on linux, probably won't work on Windows
##This software is distributed without any warranty. It will probably brick your computer.
def print_help():
    print("Usage: python restsdk_public.py [options]")
    print("Options:")
    print("  --dry_run     Perform a dry run (do not copy files)")
    print("  --help        Show this help message")
    print("  --db          Path to the file DB (example: /restsdk/data/db/index.db)")
    print("  --filedir     Path to the files directory (example: /restsdk/data/files)")
    print("  --dumpdir     Path to the directory to dump files (example: /location/to/dump/files/to)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry_run', action='store_true', default=False, help='Perform a dry run')
    parser.add_argument('--db', help='Path to the file DB')
    parser.add_argument('--filedir', help='Path to the files directory')
    parser.add_argument('--dumpdir', help='Path to the directory to dump files')
    args = parser.parse_args()

    db = args.db
    filedir = args.filedir
    dumpdir = args.dumpdir
    dry_run = args.dry_run

    if db is None or filedir is None or dumpdir is None:
        print("Error: Missing required arguments. Please provide values for --db, --filedir, and --dumpdir.")
        sys.exit(1)

    if "--help" in sys.argv:
        print_help()
        sys.exit(0)

    # Rest of the code...
#NOTHING AFTER THIS LINE NEEDS TO BE EDITED
# add a help command to the script to give a manual for usage and parameters
def print_help():
    print("Usage: python restsdk_public.py [options]")
    print("Options:")
    print("  --dry_run     Perform a dry run (do not copy files)")
    print("  --help        Show this help message")

if __name__ == "__main__":
    if "--help" in sys.argv:
        print_help()
        sys.exit(0)
skipnames=[filedir] #remove these strings from the final file/path name. Don't edit this.
import sqlite3
import pprint
import copy
import os
from shutil import copyfile
import argparse
import sys
import argparse
    
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
        #print("Found file " + value['Name'] + 'searching for parents')
        #print('Totalpath is ' + path)
        path=findTree(fileID,value['Name'],value['Parent'])
    else:
        #print("Found file " + value['Name'] + 'no parent search needed')
        path=fileDIC[fileID]['Name']
    return path

def filenameToID(filename):
    #turn a filename from filesystem into a db id
    for keys,values in fileDIC.items():
        if values['contentID']==filename:
            #print('Found filename ' + filename + ' in DBkey ' + str(keys) +' with name ' + values['Name'])
            return str(keys)
    #print('Unable to find filename' + filename)
    return None

def getRootDirs():
    #quick function to find annoying "auth folder" name for filtering purposes
    for keys,values in fileDIC.items():
        if 'auth' in values['Name'] and '|' in values['Name']:
            return str(values['Name'])

#open the sqlite database
print('Opening database...',end="/r")
try:
    con = sqlite3.connect(db)
except:
    print('Error opening database at ' + db)
    quit()
print('Querying database...',end="/r")
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
#how can I modify this function so that I can do a dry run and not actually copy the files?
parser = argparse.ArgumentParser()
parser.add_argument('--dry_run', action='store_true', default=False, help='Perform a dry run')
args = parser.parse_args()

dry_run = args.dry_run

for root, dirs, files in os.walk(filedir):  # find all files in original directory structure
    for file in files:
        filename = str(file)
        print('FOUND FILE ' + filename + ' SEARCHING......', end="\r")
        fileID = filenameToID(str(file))
        fullpath = None
        if fileID != None:
            fullpath = idToPath2(fileID)
        if fullpath != None:
            # print('FILE RESOLVED TO ' + fullpath)
            for paths in skipnames:
                newpath = fullpath.replace(paths, '')
            newpath = dumpdir + newpath
            fullpath = str(os.path.join(root, file))
            if dry_run:
                print('Dry run: Skipping copying ' + fullpath + ' to ' + newpath)
            else:
                # print('Copying ' + fullpath + ' to ' + newpath,end="\r")
                print('Copying ' + newpath)
                try:
                    os.makedirs(os.path.dirname(newpath), exist_ok=True)
                    copyfile(fullpath, newpath)
                except:
                    print('Error copying file ' + fullpath + ' to ' + newpath)

print("Did this script help you recover your data? Save you a few hundred bucks? Or make you some money recovering somebody else's data?")
print("Consider sending us some bitcoin/crypto as a way of saying thanks!")
print("Bitcoin: 1DqSLNR8kTgwq5rvveUFDSbYQnJp9D5gfR")
print("ETH: 0x9e765052283Ce6521E40069Ac52ffA5B277bD8AB")
print("Zcash: t1RetUQktuUBL2kbX72taERb6QcuAiDsvC4")

