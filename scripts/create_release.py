#!/usr/bin/env python3
"""
Create GitHub release and upload files
"""
import os
import sys
from pathlib import Path
from github import Github, Auth, GithubException
from datetime import datetime, UTC


def create_release(repo_name, tag, repo_type, files):
    """Create release and upload files"""
    token = os.getenv("GITHUB_TOKEN")
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_name)
    
    release_tag = f"{repo_type}-PIF-{tag}"
    notes = f"Auto-generated {len(files)} PIF JSON files. Generated: {datetime.now(UTC).strftime('%Y-%m-%d')}"
    
    # Create or get release
    try:
        release = repo.create_git_release(
            tag=release_tag,
            name=f"{repo_type} PIF - {tag}",
            message=notes
        )
        print(f"[OK] Created release: {release_tag}")
    except GithubException as e:
        if e.status == 422:  # Already exists
            release = repo.get_release(release_tag)
            print(f"[INFO] Release exists: {release_tag}")
        else:
            raise
    
    # Get existing asset names
    existing_assets = {asset.name: asset for asset in release.get_assets()}
    
    # Upload files
    uploaded = 0
    skipped = 0
    
    for file in files:
        filepath = Path(file)
        if not filepath.exists():
            print(f"[SKIP] File not found: {file}")
            continue
        
        filename = filepath.name
        
        # Check if already uploaded
        if filename in existing_assets:
            print(f"[SKIP] Already uploaded: {filename}")
            skipped += 1
            
            # Optional: Delete and re-upload to update
            # existing_assets[filename].delete_asset()
            # print(f"[UPDATE] Deleted old version: {filename}")
            # release.upload_asset(str(filepath))
            # print(f"[UPLOAD] Re-uploaded: {filename}")
            # uploaded += 1
        else:
            try:
                print(f"[UPLOAD] {filename}")
                release.upload_asset(str(filepath))
                uploaded += 1
            except GithubException as e:
                print(f"[ERROR] Failed to upload {filename}: {e}")
    
    print(f"\n[SUMMARY] Uploaded: {uploaded}, Skipped: {skipped}/{len(files)}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: create_release.py <repo> <tag> <repo_type>")
        sys.exit(1)
    
    files = Path("generated_files.txt").read_text().splitlines()
    create_release(sys.argv[1], sys.argv[2], sys.argv[3], files)
