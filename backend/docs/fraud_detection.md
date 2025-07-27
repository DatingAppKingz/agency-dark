# Fraud Detection System Documentation

## Overview

The fraud detection system provides comprehensive protection against fraudulent activities in the AgencyDark platform. It uses multiple detection methods including velocity checks, pattern matching, anomaly detection, and rule-based evaluation to identify and prevent fraudulent transactions and behaviors.

## Key Features

- **Multi-layered Detection**: Combines velocity checks, pattern matching, anomaly detection, and rule-based evaluation
- **Real-time Risk Scoring**: Calculates risk scores in real-time for every transaction
- **Automated Actions**: Automatically blocks, suspends, or flags suspicious activities based on risk levels
- **Manual Review Queue**: Provides a queue for manual review of borderline cases
- **Whitelisting**: Supports whitelisting trusted entities to reduce false positives
- **Comprehensive Logging**: Logs all fraud events for analysis and reporting
- **ML-Ready Architecture**: Designed to support machine learning models for advanced detection

## Architecture

### Components

1. **FraudDetector Service**: Core service that orchestrates all fraud checks
2. **FraudDetectionMiddleware**: Middleware that intercepts sensitive API calls
3. **Models**: Database models for rules, patterns, scores, events, and queues
4. **API Endpoints**: Management endpoints for configuration and monitoring

### Detection Methods

#### 1. Velocity Checks
Monitors the rate of activities to detect unusual patterns:
- Transaction frequency per user
- Amount sums over time windows
- Multiple users from same IP
- Rapid succession patterns

#### 2. Pattern Matching
Matches transactions against known fraud patterns:
- Card testing patterns (small amounts)
- Unusual time patterns (late night high values)
- Geographic anomalies
- Payment method patterns

#### 3. Anomaly Detection
Uses statistical analysis to detect outliers:
- Z-score calculation for transaction amounts
- Time-based anomalies
- Behavioral deviations
- Historical comparisons

#### 4. Rule-Based Detection
Evaluates custom rules defined by administrators:
- Threshold-based rules
- Complex condition evaluation
- Regex pattern matching
- Multi-field validation

## Risk Scoring

The system calculates a cumulative risk score from all detection methods:

- **0-20**: Low risk (monitor only)
- **21-40**: Medium risk (flag for monitoring)
- **41-60**: High risk (restrict or review)
- **61-80**: Critical risk (suspend or review)
- **81-100**: Maximum risk (block immediately)

## Actions

Based on risk scores, the system takes automated actions:

- **MONITOR**: Log the activity but allow it
- **FLAG**: Mark for increased monitoring
- **RESTRICT**: Apply limitations to the user
- **REVIEW**: Send to manual review queue
- **SUSPEND**: Temporarily suspend the account
- **BLOCK**: Immediately block the transaction/user

## API Endpoints

### Dashboard
```
GET /api/v1/fraud-detection/dashboard
```
Returns fraud detection statistics and current status.

### Rules Management
```
POST /api/v1/fraud-detection/rules
GET /api/v1/fraud-detection/rules
```
Create and retrieve fraud detection rules.

### Pattern Management
```
POST /api/v1/fraud-detection/patterns
```
Create fraud patterns for pattern matching.

### Velocity Checks
```
POST /api/v1/fraud-detection/velocity-checks
```
Configure velocity check parameters.

### Review Queue
```
GET /api/v1/fraud-detection/review-queue
POST /api/v1/fraud-detection/review-queue/{id}/assign
POST /api/v1/fraud-detection/review-queue/{id}/resolve
```
Manage the manual review queue.

### Manual Check
```
POST /api/v1/fraud-detection/check
```
Manually run fraud check on transaction data.

### Whitelisting
```
POST /api/v1/fraud-detection/whitelist
```
Add entities to the whitelist.

## Usage Examples

### 1. Using Fraud Detection Decorator

```python
from core.middleware.fraud_detection import fraud_check

@router.post("/high-risk-operation")
@fraud_check(risk_threshold="medium")
async def high_risk_operation(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    # Operation code here
    pass
```

### 2. Manual Fraud Check

```python
from core.fraud_detection import fraud_detector

result = await fraud_detector.check_transaction(
    transaction_data={
        "amount": 1000.0,
        "currency": "USD",
        "payment_method": "card"
    },
    user_id=str(user.id),
    ip_address=request.client.host,
    session=db
)

if not result["allowed"]:
    raise HTTPException(403, "Transaction blocked")
```

### 3. Creating Custom Rules

```python
rule = FraudRule(
    name="High amount review",
    rule_type="threshold",
    fraud_type=FraudType.PAYMENT_FRAUD,
    conditions=[
        {"field": "amount", "operator": "greater_than", "value": 1000}
    ],
    risk_score=50,
    auto_action=ActionType.REVIEW,
    is_active=True
)
```

## Configuration

### Default Velocity Checks

The system comes with pre-configured velocity checks:
- 5 transactions per 5 minutes
- 20 transactions per hour
- 100 transactions per day
- Amount limits per time window
- IP-based limitations

### Default Patterns

Pre-configured patterns include:
- Card testing (multiple small transactions)
- Late night high-value transactions
- Rapid succession patterns

## Best Practices

1. **Start Conservative**: Begin with lower risk scores and adjust based on false positive rates
2. **Regular Review**: Review fraud events regularly to identify false positives
3. **Pattern Updates**: Update patterns based on new fraud trends
4. **Whitelist Management**: Maintain an up-to-date whitelist for trusted users
5. **Monitor Performance**: Track detection rates and system performance
6. **User Communication**: Provide clear messages when blocking transactions

## Integration with Other Systems

The fraud detection system integrates with:
- **Rate Limiting**: Works in conjunction with rate limiting for additional protection
- **Authentication**: Uses user authentication data for risk assessment
- **Analytics**: Provides data for fraud analytics and reporting
- **Financial Module**: Protects payment and payout operations
- **Webhooks**: Can trigger webhooks on fraud events

## Future Enhancements

1. **Machine Learning Models**: Integration of ML models for advanced pattern recognition
2. **Graph Analysis**: Detect fraud rings using relationship analysis
3. **External Data Sources**: Integration with external fraud databases
4. **Behavioral Biometrics**: Mouse movement and typing pattern analysis
5. **Device Fingerprinting**: Advanced device identification and tracking