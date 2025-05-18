import os
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

def disk_speed_test(path, file_size_mb=128):
    test_file = Path(path) / 'preflight_speed_test.tmp'
    data = os.urandom(1024 * 1024)  # 1MB buffer
    start = time.time()
    with open(test_file, 'wb') as f:
        for _ in range(file_size_mb):
            f.write(data)
    write_time = time.time() - start
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

def recommend_thread_count(cpu_count, file_stats):
    # For many small files, more threads help; for large files, fewer threads
    if file_stats['small_files'] > file_stats['medium_files'] + file_stats['large_files']:
        return min(max(4, cpu_count * 2), 32)
    else:
        return min(max(2, cpu_count), 16)

def preflight_summary(source, dest):
    cpu = get_cpu_info()
    mem = get_memory_info()
    disk_src = get_disk_info(source)
    disk_dst = get_disk_info(dest)
    net = get_network_info()
    file_stats = get_file_stats(source)
    disk_speed = disk_speed_test(dest)
    min_MBps = min(disk_speed['write_MBps'], disk_speed['read_MBps'])
    est_min = estimate_duration(file_stats['total_size_GB'], min_MBps)
    thread_count = recommend_thread_count(cpu['cpu_count'], file_stats)
    return {
        'cpu': cpu,
        'memory': mem,
        'disk_src': disk_src,
        'disk_dst': disk_dst,
        'network': net,
        'file_stats': file_stats,
        'disk_speed': disk_speed,
        'est_min': est_min,
        'thread_count': thread_count,
    }

def print_preflight_report(summary, source, dest):
    print("\n🚀  ===== Pre-flight Hardware & File System Check ===== 🚀\n")
    cpu = summary['cpu']
    mem = summary['memory']
    print(f"🖥️  CPU: {cpu['cpu_model']} | Cores: {cpu['cpu_count']} | Freq: {cpu['cpu_freq']} MHz")
    print(f"💾 RAM: {mem['total'] // (1024**3)} GB total | {mem['available'] // (1024**3)} GB available")
    print(f"📂 Source: {source}")
    print(f"  - Size: {summary['file_stats']['total_size_GB']:.2f} GB | Files: {summary['file_stats']['total_files']}")
    print(f"  - Small: {summary['file_stats']['small_files']} | Medium: {summary['file_stats']['medium_files']} | Large: {summary['file_stats']['large_files']}")
    print(f"💽 Dest: {dest}")
    print(f"  - Free: {summary['disk_dst']['free'] // (1024**3)} GB | Total: {summary['disk_dst']['total'] // (1024**3)} GB")
    print(f"⚡ Disk Speed (dest): Write: {summary['disk_speed']['write_MBps']:.1f} MB/s | Read: {summary['disk_speed']['read_MBps']:.1f} MB/s")
    print(f"⏱️  Estimated Duration: {summary['est_min']:.1f} minutes (best case)")
    print(f"🔢 Recommended Threads: {summary['thread_count']}")
    print("\n✨ Recommended Command:")
    cmd = f"python restsdk_public.py --db <path/to/index.db> --filedir {source} --dumpdir {dest} --log_file <path/to/logfile.log> --thread-count {summary['thread_count']}"
    print(f"\n📝 {cmd}\n")
    print("Copy and paste the above command, replacing <...> with your actual file paths!")
    print("\nQuestions? See the README or /docs for help. Happy transferring! 🚚✨\n")
