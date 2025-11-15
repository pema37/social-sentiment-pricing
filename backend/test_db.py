from db import engine

with engine.connect() as conn:
    result = conn.exec_driver_sql("SELECT 1;")
    print("DB test result:", result.scalar())
    