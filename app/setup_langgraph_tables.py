import os
from psycopg import Connection
from langgraph.checkpoint.postgres import PostgresSaver

def setup_langgraph_tables():
    """Создание таблиц checkpoints и writes для LangGraph, а также таблицы conversations."""
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    print("🔧 Connecting to PostgreSQL...")
    
    with Connection.connect(db_url, autocommit=True) as conn:
        print("🔧 Setting up LangGraph internal tables...")
        from psycopg.rows import dict_row
        
        # 1. Standart LangGraph Tables (checkpoints, writes)
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        
        with conn.cursor() as cur:
            # 2. Custom conversations table
            print("🔧 Setting up 'conversations' table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    thread_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    history JSONB DEFAULT '[]'::jsonb,
                    context JSONB DEFAULT '{}'::jsonb,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    states JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 3. Migration: Ensure 'states' column exists (for existing DBs)
            cur.execute("""
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS states JSONB DEFAULT '[]'::jsonb;
            """)
            
        print("✅ All tables (checkpoints, writes, conversations) are ready!")

if __name__ == "__main__":
    setup_langgraph_tables()
