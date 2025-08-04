#!/bin/bash

# Security Test Runner for Agency Dark

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔒 Agency Dark Security Testing Suite${NC}"
echo "========================================"
echo ""

# Create results directory
mkdir -p test-results/security
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="test-results/security/security-report-${TIMESTAMP}.html"

# Check if backend is running
echo -e "${YELLOW}Checking backend availability...${NC}"
if ! curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo -e "${RED}❌ Backend is not running!${NC}"
    echo "Please start the backend first."
    exit 1
fi
echo -e "${GREEN}✅ Backend is available${NC}"

# Run security tests
echo -e "\n${YELLOW}Running security tests...${NC}"
echo "========================================"

# SQL Injection Tests
echo -e "\n${BLUE}1. SQL Injection Tests${NC}"
npx playwright test tests/security/sql-injection.spec.ts --config=tests/security/security.config.ts
SQL_RESULT=$?

# XSS Tests
echo -e "\n${BLUE}2. Cross-Site Scripting (XSS) Tests${NC}"
npx playwright test tests/security/xss-vulnerabilities.spec.ts --config=tests/security/security.config.ts
XSS_RESULT=$?

# Authentication Security Tests
echo -e "\n${BLUE}3. Authentication Security Tests${NC}"
npx playwright test tests/security/auth-security.spec.ts --config=tests/security/security.config.ts
AUTH_RESULT=$?

# API Security Tests
echo -e "\n${BLUE}4. API Security Tests${NC}"
npx playwright test tests/security/api-security.spec.ts --config=tests/security/security.config.ts
API_RESULT=$?

# Additional security checks
echo -e "\n${BLUE}5. Additional Security Checks${NC}"

# Check for exposed sensitive files
echo -e "\n${YELLOW}Checking for exposed sensitive files...${NC}"
SENSITIVE_FILES=(
    "/.env"
    "/.git/config"
    "/package-lock.json"
    "/yarn.lock"
    "/.DS_Store"
    "/Thumbs.db"
    "/phpinfo.php"
    "/.htaccess"
    "/web.config"
    "/robots.txt"
)

for file in "${SENSITIVE_FILES[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5173${file}")
    if [ "$response" != "404" ] && [ "$response" != "403" ]; then
        echo -e "${RED}⚠️  Exposed: ${file} (HTTP ${response})${NC}"
    fi
done

# Check security headers
echo -e "\n${YELLOW}Checking security headers...${NC}"
headers=$(curl -s -I http://localhost:5173)

check_header() {
    if echo "$headers" | grep -qi "$1"; then
        echo -e "${GREEN}✅ $1 header present${NC}"
    else
        echo -e "${RED}❌ $1 header missing${NC}"
    fi
}

check_header "X-Frame-Options"
check_header "X-Content-Type-Options"
check_header "X-XSS-Protection"
check_header "Content-Security-Policy"
check_header "Strict-Transport-Security"

# Generate summary report
echo -e "\n${BLUE}Generating Security Report...${NC}"

cat > "$REPORT_FILE" <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Security Test Report - ${TIMESTAMP}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        .pass { color: #27ae60; }
        .fail { color: #e74c3c; }
        .warning { color: #f39c12; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        .recommendations { background: #f8f9fa; padding: 15px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Security Test Report</h1>
        <p>Generated: $(date)</p>
    </div>

    <div class="section">
        <h2>Test Results Summary</h2>
        <table>
            <tr>
                <th>Test Category</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>SQL Injection Protection</td>
                <td class="$([ $SQL_RESULT -eq 0 ] && echo 'pass' || echo 'fail')">
                    $([ $SQL_RESULT -eq 0 ] && echo '✅ PASSED' || echo '❌ FAILED')
                </td>
            </tr>
            <tr>
                <td>XSS Protection</td>
                <td class="$([ $XSS_RESULT -eq 0 ] && echo 'pass' || echo 'fail')">
                    $([ $XSS_RESULT -eq 0 ] && echo '✅ PASSED' || echo '❌ FAILED')
                </td>
            </tr>
            <tr>
                <td>Authentication Security</td>
                <td class="$([ $AUTH_RESULT -eq 0 ] && echo 'pass' || echo 'fail')">
                    $([ $AUTH_RESULT -eq 0 ] && echo '✅ PASSED' || echo '❌ FAILED')
                </td>
            </tr>
            <tr>
                <td>API Security</td>
                <td class="$([ $API_RESULT -eq 0 ] && echo 'pass' || echo 'fail')">
                    $([ $API_RESULT -eq 0 ] && echo '✅ PASSED' || echo '❌ FAILED')
                </td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Security Headers Analysis</h2>
        <pre>$headers</pre>
    </div>

    <div class="recommendations">
        <h2>🔍 Security Recommendations</h2>
        <ul>
            <li>Implement Content Security Policy (CSP) to prevent XSS attacks</li>
            <li>Enable HTTPS and set Strict-Transport-Security header</li>
            <li>Implement rate limiting on all API endpoints</li>
            <li>Use parameterized queries to prevent SQL injection</li>
            <li>Validate and sanitize all user inputs</li>
            <li>Implement proper session management</li>
            <li>Enable security logging and monitoring</li>
            <li>Regular security audits and penetration testing</li>
            <li>Keep all dependencies up to date</li>
            <li>Implement Web Application Firewall (WAF) in production</li>
        </ul>
    </div>

    <div class="section">
        <h2>OWASP Top 10 Coverage</h2>
        <ol>
            <li>✅ Injection (SQL, NoSQL, Command)</li>
            <li>✅ Broken Authentication</li>
            <li>✅ Sensitive Data Exposure</li>
            <li>✅ XML External Entities (XXE)</li>
            <li>✅ Broken Access Control</li>
            <li>✅ Security Misconfiguration</li>
            <li>✅ Cross-Site Scripting (XSS)</li>
            <li>⚠️ Insecure Deserialization</li>
            <li>⚠️ Using Components with Known Vulnerabilities</li>
            <li>⚠️ Insufficient Logging & Monitoring</li>
        </ol>
    </div>
</body>
</html>
EOF

# Summary
echo -e "\n${BLUE}========================================"
echo -e "Security Testing Complete!${NC}"
echo -e "\nReport saved to: ${REPORT_FILE}"

# Calculate overall result
TOTAL_TESTS=4
FAILED_TESTS=0
[ $SQL_RESULT -ne 0 ] && ((FAILED_TESTS++))
[ $XSS_RESULT -ne 0 ] && ((FAILED_TESTS++))
[ $AUTH_RESULT -ne 0 ] && ((FAILED_TESTS++))
[ $API_RESULT -ne 0 ] && ((FAILED_TESTS++))

PASSED_TESTS=$((TOTAL_TESTS - FAILED_TESTS))

echo -e "\n${GREEN}Passed: ${PASSED_TESTS}${NC} / ${RED}Failed: ${FAILED_TESTS}${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}✅ All security tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some security tests failed. Please review the report.${NC}"
    echo "Run 'open ${REPORT_FILE}' to view the detailed report."
    exit 1
fi