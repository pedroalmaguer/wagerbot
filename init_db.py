import os
import aiosqlite
import asyncio
from datetime import datetime

DB_FILE = "wagerbot.db"

async def init_database():
    """Initialize the SQLite database with necessary tables if the file doesn't exist."""
    
    # Check if database file already exists
    if os.path.exists(DB_FILE):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [💾] Database file already exists, skipping initialization.")
        
        # If database exists, check if we need to add the american_odds column
        async with aiosqlite.connect(DB_FILE) as db:
            # Check if american_odds column exists
            cursor = await db.execute("PRAGMA table_info(bet_options)")
            columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'american_odds' not in column_names:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [🔄] Adding american_odds column to bet_options table...")
                await db.execute("ALTER TABLE bet_options ADD COLUMN american_odds TEXT")
                await db.commit()
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [✅] american_odds column added successfully!")
        
        return False
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [💾] Initializing new database...")
    
    # Create new database with all required tables
    async with aiosqlite.connect(DB_FILE) as db:
        # Users table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT,
            username TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Sessions table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            created_at DATETIME,
            is_active INTEGER DEFAULT 0
        )
        ''')

        # Bankroll table - adding from_wallet column
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bankroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id INTEGER,
            balance INTEGER DEFAULT 1000,
            from_wallet INTEGER DEFAULT 0,
            UNIQUE(user_id, session_id)
        )
        ''')

        # Wallet table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS wallet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            balance INTEGER DEFAULT 1000
        )
        ''')

        # Bet table - ensure bet_type support for fun bets
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NULL,    -- NULL allowed for fun bets
            name TEXT,
            description TEXT,
            bet_type TEXT DEFAULT 'moneyline',  -- 'moneyline', 'funbet', etc.
            is_resolved INTEGER DEFAULT 0
        )
        ''')

        # Bet options table - now includes american_odds column
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bet_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prop_id INTEGER,
            label TEXT,
            odds INTEGER DEFAULT 100,
            is_winner INTEGER DEFAULT 0,
            american_odds TEXT         -- New column for storing American-style odds format (+150, -120, etc.)
        )
        ''')

        # Wagers table - session_id can be NULL for fun bets
        await db.execute('''
        CREATE TABLE IF NOT EXISTS wagers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id INTEGER NULL,    -- NULL allowed for fun bets
            prop_id INTEGER,
            prop_option_id INTEGER,
            amount INTEGER,
            odds INTEGER,
            result TEXT,
            payout INTEGER,
            from_wallet INTEGER DEFAULT 0
        )
        ''')

        await db.commit()
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [💾] Database initialization complete!")
    return True

# This allows the file to be run directly if needed
if __name__ == "__main__":
    print("Running database initialization directly...")
    asyncio.run(init_database())
    print("Done!")