/**
 * Check PostgreSQL Timezone Configuration
 */

const { Pool } = require('pg')

const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
  database: process.env.PGDATABASE || 'postgres',
})

async function checkTimezone() {
  console.log('⏰ TIMEZONE VERIFICATION\n')

  try {
    const client = await pool.connect()

    // Check database timezone
    const tzResult = await client.query(`SHOW timezone`)
    console.log('PostgreSQL Timezone:', tzResult.rows[0].TimeZone)

    // Check current timestamp
    const nowResult = await client.query(`SELECT NOW() as db_now, CURRENT_TIMESTAMP as current_ts`)
    console.log('Database NOW():', nowResult.rows[0].db_now)
    console.log('Database CURRENT_TIMESTAMP:', nowResult.rows[0].current_ts)

    // Check UTC timestamp
    const utcResult = await client.query(`SELECT NOW() AT TIME ZONE 'UTC' as utc_now`)
    console.log('Database UTC NOW:', utcResult.rows[0].utc_now)

    // System time
    console.log('\nSystem Time (Node.js):', new Date().toISOString())
    console.log('System Local:', new Date().toString())

    client.release()
  } catch (error) {
    console.error('Error:', error.message)
  } finally {
    await pool.end()
  }
}

checkTimezone()
