# Documentation - File Organization

This document explains the organization of development documentation and project files.

## Directory Structure

```
docs/
├── README.md                           # Main documentation index
├── FILE_ORGANIZATION.md               # This file - explains the structure
├── CONSOLIDATED_HISTORY.md            # Complete development timeline
├── MASTER_PLANNING_DOCUMENT.md        # All planning documents consolidated
├── MASTER_TESTING_DOCUMENT.md         # Complete testing documentation
├── IMPLEMENTATION_NOTES.md            # Implementation details and progress
├── PROJECT_SUMMARY.md                 # Comprehensive project overview
├── NEXT_STEPS_QUICK_GUIDE.md          # Quick guide for next development steps
│
├── documentation/
│   ├── BEST_PRACTICES_AND_RULES.md    # Coding standards and best practices
│   └── agencydark-claude-code-prompt.md # AI assistant guidelines
│
├── production/
│   ├── README.md                      # Production deployment guide
│   ├── sla.md                         # Service Level Agreement
│   └── runbooks/
│       └── incident-response.md       # Incident response procedures
│
├── summaries/
│   └── backend-polish-complete.md     # Final project status
│
├── development-logs/
│   ├── development-log-2025-01-27.md  # Daily development log
│   ├── CURRENT_STATUS.md              # Project status snapshot
│   ├── TEST_SUMMARY.md                # Test results summary
│   └── TEST_DATA_SUMMARY.md           # Test data documentation
│
└── setup-guides/
    ├── QUICKSTART.md                  # Quick start guide
    ├── CREDENTIALS.md                 # Test credentials
    ├── DEBUG_INSTRUCTIONS.md          # General debugging instructions
    ├── DASHBOARD_DEBUG_INSTRUCTIONS.md # Dashboard-specific debugging
    ├── DASHBOARD_DATA_SETUP.md        # Dashboard data setup guide
    └── WORKING_SETUP.md               # Working environment setup
│
├── API.md                             # API documentation
├── API_GUIDE.md                       # API usage guide
├── DEPLOYMENT.md                      # Deployment instructions
├── DEVELOPMENT_LOG.md                 # Development history
├── getting-started.md                 # Getting started guide
└── webhooks.md                        # Webhooks documentation
```

## Files Remaining in Root

The following files remain in the project root as they are essential project documentation:

- **README.md** - Main project documentation
- **CHANGELOG.md** - Official change log following semantic versioning

## Navigation Guide

### For Development History
- Start with `CONSOLIDATED_HISTORY.md` for complete timeline
- Check `IMPLEMENTATION_NOTES.md` for technical details
- Review `development-logs/` for daily progress

### For Project Understanding
- Read `PROJECT_SUMMARY.md` for comprehensive overview
- Check `MASTER_PLANNING_DOCUMENT.md` for architecture decisions
- Review `summaries/backend-polish-complete.md` for final status

### For Setup and Debugging
- Use `setup-guides/QUICKSTART.md` for quick setup
- Follow `setup-guides/DEBUG_INSTRUCTIONS.md` for troubleshooting
- Check `setup-guides/CREDENTIALS.md` for test accounts

### For Testing
- See `MASTER_TESTING_DOCUMENT.md` for test strategies
- Check `development-logs/TEST_SUMMARY.md` for test results
- Review `development-logs/TEST_DATA_SUMMARY.md` for test data

## Updates

This organization was created on January 29, 2025 to consolidate and structure all development documentation. All markdown files from the root directory (except README.md and CHANGELOG.md) have been moved to the docs/ directory, and the claude-history folder has been renamed to docs/ for better clarity.