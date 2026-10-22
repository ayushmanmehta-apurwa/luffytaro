"""Create the database tables. The API also does this automatically at start-up; this script is for people who want to do it by hand."""
from app import config
from app.db import init_db

init_db()
print('Database ready:', config.DATABASE_URL.split('@')[-1])
