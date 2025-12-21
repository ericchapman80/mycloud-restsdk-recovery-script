#!/usr/bin/env python3
"""
rsync-based restore tool with monitoring and progress tracking.

This script wraps rsync to provide:
1. Pre-flight stats (sizes, counts, free space)
2. Symlink farm creation (or verification)
3. rsync with progress parsing and monitoring
4. Retry logic for failed files
5. Comprehensive summary

Usage:
    # Full workflow with wizard
    python rsync_restore.py --wizard
    
    # Command-line mode
    python rsync_restore.py \\
        --db /mnt/backupdrive/restsdk/data/db/index.db \\
        --source /mnt/backupdrive/restsdk/data/files \\
        --dest /mnt/nfs-media \\
        --farm /tmp/restore-farm

    # Preflight only
    python rsync_restore.py --preflight-only --source /path --dest /path
"""

import argparse
import datetime
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Try to import preflight for stats
try:
    from preflight import (
        get_cpu_info, get_memory_info, get_disk_info, 
        get_file_stats, disk_speed_test
    )
    HAS_PREFLIGHT = True
except ImportError:
    HAS_PREFLIGHT = False

# Try to import psutil for monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def colorize(text: str, color: str) -> str:
    """Add color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.ENDC}"
    return text


def print_header(text: str):
    print()
    print(colorize("=" * 60, Colors.CYAN))
    print(colorize(f"  {text}", Colors.BOLD + Colors.CYAN))
    print(colorize("=" * 60, Colors.CYAN))
    print()


def print_success(text: str):
    print(colorize(f"✅ {text}", Colors.GREEN))


def print_warning(text: str):
    print(colorize(f"⚠️  {text}", Colors.YELLOW))


def print_error(text: str):
    print(colorize(f"❌ {text}", Colors.RED))


def print_info(text: str):
    print(colorize(f"ℹ️  {text}", Colors.BLUE))


def format_bytes(n: int) -> str:
    """Format bytes in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PB"


