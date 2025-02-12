from dotenv import load_dotenv
import os

load_dotenv()

# databases
POSTGRES_URL = os.getenv("POSTGRES_URL")
REDIS_URL = os.getenv("REDIS_URL")