# Permission Flow Diagrams

## Overview

This document provides visual representations of permission flows in the Agency Dark platform using Mermaid diagrams.

## Main Permission Check Flow

```mermaid
flowchart TD
    A[User Request] --> B{Authenticated?}
    B -->|No| C[401 Unauthorized]
    B -->|Yes| D{Rate Limited?}
    
    D -->|Yes| E[429 Too Many Requests]
    D -->|No| F{Check Feature Permission}
    
    F --> G[Get User Permissions]
    F --> H[Get Role Permissions]
    F --> I[Get Agency Defaults]
    
    G --> J[Merge Permissions]
    H --> J
    I --> J
    
    J --> K{Evaluate Access}
    
    K -->|Denied| L{Explicit Deny?}
    L -->|Yes| M[403 Forbidden]
    L -->|No| N{Time Restriction?}
    
    N -->|Yes| O[403 Outside Hours]
    N -->|No| P{Geographic Restriction?}
    
    P -->|Yes| Q[403 Location Blocked]
    P -->|No| R{MFA Required?}
    
    R -->|Yes| S{MFA Valid?}
    S -->|No| T[401 MFA Required]
    S -->|Yes| U[Check Data Sensitivity]
    R -->|No| U
    
    U --> V{Sensitivity Allowed?}
    V -->|No| W[403 Insufficient Privilege]
    V -->|Yes| X[200 Access Granted]
    
    K -->|Allowed| Y[Log Audit Trail]
    Y --> X
    
    X --> Z[Execute Request]
```

## Export Permission Flow

```mermaid
flowchart TD
    A[Export Request] --> B{Check Export Permission}
    
    B --> C{Format Allowed?}
    C -->|No| D[400 Invalid Format]
    C -->|Yes| E{Check Row Limit}
    
    E --> F{Rows > Max?}
    F -->|Yes| G[400 Too Many Rows]
    F -->|No| H{Check Export Quota}
    
    H --> I[Get Daily Usage]
    I --> J{Quota Exceeded?}
    
    J -->|Yes| K[429 Quota Exceeded]
    J -->|No| L{Check Rate Limit}
    
    L --> M[Get Hourly Exports]
    M --> N{Rate Limited?}
    
    N -->|Yes| O[429 Rate Limited]
    N -->|No| P{Contains PII?}
    
    P -->|Yes| Q{PII Permission?}
    Q -->|No| R[403 No PII Access]
    Q -->|Yes| S{Requires Approval?}
    
    P -->|No| T[Generate Export]
    
    S -->|Yes| U[Create Approval Request]
    S -->|No| T
    
    T --> V[Log Export Audit]
    V --> W[200 Export Started]
    
    U --> X[202 Approval Pending]
```

## Analytics Permission Flow

```mermaid
flowchart TD
    A[Analytics Request] --> B{Check Analytics Permission}
    
    B --> C{Scope Check}
    C --> D{Own Data?}
    D -->|Yes| E[Scope: OWN]
    D -->|No| F{Team Data?}
    
    F -->|Yes| G{Is Team Leader?}
    G -->|No| H[403 Not Team Leader]
    G -->|Yes| I[Scope: TEAM]
    
    F -->|No| J{Agency Data?}
    J -->|Yes| K{Manager Role?}
    K -->|No| L[403 Not Manager]
    K -->|Yes| M[Scope: AGENCY]
    
    J -->|No| N{Global Data?}
    N -->|Yes| O{Admin Role?}
    O -->|No| P[403 Not Admin]
    O -->|Yes| Q[Scope: GLOBAL]
    
    E --> R{Check Metrics}
    I --> R
    M --> R
    Q --> R
    
    R --> S{Financial Metrics?}
    S -->|Yes| T{Can View Financial?}
    T -->|No| U[Filter Financial Data]
    T -->|Yes| V[Include Financial]
    
    S -->|No| V
    U --> V
    
    V --> W{Time Range Check}
    W --> X{Real-time?}
    X -->|Yes| Y{Real-time Allowed?}
    Y -->|No| Z[Use Cached Data]
    Y -->|Yes| AA[Fetch Real-time]
    
    X -->|No| AB{Historical?}
    AB -->|Yes| AC{Historical Allowed?}
    AC -->|No| AD[400 Time Range Limited]
    AC -->|Yes| AE[Fetch Historical]
    
    AB -->|No| AE
    
    Z --> AF[Return Analytics]
    AA --> AF
    AE --> AF
    
    AF --> AG[Log Analytics Access]
    AG --> AH[200 Success]
```

