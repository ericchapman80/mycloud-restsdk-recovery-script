#!/usr/bin/env python3
"""
Create Test Dataset - Extract representative sample from production data

Creates a small, diverse test dataset from production MyCloud data for:
- Phase 0 validation testing
- CI/CD regression tests  
- Development iteration

Sampling strategies ensure edge cases are tested (special chars, deep paths, etc.)
"""

import argparse
import sqlite3
import shutil
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Sampling strategies
SAMPLING_STRATEGIES = {
    'diverse': {
        'description': 'Balanced mix of file types, sizes, and edge cases',
        'criteria': {
            'small_files': ('LENGTH(name) < 50 AND contentID != ""', 5),
            'long_names': ('LENGTH(name) >= 50 AND contentID != ""', 3),
            'special_chars': ("(name LIKE '%|%' OR name LIKE '%&%' OR name LIKE '%@%') AND contentID != ''", 5),
            'images': ("(name LIKE '%.jpg' OR name LIKE '%.png' OR name LIKE '%.jpeg') AND imageDate IS NOT NULL", 10),
            'videos': ("(name LIKE '%.mp4' OR name LIKE '%.mov' OR name LIKE '%.avi') AND videoDate IS NOT NULL", 5),
            'recent': ("(imageDate > 1577836800000 OR videoDate > 1577836800000) AND contentID != ''", 5),
            'old': ("(imageDate < 1577836800000 OR videoDate < 1577836800000) AND contentID != ''", 3),
            'random': ('contentID != ""', 10),
        }
    },
    'edge_cases': {
        'description': 'Focus on problematic filenames and paths',
        'criteria': {
            'pipe_names': ("name LIKE '%|%' AND contentID != ''", 10),
            'unicode': ("(name LIKE '%é%' OR name LIKE '%ñ%' OR LENGTH(name) != LENGTH(CAST(name AS BLOB))) AND contentID != ''", 10),
            'spaces': ("name LIKE '% %' AND contentID != ''", 10),
            'dots': ("name LIKE '%.%' AND contentID != ''", 10),
        }
    },
    'quick': {
        'description': 'Just grab random files for quick testing',
        'criteria': {
            'random': ('contentID != ""', 20),
        }
    }
}


def print_info(msg):
    print(f"ℹ️  {msg}")


def print_success(msg):
    print(f"✅ {msg}")


def print_error(msg):
    print(f"❌ {msg}")


def print_warning(msg):
    print(f"⚠️  {msg}")


def resolve_content_path(filedir: str, content_id: str) -> Path:
    """Find file by contentID (supports flat or sharded layout)"""
    # Try sharded first (most common)
    sharded = Path(filedir) / content_id[:2] / content_id
    if sharded.exists():
        return sharded
    
    # Try flat layout
    flat = Path(filedir) / content_id
    if flat.exists():
        return flat
    
    return None


def get_file_parents(conn: sqlite3.Connection, file_id: str) -> List[Tuple[str, str]]:
    """Get all parent directories for a file (returns list of (id, name) tuples)"""
    parents = []
    current_id = file_id
    
    while current_id:
        row = conn.execute(
            "SELECT id, parentID, name FROM files WHERE id = ?",
            (current_id,)
        ).fetchone()
        
        if not row:
            break
        
        parent_id = row[1]
        if parent_id:
            parent_row = conn.execute(
                "SELECT id, name FROM files WHERE id = ?",
                (parent_id,)
            ).fetchone()
            if parent_row:
                parents.append((parent_row[0], parent_row[1]))
                current_id = parent_id
            else:
                break
        else:
            break
    
    return parents


