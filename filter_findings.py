import json
import sys
from collections import defaultdict

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open('scan_out/findings.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Phân loại findings
findings_analysis = {
    'likely_false_positive': [],  # Require login, INFO level
    'potential_real_issues': [],  # Might be real
    'lfi_issues': [],              # LFI vulnerabilities
    'public_endpoints': [],        # Public endpoints without proper checks
}

for finding in data.get('results', []):
    check_id = finding.get('check_id', '')
    severity = finding.get('extra', {}).get('severity', '')
    fingerprint = finding.get('extra', {}).get('fingerprint', '')
    message = finding.get('extra', {}).get('message', '')
    path = finding.get('path', '')
    validation_state = finding.get('extra', {}).get('validation_state', '')
    
    # Extract plugin name
    parts = path.split('/unzipped/')
    plugin = parts[1].split('/')[0] if len(parts) > 1 else 'unknown'
    
    finding_info = {
        'plugin': plugin,
        'check_id': check_id,
        'severity': severity,
        'fingerprint': fingerprint,
        'message': message,
        'path': path,
        'validation_state': validation_state
    }
    
    # Classify
    if check_id == 'wp-direct-file-no-abspath-guard':
        if severity == 'INFO' and fingerprint == 'requires login':
            findings_analysis['likely_false_positive'].append(finding_info)
        else:
            findings_analysis['potential_real_issues'].append(finding_info)
    
    elif check_id == 'wp-lfi-taint':
        findings_analysis['lfi_issues'].append(finding_info)
    
    elif check_id in ['wp-nopriv-ajax-handler', 'wp-rest-public-route', 'wp-nopriv-admin-post']:
        findings_analysis['public_endpoints'].append(finding_info)
    
    else:
        findings_analysis['potential_real_issues'].append(finding_info)

print('=' * 80)
print('PHAN LOAI FINDINGS: FALSE POSITIVE VS REAL VULNERABILITIES')
print('=' * 80)

print(f'\n[FALSE POSITIVE - Require Login + INFO Level]')
print(f'  Total: {len(findings_analysis["likely_false_positive"])} findings')
print(f'  Ly do loc: These are INFO level findings requiring login')

print(f'\n[POTENTIAL REAL ISSUES]')
print(f'  Total: {len(findings_analysis["potential_real_issues"])} findings')
if findings_analysis['potential_real_issues']:
    plugins = defaultdict(int)
    for f in findings_analysis['potential_real_issues']:
        plugins[f['plugin']] += 1
    print('  Plugins affected:')
    for plugin, count in sorted(plugins.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f'    - {plugin}: {count}')

print(f'\n[LFI (Local File Inclusion) ISSUES]')
print(f'  Total: {len(findings_analysis["lfi_issues"])} findings')
if findings_analysis['lfi_issues']:
    print('  DANGER: These vulnerabilities CAN BE REAL!')
    plugins = defaultdict(list)
    for f in findings_analysis['lfi_issues']:
        plugins[f['plugin']].append(f)
    
    print('\n  Top plugins with LFI issues:')
    sorted_plugins = sorted(plugins.items(), key=lambda x: len(x[1]), reverse=True)[:15]
    for plugin, vulns in sorted_plugins:
        print(f'    {plugin}: {len(vulns)} findings')

print(f'\n[PUBLIC ENDPOINTS WITHOUT PROPER CHECKS]')
print(f'  Total: {len(findings_analysis["public_endpoints"])} findings')
if findings_analysis['public_endpoints']:
    print('  WARNING: Public endpoints might allow unauthorized access')
    plugins = defaultdict(list)
    check_types = defaultdict(list)
    for f in findings_analysis['public_endpoints']:
        plugins[f['plugin']].append(f)
        check_types[f['check_id']].append(f)
    
    print('\n  By check type:')
    for check_id in sorted(check_types.keys()):
        print(f'    - {check_id}: {len(check_types[check_id])} findings')
    
    print('\n  Affected plugins:')
    for plugin in sorted(plugins.keys(), key=lambda x: len(plugins[x]), reverse=True):
        print(f'    - {plugin}: {len(plugins[plugin])} findings')

print('\n' + '=' * 80)
print('KET LUAN VE FALSE POSITIVE')
print('=' * 80)
total_all = len(data.get('results', []))
fp_percentage = (len(findings_analysis['likely_false_positive']) / total_all * 100) if total_all > 0 else 0
real_percentage = (len(findings_analysis['potential_real_issues']) + len(findings_analysis['lfi_issues']) + len(findings_analysis['public_endpoints'])) / total_all * 100 if total_all > 0 else 0

print(f'\nTong findings: {total_all}')
print(f'  * Likely FALSE POSITIVE: {len(findings_analysis["likely_false_positive"])} ({fp_percentage:.1f}%)')
print(f'  * Potential REAL ISSUES: {len(findings_analysis["potential_real_issues"]) + len(findings_analysis["lfi_issues"]) + len(findings_analysis["public_endpoints"])} ({real_percentage:.1f}%)')
print(f'    - LFI issues: {len(findings_analysis["lfi_issues"])}')
print(f'    - Public endpoints: {len(findings_analysis["public_endpoints"])}')
print(f'    - Other potential: {len(findings_analysis["potential_real_issues"])}')

print('\n' + '=' * 80)