## Rate Limiting Flow

```mermaid
flowchart TD
    A[Request] --> B[Identify Request]
    
    B --> C{Get Applicable Limits}
    C --> D[Global Limit]
    C --> E[User Limit]
    C --> F[IP Limit]
    C --> G[Endpoint Limit]
    
    D --> H[Check Each Limit]
    E --> H
    F --> H
    G --> H
    
    H --> I{Cost-based?}
    I -->|Yes| J[Calculate Request Cost]
    I -->|No| K[Use Count-based]
    
    J --> L[Check Cost Budget]
    K --> M[Check Request Count]
    
    L --> N{Budget Available?}
    M --> O{Count Available?}
    
    N -->|No| P[Rate Limited]
    N -->|Yes| Q[Deduct Cost]
    
    O -->|No| P
    O -->|Yes| R[Increment Count]
    
    Q --> S[Allow Request]
    R --> S
    
    P --> T{Adaptive Mode?}
    T -->|Yes| U[Check System Load]
    T -->|No| V[429 Response]
    
    U --> W{High Load?}
    W -->|Yes| X[Tighten Limits]
    W -->|No| Y{Low Load?}
    
    Y -->|Yes| Z[Relax Limits]
    Y -->|No| AA[Maintain Limits]
    
    X --> V
    Z --> AB{Retry Allowed?}
    AA --> V
    
    AB -->|Yes| S
    AB -->|No| V
```

## Audit Trail Flow

```mermaid
flowchart TD
    A[Security Event] --> B{Event Type}
    
    B -->|Login| C[Login Audit]
    B -->|Permission Check| D[Permission Audit]
    B -->|Data Access| E[Data Access Audit]
    B -->|Configuration Change| F[Config Change Audit]
    
    C --> G[Capture Context]
    D --> G
    E --> G
    F --> G
    
    G --> H[User Info]
    G --> I[IP Address]
    G --> J[User Agent]
    G --> K[Timestamp]
    G --> L[Session ID]
    
    H --> M[Calculate Risk Score]
    I --> M
    J --> M
    K --> M
    L --> M
    
    M --> N{Risk Level}
    N -->|Low| O[Info Severity]
    N -->|Medium| P[Warning Severity]
    N -->|High| Q[Error Severity]
    N -->|Critical| R[Critical Severity]
    
    O --> S[Create Audit Log]
    P --> S
    Q --> S
    R --> S
    
    S --> T{Compliance Mode?}
    T -->|GDPR| U[Add GDPR Fields]
    T -->|SOX| V[Add SOX Fields]
    T -->|HIPAA| W[Add HIPAA Fields]
    T -->|None| X[Standard Fields]
    
    U --> Y[Store Audit Log]
    V --> Y
    W --> Y
    X --> Y
    
    Y --> Z{Alert Required?}
    Z -->|Yes| AA[Send Alert]
    Z -->|No| AB[Complete]
    
    AA --> AB
```

## API Key Validation Flow

```mermaid
flowchart TD
    A[API Request] --> B{Has API Key?}
    B -->|No| C[401 No API Key]
    B -->|Yes| D[Extract Key]
    
    D --> E[Hash API Key]
    E --> F{Key in Cache?}
    
    F -->|Yes| G[Get Cached Info]
    F -->|No| H[Query Database]
    
    H --> I{Key Found?}
    I -->|No| J[401 Invalid Key]
    I -->|Yes| K[Load Key Info]
    
    G --> L{Key Active?}
    K --> L
    
    L -->|No| M[401 Key Inactive]
    L -->|Yes| N{Key Expired?}
    
    N -->|Yes| O[401 Key Expired]
    N -->|No| P{IP Allowed?}
    
    P -->|No| Q[403 IP Blocked]
    P -->|Yes| R{Check Scopes}
    
    R --> S{Endpoint in Scope?}
    S -->|No| T[403 Out of Scope]
    S -->|Yes| U{Rate Limit Check}
    
    U --> V{Limited?}
    V -->|Yes| W[429 Rate Limited]
    V -->|No| X[Update Usage]
    
    X --> Y[Cache Key Info]
    Y --> Z[Allow Request]
    
    Z --> AA[Log API Usage]
```

## Permission Priority Resolution

