#!/usr/bin/env python3
"""
Lightweight mtime synchronization tool.

Updates modification times on destination files to match original timestamps
from the database (imageDate, videoDate, cTime, or birthTime). Designed for
minimal memory usage - processes files one at a time without loading the
entire database into memory.

Usage:
    # Dry run (see what would be updated)
    python sync_mtime.py --db /path/to/index.db --dest /mnt/nfs-media --dry-run
    
    # Actually update mtimes
    python sync_mtime.py --db /path/to/index.db --dest /mnt/nfs-media
    
    # Verbose output
    python sync_mtime.py --db /path/to/index.db --dest /mnt/nfs-media --verbose
    
    # Resume from specific file
    python sync_mtime.py --db /path/to/index.db --dest /mnt/nfs-media --resume-from 1000
"""

import argparse
import datetime
import os
import sqlite3
import sys
import time
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def colorize(text, color):
    """Add color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.ENDC}"
    return text


def format_timestamp(ts_ms):
    """Format millisecond timestamp to readable date."""
    if ts_ms:
        return datetime.datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    return "N/A"


def get_file_info_streaming(db_path):
    """
    Stream file information from database without loading everything into memory.
    
    Yields tuples of (file_id, relative_path, timestamp_ms) for files that have
    been copied (exist in copied_files table).
    
    Args:
        db_path: Path to SQLite database
        
    Yields:
        Tuple of (file_id, relative_path, timestamp_ms)
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    cursor = conn.cursor()
    
    # Query to get copied files with their paths and timestamps
    # Joins copied_files with files table to get metadata
    query = """
        SELECT 
            cf.file_id,
            cf.filename,
            f.imageDate,
            f.videoDate,
            f.cTime,
            f.birthTime
        FROM copied_files cf
        JOIN files f ON cf.file_id = f.id
        ORDER BY CAST(cf.file_id AS INTEGER)
    """
    
    cursor.execute(query)
    
    for row in cursor:
        file_id = row[0]
        relative_path = row[1]
        
        # Priority: imageDate > videoDate > cTime > birthTime
        timestamp_ms = None
        for ts in [row[2], row[3], row[4], row[5]]:
            if ts is not None and isinstance(ts, (int, float)):
                timestamp_ms = ts
                break
        
        yield (file_id, relative_path, timestamp_ms)
    
    conn.close()


def update_mtime(file_path, timestamp_ms, dry_run=False):
    """
    Update file's modification time.
    
    Args:
        file_path: Path to file
        timestamp_ms: Timestamp in milliseconds
        dry_run: If True, don't actually update
        
    Returns:
        Tuple of (success, old_mtime, new_mtime, error_message)
    """
    try:
        old_mtime = os.path.getmtime(file_path)
        new_mtime = timestamp_ms / 1000  # Convert ms to seconds
        
        if not dry_run:
            os.utime(file_path, (new_mtime, new_mtime))
        
        return (True, old_mtime, new_mtime, None)
    except FileNotFoundError:
        return (False, None, None, "File not found")
    except PermissionError:
        return (False, None, None, "Permission denied")
    except Exception as e:
        return (False, None, None, str(e))


