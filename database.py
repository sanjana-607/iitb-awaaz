import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "grievances.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grievances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            author_name TEXT,
            is_anonymous BOOLEAN DEFAULT 0,
            student_hostel TEXT,
            student_department TEXT,
            student_batch TEXT,
            raw_transcript TEXT,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            scope TEXT NOT NULL,
            scope_name TEXT,
            category TEXT NOT NULL,
            department TEXT NOT NULL,
            location TEXT,
            urgency TEXT NOT NULL,
            sensitive BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'Open',
            detected_language TEXT,
            keywords TEXT,
            upvotes INTEGER DEFAULT 1,
            affected_count INTEGER DEFAULT 1,
            audio_confirmation_path TEXT,
            merged_into_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def find_potential_duplicate(scope: str, scope_name: Optional[str], category: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
    """Finds if a similar open/in-progress complaint already exists to support duplicate merging."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT * FROM grievances 
        WHERE sensitive = 0 
          AND status IN ('Open', 'Seen', 'In Progress')
          AND scope = ?
          AND category = ?
    """
    params = [scope, category]
    if scope_name:
        query += " AND LOWER(scope_name) = LOWER(?)"
        params.append(scope_name)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    # Check keyword overlap
    current_kw_set = {k.lower() for k in keywords}
    for row in rows:
        row_dict = dict(row)
        try:
            row_kws = json.loads(row_dict.get("keywords") or "[]")
            row_kw_set = {k.lower() for k in row_kws}
            if len(current_kw_set.intersection(row_kw_set)) >= 2:
                return row_dict
        except Exception:
            continue
    return None

def create_grievance(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO grievances (
            author_name, is_anonymous, student_hostel, student_department, student_batch,
            raw_transcript, title, summary, scope, scope_name, category, department,
            location, urgency, sensitive, status, detected_language, keywords,
            upvotes, affected_count, audio_confirmation_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "Anonymous" if data.get("is_anonymous") else data.get("author_name", "Student"),
        1 if data.get("is_anonymous") else 0,
        data.get("student_hostel"),
        data.get("student_department"),
        data.get("student_batch"),
        data.get("raw_transcript"),
        data.get("title"),
        data.get("summary"),
        data.get("scope"),
        data.get("scope_name"),
        data.get("category"),
        data.get("department"),
        data.get("location"),
        data.get("urgency", "medium"),
        1 if data.get("sensitive") else 0,
        data.get("status", "Open"),
        data.get("detected_language"),
        json.dumps(data.get("keywords") or []),
        data.get("upvotes", 1),
        data.get("affected_count", 1),
        data.get("audio_confirmation_path"),
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def merge_with_existing(existing_id: int) -> int:
    """Increments affected_count and upvotes when a duplicate complaint is submitted."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE grievances 
        SET affected_count = affected_count + 1, upvotes = upvotes + 1 
        WHERE id = ?
    """, (existing_id,))
    cursor.execute("SELECT affected_count FROM grievances WHERE id = ?", (existing_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row["affected_count"] if row else 1

def upvote_grievance(grievance_id: int) -> int:
    """Me-too / upvote action by another student."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE grievances 
        SET upvotes = upvotes + 1, affected_count = affected_count + 1 
        WHERE id = ?
    """, (grievance_id,))
    cursor.execute("SELECT upvotes FROM grievances WHERE id = ?", (grievance_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    return row["upvotes"] if row else 0

def update_status(grievance_id: int, new_status: str) -> bool:
    valid_statuses = ["Open", "Seen", "In Progress", "Resolved", "Rejected"]
    if new_status not in valid_statuses:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE grievances SET status = ? WHERE id = ?", (new_status, grievance_id))
    conn.commit()
    conn.close()
    return True

def get_feed_posts(
    tab: str = "institute",
    student_profile: Optional[Dict[str, str]] = None,
    category_filter: Optional[str] = None,
    urgency_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: str = "upvotes"
) -> List[Dict[str, Any]]:
    """Retrieves public grievance posts according to feed tab and filters."""
    conn = get_connection()
    cursor = conn.cursor()

    # Rule: Sensitive complaints NEVER appear on the public feed
    query = "SELECT * FROM grievances WHERE sensitive = 0"
    params = []

    # Tab matching
    if tab == "my_hostel" and student_profile and student_profile.get("hostel"):
        query += " AND scope = 'hostel' AND (LOWER(scope_name) = LOWER(?) OR LOWER(student_hostel) = LOWER(?))"
        params.extend([student_profile["hostel"], student_profile["hostel"]])
    elif tab == "my_department" and student_profile and student_profile.get("department"):
        query += " AND scope = 'academic_department' AND (LOWER(scope_name) = LOWER(?) OR LOWER(student_department) = LOWER(?))"
        params.extend([student_profile["department"], student_profile["department"]])
    elif tab == "my_batch" and student_profile and student_profile.get("batch"):
        query += " AND scope = 'batch' AND (LOWER(scope_name) = LOWER(?) OR LOWER(student_batch) = LOWER(?))"
        params.extend([student_profile["batch"], student_profile["batch"]])
    elif tab == "clubs_events":
        query += " AND (scope = 'club_or_committee' OR category = 'Clubs/Events')"
    elif tab == "institute_wide":
        query += " AND scope = 'institute'"

    # Additional filters
    if category_filter and category_filter != "all":
        query += " AND category = ?"
        params.append(category_filter)
    if urgency_filter and urgency_filter != "all":
        query += " AND urgency = ?"
        params.append(urgency_filter)
    if status_filter and status_filter != "all":
        query += " AND status = ?"
        params.append(status_filter)

    # Sorting
    if sort_by == "upvotes":
        query += " ORDER BY upvotes DESC, created_at DESC"
    else:
        query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    for r in rows:
        try:
            r["keywords_list"] = json.loads(r.get("keywords") or "[]")
        except Exception:
            r["keywords_list"] = []
    return rows

def get_role_scoped_posts(role: str, role_target: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Role filtering:
    - Warden sees only their hostel
    - Dept Head sees only their department
    - Admin sees all (including sensitive queue)
    """
    conn = get_connection()
    cursor = conn.cursor()

    if role == "Warden":
        cursor.execute("""
            SELECT * FROM grievances 
            WHERE sensitive = 0 AND scope = 'hostel' AND (LOWER(scope_name) = LOWER(?) OR LOWER(student_hostel) = LOWER(?))
            ORDER BY created_at DESC
        """, (role_target, role_target))
    elif role == "Dept Head":
        cursor.execute("""
            SELECT * FROM grievances 
            WHERE sensitive = 0 AND scope = 'academic_department' AND (LOWER(scope_name) = LOWER(?) OR LOWER(student_department) = LOWER(?))
            ORDER BY created_at DESC
        """, (role_target, role_target))
    elif role == "Admin":
        cursor.execute("SELECT * FROM grievances ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT * FROM grievances WHERE sensitive = 0 ORDER BY created_at DESC")

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["keywords_list"] = json.loads(r.get("keywords") or "[]")
        except Exception:
            r["keywords_list"] = []
    return rows

def get_sensitive_queue() -> List[Dict[str, Any]]:
    """Private queue for Admin view only (harassment, ragging, mental health, safety)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM grievances WHERE sensitive = 1 ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    for r in rows:
        try:
            r["keywords_list"] = json.loads(r.get("keywords") or "[]")
        except Exception:
            r["keywords_list"] = []
    return rows

def get_admin_metrics() -> Dict[str, Any]:
    """Generates counts by scope, category, and status for the admin dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM grievances")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total_sensitive FROM grievances WHERE sensitive = 1")
    sensitive_count = cursor.fetchone()["total_sensitive"]

    cursor.execute("SELECT scope, COUNT(*) as count FROM grievances GROUP BY scope")
    scope_counts = {r["scope"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("SELECT category, COUNT(*) as count FROM grievances GROUP BY category")
    category_counts = {r["category"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("SELECT status, COUNT(*) as count FROM grievances GROUP BY status")
    status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    conn.close()
    return {
        "total": total,
        "sensitive": sensitive_count,
        "by_scope": scope_counts,
        "by_category": category_counts,
        "by_status": status_counts,
    }

def seed_sample_data():
    """Seeds the initial sample complaints if table is empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM grievances")
    count = cursor.fetchone()["count"]
    if count == 0:
        samples = [
            {
                "author_name": "Anonymous",
                "is_anonymous": True,
                "student_hostel": "Hostel B",
                "student_department": "Mechanical Engineering",
                "student_batch": "UG 2023",
                "raw_transcript": "Hostel B ka geyser teen din se kharab hai, bahut thanda paani aata hai",
                "title": "Non-functional Geyser in Hostel B",
                "summary": "The geyser in Hostel B has been out of order for three days. Residents are receiving cold water due to the malfunction.",
                "scope": "hostel",
                "scope_name": "Hostel B",
                "category": "Infrastructure/Maintenance",
                "department": "Hostel Warden Office",
                "location": "Hostel B Washrooms",
                "urgency": "medium",
                "sensitive": False,
                "status": "In Progress",
                "detected_language": "Hinglish",
                "keywords": ["geyser", "cold water", "Hostel B", "maintenance"],
                "upvotes": 14,
                "affected_count": 14,
            },
            {
                "author_name": "Student",
                "is_anonymous": False,
                "student_hostel": "Hostel 5",
                "student_department": "Computer Science and Engineering",
                "student_batch": "UG 2024",
                "raw_transcript": "CS department ki lab mein computers kaam nahi kar rahe, practical nahi ho pa raha",
                "title": "CS Lab Computers Malfunctioning",
                "summary": "Computers in the Computer Science department lab are not functioning, which prevents conduct of practical sessions.",
                "scope": "academic_department",
                "scope_name": "Computer Science",
                "category": "Infrastructure/Maintenance",
                "department": "Head of Department",
                "location": "Software Lab 2",
                "urgency": "medium",
                "sensitive": False,
                "status": "Open",
                "detected_language": "Hinglish",
                "keywords": ["lab", "computers", "practical", "CS department"],
                "upvotes": 9,
                "affected_count": 9,
            },
            {
                "author_name": "Student",
                "is_anonymous": False,
                "student_hostel": "Hostel 12",
                "student_department": "Electrical Engineering",
                "student_batch": "UG 2022",
                "raw_transcript": "Campus mein wifi bahut slow hai, library mein bhi kaam nahi kar raha",
                "title": "Slow Campus WiFi in Library",
                "summary": "Campus wifi is experiencing slow speeds and connectivity failures, especially in the library study area.",
                "scope": "institute",
                "scope_name": None,
                "category": "Wifi/IT",
                "department": "IT/Network Cell",
                "location": "Central Library",
                "urgency": "medium",
                "sensitive": False,
                "status": "Seen",
                "detected_language": "Hinglish",
                "keywords": ["wifi", "slow", "library", "internet", "connectivity"],
                "upvotes": 28,
                "affected_count": 28,
            },
            {
                "author_name": "Student",
                "is_anonymous": False,
                "student_hostel": "Hostel 3",
                "student_department": "Civil Engineering",
                "student_batch": "UG 2024",
                "raw_transcript": "WnCC ka meeting room book nahi ho raha, koi reply nahi de raha",
                "title": "WnCC Meeting Room Booking Unresponsive",
                "summary": "The WnCC meeting room cannot be booked and there is no response from the concerned club coordinators.",
                "scope": "club_or_committee",
                "scope_name": "WnCC",
                "category": "Clubs/Events",
                "department": "Institute Technical Council",
                "location": "SAC Room 102",
                "urgency": "low",
                "sensitive": False,
                "status": "Open",
                "detected_language": "Hinglish",
                "keywords": ["WnCC", "meeting room", "booking", "club"],
                "upvotes": 5,
                "affected_count": 5,
            },
            {
                "author_name": "Anonymous",
                "is_anonymous": True,
                "student_hostel": "Hostel 16",
                "student_department": "Chemistry",
                "student_batch": "UG 2025",
                "raw_transcript": "[Confidential - Harassment report in wing common room late night]",
                "title": "Harassment Incident in Hostel Wing",
                "summary": "Urgent safety complaint regarding harassment in hostel common room.",
                "scope": "hostel",
                "scope_name": "Hostel 16",
                "category": "Safety/Security",
                "department": "Internal Complaints Committee",
                "location": "Wing B Common Area",
                "urgency": "critical",
                "sensitive": True,
                "status": "Seen",
                "detected_language": "English",
                "keywords": ["harassment", "safety", "confidential"],
                "upvotes": 1,
                "affected_count": 1,
            }
        ]
        for s in samples:
            create_grievance(s)
    conn.close()
