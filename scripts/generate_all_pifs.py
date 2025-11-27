#!/usr/bin/env python3
"""
Generate all PIF JSON files from asset list
FIXED: Process all assets, validate output
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pif_generator import PIFGenerator


def main():
    if len(sys.argv) != 3:
        print("Usage: generate_all_pifs.py <assets_json> <repo_type>")
        sys.exit(1)
    
    assets = json.loads(sys.argv[1])
    repo_type = sys.argv[2]
    
    print(f"[INFO] Processing {len(assets)} assets for {repo_type}")
    print("=" * 60)
    
    generator = PIFGenerator(repo_type)
    
    generated = []
    failed = []
    
    for i, asset in enumerate(assets, 1):
        print(f"\n[{i}/{len(assets)}] {asset['name']}")
        print("-" * 60)
        
        try:
            filename = generator.generate(asset['name'], asset['url'])
            generated.append(filename)
            
            # Verify file exists and is valid JSON
            with open(filename) as f:
                data = json.load(f)
                print(f"[VERIFY] All fields: {all(data.values())}")
                
        except Exception as e:
            print(f"[FAILED] {e}")
            failed.append(asset['name'])
    
    # Summary
    print("\n" + "=" * 60)
    print(f"SUCCESS: {len(generated)}/{len(assets)}")
    print(f"FAILED:  {len(failed)}/{len(assets)}")
    print("=" * 60)
    
    if failed:
        print("\nFailed files:")
        for f in failed:
            print(f"  - {f}")
    
    if generated:
        Path("generated_files.txt").write_text("\n".join(generated))
        print(f"\nGenerated files list: generated_files.txt")
        
        # Update tag file
        tag_file = Path(f"last_release_{repo_type}_tag.txt")
        # Tag will be written by workflow
    else:
        print("\n[ERROR] No files generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