def sync_mtimes(db_path, dest_dir, dry_run=False, verbose=False, resume_from=0):
    """
    Synchronize modification times for all copied files.
    
    Args:
        db_path: Path to SQLite database
        dest_dir: Destination directory root
        dry_run: If True, show what would be done without doing it
        verbose: If True, show details for each file
        resume_from: Skip files before this ID (for resuming interrupted runs)
    """
    print(colorize(f"\n{'='*70}", Colors.BOLD))
    print(colorize("  MTIME SYNCHRONIZATION TOOL", Colors.BOLD))
    print(colorize(f"{'='*70}\n", Colors.BOLD))
    
    print(f"Database: {db_path}")
    print(f"Destination: {dest_dir}")
    print(f"Mode: {colorize('DRY RUN', Colors.YELLOW) if dry_run else colorize('LIVE UPDATE', Colors.GREEN)}")
    if resume_from > 0:
        print(f"Resuming from file ID: {resume_from}")
    print()
    
    # Statistics
    stats = {
        'total': 0,
        'updated': 0,
        'skipped_no_timestamp': 0,
        'skipped_not_found': 0,
        'errors': 0,
        'no_change_needed': 0
    }
    
    start_time = time.time()
    last_report_time = start_time
    
    try:
        for file_id, relative_path, timestamp_ms in get_file_info_streaming(db_path):
            stats['total'] += 1
            
            # Skip if before resume point
            if stats['total'] < resume_from:
                continue
            
            # Report progress every 1000 files or 5 seconds
            current_time = time.time()
            if stats['total'] % 1000 == 0 or (current_time - last_report_time) >= 5:
                elapsed = current_time - start_time
                rate = stats['total'] / elapsed if elapsed > 0 else 0
                print(f"\rProgress: {stats['total']} files processed ({rate:.1f} files/sec)...", end='', flush=True)
                last_report_time = current_time
            
            # Skip if no timestamp in database
            if timestamp_ms is None:
                stats['skipped_no_timestamp'] += 1
                if verbose:
                    print(f"  [SKIP] {relative_path} - No timestamp in database")
                continue
            
            # Build full destination path
            dest_path = os.path.join(dest_dir, relative_path)
            
            # Check if file exists
            if not os.path.exists(dest_path):
                stats['skipped_not_found'] += 1
                if verbose:
                    print(colorize(f"  [NOT FOUND] {relative_path}", Colors.YELLOW))
                continue
            
            # Update mtime
            success, old_mtime, new_mtime, error_msg = update_mtime(dest_path, timestamp_ms, dry_run)
            
            if success:
                # Check if change is significant (>1 second difference)
                time_diff = abs(new_mtime - old_mtime)
                if time_diff < 1:
                    stats['no_change_needed'] += 1
                else:
                    stats['updated'] += 1
                    if verbose or time_diff > 86400:  # Always show if >1 day difference
                        old_date = datetime.datetime.fromtimestamp(old_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        new_date = format_timestamp(timestamp_ms)
                        action = colorize("WOULD UPDATE", Colors.YELLOW) if dry_run else colorize("UPDATED", Colors.GREEN)
                        print(f"  [{action}] {relative_path}")
                        print(f"    Old: {old_date}  →  New: {new_date}  (Δ {time_diff/86400:.1f} days)")
            else:
                stats['errors'] += 1
                if verbose:
                    print(colorize(f"  [ERROR] {relative_path} - {error_msg}", Colors.RED))
    
    except KeyboardInterrupt:
        print(colorize("\n\n⚠️  Interrupted by user", Colors.YELLOW))
        print(f"Resume from: --resume-from {stats['total']}")
    
    # Final report
    elapsed = time.time() - start_time
    print(f"\n\n{colorize('='*70, Colors.BOLD)}")
    print(colorize("  SUMMARY", Colors.BOLD))
    print(colorize('='*70, Colors.BOLD))
    print(f"\nTotal files processed:     {stats['total']:,}")
    print(f"  {colorize('✓', Colors.GREEN)} Updated:                {stats['updated']:,}")
    print(f"  • No change needed:       {stats['no_change_needed']:,}")
    print(f"  • Skipped (no timestamp): {stats['skipped_no_timestamp']:,}")
    print(f"  • Skipped (not found):    {stats['skipped_not_found']:,}")
    print(f"  {colorize('✗', Colors.RED)} Errors:                 {stats['errors']:,}")
    print(f"\nElapsed time: {elapsed:.1f} seconds ({stats['total']/elapsed:.1f} files/sec)")
    
    if dry_run:
        print(colorize("\n⚠️  This was a DRY RUN - no files were modified", Colors.YELLOW))
        print("Remove --dry-run to actually update mtimes")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize modification times from database to destination files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be updated
  %(prog)s --db /path/to/index.db --dest /mnt/nfs-media --dry-run
  
  # Actually update modification times
  %(prog)s --db /path/to/index.db --dest /mnt/nfs-media
  
  # Verbose output showing each file
  %(prog)s --db /path/to/index.db --dest /mnt/nfs-media --verbose
  
  # Resume from file 5000 (if interrupted)
  %(prog)s --db /path/to/index.db --dest /mnt/nfs-media --resume-from 5000
"""
    )
    
    parser.add_argument(
        '--db',
        required=True,
        help='Path to SQLite database (index.db)'
    )
    
    parser.add_argument(
        '--dest',
        required=True,
        help='Destination directory root'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually updating files'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show details for each file processed'
    )
    
    parser.add_argument(
        '--resume-from',
        type=int,
        default=0,
        help='Resume from this file number (for interrupted runs)'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.db):
        print(colorize(f"Error: Database not found: {args.db}", Colors.RED))
        sys.exit(1)
    
    if not os.path.exists(args.dest):
        print(colorize(f"Error: Destination directory not found: {args.dest}", Colors.RED))
        sys.exit(1)
    
    # Run sync
    sync_mtimes(args.db, args.dest, args.dry_run, args.verbose, args.resume_from)


if __name__ == '__main__':
    main()
