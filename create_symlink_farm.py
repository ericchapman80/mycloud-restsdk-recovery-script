#!/usr/bin/env python3
"""
Create a symlink farm from MyCloud SQLite database.

This script creates a directory structure of symbolic links that point to the
original source files but with their correct names and folder hierarchy as
defined in the database. This farm can then be used with rsync to:
1. Copy files to destination with correct structure
2. Verify existing copies against the source
3. Identify missing or extra files

Usage:
    python create_symlink_farm.py --db /path/to/index.db --source /path/to/files --farm /tmp/farm

Then use rsync:
    rsync -avL --progress /tmp/farm/ /mnt/nfs-media/
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_files_from_db(db_path: str) -> Dict[str, dict]:
    """
    Load all file records from the database into a dictionary.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary mapping file_id to file metadata
    """
    file_dic = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, parentID, contentID, name, imageDate, videoDate, cTime, birthTime
            FROM Files
        """)
        for row in cur.fetchall():
            file_dic[row['id']] = {
                'Name': row['name'],
                'Parent': row['parentID'],
                'contentID': row['contentID'],
                'imageDate': row['imageDate'],
                'videoDate': row['videoDate'],
                'cTime': row['cTime'],
                'birthTime': row['birthTime'],
            }
    return file_dic


def find_root_dir_name(file_dic: Dict[str, dict]) -> Optional[str]:
    """
    Find the root directory name that contains 'auth' and '|'.
    This is a special folder name that needs to be stripped from paths.
    
    Args:
        file_dic: Dictionary of file metadata
        
    Returns:
        Root directory name to strip, or None
    """
    for file_id, meta in file_dic.items():
        name = meta.get('Name', '')
        if 'auth' in name and '|' in name:
            return name
    return None


def reconstruct_path(file_id: str, file_dic: Dict[str, dict], root_dir_to_strip: Optional[str] = None) -> Optional[str]:
    """
    Reconstruct the full path for a file by traversing parent references.
    
    Args:
        file_id: ID of the file
        file_dic: Dictionary of file metadata
        root_dir_to_strip: Optional root directory name to strip from path
        
    Returns:
        Reconstructed relative path, or None if file not found
    """
    if file_id not in file_dic:
        return None
    
    meta = file_dic[file_id]
    name = meta.get('Name', '')
    parent_id = meta.get('Parent')
    
    # Build path by traversing parents
    path_parts = [name]
    current_id = parent_id
    
    while current_id is not None and current_id in file_dic:
        parent_meta = file_dic[current_id]
        parent_name = parent_meta.get('Name', '')
        path_parts.insert(0, parent_name)
        current_id = parent_meta.get('Parent')
    
    # Join path parts
    full_path = '/'.join(path_parts)
    
    # Normalize backslashes to forward slashes
    full_path = full_path.replace('\\', '/')
    
    # Strip root directory if specified
    if root_dir_to_strip:
        full_path = full_path.replace(root_dir_to_strip + '/', '')
        full_path = full_path.replace(root_dir_to_strip, '')
    
    # Remove leading slash
    full_path = full_path.lstrip('/')
    
    return full_path if full_path else None


def get_source_file_path(content_id: str, source_dir: str) -> Optional[str]:
    """
    Get the full path to a source file given its content ID.
    Files are stored in sharded directories by first character.
    
    Args:
        content_id: The content ID of the file
        source_dir: Base directory where source files are stored
        
    Returns:
        Full path to the source file, or None if not found
    """
    if not content_id:
        return None
    
    # Files are stored in directories named by first character
    first_char = content_id[0].lower()
    file_path = os.path.join(source_dir, first_char, content_id)
    
    if os.path.exists(file_path):
        return file_path
    
    # Try without sharding (flat directory)
    flat_path = os.path.join(source_dir, content_id)
    if os.path.exists(flat_path):
        return flat_path
    
    return None


def sanitize_path(path: str, sanitize_pipes: bool = False) -> str:
    """
    Sanitize a path for filesystem compatibility.
    
    Args:
        path: Path to sanitize
        sanitize_pipes: Whether to replace | with -
        
    Returns:
        Sanitized path
    """
    if sanitize_pipes:
        path = path.replace('|', '-')
    return path


