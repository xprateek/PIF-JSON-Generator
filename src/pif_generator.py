#!/usr/bin/env python3
"""
Core PIF Generator Module for Android system.prop files
"""
import requests
import zipfile
import io
import json
import sys
from pathlib import Path


class PIFGenerator:
    """Generate PIF JSON from Android system.prop files"""
    
    def __init__(self, repo_type='stable'):
        self.repo_type = repo_type
        self.prefix = "EXPERIMENTAL_" if repo_type == "experimental" else "Stable_PIF_"
    
    def parse_system_prop(self, content):
        """Parse Android system.prop format"""
        props = {}
        for line in content.splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                try:
                    key, val = line.split('=', 1)
                    props[key.strip()] = val.strip()
                except ValueError:
                    continue
        return props
    
    def download_and_extract(self, url):
        """Download ZIP and extract system.prop"""
        print(f"[INFO] Downloading: {url}")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.endswith('system.prop'):
                    print(f"[INFO] Found: {name}")
                    return z.read(name).decode('utf-8')
        
        raise FileNotFoundError("system.prop not found in ZIP")
    
    def validate_pif(self, pif):
        """Validate PIF has no empty fields"""
        required_fields = ['MANUFACTURER', 'MODEL', 'FINGERPRINT', 'BRAND', 'PRODUCT', 'DEVICE']
        
        for field in required_fields:
            value = pif.get(field, '')
            if not value or not value.strip():
                raise ValueError(f"Field '{field}' is empty or missing")
        
        # Validate FIRST_API_LEVEL is a valid number
        try:
            api_level = int(pif.get('FIRST_API_LEVEL', 0))
            if api_level < 21:  # Minimum Android 5.0
                raise ValueError(f"Invalid FIRST_API_LEVEL: {api_level}")
        except (ValueError, TypeError):
            raise ValueError(f"FIRST_API_LEVEL must be a valid integer: {pif.get('FIRST_API_LEVEL')}")
        
        # Validate SECURITY_PATCH format (YYYY-MM-DD)
        security_patch = pif.get('SECURITY_PATCH', '')
        if security_patch and len(security_patch) != 10:
            raise ValueError(f"Invalid SECURITY_PATCH format: {security_patch}")
        
        return True
    
    def build_pif(self, props):
        """Build PIF JSON from properties with strict validation"""
        # Extract fingerprint
        fingerprint = (
            props.get('ro.build.fingerprint') or
            props.get('ro.product.build.fingerprint') or
            props.get('ro.bootimage.build.fingerprint') or
            props.get('ro.vendor.build.fingerprint') or
            props.get('ro.system.build.fingerprint') or ''
        ).strip()
        
        if not fingerprint:
            raise ValueError("No fingerprint found in system.prop")
        
        # Extract product (try multiple sources)
        product = (
            props.get('ro.build.product') or
            props.get('ro.product.device') or
            props.get('ro.product.name') or
            props.get('ro.product.board') or ''
        ).strip()
        
        # Extract device
        device = (
            props.get('ro.product.device') or
            props.get('ro.build.product') or
            props.get('ro.product.board') or ''
        ).strip()
        
        # Extract first API level
        first_api_level = (
            props.get('ro.product.first_api_level') or
            props.get('ro.board.first_api_level') or
            props.get('ro.board.api_level') or
            props.get('ro.build.version.sdk') or
            props.get('ro.system.build.version.sdk') or
            '0'
        ).strip()
        
        # Build PIF
        pif = {
            "MANUFACTURER": props.get('ro.product.manufacturer', 'Google').strip(),
            "MODEL": props.get('ro.product.model', 'Unknown').strip(),
            "FINGERPRINT": fingerprint,
            "BRAND": props.get('ro.product.brand', 'google').strip(),
            "PRODUCT": product,
            "DEVICE": device,
            "SECURITY_PATCH": (props.get('ro.build.version.security_patch') or 
                              props.get('ro.vendor.build.security_patch') or '').strip(),
            "FIRST_API_LEVEL": str(int(first_api_level))
        }
        
        # Validate before returning
        self.validate_pif(pif)
        
        return pif
    
    def generate(self, zip_name, url):
        """Generate PIF JSON from ZIP URL"""
        try:
            # Download and parse
            content = self.download_and_extract(url)
            props = self.parse_system_prop(content)
            
            print(f"[DEBUG] Parsed {len(props)} properties")
            
            pif = self.build_pif(props)
            
            # Save to file
            filename = f"{self.prefix}{zip_name.replace('.zip', '')}.json"
            output_path = Path(filename)
            output_path.write_text(json.dumps(pif, indent=2))
            
            print(f"[SUCCESS] {filename}")
            print(f"[VALIDATION] All fields populated correctly")
            
            return filename
            
        except Exception as e:
            print(f"[ERROR] {zip_name}: {e}", file=sys.stderr)
            raise
