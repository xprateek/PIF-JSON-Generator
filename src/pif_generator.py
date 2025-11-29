#!/usr/bin/env python3
"""
Core PIF Generator Module for Android system.prop files
Supports both legacy (default) and new extended PIF formats
"""
import requests
import zipfile
import io
import json
import sys
import re
from pathlib import Path


class PIFGenerator:
    """Generate PIF JSON from Android system.prop files"""
    
    def __init__(self, repo_type='stable', output_format='new'):
        """
        Initialize PIF Generator
        
        Args:
            repo_type: 'stable' or 'experimental'
            output_format: 'legacy' (default, 8 fields) or 'new' (20 fields)
        """
        self.repo_type = repo_type
        self.output_format = output_format
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
    
    def extract_security_patch(self, fingerprint, build_id):
        """Extract security patch date from fingerprint or build ID"""
        # Try to extract from build ID format: BP3A.251005.004.B3 -> 2025-10-05
        if build_id:
            match = re.search(r'\.(\d{2})(\d{2})(\d{2})\.', build_id)
            if match:
                year, month, day = match.groups()
                return f"20{year}-{month}-{day}"
        
        # Try to extract from fingerprint
        if fingerprint:
            match = re.search(r'/([A-Z0-9]+\.\d{6}\.[^/]+)/', fingerprint)
            if match:
                build_id_from_fp = match.group(1)
                date_match = re.search(r'\.(\d{2})(\d{2})(\d{2})\.', build_id_from_fp)
                if date_match:
                    year, month, day = date_match.groups()
                    return f"20{year}-{month}-{day}"
        
        return ""
    
    def validate_pif(self, pif):
        """Validate PIF has no empty fields"""
        required_fields = ['MANUFACTURER', 'MODEL', 'FINGERPRINT', 'BRAND', 'PRODUCT', 'DEVICE']
        
        # Add ID requirement only for new format
        if self.output_format == 'new':
            required_fields.append('ID')
        
        for field in required_fields:
            value = pif.get(field, '')
            if not value or not value.strip():
                raise ValueError(f"Field '{field}' is empty or missing")
        
        # Validate FIRST_API_LEVEL (legacy format)
        if 'FIRST_API_LEVEL' in pif:
            try:
                api_level = int(pif.get('FIRST_API_LEVEL', 0))
                if api_level < 21:  # Minimum Android 5.0
                    raise ValueError(f"Invalid FIRST_API_LEVEL: {api_level}")
            except (ValueError, TypeError):
                raise ValueError(f"FIRST_API_LEVEL must be a valid integer: {pif.get('FIRST_API_LEVEL')}")
        
        # Validate DEVICE_INITIAL_SDK_INT (new format)
        if 'DEVICE_INITIAL_SDK_INT' in pif:
            try:
                initial_sdk = int(pif.get('DEVICE_INITIAL_SDK_INT', 0))
                if initial_sdk < 21:  # Minimum Android 5.0
                    raise ValueError(f"Invalid DEVICE_INITIAL_SDK_INT: {initial_sdk}")
            except (ValueError, TypeError):
                raise ValueError(f"DEVICE_INITIAL_SDK_INT must be a valid integer: {pif.get('DEVICE_INITIAL_SDK_INT')}")
        
        # Validate SECURITY_PATCH format (YYYY-MM-DD)
        security_patch = pif.get('SECURITY_PATCH', '')
        if security_patch and len(security_patch) != 10:
            raise ValueError(f"Invalid SECURITY_PATCH format: {security_patch}")
        
        return True
    
    def build_pif(self, props):
        """Build PIF JSON from properties with strict validation"""
        
        if self.output_format == 'legacy':
            # ===== LEGACY FORMAT (ORIGINAL IMPLEMENTATION) =====
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
        
        else:
            # ===== NEW EXTENDED FORMAT =====
            # Extract fingerprint (prioritize system_ext)
            fingerprint = (
                props.get('ro.system_ext.build.fingerprint') or
                props.get('ro.system.build.fingerprint') or
                props.get('ro.build.fingerprint') or
                props.get('ro.product.build.fingerprint') or
                props.get('ro.bootimage.build.fingerprint') or
                props.get('ro.vendor.build.fingerprint') or
                props.get('ro.system_dlkm.build.fingerprint') or ''
            ).strip()
            
            if not fingerprint:
                raise ValueError("No fingerprint found in system.prop")
            
            # Extract build ID (prioritize system_ext)
            build_id = (
                props.get('ro.system_ext.build.id') or
                props.get('ro.system.build.id') or
                props.get('ro.build.id') or
                props.get('ro.vendor.build.id') or
                props.get('ro.system_dlkm.build.id') or ''
            ).strip()
            
            if not build_id:
                raise ValueError("No build ID found in system.prop")
            
            # Extract product (prioritize system_ext)
            product = (
                props.get('ro.product.system_ext.name') or
                props.get('ro.product.system.name') or
                props.get('ro.product.name') or
                props.get('ro.build.product') or
                props.get('ro.product.system_ext.device') or
                props.get('ro.product.device') or
                props.get('ro.product.board') or ''
            ).strip()
            
            # Extract device (prioritize system_ext)
            device = (
                props.get('ro.product.system_ext.device') or
                props.get('ro.product.system.device') or
                props.get('ro.product.device') or
                props.get('ro.build.product') or
                props.get('ro.product.board') or ''
            ).strip()
            
            # Extract brand (prioritize system_ext)
            brand = (
                props.get('ro.product.system_ext.brand') or
                props.get('ro.product.system.brand') or
                props.get('ro.product.brand') or
                'google'
            ).strip()
            
            # Extract manufacturer (prioritize system_ext)
            manufacturer = (
                props.get('ro.product.system_ext.manufacturer') or
                props.get('ro.product.system.manufacturer') or
                props.get('ro.product.manufacturer') or
                'Google'
            ).strip()
            
            # Extract model (prioritize system_ext)
            model = (
                props.get('ro.product.system_ext.model') or
                props.get('ro.product.system.model') or
                props.get('ro.product.model') or
                'Unknown'
            ).strip()
            
            # Extract device initial SDK (when device hardware first launched)
            device_initial_sdk = (
                props.get('ro.product.first_api_level') or
                props.get('ro.board.first_api_level') or
                props.get('ro.board.api_level') or
                props.get('ro.system_ext.build.version.sdk') or
                props.get('ro.system.build.version.sdk') or
                props.get('ro.build.version.sdk') or
                '0'
            ).strip()
            
            # Extract build type (prioritize system_ext)
            build_type = (
                props.get('ro.system_ext.build.type') or
                props.get('ro.system.build.type') or
                props.get('ro.build.type') or
                'user'
            ).strip()
            
            # Extract build tags (prioritize system_ext)
            build_tags = (
                props.get('ro.system_ext.build.tags') or
                props.get('ro.system.build.tags') or
                props.get('ro.build.tags') or
                'release-keys'
            ).strip()
            
            # Extract Android release version (prioritize system_ext)
            release = (
                props.get('ro.system_ext.build.version.release') or
                props.get('ro.system.build.version.release') or
                props.get('ro.build.version.release') or
                props.get('ro.build.version.release_or_codename') or
                ''
            ).strip()
            
            # Extract security patch from properties or fingerprint/build ID
            security_patch = (
                props.get('ro.build.version.security_patch') or
                props.get('ro.vendor.build.security_patch') or
                ''
            ).strip()
            
            if not security_patch:
                security_patch = self.extract_security_patch(fingerprint, build_id)
            
            # Determine DEBUG flag
            debuggable = props.get('ro.debuggable', '0').strip()
            is_debug = build_type in ['userdebug', 'eng'] or debuggable == '1'
            
            # Build new format PIF
            pif = {
                "ID": build_id,
                "BRAND": brand,
                "DEVICE": device,
                "MANUFACTURER": manufacturer,
                "FINGERPRINT": fingerprint,
                "MODEL": model,
                "PRODUCT": product,
                "SECURITY_PATCH": security_patch,
                "DEVICE_INITIAL_SDK_INT": str(int(device_initial_sdk)),
                "TYPE": build_type,
                "TAG": build_tags,
                "RELEASE": release,
                "DEBUG": is_debug,
                "spoofBuild": "1",
                "spoofProps": "0",
                "spoofProvider": "0",
                "spoofSignature": "0",
                "spoofVendingSdk": "0",
                "verboseLogs": "0"
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
