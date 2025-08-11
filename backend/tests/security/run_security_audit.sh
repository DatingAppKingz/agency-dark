#!/bin/bash

# OAuth Security Audit Runner
# Comprehensive security testing for OAuth implementation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
REPORT_DIR="security_reports_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}           OAuth Security Audit Suite${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to check dependencies
check_dependencies() {
    echo -e "\n${YELLOW}Checking dependencies...${NC}"
    
    # Check Python packages
    for pkg in pytest httpx cryptography jwt; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            echo -e "${YELLOW}Installing $pkg...${NC}"
            pip3 install $pkg
        fi
    done
    
    echo -e "${GREEN}✓ Dependencies ready${NC}"
}

# Function to check if target is accessible
check_target() {
    echo -e "\n${YELLOW}Checking target availability...${NC}"
    
    if curl -f -s -o /dev/null "$BASE_URL/docs"; then
        echo -e "${GREEN}✓ Target is accessible at $BASE_URL${NC}"
    else
        echo -e "${RED}✗ Target not accessible at $BASE_URL${NC}"
        echo -e "${YELLOW}Please ensure the OAuth server is running${NC}"
        exit 1
    fi
}

# Function to run OWASP tests
run_owasp_tests() {
    echo -e "\n${BLUE}Running OWASP Security Tests...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    python3 test_oauth_security.py 2>&1 | tee "$REPORT_DIR/owasp_audit.log"
    
    if [ -f "oauth_security_audit_report.txt" ]; then
        mv oauth_security_audit_report.txt "$REPORT_DIR/"
    fi
}

# Function to run CSRF tests
run_csrf_tests() {
    echo -e "\n${BLUE}Running CSRF Protection Tests...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    python3 test_csrf_protection.py 2>&1 | tee "$REPORT_DIR/csrf_audit.log"
}

# Function to run automated vulnerability scanning
run_vulnerability_scan() {
    echo -e "\n${BLUE}Running Automated Vulnerability Scan...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    # Check if OWASP ZAP is available
    if command -v zap-cli &> /dev/null; then
        echo -e "${GREEN}Using OWASP ZAP for scanning...${NC}"
        
        # Start ZAP in daemon mode
        zap-cli start --start-options '-daemon' &
        ZAP_PID=$!
        sleep 10
        
        # Run scan
        zap-cli open-url "$BASE_URL"
        zap-cli spider "$BASE_URL"
        zap-cli active-scan "$BASE_URL"
        
        # Generate report
        zap-cli report -o "$REPORT_DIR/zap_report.html" -f html
        
        # Stop ZAP
        zap-cli shutdown
        kill $ZAP_PID 2>/dev/null || true
        
    # Check if Nikto is available
    elif command -v nikto &> /dev/null; then
        echo -e "${GREEN}Using Nikto for scanning...${NC}"
        nikto -h "$BASE_URL" -o "$REPORT_DIR/nikto_report.txt"
        
    else
        echo -e "${YELLOW}No automated scanners available (ZAP or Nikto)${NC}"
    fi
}

# Function to check security headers
check_security_headers() {
    echo -e "\n${BLUE}Checking Security Headers...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    {
        echo "Security Headers Analysis"
        echo "========================="
        echo ""
        
        # Make request and capture headers
        HEADERS=$(curl -s -I "$BASE_URL")
        
        # Check required security headers
        declare -a security_headers=(
            "Strict-Transport-Security"
            "X-Content-Type-Options"
            "X-Frame-Options"
            "Content-Security-Policy"
            "X-XSS-Protection"
            "Referrer-Policy"
            "Permissions-Policy"
        )
        
        for header in "${security_headers[@]}"; do
            if echo "$HEADERS" | grep -qi "$header"; then
                VALUE=$(echo "$HEADERS" | grep -i "$header" | cut -d: -f2- | tr -d '\r\n' | xargs)
                echo "✅ $header: $VALUE"
            else
                echo "❌ $header: MISSING"
            fi
        done
        
        echo ""
        
        # Check for information disclosure headers
        echo "Information Disclosure Check:"
        echo "-----------------------------"
        
        declare -a info_headers=(
            "Server"
            "X-Powered-By"
            "X-AspNet-Version"
        )
        
        for header in "${info_headers[@]}"; do
            if echo "$HEADERS" | grep -qi "$header"; then
                VALUE=$(echo "$HEADERS" | grep -i "$header" | cut -d: -f2- | tr -d '\r\n' | xargs)
                echo "⚠️  $header: $VALUE (consider removing)"
            fi
        done
        
    } > "$REPORT_DIR/security_headers.txt"
    
    cat "$REPORT_DIR/security_headers.txt"
}

