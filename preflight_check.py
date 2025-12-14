import os
import sys
import platform
import psutil
import shutil
import socket
import time
from pathlib import Path


def get_cpu_info():
    cpu_count = os.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_model = platform.processor() or platform.uname().processor
    return {
        'cpu_count': cpu_count,
        'cpu_freq': cpu_freq.current if cpu_freq else None,
        'cpu_model': cpu_model,
    }

def get_memory_info():
    mem = psutil.virtual_memory()
    return {
        'total': mem.total,
        'available': mem.available,
        'used': mem.used,
        'percent': mem.percent,
    }

def get_disk_info(path):
    usage = psutil.disk_usage(path)
    return {
        'total': usage.total,
        'used': usage.used,
        'free': usage.free,
        'percent': usage.percent,
        'filesystem': platform.system() == 'Windows' and os.path.splitdrive(path)[0] or shutil.disk_usage(path),
    }

def get_network_info():
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    interfaces = {}
    for iface, addr_list in addrs.items():
        iface_stats = stats.get(iface, None)
        interfaces[iface] = {
            'isup': iface_stats.isup if iface_stats else None,
            'speed': iface_stats.speed if iface_stats else None,
            'addresses': [a.address for a in addr_list if a.family in (socket.AF_INET, socket.AF_INET6)],
        }
    return interfaces

def disk_speed_test(path, file_size_mb=256):
    # Write test
    test_file = Path(path) / 'preflight_speed_test.tmp'
    data = os.urandom(1024 * 1024)  # 1MB buffer
    start = time.time()
    with open(test_file, 'wb') as f:
        for _ in range(file_size_mb):
            f.write(data)
    write_time = time.time() - start
    # Read test
    start = time.time()
    with open(test_file, 'rb') as f:
        while f.read(1024 * 1024):
            pass
    read_time = time.time() - start
    os.remove(test_file)
    return {
        'write_MBps': file_size_mb / write_time,
        'read_MBps': file_size_mb / read_time,
    }

def get_file_stats(directory):
    total_files = 0
    total_size = 0
    small = 0
    medium = 0
    large = 0
    for root, _, files in os.walk(directory):
        for file in files:
            try:
                fp = os.path.join(root, file)
                size = os.path.getsize(fp)
                total_files += 1
                total_size += size
                if size < 1 * 1024 * 1024:
                    small += 1
                elif size < 100 * 1024 * 1024:
                    medium += 1
                else:
                    large += 1
            except Exception:
                continue
    return {
        'total_files': total_files,
        'total_size_GB': total_size / (1024 ** 3),
        'small_files': small,
        'medium_files': medium,
        'large_files': large,
    }

def estimate_duration(total_size_gb, min_MBps):
    if min_MBps <= 0:
        return float('inf')
    total_MB = total_size_gb * 1024
    return total_MB / min_MBps / 60  # in minutes

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Pre-flight hardware and file system check for file transfer optimization.')
    parser.add_argument('--source', required=True, help='Source directory to analyze')
    parser.add_argument('--dest', required=True, help='Destination directory for speed test')
    args = parser.parse_args()

    print('===== CPU Info =====')
    print(get_cpu_info())
    print('\n===== Memory Info =====')
    print(get_memory_info())
    print('\n===== Source Disk Info =====')
    print(get_disk_info(args.source))
    print('\n===== Destination Disk Info =====')
    print(get_disk_info(args.dest))
    print('\n===== Network Info =====')
    print(get_network_info())

    print('\n===== Disk Speed Test (Destination) =====')
    disk_speed = disk_speed_test(args.dest)
    print(disk_speed)

    print('\n===== File Stats (Source) =====')
    file_stats = get_file_stats(args.source)
    print(file_stats)

    min_MBps = min(disk_speed['write_MBps'], disk_speed['read_MBps'])
    est_min = estimate_duration(file_stats['total_size_GB'], min_MBps)
    print(f"\n===== Estimated Duration (best case, minutes) =====\n{est_min:.1f} min")
    print('\nRecommended thread count:')
    # Heuristic: 2-4 threads per physical core, but limit based on disk/network speed
    cpu = get_cpu_info()
    rec_threads = min(max(2, cpu['cpu_count'] * 2), 32)
    print(f"{rec_threads} (adjust based on observed throughput)")

if __name__ == '__main__':
    main()
