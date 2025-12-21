# LINE LIQUIDATION PLAN
## CEO Directive 2025-12-21-B: Position Flattening

**Directive:** Close all positions opened during cascade failure
**Execution Date:** Monday, December 23, 2025
**Executor:** LINE (Local Infrastructure, Network & Execution)
**Authorization:** CEO Directive 2025-12-21-B, Section 4

---

## 1. PRE-MARKET STATE (Snapshot: 2025-12-21T00:40:42Z)

| Metric | Value |
|--------|-------|
| Portfolio Value | $101,419.32 |
| Cash | -$93,469.98 |
| Margin Used | YES (VIOLATION) |
| Total Exposure | $194,889.30 (192%) |
| Buying Power | $7,949.34 |

---

## 2. POSITIONS TO LIQUIDATE

### Position 1: MSTR (MicroStrategy)

| Field | Value |
|-------|-------|
| Symbol | MSTR |
| Quantity | 1,088 shares |
| Side | LONG |
| Avg Entry Price | $164.33 |
| Market Value (Fri close) | $179,324.16 |
| Portfolio % | 176.8% |
| Unrealized P/L | +$529.59 |
| **Action** | **SELL 1,088 shares** |

### Position 2: NVDA (NVIDIA)

| Field | Value |
|-------|-------|
| Symbol | NVDA |
| Quantity | 86 shares |
| Side | LONG |
| Avg Entry Price | $173.76 |
| Market Value (Fri close) | $15,565.14 |
| Portfolio % | 15.3% |
| Unrealized P/L | +$621.74 |
| **Action** | **SELL 86 shares** |

---

## 3. EXECUTION SEQUENCE

### Phase 1: Pre-Market Verification (9:00 AM ET)

```
1. Verify broker connectivity
2. Confirm position quantities match plan
3. Check for any overnight corporate actions
4. Verify no pending orders exist
5. Capture pre-execution broker snapshot
```

### Phase 2: Market Open Execution (9:30 AM ET)

**Order 1: MSTR Liquidation**
```
Type: MARKET ORDER
Symbol: MSTR
Side: SELL
Quantity: 1088
Time in Force: DAY
Priority: EXECUTE FIRST (larger position)
```

**Order 2: NVDA Liquidation** (after MSTR confirmed)
```
Type: MARKET ORDER
Symbol: NVDA
Side: SELL
Quantity: 86
Time in Force: DAY
Priority: EXECUTE SECOND
```

### Phase 3: Execution Verification (9:35 AM ET)

```
1. Confirm both orders filled
2. Verify zero open positions
3. Verify cash is positive (no margin)
4. Capture post-execution broker snapshot
5. Calculate realized P/L
```

---

## 4. EXPECTED POST-LIQUIDATION STATE

| Metric | Expected Value |
|--------|----------------|
| Open Positions | 0 |
| Margin Used | NO |
| Cash | ~$100,000+ (positive) |
| Exposure | 0% |

---

## 5. ALPACA API COMMANDS

### Pre-Execution Verification
```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

client = TradingClient(api_key, secret_key, paper=True)

# Verify positions
positions = client.get_all_positions()
for p in positions:
    print(f"{p.symbol}: {p.qty} shares @ ${p.avg_entry_price}")

# Verify no pending orders
orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
assert len(orders) == 0, "Pending orders exist - resolve first"
```

### Execute Liquidation
```python
# MSTR Liquidation
mstr_order = client.submit_order(MarketOrderRequest(
    symbol="MSTR",
    qty=1088,
    side=OrderSide.SELL,
    time_in_force=TimeInForce.DAY
))
print(f"MSTR order submitted: {mstr_order.id}")

# Wait for MSTR fill confirmation
import time
time.sleep(5)
mstr_filled = client.get_order_by_id(mstr_order.id)
assert mstr_filled.status == 'filled', f"MSTR not filled: {mstr_filled.status}"

# NVDA Liquidation
nvda_order = client.submit_order(MarketOrderRequest(
    symbol="NVDA",
    qty=86,
    side=OrderSide.SELL,
    time_in_force=TimeInForce.DAY
))
print(f"NVDA order submitted: {nvda_order.id}")
```

