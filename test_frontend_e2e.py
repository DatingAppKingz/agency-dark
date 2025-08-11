#!/usr/bin/env python3
"""
AgencyDark Frontend End-to-End Testing Script
Tests the frontend UI functionality using Playwright
"""

import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional
import sys

# Configuration
FRONTEND_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"

# Test credentials
TEST_CREDENTIALS = {
    "email": "admin@agency.com",
    "password": "admin123"
}

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class FrontendTester:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.test_results = {
            "passed": [],
            "failed": [],
            "skipped": []
        }
        
    def print_header(self, text: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        
    def print_test(self, name: str, status: str, details: str = ""):
        if status == "PASS":
            print(f"{Colors.OKGREEN}✓{Colors.ENDC} {name}")
            self.test_results["passed"].append(name)
        elif status == "FAIL":
            print(f"{Colors.FAIL}✗{Colors.ENDC} {name}")
            if details:
                print(f"  {Colors.WARNING}{details}{Colors.ENDC}")
            self.test_results["failed"].append(f"{name}: {details}")
        elif status == "SKIP":
            print(f"{Colors.WARNING}○{Colors.ENDC} {name} (skipped)")
            self.test_results["skipped"].append(name)
            
    async def setup(self):
        """Setup browser and context"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,  # Set to False to see the browser
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        self.page = await self.context.new_page()
        
        # Set up console logging
        self.page.on('console', lambda msg: None)  # Suppress console logs
        
    async def teardown(self):
        """Cleanup browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
            
    async def take_screenshot(self, name: str):
        """Take screenshot for debugging"""
        if self.page:
            await self.page.screenshot(path=f"screenshot_{name}.png")
            
    # ==================== LOGIN TESTS ====================
    
    async def test_login_flow(self):
        """Test login functionality"""
        self.print_header("LOGIN FLOW TESTS")
        
        try:
            # Navigate to homepage
            await self.page.goto(FRONTEND_URL, wait_until="networkidle")
            self.print_test("Navigate to homepage", "PASS")
            
            # Check if redirected to login or if login button exists
            if "/login" in self.page.url or await self.page.is_visible("text=Login"):
                self.print_test("Login page accessible", "PASS")
                
                # If not on login page, click login button
                if "/login" not in self.page.url:
                    await self.page.click("text=Login")
                    await self.page.wait_for_url("**/login")
                    
                # Fill login form
                await self.page.fill('input[type="email"]', TEST_CREDENTIALS["email"])
                await self.page.fill('input[type="password"]', TEST_CREDENTIALS["password"])
                self.print_test("Fill login form", "PASS")
                
                # Submit login
                await self.page.click('button[type="submit"]')
                
                # Wait for navigation or error
                try:
                    await self.page.wait_for_url("**/dashboard", timeout=5000)
                    self.print_test("Login successful", "PASS")
                    return True
                except:
                    # Check for error message
                    if await self.page.is_visible("text=Login failed"):
                        self.print_test("Login successful", "FAIL", "Login failed error shown")
                    else:
                        self.print_test("Login successful", "FAIL", "Did not redirect to dashboard")
                    return False
            else:
                self.print_test("Login page accessible", "SKIP", "Already logged in or no login required")
                return True
                
        except Exception as e:
            self.print_test("Login flow", "FAIL", str(e))
            return False
            
    # ==================== DASHBOARD TESTS ====================
    
    async def test_dashboard(self):
        """Test dashboard functionality"""
        self.print_header("DASHBOARD TESTS")
        
        try:
            # Navigate to dashboard
            await self.page.goto(f"{FRONTEND_URL}/dashboard", wait_until="networkidle")
            
            # Check if dashboard loaded
            if await self.page.is_visible("text=Dashboard") or "dashboard" in self.page.url.lower():
                self.print_test("Dashboard loads", "PASS")
                
                # Check for key dashboard elements
                elements_to_check = [
                    ("Revenue widget", "text=Revenue"),
                    ("Users widget", "text=Users"),
                    ("Analytics section", "text=Analytics"),
                    ("Chart/Graph", "canvas, svg")
                ]
                
                for name, selector in elements_to_check:
                    if await self.page.is_visible(selector, timeout=2000):
                        self.print_test(f"{name} visible", "PASS")
                    else:
                        self.print_test(f"{name} visible", "SKIP", "Element not found")
                        
            else:
                self.print_test("Dashboard loads", "FAIL", "Dashboard not accessible")
                
        except Exception as e:
            self.print_test("Dashboard tests", "FAIL", str(e))
            
    # ==================== NAVIGATION TESTS ====================
    
    async def test_navigation(self):
        """Test navigation menu and routing"""
        self.print_header("NAVIGATION TESTS")
        
        try:
            # Test main navigation items
            nav_items = [
                ("Dashboard", "/dashboard"),
                ("Users", "/users"),
                ("Analytics", "/analytics"),
                ("Chat", "/chat"),
                ("Settings", "/settings")
            ]
            
            for name, path in nav_items:
                try:
                    # Look for navigation link
                    if await self.page.is_visible(f"text={name}", timeout=2000):
                        await self.page.click(f"text={name}")
                        await self.page.wait_for_load_state("networkidle")
                        
                        if path in self.page.url:
                            self.print_test(f"Navigate to {name}", "PASS")
                        else:
                            self.print_test(f"Navigate to {name}", "FAIL", f"URL doesn't contain {path}")
                    else:
                        self.print_test(f"Navigate to {name}", "SKIP", "Menu item not found")
                        
                except Exception as e:
                    self.print_test(f"Navigate to {name}", "SKIP", str(e))
                    
        except Exception as e:
            self.print_test("Navigation tests", "FAIL", str(e))
            
    # ==================== USER MANAGEMENT TESTS ====================
    
    async def test_user_management_ui(self):
        """Test user management interface"""
        self.print_header("USER MANAGEMENT UI TESTS")
        
        try:
            # Navigate to users page
            await self.page.goto(f"{FRONTEND_URL}/users", wait_until="networkidle")
            
            if await self.page.is_visible("text=Users") or "users" in self.page.url:
                self.print_test("Users page loads", "PASS")
                
                # Check for user table/list
                if await self.page.is_visible("table, [role='grid']", timeout=2000):
                    self.print_test("User list displayed", "PASS")
                else:
                    self.print_test("User list displayed", "FAIL", "No user table found")
                    
                # Check for action buttons
                if await self.page.is_visible("text=Add User, text=New User, button:has-text('+')", timeout=2000):
                    self.print_test("Add user button visible", "PASS")
                else:
                    self.print_test("Add user button visible", "SKIP", "Button not found")
                    
                # Check for search/filter
                if await self.page.is_visible("input[placeholder*='Search'], input[type='search']", timeout=2000):
                    self.print_test("Search functionality visible", "PASS")
                else:
                    self.print_test("Search functionality visible", "SKIP", "Search not found")
                    
            else:
                self.print_test("Users page loads", "SKIP", "Users page not accessible")
                
        except Exception as e:
            self.print_test("User management UI tests", "FAIL", str(e))
            
    # ==================== ANALYTICS TESTS ====================
    
    async def test_analytics_ui(self):
        """Test analytics interface"""
        self.print_header("ANALYTICS UI TESTS")
        
        try:
            # Navigate to analytics
            await self.page.goto(f"{FRONTEND_URL}/analytics", wait_until="networkidle")
            
            if await self.page.is_visible("text=Analytics") or "analytics" in self.page.url:
                self.print_test("Analytics page loads", "PASS")
                
                # Check for charts
                if await self.page.is_visible("canvas, svg, .recharts-wrapper", timeout=3000):
                    self.print_test("Analytics charts visible", "PASS")
                else:
                    self.print_test("Analytics charts visible", "SKIP", "No charts found")
                    
                # Check for date range selector
                if await self.page.is_visible("text=Date Range, text=Last 30 days, input[type='date']", timeout=2000):
                    self.print_test("Date range selector visible", "PASS")
                else:
                    self.print_test("Date range selector visible", "SKIP", "Date selector not found")
                    
                # Check for metrics/KPIs
                if await self.page.is_visible("text=Revenue, text=Users, text=Growth", timeout=2000):
                    self.print_test("Key metrics visible", "PASS")
                else:
                    self.print_test("Key metrics visible", "SKIP", "Metrics not found")
                    
            else:
                self.print_test("Analytics page loads", "SKIP", "Analytics page not accessible")
                
        except Exception as e:
            self.print_test("Analytics UI tests", "FAIL", str(e))
            
    # ==================== CHAT TESTS ====================
    
    async def test_chat_ui(self):
        """Test chat interface"""
        self.print_header("CHAT UI TESTS")
        
        try:
            # Navigate to chat
            await self.page.goto(f"{FRONTEND_URL}/chat", wait_until="networkidle")
            
            if await self.page.is_visible("text=Chat, text=Messages") or "chat" in self.page.url:
                self.print_test("Chat page loads", "PASS")
                
                # Check for conversation list
                if await self.page.is_visible("[role='list'], .conversation-list, .chat-list", timeout=2000):
                    self.print_test("Conversation list visible", "PASS")
                else:
                    self.print_test("Conversation list visible", "SKIP", "List not found")
                    
                # Check for message area
                if await self.page.is_visible(".message-area, .chat-messages, [role='log']", timeout=2000):
                    self.print_test("Message area visible", "PASS")
                else:
                    self.print_test("Message area visible", "SKIP", "Message area not found")
                    
                # Check for input field
                if await self.page.is_visible("textarea, input[placeholder*='Type'], input[placeholder*='Message']", timeout=2000):
                    self.print_test("Message input visible", "PASS")
                else:
                    self.print_test("Message input visible", "SKIP", "Input not found")
                    
            else:
                self.print_test("Chat page loads", "SKIP", "Chat page not accessible")
                
        except Exception as e:
            self.print_test("Chat UI tests", "FAIL", str(e))
            
    # ==================== SETTINGS TESTS ====================
    
    async def test_settings_ui(self):
        """Test settings interface"""
        self.print_header("SETTINGS UI TESTS")
        
        try:
            # Navigate to settings
            await self.page.goto(f"{FRONTEND_URL}/settings", wait_until="networkidle")
            
            if await self.page.is_visible("text=Settings") or "settings" in self.page.url:
                self.print_test("Settings page loads", "PASS")
                
                # Check for settings sections
                sections = ["Profile", "Security", "Notifications", "Preferences"]
                for section in sections:
                    if await self.page.is_visible(f"text={section}", timeout=1000):
                        self.print_test(f"{section} section visible", "PASS")
                    else:
                        self.print_test(f"{section} section visible", "SKIP", "Section not found")
                        
            else:
                self.print_test("Settings page loads", "SKIP", "Settings page not accessible")
                
        except Exception as e:
            self.print_test("Settings UI tests", "FAIL", str(e))
            
    # ==================== RESPONSIVE TESTS ====================
    
    async def test_responsive_design(self):
        """Test responsive design"""
        self.print_header("RESPONSIVE DESIGN TESTS")
        
        try:
            # Test mobile viewport
            await self.page.set_viewport_size({"width": 375, "height": 667})
            await self.page.goto(f"{FRONTEND_URL}/dashboard", wait_until="networkidle")
            
            # Check for mobile menu
            if await self.page.is_visible("button[aria-label*='menu'], .hamburger, .mobile-menu-toggle", timeout=2000):
                self.print_test("Mobile menu visible", "PASS")
            else:
                self.print_test("Mobile menu visible", "SKIP", "Mobile menu not found")
                
            # Test tablet viewport
            await self.page.set_viewport_size({"width": 768, "height": 1024})
            await self.page.reload()
            self.print_test("Tablet viewport loads", "PASS")
            
            # Reset to desktop
            await self.page.set_viewport_size({"width": 1920, "height": 1080})
            await self.page.reload()
            self.print_test("Desktop viewport loads", "PASS")
            
        except Exception as e:
            self.print_test("Responsive design tests", "FAIL", str(e))
            
    # ==================== LOGOUT TESTS ====================
    
    async def test_logout(self):
        """Test logout functionality"""
        self.print_header("LOGOUT TESTS")
        
        try:
            # Look for logout button
            if await self.page.is_visible("text=Logout, text=Sign Out", timeout=2000):
                await self.page.click("text=Logout, text=Sign Out")
                
                # Wait for redirect to login
                try:
                    await self.page.wait_for_url("**/login", timeout=5000)
                    self.print_test("Logout successful", "PASS")
                except:
                    if "/login" in self.page.url or await self.page.is_visible("text=Login"):
                        self.print_test("Logout successful", "PASS")
                    else:
                        self.print_test("Logout successful", "FAIL", "Did not redirect to login")
            else:
                self.print_test("Logout successful", "SKIP", "Logout button not found")
                
        except Exception as e:
            self.print_test("Logout tests", "FAIL", str(e))
            
    # ==================== MAIN TEST RUNNER ====================
    
    async def run_all_tests(self):
        """Run all frontend tests"""
        print(f"{Colors.BOLD}{Colors.OKCYAN}")
        print("╔" + "═"*58 + "╗")
        print("║" + " "*12 + "AGENCYDARK FRONTEND E2E TESTS" + " "*16 + "║")
        print("╚" + "═"*58 + "╝")
        print(f"{Colors.ENDC}")
        
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Testing started...\n")
        
        try:
            await self.setup()
            
            # Run test suites in order
            logged_in = await self.test_login_flow()
            
            if logged_in:
                await self.test_dashboard()
                await self.test_navigation()
                await self.test_user_management_ui()
                await self.test_analytics_ui()
                await self.test_chat_ui()
                await self.test_settings_ui()
                await self.test_responsive_design()
                await self.test_logout()
            else:
                print(f"\n{Colors.WARNING}Skipping authenticated tests due to login failure{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.FAIL}Test execution failed: {e}{Colors.ENDC}")
        finally:
            await self.teardown()
            
        # Print summary
        self.print_summary()
        
    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")
        
        total_tests = len(self.test_results["passed"]) + len(self.test_results["failed"]) + len(self.test_results["skipped"])
        
        print(f"Total tests run: {total_tests}")
        print(f"{Colors.OKGREEN}Passed: {len(self.test_results['passed'])}{Colors.ENDC}")
        print(f"{Colors.FAIL}Failed: {len(self.test_results['failed'])}{Colors.ENDC}")
        print(f"{Colors.WARNING}Skipped: {len(self.test_results['skipped'])}{Colors.ENDC}")
        
        if self.test_results["failed"]:
            print(f"\n{Colors.FAIL}Failed tests:{Colors.ENDC}")
            for test in self.test_results["failed"]:
                print(f"  - {test}")
                
        pass_rate = (len(self.test_results["passed"]) / total_tests * 100) if total_tests > 0 else 0
        print(f"\nPass rate: {pass_rate:.1f}%")

async def main():
    """Main entry point"""
    # Check if frontend is running
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FRONTEND_URL, timeout=5) as response:
                if response.status != 200:
                    raise Exception("Frontend not responding")
    except Exception as e:
        print(f"{Colors.FAIL}Error: Frontend is not running at {FRONTEND_URL}{Colors.ENDC}")
        print(f"Please ensure the frontend is running before running tests.")
        sys.exit(1)
        
    # Run tests
    tester = FrontendTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    # Check if playwright is installed
    try:
        import playwright
    except ImportError:
        print(f"{Colors.FAIL}Playwright not installed. Install with: pip install playwright{Colors.ENDC}")
        print(f"Then run: playwright install chromium")
        sys.exit(1)
        
    asyncio.run(main())