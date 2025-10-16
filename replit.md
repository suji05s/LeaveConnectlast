# Online Leave Portal

A Flask-based leave management system with employee leave requests, manager approvals, and calendar visualization.

## Overview

This application provides a complete leave management solution where:
- Employees can request leave (sick, vacation, personal)
- Managers can approve or reject leave requests
- Leave balances are tracked automatically
- Calendar view shows approved leaves
- Authentication powered by Replit Auth (OIDC)

## Recent Changes

**October 16, 2025**
- Initial implementation of leave portal
- Integrated Replit Auth for user authentication
- Created database models for users, leave requests, and balances
- Implemented employee and manager dashboards
- Added calendar view with FullCalendar.js
- Configured Flask workflow on port 5000

## Project Architecture

### Backend (Flask/Python)
- **app.py**: Flask application initialization with SQLAlchemy
- **models.py**: Database models (User, OAuth, LeaveBalance, LeaveRequest)
- **replit_auth.py**: Replit Auth/OIDC integration using Flask-Dance
- **routes.py**: Application routes and business logic
- **main.py**: Application entry point

### Frontend (HTML/Bootstrap/JavaScript)
- **templates/**: Jinja2 templates with Bootstrap 5 styling
  - Landing page for unauthenticated users
  - Employee dashboard with leave balance and request history
  - Leave request form with validation
  - Manager dashboard for approvals
  - Calendar view with FullCalendar.js
- **static/**: Static assets (currently minimal, using CDNs)

### Database Schema
- **users**: User authentication and profile data (managed by Replit Auth)
- **oauth**: OAuth tokens and session management (required for Replit Auth)
- **leave_balances**: Employee leave allocations (sick: 10, vacation: 15, personal: 5)
- **leave_requests**: Leave request records with status tracking

## Key Features

1. **Authentication**: Replit Auth with support for Google, GitHub, X, Apple, and email login
2. **Leave Request**: Submit requests with date range, type, and reason
3. **Leave Balance**: Automatic balance tracking and deduction on approval
4. **Manager Workflow**: Approve/reject requests with comments
5. **Calendar View**: Visual representation of approved leaves
6. **Role Switching**: Demo feature to switch between employee and manager roles

## Security Considerations

### Authentication Security
- Uses Replit Auth (OIDC/OAuth2) with PKCE for authorization code flow
- Session tokens stored server-side in PostgreSQL
- Full JWT signature verification enforced using PyJWT with JWKS
- Validates JWT signature (RS256), issuer, audience (REPL_ID), and expiration
- Fetches and uses Replit's public keys for signature validation
- Comprehensive error handling for expired, invalid, or mismatched tokens
- Token claims verified before user authentication is granted

### Best Practices
- Environment variables for sensitive configuration (SESSION_SECRET, DATABASE_URL)
- Server-side validation of all leave requests
- Role-based access control for manager functions
- HTTPS enforcement via ProxyFix middleware

## Environment Variables

Required:
- `DATABASE_URL`: PostgreSQL connection string (auto-configured)
- `SESSION_SECRET`: Flask session secret (auto-configured)
- `REPL_ID`: Replit workspace identifier (auto-configured)

Optional:
- `ISSUER_URL`: OIDC issuer URL (defaults to https://replit.com/oidc)

## Running the Application

The Flask server runs automatically via the configured workflow:
```bash
python main.py
```

Server listens on `0.0.0.0:5000`

## Future Enhancements

- Email notifications for leave status updates
- Multi-level approval workflows
- Admin panel for policy management
- Leave balance carry-forward rules
- Holiday calendar integration
- Report generation and analytics