### Post-Execution Verification
```python
# Verify zero positions
positions = client.get_all_positions()
assert len(positions) == 0, f"Positions remain: {[p.symbol for p in positions]}"

# Verify positive cash
account = client.get_account()
assert float(account.cash) > 0, f"Cash still negative: {account.cash}"

print(f"Liquidation complete. Cash: ${float(account.cash):,.2f}")
```

---

## 6. POST-CLOSE RECONCILIATION (4:00 PM ET)

### Database Synchronization

```sql
-- Mark all open trades as CLOSED
UPDATE fhq_canonical.g5_paper_trades
SET
    exit_timestamp = NOW(),
    exit_price = <actual_fill_price>,
    exit_reason = 'CEO_DIRECTIVE_LIQUIDATION',
    realized_pnl = <calculated_pnl>
WHERE exit_timestamp IS NULL
  AND symbol IN ('MSTR', 'NVDA');

-- Update signal states
UPDATE fhq_canonical.g5_signal_state
SET
    current_state = 'DORMANT',
    position_direction = NULL,
    position_entry_price = NULL,
    position_size = NULL,
    last_transition = 'PRIMED_TO_DORMANT',
    last_transition_at = NOW()
WHERE current_state = 'PRIMED';
```

### Broker Reconciliation Daemon

```bash
cd /c/fhq-market-system/vision-ios/03_FUNCTIONS
python broker_reconciliation_daemon.py --once
```

Expected output:
- `divergence_detected: false`
- `alpaca_positions: 0`
- `fhq_open_trades: 0`

---

## 7. GOVERNANCE LOG

After successful liquidation, log to governance:

```sql
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    agent_id,
    metadata
) VALUES (
    'POSITION_LIQUIDATION',
    'CEO_DIRECTIVE_2025-12-21-B',
    'CASCADE_FAILURE_CLEANUP',
    'LINE',
    'EXECUTED',
    'All positions flattened per CEO directive. Zero margin, zero exposure.',
    'LINE',
    '{
        "mstr_qty": 1088,
        "mstr_fill_price": <actual>,
        "mstr_realized_pnl": <actual>,
        "nvda_qty": 86,
        "nvda_fill_price": <actual>,
        "nvda_realized_pnl": <actual>,
        "total_realized_pnl": <actual>,
        "execution_time": "<timestamp>",
        "post_cash": <actual>,
        "margin_cleared": true
    }'::jsonb
);
```

---

## 8. ESCALATION PROTOCOL

### If Orders Fail to Fill
1. Check for trading halts on MSTR/NVDA
2. If halted, wait for resumption
3. If persistent failure, use LIMIT orders at market bid
4. Escalate to CEO if unresolved by 10:00 AM ET

### If Partial Fill
1. Submit new order for remaining quantity
2. Do not leave partial positions overnight
3. Document all partial fills

### If Account Restricted
1. Contact Alpaca support immediately
2. Escalate to CEO
3. Document restriction reason

---

## 9. SUCCESS CRITERIA

| Criterion | Requirement |
|-----------|-------------|
| MSTR Position | 0 shares |
| NVDA Position | 0 shares |
| Open Positions | 0 |
| Cash Balance | Positive |
| Margin Used | No |
| Database Reconciled | Yes |
| Governance Logged | Yes |

---

## 10. AUTHORIZATION CHAIN

| Role | Agent | Status |
|------|-------|--------|
| Directive | CEO | ISSUED |
| Code Remediation | STIG | COMPLETE |
| Attestation | VEGA | ATTESTED |
| Liquidation Execution | LINE | PENDING (Monday) |
| Re-enablement Decision | CEO | PENDING (Post-reconciliation) |

---

**Document Prepared By:** STIG
**Date:** 2025-12-21
**Classification:** OPERATIONAL / CRITICAL

---

*This plan is subject to CEO Directive 2025-12-21-B. No deviation permitted without explicit CEO authorization.*
