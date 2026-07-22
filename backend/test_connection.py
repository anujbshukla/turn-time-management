from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT current_database(), current_user"))
    for row in result:
        print(f"Database: {row[0]}")
        print(f"User: {row[1]}")

print("Connection successful!")