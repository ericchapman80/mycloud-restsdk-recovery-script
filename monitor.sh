#!/bin/bash
# Monitor script for restsdk copy operations
# Run alongside the main script to track system health and catch issues early

LOGFILE="${1:-/home/chapman/projects/mycloud-restsdk-recovery-script/monitor.log}"
INTERVAL="${2:-30}"  # seconds between checks
NFS_MOUNT="/mnt/nfs-media"
DB_PATH="/mnt/backupdrive/restsdk/data/db/index.db"

echo "=== Monitor Started: $(date) ===" | tee -a "$LOGFILE"
echo "Logging to: $LOGFILE (interval: ${INTERVAL}s)" | tee -a "$LOGFILE"
echo ""

check_count=0

while true; do
    check_count=$((check_count + 1))
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Memory usage
    mem_info=$(free -m | awk 'NR==2{printf "%.1f%% (%dMB/%dMB)", $3*100/$2, $3, $2}')
    
    # Load average
    load=$(cat /proc/loadavg | awk '{print $1, $2, $3}')
    
    # Open file descriptors for python processes
    fd_count=$(ls /proc/*/fd 2>/dev/null | wc -l)
    python_fd=$(lsof -c python 2>/dev/null | wc -l)
    
    # NFS mount status
    nfs_status="OK"
    if ! mountpoint -q "$NFS_MOUNT" 2>/dev/null; then
        nfs_status="UNMOUNTED!"
    elif ! timeout 5 ls "$NFS_MOUNT" >/dev/null 2>&1; then
        nfs_status="STALLED!"
    fi
    
    # Copied files count (with timeout to avoid blocking)
    copied_count="N/A"
    if [ -f "$DB_PATH" ]; then
        copied_count=$(timeout 5 sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM copied_files" 2>/dev/null || echo "DB_LOCKED")
    fi
    
    # Disk I/O wait
    iowait=$(iostat -c 1 2 2>/dev/null | tail -1 | awk '{print $4}' || echo "N/A")
    
    # Process status
    script_running=$(pgrep -f "restsdk_public.py" >/dev/null && echo "RUNNING" || echo "STOPPED")
    
    # Log entry
    log_entry="[$timestamp] #$check_count | Script: $script_running | NFS: $nfs_status | Mem: $mem_info | Load: $load | FDs: $python_fd | IOWait: ${iowait}% | Copied: $copied_count"
    
    echo "$log_entry" | tee -a "$LOGFILE"
    
    # Alerts
    if [ "$nfs_status" = "STALLED!" ]; then
        echo "  ⚠️  ALERT: NFS appears stalled! Check mount." | tee -a "$LOGFILE"
    fi
    
    if [ "$script_running" = "STOPPED" ]; then
        echo "  ⚠️  ALERT: Script is not running!" | tee -a "$LOGFILE"
    fi
    
    # Check for high memory usage (>90%)
    mem_pct=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$mem_pct" -gt 90 ] 2>/dev/null; then
        echo "  ⚠️  ALERT: Memory usage critical: ${mem_pct}%!" | tee -a "$LOGFILE"
    fi
    
    sleep "$INTERVAL"
done
