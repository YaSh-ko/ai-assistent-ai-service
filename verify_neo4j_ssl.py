import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load variables from .env
load_dotenv(".env")

uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

print(f"Connecting to: {uri} as user {user}")

try:
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        print("✅ Connection verified successfully via bolt+s://!")
        
        # Test query
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j is alive via SSL' AS message")
            msg = result.single()["message"]
            print(f"Server response: {msg}")

except Exception as e:
    print(f"❌ Connection failed: {e}")