def sample_files_by_criteria(
    conn: sqlite3.Connection,
    strategy: Dict[str, Tuple[str, int]],
    max_per_category: int = None
) -> List[Dict]:
    """
    Sample files based on strategy criteria.
    
    Returns list of file dictionaries with keys:
        id, name, parentID, contentID, imageDate, videoDate, cTime, birthTime
    """
    sampled_files = []
    
    for category, (where_clause, count) in strategy.items():
        if max_per_category:
            count = min(count, max_per_category)
        
        query = f"""
            SELECT id, name, parentID, contentID, 
                   imageDate, videoDate, cTime, birthTime
            FROM files 
            WHERE {where_clause}
            ORDER BY RANDOM() 
            LIMIT ?
        """
        
        rows = conn.execute(query, (count,)).fetchall()
        
        for row in rows:
            sampled_files.append({
                'id': row[0],
                'name': row[1],
                'parentID': row[2],
                'contentID': row[3],
                'imageDate': row[4],
                'videoDate': row[5],
                'cTime': row[6],
                'birthTime': row[7],
                'category': category
            })
        
        print_info(f"  {category}: sampled {len(rows)}/{count} files")
    
    return sampled_files


def create_test_dataset(
    prod_db: str,
    prod_files: str,
    test_db: str,
    test_files: str,
    strategy_name: str = 'diverse',
    max_files: int = None
):
    """
    Create test dataset from production data.
    
    Steps:
    1. Sample files using strategy
    2. Get all parent directories
    3. Copy database schema and sampled data
    4. Copy actual files to test directory
    """
    
    # Validate inputs
    if not os.path.exists(prod_db):
        print_error(f"Production database not found: {prod_db}")
        return 1
    
    if not os.path.isdir(prod_files):
        print_error(f"Production files directory not found: {prod_files}")
        return 1
    
    # Create output directories
    Path(test_files).mkdir(parents=True, exist_ok=True)
    Path(test_db).parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to databases
    print_info(f"Connecting to production database: {prod_db}")
    prod_conn = sqlite3.connect(prod_db)
    prod_conn.row_factory = sqlite3.Row
    
    # Remove existing test DB if it exists
    if os.path.exists(test_db):
        print_warning(f"Removing existing test database: {test_db}")
        os.remove(test_db)
    
    test_conn = sqlite3.connect(test_db)
    
    try:
        # Copy schema
        print_info("Copying database schema...")
        schema_queries = prod_conn.execute(
            """SELECT sql FROM sqlite_master 
               WHERE type='table' 
               AND sql IS NOT NULL 
               AND name NOT LIKE 'sqlite_%'"""
        ).fetchall()
        
        for row in schema_queries:
            test_conn.execute(row[0])
        
        test_conn.commit()
        print_success(f"Created {len(schema_queries)} tables")
        
        # Sample files
        strategy = SAMPLING_STRATEGIES.get(strategy_name, SAMPLING_STRATEGIES['diverse'])
        print_info(f"Using strategy: {strategy_name} - {strategy['description']}")
        
        sampled_files = sample_files_by_criteria(
            prod_conn,
            strategy['criteria'],
            max_per_category=max_files
        )
        
        print_success(f"Sampled {len(sampled_files)} files")
        
        # Get all parent directories
        print_info("Collecting parent directories...")
        all_parent_ids = set()
        
        for file_info in sampled_files:
            parents = get_file_parents(prod_conn, file_info['id'])
            for parent_id, _ in parents:
                all_parent_ids.add(parent_id)
        
        print_success(f"Found {len(all_parent_ids)} parent directories")
        
        # Insert parent directories into test DB
        print_info("Inserting parent directories...")
        for parent_id in all_parent_ids:
            row = prod_conn.execute(
                "SELECT id, parentID, name, contentID, version FROM files WHERE id = ?",
                (parent_id,)
            ).fetchone()
            
            if row:
                test_conn.execute(
                    "INSERT OR IGNORE INTO files (id, parentID, name, contentID, version) VALUES (?, ?, ?, ?, ?)",
                    (row[0], row[1], row[2], row[3], row[4])
                )
        
        test_conn.commit()
        
        # Insert sampled files
        print_info("Inserting sampled files...")
        files_copied = 0
        files_skipped = 0
        
        for file_info in sampled_files:
            # Insert into test database
            test_conn.execute("""
                INSERT OR IGNORE INTO files 
                (id, name, parentID, contentID, imageDate, videoDate, cTime, birthTime, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                file_info['id'],
                file_info['name'],
                file_info['parentID'],
                file_info['contentID'],
                file_info['imageDate'],
                file_info['videoDate'],
                file_info['cTime'],
                file_info['birthTime']
            ))
            
            # Copy actual file
            content_id = file_info['contentID']
            src_path = resolve_content_path(prod_files, content_id)
            
            if src_path and src_path.exists():
                # Preserve sharded structure
                dest_dir = Path(test_files) / content_id[:2]
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / content_id
                
                shutil.copy2(src_path, dest_path)
                files_copied += 1
                
                # Show progress
                if files_copied % 10 == 0:
                    print(f"  Copied {files_copied}/{len(sampled_files)} files...", end='\r')
            else:
                files_skipped += 1
                print_warning(f"  Source file not found: {content_id} ({file_info['name']})")
        
        test_conn.commit()
        
        print()  # New line after progress
        print_success(f"Copied {files_copied} files")
        if files_skipped > 0:
            print_warning(f"Skipped {files_skipped} files (source not found)")
        
        # Summary
        print("\n" + "="*60)
        print("TEST DATASET CREATED")
        print("="*60)
        
        # Calculate sizes
        db_size = os.path.getsize(test_db) / (1024 * 1024)
        files_size = sum(f.stat().st_size for f in Path(test_files).rglob('*') if f.is_file()) / (1024 * 1024)
        
        print(f"📊 Database: {test_db}")
        print(f"   Size: {db_size:.2f} MB")
        print(f"   Files in DB: {len(sampled_files)}")
        print(f"   Parent dirs: {len(all_parent_ids)}")
        
        print(f"\n📁 Files: {test_files}")
        print(f"   Size: {files_size:.2f} MB")
        print(f"   Files copied: {files_copied}")
        
        print(f"\n📋 Strategy: {strategy_name}")
        print(f"   Description: {strategy['description']}")
        
        print("\n✅ Test dataset ready for use!")
        print("\nNext steps:")
        print(f"  cd legacy && python restsdk_public.py --db ../{test_db} --filedir ../{test_files} --dumpdir /tmp/legacy-test")
        print(f"  cd modern && poetry run python rsync_restore.py --db ../{test_db} --source ../{test_files} --dest /tmp/modern-test --farm /tmp/farm")
        
        return 0
        
    finally:
        prod_conn.close()
        test_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Create test dataset from production MyCloud data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sampling Strategies:
  diverse    - Balanced mix of file types, sizes, edge cases (default)
  edge_cases - Focus on problematic filenames (pipes, unicode, etc.)
  quick      - Random sample for fast testing

Examples:
  # Create diverse test set with 50 files
  python create_test_dataset.py \\
      --prod-db /prod/index.db \\
      --prod-files /prod/files \\
      --test-db shared/test-fixtures/test.db \\
      --test-files shared/test-fixtures/files \\
      --strategy diverse \\
      --max-per-category 5

  # Create quick test set
  python create_test_dataset.py \\
      --prod-db index.db \\
      --prod-files /source \\
      --test-db test.db \\
      --test-files test-files \\
      --strategy quick
"""
    )
    
    parser.add_argument('--prod-db', required=True,
                       help='Path to production database (index.db)')
    parser.add_argument('--prod-files', required=True,
                       help='Path to production files directory')
    parser.add_argument('--test-db', required=True,
                       help='Path to output test database')
    parser.add_argument('--test-files', required=True,
                       help='Path to output test files directory')
    parser.add_argument('--strategy', default='diverse',
                       choices=list(SAMPLING_STRATEGIES.keys()),
                       help='Sampling strategy (default: diverse)')
    parser.add_argument('--max-per-category', type=int,
                       help='Max files per category (overrides strategy defaults)')
    
    args = parser.parse_args()
    
    return create_test_dataset(
        prod_db=args.prod_db,
        prod_files=args.prod_files,
        test_db=args.test_db,
        test_files=args.test_files,
        strategy_name=args.strategy,
        max_files=args.max_per_category
    )


if __name__ == '__main__':
    sys.exit(main())
