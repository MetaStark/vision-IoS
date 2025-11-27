/**
 * Database connection module for Vision-IoS Dashboard
 * Uses SQLite via better-sqlite3 and Drizzle ORM
 */

import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import * as schema from './schema';
import path from 'path';

// Database file path - relative to project root
const dbPath = path.join(process.cwd(), 'db', 'vision-ios.db');

// Create SQLite connection
const sqlite = new Database(dbPath);

// Enable WAL mode for better concurrent access
sqlite.pragma('journal_mode = WAL');

// Create Drizzle instance with schema
export const db = drizzle(sqlite, { schema });

// Export schema for use in queries
export * from './schema';

// Helper to close database connection
export const closeDb = () => {
  sqlite.close();
};

// Get database instance for direct queries if needed
export const getSqlite = () => sqlite;
