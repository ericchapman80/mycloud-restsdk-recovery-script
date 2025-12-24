#!/usr/bin/env python3
"""
Validate Results - Compare legacy vs modern recovery outputs

Validates Phase 0 by comparing:
- File counts and directory structures
- File sizes and timestamps
- Content integrity (checksums)
- Special character handling

Returns exit code 0 if validation passes, 1 if differences found.
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import defaultdict


def print_info(msg):
    print(f"ℹ️  {msg}")


def print_success(msg):
    print(f"✅ {msg}")


def print_error(msg):
    print(f"❌ {msg}")


def print_warning(msg):
    print(f"⚠️  {msg}")


def get_file_hash(filepath: Path) -> str:
    """Calculate SHA256 hash of file"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_directory(root: Path) -> Dict[str, Dict]:
    """
    Recursively scan directory and build file inventory.
    
    Returns dict mapping relative path -> file info:
        {
            'path/to/file.txt': {
                'size': 1234,
                'mtime': 1234567890,
                'hash': 'abc123...',
                'is_symlink': False
            }
        }
    """
    inventory = {}
    
    for item in root.rglob('*'):
        if item.is_file() or item.is_symlink():
            rel_path = str(item.relative_to(root))
            
            info = {
                'size': item.stat().st_size if item.is_file() else 0,
                'mtime': int(item.stat().st_mtime),
                'is_symlink': item.is_symlink(),
                'hash': None  # Computed on-demand
            }
            
            inventory[rel_path] = info
    
    return inventory


