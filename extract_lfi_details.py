import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

with open('scan_out/findings.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract LFI findings for specific plugins
target_plugins = ['backuply', 'aruba-hispeed-cache', 'cartflows']
lfi_findings = {plugin: [] for plugin in target_plugins}

for finding in data.get('results', []):
    if finding.get('check_id') != 'wp-lfi-taint':
        continue
    
    path = finding.get('path', '')
    parts = path.split('/unzipped/')
    if len(parts) > 1:
        plugin = parts[1].split('/')[0]
        if plugin in target_plugins:
            lfi_findings[plugin].append({
                'file': parts[1],
                'line': finding.get('start', {}).get('line'),
                'col': finding.get('start', {}).get('col'),
                'message': finding.get('extra', {}).get('message', ''),
                'full_path': path
            })

# Print findings
for plugin, vulns in lfi_findings.items():
    print(f'\n{"="*100}')
    print(f'PLUGIN: {plugin.upper()}')
    print(f'Total LFI findings: {len(vulns)}')
    print(f'{"="*100}\n')
    
    for idx, vuln in enumerate(vulns[:5], 1):
        print(f'{idx}. File: {vuln["file"]}')
        print(f'   Line: {vuln["line"]}')
        print(f'   Col: {vuln["col"]}')
        print(f'   Message: {vuln["message"]}')
        print()