def create_symlink_farm(
    db_path: str,
    source_dir: str,
    farm_dir: str,
    sanitize_pipes: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> Tuple[int, int, int, int]:
    """
    Create a symlink farm from the database.
    
    Args:
        db_path: Path to SQLite database
        source_dir: Directory containing source files
        farm_dir: Directory to create symlink farm in
        sanitize_pipes: Replace | with - in paths
        dry_run: Don't create symlinks, just report
        verbose: Print verbose output
        
    Returns:
        Tuple of (created, skipped_no_content, skipped_no_source, errors)
    """
    # Load files from database
    print(f"Loading files from database: {db_path}")
    file_dic = load_files_from_db(db_path)
    print(f"Loaded {len(file_dic)} file records")
    
    # Find root directory to strip
    root_dir = find_root_dir_name(file_dic)
    if root_dir:
        print(f"Will strip root directory: {root_dir[:50]}...")
    
    # Statistics
    created = 0
    skipped_no_content = 0
    skipped_no_source = 0
    errors = 0
    
    # Create farm directory
    if not dry_run:
        os.makedirs(farm_dir, exist_ok=True)
    
    total = len(file_dic)
    for i, (file_id, meta) in enumerate(file_dic.items()):
        # Progress
        if (i + 1) % 50000 == 0:
            print(f"Progress: {i + 1}/{total} ({(i + 1) * 100 // total}%)")
        
        content_id = meta.get('contentID')
        
        # Skip directories (no content ID)
        if not content_id:
            skipped_no_content += 1
            continue
        
        # Get source file path
        source_path = get_source_file_path(content_id, source_dir)
        if not source_path:
            skipped_no_source += 1
            if verbose:
                print(f"  [SKIP] No source file for {content_id}")
            continue
        
        # Reconstruct destination path
        rel_path = reconstruct_path(file_id, file_dic, root_dir)
        if not rel_path:
            errors += 1
            if verbose:
                print(f"  [ERROR] Could not reconstruct path for {file_id}")
            continue
        
        # Sanitize path
        rel_path = sanitize_path(rel_path, sanitize_pipes)
        
        # Full path in farm
        farm_path = os.path.join(farm_dir, rel_path)
        
        if dry_run:
            if verbose:
                print(f"  [DRY-RUN] {source_path} -> {farm_path}")
            created += 1
            continue
        
        try:
            # Create parent directories
            os.makedirs(os.path.dirname(farm_path), exist_ok=True)
            
            # Create symlink (remove existing if present)
            if os.path.islink(farm_path):
                os.remove(farm_path)
            elif os.path.exists(farm_path):
                # Real file exists, skip
                if verbose:
                    print(f"  [SKIP] Real file exists: {farm_path}")
                continue
            
            os.symlink(source_path, farm_path)
            created += 1
            
            if verbose:
                print(f"  [LINK] {source_path} -> {farm_path}")
                
        except OSError as e:
            errors += 1
            if verbose:
                print(f"  [ERROR] {e}")
    
    return created, skipped_no_content, skipped_no_source, errors


def main():
    parser = argparse.ArgumentParser(
        description='Create a symlink farm from MyCloud database for rsync verification/copying'
    )
    parser.add_argument('--db', required=True, help='Path to SQLite database (index.db)')
    parser.add_argument('--source', required=True, help='Source directory containing files')
    parser.add_argument('--farm', required=True, help='Output directory for symlink farm')
    parser.add_argument('--sanitize-pipes', action='store_true', help='Replace | with - in paths')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Dry run - do not create symlinks')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.db):
        print(f"Error: Database not found: {args.db}")
        sys.exit(1)
    
    if not os.path.isdir(args.source):
        print(f"Error: Source directory not found: {args.source}")
        sys.exit(1)
    
    if os.path.exists(args.farm) and os.listdir(args.farm):
        print(f"Warning: Farm directory is not empty: {args.farm}")
        response = input("Continue? [y/N] ")
        if response.lower() != 'y':
            sys.exit(0)
    
    print("=" * 60)
    print("Symlink Farm Creator")
    print("=" * 60)
    print(f"Database: {args.db}")
    print(f"Source:   {args.source}")
    print(f"Farm:     {args.farm}")
    print(f"Dry run:  {args.dry_run}")
    print("=" * 60)
    
    created, skipped_no_content, skipped_no_source, errors = create_symlink_farm(
        db_path=args.db,
        source_dir=args.source,
        farm_dir=args.farm,
        sanitize_pipes=args.sanitize_pipes,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    print("=" * 60)
    print("Summary:")
    print(f"  Symlinks created:     {created}")
    print(f"  Skipped (no content): {skipped_no_content} (directories)")
    print(f"  Skipped (no source):  {skipped_no_source}")
    print(f"  Errors:               {errors}")
    print("=" * 60)
    
    if not args.dry_run:
        print("\nNext steps:")
        print(f"  # Verify farm structure:")
        print(f"  find {args.farm} -type l | head -20")
        print(f"")
        print(f"  # Copy to destination with rsync:")
        print(f"  rsync -avL --progress {args.farm}/ /mnt/nfs-media/")
        print(f"")
        print(f"  # Dry-run to see what would be copied:")
        print(f"  rsync -avnL {args.farm}/ /mnt/nfs-media/")
    
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
