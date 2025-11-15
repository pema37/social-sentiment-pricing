from db import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized (tables created if they didn't exist).")