```mermaid
flowchart TD
    A[Multiple Permissions] --> B[Sort by Priority]
    
    B --> C[User Permissions - Priority 100]
    B --> D[Role Permissions - Priority 50]
    B --> E[Agency Permissions - Priority 25]
    B --> F[System Defaults - Priority 1]
    
    C --> G{Has Explicit Deny?}
    G -->|Yes| H[DENY - Immediate]
    G -->|No| I{Has Allow?}
    
    I -->|Yes| J[Check Next Level]
    I -->|No| J
    
    D --> K{Has Explicit Deny?}
    K -->|Yes| H
    K -->|No| L{Has Allow?}
    
    L -->|Yes| M[Mark Allowed]
    L -->|No| N[Check Next Level]
    
    E --> O{Has Settings?}
    O -->|Yes| P[Apply Settings]
    O -->|No| Q[Check System Default]
    
    F --> R[Apply Defaults]
    
    M --> S{All Levels Checked?}
    N --> S
    P --> S
    R --> S
    
    S -->|No| T[Continue Checking]
    S -->|Yes| U{Final Decision}
    
    U --> V{Any Explicit Deny?}
    V -->|Yes| W[DENY]
    V -->|No| X{Any Allow?}
    
    X -->|Yes| Y[ALLOW]
    X -->|No| Z[DENY - Default]
```

## Emergency Response Flow

```mermaid
flowchart TD
    A[Security Incident] --> B{Incident Type}
    
    B -->|Data Breach| C[Lockdown Mode]
    B -->|DDoS Attack| D[Rate Limit Mode]
    B -->|Unauthorized Access| E[Revoke Mode]
    
    C --> F[Disable Exports]
    C --> G[Disable API Keys]
    C --> H[Force Re-auth]
    
    D --> I[Activate Strict Limits]
    D --> J[Enable Geo Blocking]
    D --> K[Cache Static Content]
    
    E --> L[Revoke Sessions]
    E --> M[Reset Passwords]
    E --> N[Audit All Access]
    
    F --> O[Alert Admins]
    G --> O
    H --> O
    I --> O
    J --> O
    K --> O
    L --> O
    M --> O
    N --> O
    
    O --> P{Auto-Response?}
    P -->|Yes| Q[Execute Playbook]
    P -->|No| R[Wait for Admin]
    
    Q --> S[Log All Actions]
    R --> S
    
    S --> T[Monitor Status]
    T --> U{Threat Resolved?}
    
    U -->|No| V[Maintain Protection]
    U -->|Yes| W[Begin Recovery]
    
    V --> T
    
    W --> X[Restore Services]
    X --> Y[Post-Incident Review]
    Y --> Z[Update Playbooks]
```

## Data Classification Flow

```mermaid
flowchart TD
    A[Data Request] --> B[Identify Data Type]
    
    B --> C{Classification Level}
    C -->|Public| D[No Restrictions]
    C -->|Internal| E[Employee Only]
    C -->|Confidential| F[Need to Know]
    C -->|Restricted| G[Special Access]
    
    D --> H[Allow Access]
    
    E --> I{Is Employee?}
    I -->|No| J[Deny Access]
    I -->|Yes| K[Check Purpose]
    
    F --> L{Has Business Need?}
    L -->|No| J
    L -->|Yes| M{Manager Approval?}
    M -->|No| N[Request Approval]
    M -->|Yes| O{MFA Enabled?}
    
    G --> P{Admin Role?}
    P -->|No| J
    P -->|Yes| Q{Compliance Training?}
    Q -->|No| R[Require Training]
    Q -->|Yes| S{Audit Committee Approval?}
    S -->|No| T[Request Committee Review]
    S -->|Yes| O
    
    O -->|No| U[Require MFA]
    O -->|Yes| V[Grant Access]
    
    K --> W{Valid Purpose?}
    W -->|No| J
    W -->|Yes| V
    
    V --> X[Log Access]
    X --> Y[Set Expiration]
    Y --> Z[Monitor Usage]
```

## Implementation Notes

1. **Performance Considerations**
   - Cache permission results for 5 minutes
   - Use Redis for distributed caching
   - Batch permission checks when possible

2. **Security Considerations**
   - Always fail closed (deny by default)
   - Log all permission denials
   - Alert on unusual patterns

3. **Monitoring Points**
   - Permission check latency
   - Cache hit rates
   - Denial rates by user/role
   - Rate limit violations

4. **Integration Points**
   - Authentication service
   - Rate limiting service
   - Audit logging service
   - Cache layer
   - Database layer