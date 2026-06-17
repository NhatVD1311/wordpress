import json
from collections import defaultdict

with open('scan_out/findings.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Thống kê vuln theo plugin
plugin_vulns = defaultdict(list)
check_types = defaultdict(int)
severity_count = defaultdict(int)

for finding in data.get('results', []):
    # Extract plugin name from path
    path = finding.get('path', '')
    parts = path.split('/unzipped/')
    if len(parts) > 1:
        plugin = parts[1].split('/')[0]
    else:
        plugin = 'unknown'
    
    check_id = finding.get('check_id', 'unknown')
    severity = finding.get('extra', {}).get('severity', 'UNKNOWN')
    message = finding.get('extra', {}).get('message', '')
    fingerprint = finding.get('extra', {}).get('fingerprint', '')
    
    check_types[check_id] += 1
    severity_count[severity] += 1
    
    plugin_vulns[plugin].append({
        'check_id': check_id,
        'severity': severity,
        'message': message,
        'fingerprint': fingerprint,
        'path': path
    })

# Print summary
print('=' * 70)
print('TỔNG QUAN SCAN RESULTS')
print('=' * 70)
print(f'Total findings: {len(data.get("results", []))}')
print(f'Total plugins affected: {len(plugin_vulns)}')
print()

print('=' * 70)
print('PHÂN BỐ MỨC ĐỘ NGHIÊM TRỌNG (SEVERITY)')
print('=' * 70)
for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
    count = severity_count.get(severity, 0)
    print(f'{severity}: {count}')
print()

print('=' * 70)
print('LOẠI LỖ HỖNG (CHECK_ID)')
print('=' * 70)
for check, count in sorted(check_types.items(), key=lambda x: x[1], reverse=True):
    print(f'{check}: {count}')
print()

print('=' * 70)
print('PLUGIN CÓ LỖ HỖNG NGHIÊM TRỌNG NHẤT (Top 20)')
print('=' * 70)
sorted_plugins = sorted(plugin_vulns.items(), key=lambda x: len(x[1]), reverse=True)[:20]
for idx, (plugin, vulns) in enumerate(sorted_plugins, 1):
    # Count severity levels for this plugin
    high_count = sum(1 for v in vulns if v['severity'] in ['CRITICAL', 'HIGH'])
    print(f'{idx}. {plugin}: {len(vulns)} findings (High/Critical: {high_count})')

# Save detailed report
print()
print('=' * 70)
print('PHÂN TÍCH CHI TIẾT - PLUGIN CÓ HIGH/CRITICAL VULNERABILITIES')
print('=' * 70)

high_critical_plugins = {}
for plugin, vulns in plugin_vulns.items():
    high_crit = [v for v in vulns if v['severity'] in ['CRITICAL', 'HIGH']]
    if high_crit:
        high_critical_plugins[plugin] = high_crit

if high_critical_plugins:
    for plugin, vulns in sorted(high_critical_plugins.items(), key=lambda x: len(x[1]), reverse=True):
        print(f'\n>>> {plugin} ({len(vulns)} HIGH/CRITICAL)')
        for vuln in vulns[:5]:  # Show top 5
            print(f'    - {vuln["check_id"]} ({vuln["severity"]})')
            print(f'      Message: {vuln["message"]}')
else:
    print('\nKHÔNG CÓ plugin nào có HIGH hoặc CRITICAL vulnerabilities')

print('\n' + '=' * 70)
