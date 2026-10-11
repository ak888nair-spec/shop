import os, sys
import mysql.connector
from werkzeug.security import generate_password_hash
from config import DB_CONFIG

BASE = os.path.dirname(os.path.abspath(__file__))

def run_file(cur, filename):
    with open(os.path.join(BASE, filename), encoding="utf-8") as f:
        for statement in f.read().split(";"):
            if statement.strip():
                cur.execute(statement)

if __name__ == "__main__":
    if "--reset" not in sys.argv:
        sys.exit("This DELETES all data. Run: python init_db.py --reset")
    cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    db = mysql.connector.connect(**cfg)
    cur = db.cursor()
    for name in ["schema.sql", "extras.sql", "seed.sql"]:
        run_file(cur, name)
        print("ran", name)
    for table, idcol, user, pw in [("Admin", "Admin_ID", "admin", "admin123"),
                                   ("Supplier", "Supplier_ID", "seller", "seller123"),
                                   ("Customer", "Customer_ID", "asha", "asha123")]:
        cur.execute(f"UPDATE {table} SET Username=%s, Password_Hash=%s WHERE {idcol}=1",
                    (user, generate_password_hash(pw)))
    db.commit()
    print("demo logins: admin/admin123, seller/seller123, asha/asha123")