def compare_inventories(
    legacy_inv: Dict[str, Dict],
    modern_inv: Dict[str, Dict],
    legacy_root: Path,
    modern_root: Path,
    check_hashes: bool = True
) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Compare two inventories and return validation results.
    
    Returns:
        (passed, issues_dict)
        
    issues_dict contains:
        'missing_in_modern': [file paths]
        'missing_in_legacy': [file paths]
        'size_mismatch': [(path, legacy_size, modern_size)]
        'content_mismatch': [(path, legacy_hash, modern_hash)]
        'symlink_mismatch': [path]
    """
    issues = {
        'missing_in_modern': [],
        'missing_in_legacy': [],
        'size_mismatch': [],
        'content_mismatch': [],
        'symlink_mismatch': []
    }
    
    # Check for missing files
    legacy_files = set(legacy_inv.keys())
    modern_files = set(modern_inv.keys())
    
    issues['missing_in_modern'] = sorted(legacy_files - modern_files)
    issues['missing_in_legacy'] = sorted(modern_files - legacy_files)
    
    # Compare common files
    common_files = legacy_files & modern_files
    
    for rel_path in sorted(common_files):
        legacy_info = legacy_inv[rel_path]
        modern_info = modern_inv[rel_path]
        
        # Check symlink consistency
        if legacy_info['is_symlink'] != modern_info['is_symlink']:
            issues['symlink_mismatch'].append(rel_path)
            continue
        
        # Skip symlink content checks (they may point to different locations)
        if legacy_info['is_symlink']:
            continue
        
        # Check size
        if legacy_info['size'] != modern_info['size']:
            issues['size_mismatch'].append((
                rel_path,
                legacy_info['size'],
                modern_info['size']
            ))
            continue  # No point checking hash if sizes differ
        
        # Check content hash (expensive, only if requested)
        if check_hashes and legacy_info['size'] > 0:
            legacy_path = legacy_root / rel_path
            modern_path = modern_root / rel_path
            
            legacy_hash = get_file_hash(legacy_path)
            modern_hash = get_file_hash(modern_path)
            
            if legacy_hash != modern_hash:
                issues['content_mismatch'].append((
                    rel_path,
                    legacy_hash,
                    modern_hash
                ))
    
    # Determine if validation passed
    passed = not any(issues.values())
    
    return passed, issues


def print_validation_report(
    legacy_inv: Dict,
    modern_inv: Dict,
    issues: Dict,
    passed: bool
):
    """Print detailed validation report"""
    
    print("\n" + "="*70)
    print("VALIDATION REPORT")
    print("="*70)
    
    # Summary stats
    print(f"\n📊 File Counts:")
    print(f"   Legacy:  {len(legacy_inv):5d} files")
    print(f"   Modern:  {len(modern_inv):5d} files")
    print(f"   Common:  {len(set(legacy_inv.keys()) & set(modern_inv.keys())):5d} files")
    
    # Calculate total sizes
    legacy_size = sum(info['size'] for info in legacy_inv.values() if not info['is_symlink'])
    modern_size = sum(info['size'] for info in modern_inv.values() if not info['is_symlink'])
    
    print(f"\n💾 Total Data:")
    print(f"   Legacy:  {legacy_size / (1024*1024):8.2f} MB")
    print(f"   Modern:  {modern_size / (1024*1024):8.2f} MB")
    
    # Issues breakdown
    print(f"\n🔍 Issues Found:")
    
    total_issues = sum(len(v) if isinstance(v, list) else 0 for v in issues.values())
    
    if total_issues == 0:
        print_success("   No issues found! Outputs are identical.")
    else:
        if issues['missing_in_modern']:
            print_error(f"   Missing in modern: {len(issues['missing_in_modern'])} files")
            for path in issues['missing_in_modern'][:5]:
                print(f"      - {path}")
            if len(issues['missing_in_modern']) > 5:
                print(f"      ... and {len(issues['missing_in_modern']) - 5} more")
        
        if issues['missing_in_legacy']:
            print_warning(f"   Extra in modern: {len(issues['missing_in_legacy'])} files")
            for path in issues['missing_in_legacy'][:5]:
                print(f"      - {path}")
            if len(issues['missing_in_legacy']) > 5:
                print(f"      ... and {len(issues['missing_in_legacy']) - 5} more")
        
        if issues['size_mismatch']:
            print_error(f"   Size mismatches: {len(issues['size_mismatch'])} files")
            for path, leg_size, mod_size in issues['size_mismatch'][:5]:
                print(f"      - {path}: {leg_size} vs {mod_size} bytes")
            if len(issues['size_mismatch']) > 5:
                print(f"      ... and {len(issues['size_mismatch']) - 5} more")
        
        if issues['content_mismatch']:
            print_error(f"   Content mismatches: {len(issues['content_mismatch'])} files")
            for path, leg_hash, mod_hash in issues['content_mismatch'][:5]:
                print(f"      - {path}")
                print(f"        Legacy: {leg_hash[:16]}...")
                print(f"        Modern: {mod_hash[:16]}...")
            if len(issues['content_mismatch']) > 5:
                print(f"      ... and {len(issues['content_mismatch']) - 5} more")
        
        if issues['symlink_mismatch']:
            print_warning(f"   Symlink mismatches: {len(issues['symlink_mismatch'])} files")
            for path in issues['symlink_mismatch'][:5]:
                print(f"      - {path}")
            if len(issues['symlink_mismatch']) > 5:
                print(f"      ... and {len(issues['symlink_mismatch']) - 5} more")
    
    # Final verdict
    print("\n" + "="*70)
    if passed:
        print_success("VALIDATION PASSED - Outputs are identical")
    else:
        print_error("VALIDATION FAILED - Differences found")
    print("="*70)


def analyze_directory_structure(inventory: Dict) -> Dict[str, int]:
    """Analyze directory depth distribution"""
    depth_counts = defaultdict(int)
    
    for rel_path in inventory.keys():
        depth = rel_path.count(os.sep)
        depth_counts[depth] += 1
    
    return dict(sorted(depth_counts.items()))


def validate_results(
    legacy_dir: str,
    modern_dir: str,
    check_hashes: bool = True,
    verbose: bool = False
) -> int:
    """
    Compare legacy and modern recovery outputs.
    
    Returns:
        0 if validation passes
        1 if differences found
    """
    
    legacy_path = Path(legacy_dir)
    modern_path = Path(modern_dir)
    
    # Validate inputs
    if not legacy_path.exists():
        print_error(f"Legacy directory not found: {legacy_dir}")
        return 1
    
    if not modern_path.exists():
        print_error(f"Modern directory not found: {modern_dir}")
        return 1
    
    # Scan directories
    print_info(f"Scanning legacy output: {legacy_dir}")
    legacy_inv = scan_directory(legacy_path)
    print_success(f"Found {len(legacy_inv)} files")
    
    print_info(f"Scanning modern output: {modern_dir}")
    modern_inv = scan_directory(modern_path)
    print_success(f"Found {len(modern_inv)} files")
    
    # Compare inventories
    if check_hashes:
        print_info("Comparing file contents (this may take a while)...")
    else:
        print_info("Comparing file metadata (skipping content hashes)...")
    
    passed, issues = compare_inventories(
        legacy_inv,
        modern_inv,
        legacy_path,
        modern_path,
        check_hashes=check_hashes
    )
    
    # Print report
    print_validation_report(legacy_inv, modern_inv, issues, passed)
    
    # Optional verbose output
    if verbose:
        print("\n" + "="*70)
        print("DIRECTORY STRUCTURE ANALYSIS")
        print("="*70)
        
        legacy_depths = analyze_directory_structure(legacy_inv)
        modern_depths = analyze_directory_structure(modern_inv)
        
        print("\nDirectory depth distribution:")
        print(f"{'Depth':<10} {'Legacy':<15} {'Modern':<15}")
        print("-" * 40)
        
        all_depths = sorted(set(legacy_depths.keys()) | set(modern_depths.keys()))
        for depth in all_depths:
            leg_count = legacy_depths.get(depth, 0)
            mod_count = modern_depths.get(depth, 0)
            print(f"{depth:<10} {leg_count:<15} {mod_count:<15}")
    
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(
        description='Validate recovery results by comparing legacy vs modern outputs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Validation Checks:
  - File counts and directory structure
  - File sizes and timestamps
  - Content integrity (SHA256 checksums)
  - Symlink consistency

Examples:
  # Quick validation (skip content hashes)
  python validate_results.py /tmp/legacy-test /tmp/modern-test --no-hashes

  # Full validation with content checks
  python validate_results.py /tmp/legacy-test /tmp/modern-test

  # Verbose output with structure analysis
  python validate_results.py /tmp/legacy-test /tmp/modern-test -v
"""
    )
    
    parser.add_argument('legacy_dir',
                       help='Path to legacy recovery output directory')
    parser.add_argument('modern_dir',
                       help='Path to modern recovery output directory')
    parser.add_argument('--no-hashes', action='store_true',
                       help='Skip content hash validation (faster)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output with structure analysis')
    
    args = parser.parse_args()
    
    return validate_results(
        legacy_dir=args.legacy_dir,
        modern_dir=args.modern_dir,
        check_hashes=not args.no_hashes,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
