/**
 * Database Verification Script
 * Checks if all required tables and views exist
 */

const { Pool } = require('pg')

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
  database: process.env.PGDATABASE || 'postgres',
})

async function verifyDatabase() {
  console.log('🔍 Verifying PostgreSQL Database Connection...\n')

  try {
    // Test connection
    const client = await pool.connect()
    console.log('✅ Database connection successful\n')

    // Check required tables
    const requiredTables = [
      'fhq_data.price_series',
      'fhq_finn.serper_events',
      'fhq_validation.v_gate_a_summary',
      'fhq_meta.adr_registry',
    ]

    console.log('📊 Checking required tables/views:\n')

    for (const table of requiredTables) {
      const [schema, name] = table.split('.')
      const result = await client.query(`
        SELECT EXISTS (
          SELECT FROM information_schema.tables
          WHERE table_schema = $1 AND table_name = $2
        ) as exists
      `, [schema, name])

      const exists = result.rows[0]?.exists
      console.log(`${exists ? '✅' : '❌'} ${table}`)

      if (exists) {
        // Count rows
        try {
          const countResult = await client.query(`SELECT COUNT(*) as count FROM ${table}`)
          console.log(`   → ${countResult.rows[0].count} rows\n`)
        } catch (err) {
          console.log(`   → Error counting: ${err.message}\n`)
        }
      } else {
        console.log('   → MISSING!\n')
      }
    }

    // Test specific queries
    console.log('🧪 Testing dashboard queries:\n')

    // Test 1: BTC price
    try {
      const btcResult = await client.query(`
        SELECT date, close
        FROM fhq_data.price_series
        WHERE listing_id = 'LST_BTC_XCRYPTO'
          AND resolution = '1d'
        ORDER BY date DESC
        LIMIT 1
      `)
      console.log('✅ BTC price query:', btcResult.rows[0])
    } catch (err) {
      console.log('❌ BTC price query failed:', err.message)
    }

    // Test 2: Serper events
    try {
      const eventsResult = await client.query(`
        SELECT COUNT(*) as count
        FROM fhq_finn.serper_events
        WHERE detected_at_utc >= NOW() - INTERVAL '24 hours'
      `)
      console.log('✅ Serper events (24h):', eventsResult.rows[0])
    } catch (err) {
      console.log('❌ Serper events query failed:', err.message)
    }

    // Test 3: Gates
    try {
      const gatesResult = await client.query(`
        SELECT * FROM fhq_validation.v_gate_a_summary
        LIMIT 1
      `)
      console.log('✅ Gates query:', gatesResult.rows.length, 'gates found')
    } catch (err) {
      console.log('❌ Gates query failed:', err.message)
    }

    client.release()
    console.log('\n✅ Verification complete')
  } catch (error) {
    console.error('❌ Database verification failed:', error.message)
    process.exit(1)
  } finally {
    await pool.end()
  }
}

verifyDatabase()
