"""STIG-011: Backfill target_exposure_daily"""
import psycopg2
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

conn = psycopg2.connect(host='127.0.0.1', port=54322, database='postgres', user='postgres', password='postgres')
cur = conn.cursor()

# Get model_id
cur.execute('SELECT model_id FROM fhq_research.regime_model_registry WHERE is_active = true LIMIT 1')
model_id = cur.fetchone()[0]

# Get missing dates
cur.execute("""
    SELECT DISTINCT r.timestamp
    FROM fhq_perception.regime_daily r
    WHERE r.timestamp > '2025-11-28'
    AND NOT EXISTS (
        SELECT 1 FROM fhq_positions.target_exposure_daily t
        WHERE t.timestamp = r.timestamp
    )
    ORDER BY r.timestamp
""")
missing_dates = [row[0] for row in cur.fetchall()]
print(f'Missing dates: {len(missing_dates)}')

for dt in missing_dates:
    # Get regime data for this date
    cur.execute("""
        SELECT asset_id, regime_classification, regime_confidence, lineage_hash, hash_self
        FROM fhq_perception.regime_daily
        WHERE timestamp = %s
        ORDER BY asset_id
    """, (dt,))
    regimes = cur.fetchall()

    n_assets = len(regimes)
    if n_assets == 0:
        continue

    # Per-asset exposure = 0.75 / n_assets for BULL
    per_asset_exp = Decimal('0.75') / n_assets

    running_total = Decimal('0')

    for asset_id, regime, conf, lineage, hash_s in regimes:
        if regime in ('BULL', 'STRONG_BULL'):
            exp = per_asset_exp
        else:
            exp = Decimal('0')

        running_total += exp
        cash_weight = Decimal('1.0') - running_total

        hash_self = hashlib.sha256((asset_id + str(dt) + regime).encode()).hexdigest()

        cur.execute("""
            INSERT INTO fhq_positions.target_exposure_daily
            (asset_id, timestamp, exposure_raw, exposure_constrained, cash_weight,
             model_id, regime_label, confidence, lineage_hash, hash_prev, hash_self,
             created_at, engine_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (asset_id, dt, float(exp), float(exp), float(cash_weight), model_id, regime, conf,
              lineage or hash_self, hash_s or 'genesis', hash_self,
              datetime.now(timezone.utc), 'IoS-004_v2026.PROD.1'))

    conn.commit()
    print(f'  {dt}: {n_assets} assets inserted')

print('Done')
cur.close()
conn.close()
