"""
FjordHQ Vision-IoS Database Configuration
==========================================

Central database configuration for all Vision-IoS components.

CANONICAL DATABASE:
- Host: 127.0.0.1
- Port: 54322
- Type: Local Supabase PostgreSQL instance
- Database: postgres

Authority: ADR-006_2026_PRODUCTION
Reference: VEGA Database Integration

Usage:
    from db_config import get_connection_string, DatabaseConfig

    # Get connection string
    conn_str = get_connection_string()

    # Get config object
    config = DatabaseConfig()
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """
    Canonical database configuration for Vision-IoS.

    IMPORTANT: Default values point to local Supabase instance.
    Override via environment variables for production.
    """
    host: str = "127.0.0.1"
    port: int = 54322
    database: str = "postgres"
    user: str = "postgres"
    password: str = "postgres"

    # Schema defaults
    meta_schema: str = "fhq_meta"
    governance_schema: str = "fhq_governance"
    phase3_schema: str = "fhq_phase3"
    monitoring_schema: str = "fhq_monitoring"
    data_schema: str = "fhq_data"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("PGHOST", "127.0.0.1"),
            port=int(os.getenv("PGPORT", "54322")),
            database=os.getenv("PGDATABASE", "postgres"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "postgres"),
        )

    def get_connection_string(self, schema: Optional[str] = None) -> str:
        """
        Get PostgreSQL connection string.

        Args:
            schema: Optional schema to set in search_path

        Returns:
            PostgreSQL connection string
        """
        base = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        if schema:
            return f"{base}?options=-csearch_path%3D{schema}"
        return base

    def get_dsn(self) -> dict:
        """Get DSN dictionary for psycopg2.connect()."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


# Singleton instance
_config: Optional[DatabaseConfig] = None


def get_config() -> DatabaseConfig:
    """Get singleton database config instance."""
    global _config
    if _config is None:
        _config = DatabaseConfig.from_env()
    return _config


def get_connection_string(schema: Optional[str] = None) -> str:
    """
    Get PostgreSQL connection string.

    Args:
        schema: Optional schema name

    Returns:
        Connection string for 127.0.0.1:54322
    """
    return get_config().get_connection_string(schema)


def get_dsn() -> dict:
    """Get DSN dictionary for psycopg2."""
    return get_config().get_dsn()


# Export canonical values
CANONICAL_HOST = "127.0.0.1"
CANONICAL_PORT = 54322
CANONICAL_DATABASE = "postgres"
CANONICAL_USER = "postgres"

# Connection string templates
CONN_STRING_TEMPLATE = f"postgresql://{CANONICAL_USER}:{{password}}@{CANONICAL_HOST}:{CANONICAL_PORT}/{CANONICAL_DATABASE}"
DEFAULT_CONN_STRING = f"postgresql://{CANONICAL_USER}:postgres@{CANONICAL_HOST}:{CANONICAL_PORT}/{CANONICAL_DATABASE}"


if __name__ == "__main__":
    # Verification
    config = get_config()
    print("=" * 60)
    print("VISION-IOS DATABASE CONFIGURATION")
    print("=" * 60)
    print(f"Host:     {config.host}")
    print(f"Port:     {config.port}")
    print(f"Database: {config.database}")
    print(f"User:     {config.user}")
    print(f"Schemas:  {config.meta_schema}, {config.governance_schema}, {config.phase3_schema}")
    print("=" * 60)
    print(f"Connection String: {get_connection_string()}")
    print("=" * 60)