def format_number(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins, secs = divmod(int(seconds), 60)
        return f"{mins}m {secs}s"
    else:
        hours, remainder = divmod(int(seconds), 3600)
        mins, secs = divmod(remainder, 60)
        return f"{hours}h {mins}m {secs}s"


def get_db_stats(db_path: str) -> Dict:
    """Get file statistics from the database."""
    stats = {
        'total_files': 0,
        'total_dirs': 0,
        'copied_files': 0,
        'skipped_files': 0,
    }
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.cursor()
        
        # Total files (entries with contentID)
        cur.execute("SELECT COUNT(*) FROM files WHERE contentID IS NOT NULL")
        stats['total_files'] = cur.fetchone()[0]
        
        # Total directories
        cur.execute("SELECT COUNT(*) FROM files WHERE contentID IS NULL")
        stats['total_dirs'] = cur.fetchone()[0]
        
        # Check if tracking tables exist
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='copied_files'")
        if cur.fetchone():
            cur.execute("SELECT COUNT(*) FROM copied_files")
            stats['copied_files'] = cur.fetchone()[0]
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='skipped_files'")
        if cur.fetchone():
            cur.execute("SELECT COUNT(*) FROM skipped_files")
            stats['skipped_files'] = cur.fetchone()[0]
    
    stats['remaining'] = stats['total_files'] - stats['copied_files'] - stats['skipped_files']
    stats['percent_complete'] = (stats['copied_files'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
    
    return stats


def count_files_in_dir(path: str) -> Tuple[int, int]:
    """Count files and get total size in a directory."""
    total_files = 0
    total_size = 0
    for root, dirs, files in os.walk(path):
        total_files += len(files)
        for f in files:
            try:
                total_size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total_files, total_size


def run_preflight(source: str, dest: str, db_path: Optional[str] = None, farm: Optional[str] = None) -> Dict:
    """Run preflight checks and gather statistics."""
    print_header("Pre-flight Checks")
    
    results = {
        'source': source,
        'dest': dest,
        'db_path': db_path,
        'farm': farm,
        'checks_passed': True,
        'warnings': [],
    }
    
    # Check source exists
    if os.path.isdir(source):
        print_success(f"Source directory exists: {source}")
        src_files, src_size = count_files_in_dir(source)
        results['source_files'] = src_files
        results['source_size'] = src_size
        print_info(f"  Files: {format_number(src_files)} | Size: {format_bytes(src_size)}")
    else:
        print_error(f"Source directory not found: {source}")
        results['checks_passed'] = False
        return results
    
    # Check destination
    if os.path.isdir(dest):
        print_success(f"Destination directory exists: {dest}")
        dest_files, dest_size = count_files_in_dir(dest)
        results['dest_files'] = dest_files
        results['dest_size'] = dest_size
        print_info(f"  Files: {format_number(dest_files)} | Size: {format_bytes(dest_size)}")
        
        # Check free space
        if HAS_PSUTIL:
            usage = psutil.disk_usage(dest)
            results['dest_free'] = usage.free
            print_info(f"  Free space: {format_bytes(usage.free)}")
            
            # Warn if free space is low
            estimated_remaining = src_size - dest_size
            if estimated_remaining > 0 and usage.free < estimated_remaining * 1.1:
                print_warning(f"Low free space! May need {format_bytes(estimated_remaining)}")
                results['warnings'].append('low_free_space')
    else:
        print_warning(f"Destination directory will be created: {dest}")
        results['dest_files'] = 0
        results['dest_size'] = 0
    
    # Check database
    if db_path:
        if os.path.isfile(db_path):
            print_success(f"Database found: {db_path}")
            db_stats = get_db_stats(db_path)
            results['db_stats'] = db_stats
            print_info(f"  Total files in DB: {format_number(db_stats['total_files'])}")
            print_info(f"  Already copied: {format_number(db_stats['copied_files'])} ({db_stats['percent_complete']:.1f}%)")
            print_info(f"  Remaining: {format_number(db_stats['remaining'])}")
        else:
            print_error(f"Database not found: {db_path}")
            results['checks_passed'] = False
    
    # Check symlink farm
    if farm:
        if os.path.isdir(farm):
            farm_files, _ = count_files_in_dir(farm)
            print_success(f"Symlink farm exists: {farm}")
            print_info(f"  Symlinks: {format_number(farm_files)}")
            results['farm_files'] = farm_files
        else:
            print_info(f"Symlink farm will be created: {farm}")
            results['farm_files'] = 0
    
    # Check rsync
    rsync_path = shutil.which('rsync')
    if rsync_path:
        print_success(f"rsync found: {rsync_path}")
        results['rsync_path'] = rsync_path
    else:
        print_error("rsync not found! Please install rsync.")
        results['checks_passed'] = False
    
    # System stats
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        print_info(f"Memory: {mem.percent:.1f}% used ({format_bytes(mem.available)} available)")
        results['memory_percent'] = mem.percent
        results['memory_available'] = mem.available
        
        load = os.getloadavg()
        print_info(f"Load average: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}")
        results['load_avg'] = load
    
    return results


class RsyncMonitor:
    """Monitor rsync progress and system health."""
    
    def __init__(self, log_file: str, log_interval: int = 60):
        self.log_file = log_file
        self.log_interval = log_interval
        self.running = False
        self.thread = None
        self.start_time = None
        
        # Progress tracking
        self.bytes_transferred = 0
        self.files_transferred = 0
        self.percent_complete = 0
        self.transfer_speed = 0
        self.eta = ""
        self.current_file = ""
        self.errors: List[str] = []
        
        # Lock for thread-safe updates
        self.lock = threading.Lock()
    
    def start(self):
        """Start the monitoring thread."""
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
        # Write header to log file
        with open(self.log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"rsync restore started: {datetime.datetime.now()}\n")
            f.write(f"{'='*60}\n\n")
    
    def stop(self):
        """Stop the monitoring thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def update_progress(self, bytes_transferred: int = None, files_transferred: int = None,
                       percent: float = None, speed: float = None, eta: str = None,
                       current_file: str = None):
        """Update progress from rsync output parsing."""
        with self.lock:
            if bytes_transferred is not None:
                self.bytes_transferred = bytes_transferred
            if files_transferred is not None:
                self.files_transferred = files_transferred
            if percent is not None:
                self.percent_complete = percent
            if speed is not None:
                self.transfer_speed = speed
            if eta is not None:
                self.eta = eta
            if current_file is not None:
                self.current_file = current_file
    
    def add_error(self, error: str):
        """Record an error."""
        with self.lock:
            self.errors.append(error)
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            self._log_status()
            time.sleep(self.log_interval)
    
    def _log_status(self):
        """Log current status to file and stdout."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # Get system stats
        mem_pct = "N/A"
        load = "N/A"
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            mem_pct = f"{mem.percent:.1f}%"
            load_avg = os.getloadavg()
            load = f"{load_avg[0]:.2f} {load_avg[1]:.2f} {load_avg[2]:.2f}"
        
        with self.lock:
            status_line = (
                f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"Files: {format_number(self.files_transferred)} | "
                f"Data: {format_bytes(self.bytes_transferred)} | "
                f"{self.percent_complete:.1f}% | "
                f"Speed: {format_bytes(int(self.transfer_speed))}/s | "
                f"ETA: {self.eta} | "
                f"Mem: {mem_pct} | "
                f"Load: {load}"
            )
        
        print(status_line)
        
        with open(self.log_file, 'a') as f:
            f.write(status_line + '\n')


def parse_rsync_progress(line: str, monitor: RsyncMonitor):
    """Parse rsync --info=progress2 output and update monitor."""
    # Format: "1,234,567,890  45%   12.34MB/s    1:23:45"
    # Or: "          1,234  100%   12.34MB/s    0:00:00 (xfr#123, to-chk=456/789)"
    
    progress_match = re.search(
        r'([\d,]+)\s+(\d+)%\s+([\d.]+)([KMG]?)B/s\s+(\d+:\d+:\d+|\d+:\d+)',
        line
    )
    
    if progress_match:
        bytes_str = progress_match.group(1).replace(',', '')
        percent = int(progress_match.group(2))
        speed_num = float(progress_match.group(3))
        speed_unit = progress_match.group(4)
        eta = progress_match.group(5)
        
        # Convert speed to bytes/s
        speed_multiplier = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3}
        speed = speed_num * speed_multiplier.get(speed_unit, 1)
        
        monitor.update_progress(
            bytes_transferred=int(bytes_str),
            percent=percent,
            speed=speed,
            eta=eta
        )
    
    # Count transferred files
    xfr_match = re.search(r'xfr#(\d+)', line)
    if xfr_match:
        monitor.update_progress(files_transferred=int(xfr_match.group(1)))
    
    # Check for errors
    if 'error' in line.lower() or 'failed' in line.lower():
        monitor.add_error(line.strip())


def run_rsync(
    source: str,
    dest: str,
    monitor: RsyncMonitor,
    checksum: bool = True,
    dry_run: bool = False,
    delete: bool = False,
    exclude: List[str] = None
) -> Tuple[int, List[str]]:
    """
    Run rsync with progress monitoring.
    
    Returns:
        Tuple of (return_code, list_of_errors)
    """
    # Build rsync command
    cmd = ['rsync', '-avL', '--info=progress2']
    
    if checksum:
        cmd.append('--checksum')
    
    if dry_run:
        cmd.append('--dry-run')
    
    if delete:
        cmd.append('--delete')
    
    if exclude:
        for pattern in exclude:
            cmd.extend(['--exclude', pattern])
    
    # Ensure source ends with / to copy contents
    if not source.endswith('/'):
        source = source + '/'
    
    cmd.extend([source, dest])
    
    print_info(f"Running: {' '.join(cmd)}")
    print()
    
    errors = []
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        for line in process.stdout:
            line = line.strip()
            if line:
                parse_rsync_progress(line, monitor)
                
                # Check for errors
                if 'error' in line.lower() or 'failed' in line.lower():
                    errors.append(line)
                    print_warning(line)
        
        process.wait()
        return process.returncode, errors
        
    except KeyboardInterrupt:
        print_warning("\nInterrupted by user")
        process.terminate()
        return 130, errors
    except Exception as e:
        print_error(f"rsync failed: {e}")
        errors.append(str(e))
        return 1, errors


def create_symlink_farm_streaming(
    db_path: str,
    source_dir: str,
    farm_dir: str,
    sanitize_pipes: bool = False
) -> Tuple[int, int, int]:
    """
    Create symlink farm by streaming from database (minimal memory).
    
    Returns:
        Tuple of (created, skipped, errors)
    """
    print_info("Creating symlink farm (streaming from database)...")
    
    created = 0
    skipped = 0
    errors = 0
    
    os.makedirs(farm_dir, exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get total count for progress
        cur.execute("SELECT COUNT(*) FROM files WHERE contentID IS NOT NULL")
        total = cur.fetchone()[0]
        
        # Find root dir to strip
        cur.execute("SELECT name FROM files WHERE name LIKE '%auth%|%' LIMIT 1")
        row = cur.fetchone()
        root_dir = row['name'] if row else None
        
        # Stream files and create symlinks
        cur.execute("""
            SELECT id, name, parentID, contentID 
            FROM files 
            WHERE contentID IS NOT NULL
        """)
        
        # Build minimal parent lookup (just id -> name, parent)
        parent_lookup = {}
        cur2 = conn.cursor()
        cur2.execute("SELECT id, name, parentID FROM files")
        for row in cur2:
            parent_lookup[row['id']] = (row['name'], row['parentID'])
        
        processed = 0
        last_progress = 0
        
        for row in cur:
            processed += 1
            
            # Progress every 5%
            pct = int(processed / total * 100)
            if pct >= last_progress + 5:
                print(f"  Progress: {pct}% ({format_number(processed)}/{format_number(total)})")
                last_progress = pct
            
            content_id = row['contentID']
            file_id = row['id']
            
            # Reconstruct path
            path_parts = [row['name']]
            current_id = row['parentID']
            while current_id and current_id in parent_lookup:
                name, parent_id = parent_lookup[current_id]
                path_parts.insert(0, name)
                current_id = parent_id
            
            rel_path = '/'.join(path_parts)
            
            # Strip root dir
            if root_dir:
                rel_path = rel_path.replace(root_dir + '/', '').replace(root_dir, '')
            rel_path = rel_path.lstrip('/')
            
            if sanitize_pipes:
                rel_path = rel_path.replace('|', '-')
            
            if not rel_path:
                skipped += 1
                continue
            
            # Find source file
            source_path = None
            for candidate in [
                os.path.join(source_dir, content_id[0], content_id),
                os.path.join(source_dir, content_id)
            ]:
                if os.path.exists(candidate):
                    source_path = candidate
                    break
            
            if not source_path:
                skipped += 1
                continue
            
            # Create symlink
            farm_path = os.path.join(farm_dir, rel_path)
            
            try:
                os.makedirs(os.path.dirname(farm_path), exist_ok=True)
                
                if os.path.islink(farm_path):
                    os.remove(farm_path)
                elif os.path.exists(farm_path):
                    skipped += 1
                    continue
                
                os.symlink(source_path, farm_path)
                created += 1
                
            except OSError as e:
                errors += 1
        
        # Clear parent lookup to free memory
        del parent_lookup
    
    print_success(f"Created {format_number(created)} symlinks")
    if skipped > 0:
        print_info(f"Skipped {format_number(skipped)} (no source or duplicate)")
    if errors > 0:
        print_warning(f"Errors: {format_number(errors)}")
    
    return created, skipped, errors


def run_restore(
    db_path: str,
    source: str,
    dest: str,
    farm: str,
    checksum: bool = True,
    dry_run: bool = False,
    retry_count: int = 3,
    log_interval: int = 60,
    log_file: str = "rsync_restore.log",
    sanitize_pipes: bool = False,
    skip_farm: bool = False
) -> int:
    """
    Run the full restore process.
    
    Returns:
        Exit code (0 = success)
    """
    start_time = time.time()
    
    # Preflight checks
    preflight = run_preflight(source, dest, db_path, farm)
    if not preflight['checks_passed']:
        print_error("Pre-flight checks failed. Please fix the issues above.")
        return 1
    
    # Create/verify symlink farm
    if not skip_farm:
        print_header("Symlink Farm")
        
        if os.path.isdir(farm) and os.listdir(farm):
            farm_files, _ = count_files_in_dir(farm)
            print_info(f"Existing farm found with {format_number(farm_files)} symlinks")
            
            # Check if farm is up to date
            if 'db_stats' in preflight:
                expected = preflight['db_stats']['total_files']
                if farm_files < expected * 0.9:
                    print_warning(f"Farm may be incomplete (expected ~{format_number(expected)})")
                    response = input("Rebuild farm? [y/N]: ").strip().lower()
                    if response == 'y':
                        print_info("Removing old farm...")
                        shutil.rmtree(farm)
                        created, skipped, errors = create_symlink_farm_streaming(
                            db_path, source, farm, sanitize_pipes
                        )
        else:
            created, skipped, errors = create_symlink_farm_streaming(
                db_path, source, farm, sanitize_pipes
            )
    else:
        print_info("Skipping symlink farm (--skip-farm)")
    
    # Start monitoring
    print_header("Starting rsync")
    monitor = RsyncMonitor(log_file, log_interval)
    monitor.start()
    
    try:
        # Run rsync
        return_code, errors = run_rsync(
            source=farm,
            dest=dest,
            monitor=monitor,
            checksum=checksum,
            dry_run=dry_run
        )
        
        # Retry failed files if any
        if errors and retry_count > 0 and not dry_run:
            print_header(f"Retrying {len(errors)} failed items")
            for attempt in range(retry_count):
                print_info(f"Retry attempt {attempt + 1}/{retry_count}")
                return_code, errors = run_rsync(
                    source=farm,
                    dest=dest,
                    monitor=monitor,
                    checksum=checksum,
                    dry_run=False
                )
                if not errors:
                    print_success("All retries successful")
                    break
        
    finally:
        monitor.stop()
    
    # Summary
    elapsed = time.time() - start_time
    
    print_header("Summary")
    print(f"  Started:          {datetime.datetime.fromtimestamp(start_time)}")
    print(f"  Finished:         {datetime.datetime.now()}")
    print(f"  Duration:         {format_duration(elapsed)}")
    print(f"  Files transferred: {format_number(monitor.files_transferred)}")
    print(f"  Data transferred: {format_bytes(monitor.bytes_transferred)}")
    
    if elapsed > 0:
        avg_speed = monitor.bytes_transferred / elapsed
        print(f"  Average speed:    {format_bytes(int(avg_speed))}/s")
    
    if monitor.errors:
        print_warning(f"  Errors:           {len(monitor.errors)}")
        print()
        print("Error details:")
        for err in monitor.errors[:10]:
            print(f"  - {err}")
        if len(monitor.errors) > 10:
            print(f"  ... and {len(monitor.errors) - 10} more (see {log_file})")
    else:
        print_success("  Errors:           0")
    
    print()
    print_info(f"Full log written to: {log_file}")
    
    return 0 if return_code == 0 and not monitor.errors else 1


def main():
    parser = argparse.ArgumentParser(
        description='rsync-based restore with monitoring and progress tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full restore with defaults
  python rsync_restore.py --db index.db --source /files --dest /nfs --farm /tmp/farm
  
  # Preflight only
  python rsync_restore.py --preflight-only --source /files --dest /nfs
  
  # Dry run (see what would be copied)
  python rsync_restore.py --db index.db --source /files --dest /nfs --farm /tmp/farm --dry-run
  
  # Skip checksum for faster transfer (less safe)
  python rsync_restore.py --db index.db --source /files --dest /nfs --farm /tmp/farm --no-checksum
"""
    )
    
    # Required arguments
    parser.add_argument('--db', help='Path to SQLite database (index.db)')
    parser.add_argument('--source', help='Source directory containing files')
    parser.add_argument('--dest', help='Destination directory')
    parser.add_argument('--farm', help='Symlink farm directory')
    
    # Options
    parser.add_argument('--preflight-only', action='store_true',
                       help='Run preflight checks only, do not copy')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='Dry run - show what would be copied')
    parser.add_argument('--no-checksum', action='store_true',
                       help='Skip checksum verification (faster but less safe)')
    parser.add_argument('--retry-count', type=int, default=3,
                       help='Number of retries for failed files (default: 3)')
    parser.add_argument('--log-interval', type=int, default=60,
                       help='Progress log interval in seconds (default: 60)')
    parser.add_argument('--log-file', default='rsync_restore.log',
                       help='Log file path (default: rsync_restore.log)')
    parser.add_argument('--sanitize-pipes', action='store_true',
                       help='Replace | with - in paths')
    parser.add_argument('--skip-farm', action='store_true',
                       help='Skip symlink farm creation (use existing)')
    
    args = parser.parse_args()
    
    # Preflight only mode
    if args.preflight_only:
        if not args.source or not args.dest:
            print_error("--preflight-only requires --source and --dest")
            return 1
        preflight = run_preflight(args.source, args.dest, args.db, args.farm)
        return 0 if preflight['checks_passed'] else 1
    
    # Full restore - validate required args
    if not args.db or not args.source or not args.dest or not args.farm:
        print_error("Missing required arguments. Need: --db, --source, --dest, --farm")
        parser.print_help()
        return 1
    
    # Run restore
    return run_restore(
        db_path=args.db,
        source=args.source,
        dest=args.dest,
        farm=args.farm,
        checksum=not args.no_checksum,
        dry_run=args.dry_run,
        retry_count=args.retry_count,
        log_interval=args.log_interval,
        log_file=args.log_file,
        sanitize_pipes=args.sanitize_pipes,
        skip_farm=args.skip_farm
    )


if __name__ == '__main__':
    sys.exit(main())
