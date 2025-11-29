#!/usr/bin/env python3
"""
Check for new releases from monitored repositories
"""
import os
import sys
import json
from github import Github, Auth
from pathlib import Path


REPOS = [
    {"owner": "Pixel-Props", "name": "build.prop", "type": "stable"},
    {"owner": "Elcapitanoe", "name": "Build-Prop-BETA", "type": "experimental"}
]


def check_releases(github_token):
    """Check all repos for new releases"""
    auth = Auth.Token(github_token)
    g = Github(auth=auth)
    
    results = []
    
    for repo_config in REPOS:
        try:
            repo = g.get_repo(f"{repo_config['owner']}/{repo_config['name']}")
            
            try:
                latest = repo.get_latest_release()
            except:
                print(f"[WARN] No releases for {repo.full_name}")
                continue
            
            tag = latest.tag_name
            tag_file = Path(f"last_release_{repo_config['type']}_tag.txt")
            
            # Check if new
            if tag_file.exists() and tag_file.read_text().strip() == tag:
                print(f"[INFO] {repo.full_name} @ {tag} - Already processed")
                continue
            
            # Get ALL ZIP assets
            assets = []
            for asset in latest.get_assets():
                if asset.name.endswith('.zip'):
                    assets.append({
                        "name": asset.name,
                        "url": asset.browser_download_url
                    })
            
            if not assets:
                print(f"[WARN] No ZIP assets in {tag}")
                continue
            
            print(f"[NEW] {repo.full_name} @ {tag} - {len(assets)} assets")
            
            results.append({
                "repo_type": repo_config['type'],
                "latest_tag": tag,
                "assets": assets,
                "count": len(assets)
            })
        
        except Exception as e:
            print(f"[ERROR] {repo_config['owner']}/{repo_config['name']}: {e}")
            continue
    
    # Output results
    if results:
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"new_release=true\n")
                f.write(f"results={json.dumps(results)}\n")
        
        print(f"\n[SUMMARY] Found {len(results)} new release(s)")
        return {"new_release": True, "results": results}
    else:
        print("[INFO] No new releases")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("new_release=false\n")
        
        return {"new_release": False}


if __name__ == "__main__":
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("[ERROR] GITHUB_TOKEN not set")
        sys.exit(1)
    
    result = check_releases(token)
    print(json.dumps(result, indent=2))
