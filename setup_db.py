"""Creates nesarar_auth and nesarar_api_logs by running setup_tables.sql.
Run from the project folder:   python setup_db.py"""
import pymysql, yaml

with open("config.yml") as f:
    db_config = yaml.safe_load(f)['mysql']

conn = pymysql.connect(**db_config)
cur = conn.cursor()

sql_text = open("setup_tables.sql").read()
for statement in sql_text.split(";"):
    lines = [l for l in statement.splitlines() if not l.strip().startswith("--")]
    statement = "\n".join(lines).strip()
    if statement:
        cur.execute(statement)
conn.commit()

cur.execute("SELECT * FROM nesarar_auth")
print(cur.fetchall())