# Function to test TLS/SSL configuration
test_ssl_config() {
    echo -e "\n${BLUE}Testing SSL/TLS Configuration...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    # Only run if HTTPS
    if [[ "$BASE_URL" == https://* ]]; then
        if command -v testssl &> /dev/null; then
            testssl --severity HIGH "$BASE_URL" > "$REPORT_DIR/ssl_test.txt"
        elif command -v nmap &> /dev/null; then
            DOMAIN=$(echo "$BASE_URL" | sed 's|https://||' | cut -d/ -f1)
            nmap --script ssl-enum-ciphers -p 443 "$DOMAIN" > "$REPORT_DIR/ssl_ciphers.txt"
        else
            echo -e "${YELLOW}SSL testing tools not available${NC}"
        fi
    else
        echo -e "${YELLOW}Target is not using HTTPS - skipping SSL tests${NC}"
    fi
}

# Function to generate final report
generate_final_report() {
    echo -e "\n${BLUE}Generating Final Security Report...${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    
    FINAL_REPORT="$REPORT_DIR/FINAL_SECURITY_REPORT.md"
    
    {
        echo "# OAuth Security Audit Report"
        echo ""
        echo "**Date:** $(date)"
        echo "**Target:** $BASE_URL"
        echo ""
        
        echo "## Executive Summary"
        echo ""
        
        # Count issues
        HIGH_COUNT=$(grep -c "\[HIGH\]" "$REPORT_DIR"/*.log 2>/dev/null || echo "0")
        MEDIUM_COUNT=$(grep -c "\[MEDIUM\]" "$REPORT_DIR"/*.log 2>/dev/null || echo "0")
        LOW_COUNT=$(grep -c "\[LOW\]" "$REPORT_DIR"/*.log 2>/dev/null || echo "0")
        
        echo "- **High Severity Issues:** $HIGH_COUNT"
        echo "- **Medium Severity Issues:** $MEDIUM_COUNT"
        echo "- **Low Severity Issues:** $LOW_COUNT"
        echo ""
        
        echo "## Test Results"
        echo ""
        
        # OWASP results
        if [ -f "$REPORT_DIR/oauth_security_audit_report.txt" ]; then
            echo "### OWASP Security Audit"
            echo ""
            echo '```'
            tail -n 20 "$REPORT_DIR/oauth_security_audit_report.txt"
            echo '```'
            echo ""
        fi
        
        # Security headers
        if [ -f "$REPORT_DIR/security_headers.txt" ]; then
            echo "### Security Headers"
            echo ""
            echo '```'
            cat "$REPORT_DIR/security_headers.txt"
            echo '```'
            echo ""
        fi
        
        echo "## Recommendations"
        echo ""
        echo "1. **Immediate Actions Required:**"
        echo "   - Fix all HIGH severity vulnerabilities"
        echo "   - Implement missing security headers"
        echo "   - Enable rate limiting on all endpoints"
        echo ""
        echo "2. **Best Practices:**"
        echo "   - Always require PKCE for public clients"
        echo "   - Use state parameter for CSRF protection"
        echo "   - Implement proper token storage and rotation"
        echo "   - Regular security audits and penetration testing"
        echo ""
        echo "## Compliance Status"
        echo ""
        echo "- [ ] OWASP Top 10 2021"
        echo "- [ ] OAuth 2.0 Security Best Practices (RFC 8252)"
        echo "- [ ] OAuth 2.1 Draft Compliance"
        echo "- [ ] PKCE (RFC 7636)"
        echo ""
        
    } > "$FINAL_REPORT"
    
    echo -e "${GREEN}✓ Final report generated: $FINAL_REPORT${NC}"
}

# Main execution
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --url)
                BASE_URL="$2"
                shift 2
                ;;
            --quick)
                QUICK_MODE=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --url URL     Target URL (default: http://localhost:8000)"
                echo "  --quick       Run quick scan only"
                echo "  --help        Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run security audit
    check_dependencies
    check_target
    
    echo -e "\n${GREEN}Starting Security Audit...${NC}"
    echo -e "${GREEN}Results will be saved to: $REPORT_DIR${NC}\n"
    
    # Run tests
    run_owasp_tests
    run_csrf_tests
    check_security_headers
    
    if [ "$QUICK_MODE" != "true" ]; then
        run_vulnerability_scan
        test_ssl_config
    fi
    
    # Generate final report
    generate_final_report
    
    # Summary
    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}           Security Audit Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Reports saved to: $REPORT_DIR${NC}"
    
    # Check for critical issues
    if [ "$HIGH_COUNT" -gt "0" ]; then
        echo -e "\n${RED}⚠️  WARNING: High severity issues found!${NC}"
        echo -e "${RED}Please review and fix immediately.${NC}"
        exit 1
    else
        echo -e "\n${GREEN}✅ No high severity issues found${NC}"
    fi
}

# Run main function
main "$@"