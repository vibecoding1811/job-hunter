import sqlite3, os
from datetime import datetime
DB_PATH = os.path.join(os.path.dirname(__file__), 'jobs.db')
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, group_name TEXT NOT NULL, careers_url TEXT, is_excluded INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, title TEXT NOT NULL, summary TEXT, salary_min REAL, salary_max REAL, salary_text TEXT, location TEXT, work_type TEXT DEFAULT "onsite", source TEXT DEFAULT "官网", url TEXT, is_active INTEGER DEFAULT 1, discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, keywords TEXT, FOREIGN KEY (company_id) REFERENCES companies (id))')
    c.execute('CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER UNIQUE, status TEXT DEFAULT "unread", applied_at TIMESTAMP, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (job_id) REFERENCES jobs (id))')
    conn.commit()
    conn.close()
def add_company(name, group_name, careers_url="", is_excluded=False):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO companies (name,group_name,careers_url,is_excluded) VALUES (?,?,?,?)", (name, group_name, careers_url, 1 if is_excluded else 0))
    conn.commit()
    conn.close()
def get_active_companies():
    conn = get_db()
    rows = conn.execute("SELECT * FROM companies WHERE is_excluded=0 ORDER BY group_name, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]
def add_job(company_id, title, summary="", salary_min=None, salary_max=None, salary_text="", location="", work_type="onsite", source="官网", url="", keywords=""):
    conn = get_db()
    cur = conn.execute("INSERT INTO jobs (company_id,title,summary,salary_min,salary_max,salary_text,location,work_type,source,url,keywords) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (company_id,title,summary,salary_min,salary_max,salary_text,location,work_type,source,url,keywords))
    job_id = cur.lastrowid
    conn.execute("INSERT OR IGNORE INTO applications (job_id,status) VALUES (?,'unread')", (job_id,))
    conn.commit()
    conn.close()
    return job_id
def get_all_jobs_with_status():
    conn = get_db()
    rows = conn.execute("SELECT j.*,c.name as company_name,c.group_name,a.status,a.applied_at,a.notes as app_notes FROM jobs j JOIN companies c ON j.company_id=c.id LEFT JOIN applications a ON j.id=a.job_id WHERE c.is_excluded=0 ORDER BY j.discovered_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_jobs_by_status(status):
    conn = get_db()
    rows = conn.execute("SELECT j.*,c.name as company_name,c.group_name,a.status,a.applied_at,a.notes as app_notes FROM jobs j JOIN companies c ON j.company_id=c.id JOIN applications a ON j.id=a.job_id WHERE a.status=? AND c.is_excluded=0 ORDER BY j.discovered_at DESC", (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def update_job_status(job_id, status, notes=""):
    conn = get_db()
    if status == 'applied':
        conn.execute("UPDATE applications SET status=?,applied_at=?,notes=? WHERE job_id=?", (status, datetime.now().isoformat(), notes, job_id))
    else:
        conn.execute("UPDATE applications SET status=?,notes=? WHERE job_id=?", (status, notes, job_id))
    conn.commit()
    conn.close()
def delete_job(job_id):
    conn = get_db()
    conn.execute("DELETE FROM applications WHERE job_id=?", (job_id,))
    conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
def search_jobs(keyword="", location="", salary_min=None, salary_max=None):
    conn = get_db()
    query = "SELECT j.*,c.name as company_name,c.group_name,a.status,a.applied_at,a.notes as app_notes FROM jobs j JOIN companies c ON j.company_id=c.id LEFT JOIN applications a ON j.id=a.job_id WHERE c.is_excluded=0"
    params = []
    if keyword:
        query += " AND (j.title LIKE ? OR j.summary LIKE ? OR j.keywords LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
    if location:
        query += " AND j.location LIKE ?"
        params.append(f"%{location}%")
    if salary_min is not None:
        query += " AND (j.salary_max>=? OR j.salary_max IS NULL)"
        params.append(salary_min)
    if salary_max is not None:
        query += " AND (j.salary_min<=? OR j.salary_min IS NULL)"
        params.append(salary_max)
    query += " ORDER BY j.discovered_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM jobs j JOIN companies c ON j.company_id=c.id WHERE c.is_excluded=0").fetchone()[0]
    unread = conn.execute("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id JOIN companies c ON j.company_id=c.id WHERE a.status='unread' AND c.is_excluded=0").fetchone()[0]
    applied = conn.execute("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id JOIN companies c ON j.company_id=c.id WHERE a.status='applied' AND c.is_excluded=0").fetchone()[0]
    skipped = conn.execute("SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id JOIN companies c ON j.company_id=c.id WHERE a.status='skipped' AND c.is_excluded=0").fetchone()[0]
    conn.close()
    return {'total':total,'unread':unread,'applied':applied,'skipped':skipped}
