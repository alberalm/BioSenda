import os
from sqlalchemy import create_engine

def create_db_engine():
    url = os.environ["DATABASE_URL"]
    # Expects: mysql+pymysql://user:pass@host:port/dbname
    timeout = 10
    return create_engine(
        url,
        pool_recycle=300,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": timeout,
            "read_timeout": timeout,
            "write_timeout": timeout,
            "charset": "utf8mb4"
        }
    )
