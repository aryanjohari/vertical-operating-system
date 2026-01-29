# backend/core/db.py
"""
Database Connection Factory for PostgreSQL and SQLite support.

Automatically detects database type from DATABASE_URL environment variable.
If DATABASE_URL is set and starts with postgres:// or postgresql://, uses PostgreSQL.
Otherwise, falls back to SQLite for local development.
"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Any, Dict

logger = logging.getLogger("ApexDB")

class DatabaseError(Exception):
    """Common exception for database errors."""
    pass

class DatabaseFactory:
    """
    Factory for creating database connections with unified interface.
    Supports both PostgreSQL (via psycopg2) and SQLite.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database factory.
        
        Args:
            db_path: Path to SQLite database file (only used if DATABASE_URL not set)
        """
        self.db_path = db_path
        self.db_type = self._detect_db_type()
        self.logger = logging.getLogger("ApexDB")
        
        self.pool = None  # PostgreSQL connection pool; None for SQLite or fallback
        if self.db_type == "postgresql":
            try:
                import psycopg2
                import psycopg2.extras
                self.psycopg2 = psycopg2
                self.psycopg2_extras = psycopg2.extras
                database_url = os.getenv("DATABASE_URL")
                if database_url:
                    try:
                        self.pool = psycopg2.pool.SimpleConnectionPool(
                            minconn=1, maxconn=10, dsn=database_url
                        )
                        self.logger.info("✅ Database: PostgreSQL (via psycopg2, connection pool)")
                    except Exception as e:
                        self.logger.warning(f"Pool creation failed, using non-pooled: {e}")
                        self.pool = None
                else:
                    self.logger.info("✅ Database: PostgreSQL (via psycopg2, no pool: DATABASE_URL not set)")
                if not self.pool and database_url:
                    self.logger.info("✅ Database: PostgreSQL (via psycopg2, non-pooled fallback)")
            except ImportError:
                self.logger.error("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
                raise ImportError("psycopg2 is required for PostgreSQL support")
        else:
            import sqlite3
            self.sqlite3 = sqlite3
            self.logger.info("✅ Database: SQLite")
    
    def _detect_db_type(self) -> str:
        """Detect database type from DATABASE_URL environment variable."""
        database_url = os.getenv("DATABASE_URL", "").strip()
        
        if database_url and (database_url.startswith("postgres://") or 
                           database_url.startswith("postgresql://")):
            return "postgresql"
        return "sqlite"
    
    def get_connection(self):
        """
        Get a database connection (from pool for PostgreSQL when pool is used).
        
        Returns:
            Connection object (sqlite3.Connection or psycopg2.connection)
        """
        if self.db_type == "postgresql":
            if self.pool:
                conn = self.pool.getconn()
            else:
                database_url = os.getenv("DATABASE_URL")
                conn = self.psycopg2.connect(database_url)
            conn.autocommit = False
            return conn
        else:
            if not self.db_path:
                raise ValueError("db_path must be provided for SQLite")
            return self.sqlite3.connect(self.db_path)
    
    @contextmanager
    def get_cursor(self, commit: bool = True):
        """
        Context manager for database cursor with automatic cleanup.
        
        Args:
            commit: Whether to commit transaction on success (default: True)
            
        Yields:
            Cursor object
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            # Convert database-specific exceptions to common exception
            if self.db_type == "postgresql":
                import psycopg2
                if isinstance(e, (psycopg2.Error, psycopg2.IntegrityError)):
                    raise DatabaseError(f"Database error: {e}") from e
            else:
                import sqlite3
                if isinstance(e, (sqlite3.Error, sqlite3.IntegrityError)):
                    raise DatabaseError(f"Database error: {e}") from e
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                if self.db_type == "postgresql" and self.pool:
                    self.pool.putconn(conn)
                else:
                    conn.close()

    def close_pool(self):
        """Close the connection pool (PostgreSQL only). No-op for SQLite."""
        if getattr(self, "pool", None):
            try:
                self.pool.closeall()
                self.logger.debug("Connection pool closed")
            except Exception as e:
                self.logger.warning(f"Error closing pool: {e}")
            self.pool = None

    def return_connection(self, conn):
        """Return a connection to the pool (PostgreSQL with pool) or close it (SQLite / non-pooled)."""
        if conn is None:
            return
        if self.db_type == "postgresql" and self.pool:
            self.pool.putconn(conn)
        else:
            conn.close()

    @asynccontextmanager
    async def get_session(self, commit: bool = True):
        """
        Async context manager for a DB cursor. Runs sync get_cursor in a thread pool
        so that on exit (including async cancellation) the connection is always
        returned to the pool. Use when you need cancellation-safe session handling.
        """
        ctx = self.get_cursor(commit=commit)
        cursor = None
        try:
            cursor = await asyncio.to_thread(ctx.__enter__)
        except Exception:
            try:
                ctx.__exit__(*sys.exc_info())
            except Exception:
                pass
            raise
        try:
            yield cursor
        finally:
            exc_type, exc_val, exc_tb = sys.exc_info()
            await asyncio.to_thread(ctx.__exit__, exc_type, exc_val, exc_tb)

    def get_placeholder(self) -> str:
        """Get SQL placeholder for parameterized queries."""
        return "%s" if self.db_type == "postgresql" else "?"
    
    def get_row_factory(self):
        """
        Get appropriate row factory for the database type.
        
        Returns:
            Row factory class or None
        """
        if self.db_type == "postgresql":
            return self.psycopg2_extras.RealDictRow
        else:
            return self.sqlite3.Row
    
    def set_row_factory(self, conn):
        """
        Set row factory on connection.
        
        Args:
            conn: Database connection object
        """
        if self.db_type == "postgresql":
            # PostgreSQL: RealDictRow is set per cursor, not connection
            # We'll handle this when creating cursors
            pass
        else:
            # SQLite: set row_factory on connection
            conn.row_factory = self.sqlite3.Row
    
    def get_cursor_with_row_factory(self, conn):
        """
        Get a cursor with appropriate row factory.
        
        Args:
            conn: Database connection object
            
        Returns:
            Cursor object with row factory set
        """
        if self.db_type == "postgresql":
            # PostgreSQL: use RealDictRow cursor factory
            return conn.cursor(cursor_factory=self.psycopg2_extras.RealDictRow)
        else:
            # SQLite: row factory is set on connection, just get cursor
            return conn.cursor()
    
    def get_insert_or_replace_sql(self, table: str, columns: list, primary_key: str) -> str:
        """
        Generate INSERT OR REPLACE SQL that works for both databases.
        
        Args:
            table: Table name
            columns: List of column names
            primary_key: Primary key column name for ON CONFLICT clause
            
        Returns:
            SQL statement string
        """
        placeholders = [self.get_placeholder()] * len(columns)
        cols_str = ", ".join(columns)
        vals_str = ", ".join(placeholders)
        
        if self.db_type == "postgresql":
            # PostgreSQL: INSERT ... ON CONFLICT ... DO UPDATE
            update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])
            return f"""
                INSERT INTO {table} ({cols_str})
                VALUES ({vals_str})
                ON CONFLICT ({primary_key}) DO UPDATE SET {update_clause}
            """
        else:
            # SQLite: INSERT OR REPLACE
            return f"INSERT OR REPLACE INTO {table} ({cols_str}) VALUES ({vals_str})"
    
    def get_date_start_of_month(self) -> str:
        """
        Get SQL expression for start of current month.
        
        Returns:
            SQL expression string
        """
        if self.db_type == "postgresql":
            return "date_trunc('month', CURRENT_DATE)"
        else:
            return "date('now', 'start of month')"
    
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL."""
        return self.db_type == "postgresql"
    
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self.db_type == "sqlite"
    
    def get_json_type(self) -> str:
        """
        Get appropriate JSON column type for the database.
        
        Returns:
            Type string (JSONB for PostgreSQL, TEXT for SQLite)
        """
        if self.db_type == "postgresql":
            return "JSONB"  # PostgreSQL: JSONB is more efficient than JSON
        else:
            return "TEXT"  # SQLite: JSON stored as TEXT

# Global factory instance (will be initialized by MemoryManager)
_db_factory: Optional[DatabaseFactory] = None

def get_db_factory(db_path: Optional[str] = None) -> DatabaseFactory:
    """
    Get or create the global database factory instance.
    
    Args:
        db_path: Path to SQLite database (only used for SQLite)
        
    Returns:
        DatabaseFactory instance
    """
    global _db_factory
    if _db_factory is None:
        _db_factory = DatabaseFactory(db_path=db_path)
    return _db_factory

def set_db_factory(factory: DatabaseFactory):
    """Set the global database factory instance (for testing)."""
    global _db_factory
    _db_factory = factory
