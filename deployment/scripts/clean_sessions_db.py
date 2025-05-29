from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# --- Configuration ---
# Your original database name to be recreated
TARGET_DB_NAME = 'data-explorer-sessions'

# Your current connection details for the target database
TARGET_DB_USER = 'data-explorer-sql-user'
TARGET_DB_PASSWORD = 'password'
TARGET_DB_HOST = '127.0.0.1'
TARGET_DB_PORT = '5433'

# --- Administrative Connection URL ---
# You MUST connect to a *different* database (e.g., 'postgres' or 'template1')
# to drop and create your target database.
ADMIN_DATABASE_URL = f"postgresql+psycopg2://{TARGET_DB_USER}:{TARGET_DB_PASSWORD}@{TARGET_DB_HOST}:{TARGET_DB_PORT}/postgres"

admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")

try:
    with admin_engine.connect() as admin_conn:
        # Step 2: Terminate all active connections to the target database
        print(f"Terminating all active connections to '{TARGET_DB_NAME}'...")
        try:
            admin_conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{TARGET_DB_NAME}'
                  AND pid <> pg_backend_pid();
            """))
            print("Active connections terminated (if any).")
        except Exception as e:
            print(f"Warning: Could not terminate connections (may not have permissions or no active connections): {e}")


        # Step 3: Drop the database if it exists
        print(f"Dropping existing database '{TARGET_DB_NAME}'...")
        try:
            admin_conn.execute(text(f"DROP DATABASE IF EXISTS \"{TARGET_DB_NAME}\";"))
            print(f"Database '{TARGET_DB_NAME}' dropped successfully (if it existed).")
        except ProgrammingError as e:
            print(f"Error dropping database: {e}")
            print(f"Please ensure user '{TARGET_DB_USER}' has sufficient privileges to DROP DATABASE.")
            raise


        # Step 4: Create the new database
        print(f"Creating new database '{TARGET_DB_NAME}'...")
        try:
            admin_conn.execute(text(f"CREATE DATABASE \"{TARGET_DB_NAME}\";"))
            print(f"Database '{TARGET_DB_NAME}' created successfully.")
        except ProgrammingError as e:
            print(f"Error creating database: {e}")
            print(f"Please ensure user '{TARGET_DB_USER}' has sufficient privileges to CREATE DATABASE.")
            raise

except Exception as e:
    print(f"An error occurred during database recreation: {e}")
finally:
    if admin_engine:
        admin_engine.dispose()
