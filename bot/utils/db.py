import sqlite3

def init_db(DB_FILE: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS main_domains (
                        domain TEXT PRIMARY KEY, 
                        channel_id INTEGER, 
                        webhook_url TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS subdomains (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subdomain TEXT, 
                        domain TEXT, 
                        is_alive INTEGER, 
                        timestamp TEXT,
                        UNIQUE(subdomain, domain),
                        FOREIGN KEY(domain) REFERENCES main_domains(domain))''')
    conn.commit()
    return conn