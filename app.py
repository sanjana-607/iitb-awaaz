import os
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename

import database as db
import sarvam_service as sarvam

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Ensure database and directories exist
db.init_db()
db.seed_sample_data()

AUDIO_UPLOAD_DIR = os.path.join(app.root_path, "static", "audio")
os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

# Campus reference data for IIT Bombay
CAMPUS_DATA = {
    "hostels": [f"Hostel {i}" for i in range(1, 19)] + ["Hostel B", "Day scholar"],
    "departments": [
        "Aerospace Engineering",
        "Biosciences and Bioengineering",
        "Chemical Engineering",
        "Chemistry",
        "Civil Engineering",
        "Computer Science and Engineering",
        "Earth Sciences",
        "Electrical Engineering",
        "Energy Science and Engineering",
        "Humanities and Social Sciences",
        "Mathematics",
        "Mechanical Engineering",
        "Metallurgical Engineering and Materials Science",
        "Physics",
        "IDC School of Design",
        "SJM School of Management",
        "CTARA",
        "Other"
    ],
    "batches": [
        "UG 2021", "UG 2022", "UG 2023", "UG 2024", "UG 2025",
        "PG 2023", "PG 2024", "PG 2025", "PhD"
    ],
    "categories": [
        "Hostel", "Mess/Food", "Academics", "Wifi/IT", "Infrastructure/Maintenance",
        "Library", "Transport", "Sports/Gym", "Health/Medical", "Safety/Security",
        "Administration/Fees", "Placement/Career", "Clubs/Events", "Other"
    ],
    "statuses": ["Open", "Seen", "In Progress", "Resolved", "Rejected"],
    "roles": ["Student", "Warden", "Dept Head", "Admin"]
}

@app.context_processor
def inject_campus_data():
    return dict(campus=CAMPUS_DATA)

@app.route("/")
def index():
    tab = request.args.get("tab", "all")
    category = request.args.get("category", "all")
    urgency = request.args.get("urgency", "all")
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "upvotes")

    # Role & profile simulation via session or query params
    role = request.args.get("role") or session.get("role", "Student")
    session["role"] = role

    student_hostel = request.args.get("student_hostel") or session.get("student_hostel", "Hostel 5")
    student_dept = request.args.get("student_dept") or session.get("student_dept", "Computer Science and Engineering")
    student_batch = request.args.get("student_batch") or session.get("student_batch", "UG 2024")

    session["student_hostel"] = student_hostel
    session["student_dept"] = student_dept
    session["student_batch"] = student_batch

    student_profile = {
        "hostel": student_hostel,
        "department": student_dept,
        "batch": student_batch
    }

    # If Warden or Dept Head, display scoped role view
    if role == "Warden":
        warden_hostel = request.args.get("warden_hostel", "Hostel B")
        posts = db.get_role_scoped_posts("Warden", warden_hostel)
        return render_template(
            "index.html",
            posts=posts,
            current_tab=tab,
            role=role,
            warden_target=warden_hostel,
            student_profile=student_profile,
            current_category=category,
            current_urgency=urgency,
            current_status=status,
            current_sort=sort
        )
    elif role == "Dept Head":
        dept_target = request.args.get("dept_target", "Computer Science and Engineering")
        posts = db.get_role_scoped_posts("Dept Head", dept_target)
        return render_template(
            "index.html",
            posts=posts,
            current_tab=tab,
            role=role,
            dept_target=dept_target,
            student_profile=student_profile,
            current_category=category,
            current_urgency=urgency,
            current_status=status,
            current_sort=sort
        )

    # Standard Student / Public feed
    posts = db.get_feed_posts(
        tab=tab,
        student_profile=student_profile,
        category_filter=category,
        urgency_filter=urgency,
        status_filter=status,
        sort_by=sort
    )

    return render_template(
        "index.html",
        posts=posts,
        current_tab=tab,
        role=role,
        student_profile=student_profile,
        current_category=category,
        current_urgency=urgency,
        current_status=status,
        current_sort=sort
    )

@app.route("/submit", methods=["GET"])
def submit_page():
    return render_template("submit.html")

@app.route("/api/submit", methods=["POST"])
def api_submit():
    transcript = ""
    is_anonymous = request.form.get("anonymous") == "true" or request.form.get("is_anonymous") == "1"
    author_name = "Anonymous" if is_anonymous else (request.form.get("author_name") or "Student")

    # Optional student profile fields (empty or "auto" means not provided)
    hostel = request.form.get("hostel", "").strip()
    if hostel in ["auto", "none", ""]:
        hostel = None

    department = request.form.get("department", "").strip()
    if department in ["auto", "none", ""]:
        department = None

    batch = request.form.get("batch", "").strip()
    if batch in ["auto", "none", ""]:
        batch = None

    # Check if a clarified/confirmed hostel is passed from clarification modal
    confirmed_hostel = request.form.get("confirmed_hostel", "").strip()
    if confirmed_hostel:
        hostel = confirmed_hostel

    student_profile = {}
    if hostel: student_profile["hostel"] = hostel
    if department: student_profile["department"] = department
    if batch: student_profile["batch"] = batch

    # 1. Check for audio recording upload (Voice Input -> Saaras STT)
    if "audio" in request.files and request.files["audio"].filename:
        audio_file = request.files["audio"]
        orig_filename = secure_filename(audio_file.filename) or "recording.webm"
        ext = os.path.splitext(orig_filename)[1] or ".webm"
        if not ext.startswith("."):
            ext = "." + ext
        timestamp = int(time.time() * 1000)
        temp_audio_name = f"upload_{timestamp}{ext}"
        temp_audio_path = os.path.join(AUDIO_UPLOAD_DIR, temp_audio_name)
        audio_file.save(temp_audio_path)

        stt_res = sarvam.transcribe_audio_file(temp_audio_path)
        if stt_res.get("success"):
            transcript = stt_res.get("transcript", "")
        else:
            return jsonify({"success": False, "error": f"Audio transcription failed: {stt_res.get('error')}"}), 400
    else:
        # Direct text or passed transcript from draft
        transcript = request.form.get("text", "").strip()

    if not transcript:
        return jsonify({"success": False, "error": "No voice or text input provided."}), 400

    # 2. Structure complaint using sarvam-105b
    structured = sarvam.structure_complaint(transcript, student_profile=student_profile)

    # If user provided a confirmed hostel, ensure scope_name has it
    if confirmed_hostel:
        structured["scope"] = "hostel"
        structured["scope_name"] = confirmed_hostel
        structured["department"] = "Hostel Warden Office"

    # 3. Check if Hostel clarification is needed:
    # If the issue is a hostel problem, but NO hostel was named in speech or chosen in profile
    is_hostel_issue = (
        structured.get("scope") == "hostel" or 
        structured.get("category") in ["Hostel", "Mess/Food"] or 
        "hostel" in structured.get("department", "").lower()
    )
    has_hostel_name = bool(structured.get("scope_name") and structured.get("scope_name") != "null")

    if is_hostel_issue and not has_hostel_name and not confirmed_hostel:
        return jsonify({
            "success": True,
            "needs_clarification": True,
            "clarification_type": "hostel",
            "transcript": transcript,
            "draft": structured,
            "message": "We detected a hostel issue! Which hostel are you staying in?"
        })

    # 4. Check for duplicate merging ("14 students affected")
    duplicate = db.find_potential_duplicate(
        scope=structured.get("scope", "institute"),
        scope_name=structured.get("scope_name"),
        category=structured.get("category", "Other"),
        keywords=structured.get("keywords") or []
    )

    merged = False
    target_post = None

    if duplicate and not structured.get("sensitive"):
        # Merge with existing complaint
        dup_id = duplicate["id"]
        affected_count = db.merge_with_existing(dup_id)
        merged = True
        post_id = dup_id
        target_post = duplicate
        target_post["affected_count"] = affected_count
        target_post["upvotes"] = target_post.get("upvotes", 1) + 1
    else:
        # Create new complaint
        post_data = {
            "author_name": author_name,
            "is_anonymous": is_anonymous,
            "student_hostel": structured.get("scope_name") or hostel,
            "student_department": department,
            "student_batch": batch,
            "raw_transcript": transcript,
            "title": structured.get("title", "Campus Issue"),
            "summary": structured.get("summary", transcript),
            "scope": structured.get("scope", "institute"),
            "scope_name": structured.get("scope_name"),
            "category": structured.get("category", "Other"),
            "department": structured.get("department", "DoSA (Dean of Student Affairs)"),
            "location": structured.get("location"),
            "urgency": structured.get("urgency", "medium"),
            "sensitive": structured.get("sensitive", False),
            "status": "Open",
            "detected_language": structured.get("detected_language", "Telugu"),
            "keywords": structured.get("keywords") or [],
            "upvotes": 1,
            "affected_count": 1,
            "audio_confirmation_path": None,
        }
        post_id = db.create_grievance(post_data)
        target_post = post_data
        target_post["id"] = post_id

    # 5. Generate voice confirmation using Bulbul TTS
    confirm_filename = f"confirmation_{post_id}_{int(time.time())}.wav"
    confirm_path = os.path.join(AUDIO_UPLOAD_DIR, confirm_filename)
    audio_path = sarvam.generate_confirmation_audio(structured, confirm_path)
    audio_url = f"/static/audio/{confirm_filename}" if audio_path else None

    if audio_path and not merged:
        conn = db.get_connection()
        conn.execute("UPDATE grievances SET audio_confirmation_path = ? WHERE id = ?", (audio_url, post_id))
        conn.commit()
        conn.close()

    return jsonify({
        "success": True,
        "needs_clarification": False,
        "merged": merged,
        "post_id": post_id,
        "post": target_post,
        "raw_transcript": transcript,
        "audio_url": audio_url,
        "sensitive": structured.get("sensitive", False),
        "message": (
            "This complaint matches an existing issue! We linked your report and incremented the affected student count."
            if merged else
            ("Your complaint has been classified as sensitive and routed privately to authorities."
             if structured.get("sensitive") else
             "Your complaint was successfully submitted to the public feed!")
        )
    })

@app.route("/api/upvote/<int:grievance_id>", methods=["POST"])
def api_upvote(grievance_id):
    new_votes = db.upvote_grievance(grievance_id)
    return jsonify({"success": True, "upvotes": new_votes, "affected_count": new_votes})

@app.route("/api/status/<int:grievance_id>", methods=["POST"])
def api_status(grievance_id):
    data = request.get_json(silent=True) or request.form
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "error": "Missing status"}), 400

    success = db.update_status(grievance_id, new_status)
    return jsonify({"success": success, "new_status": new_status})

@app.route("/admin")
def admin_dashboard():
    metrics = db.get_admin_metrics()
    all_posts = db.get_role_scoped_posts("Admin")
    sensitive_queue = db.get_sensitive_queue()
    return render_template(
        "admin.html",
        metrics=metrics,
        posts=all_posts,
        sensitive_queue=sensitive_queue
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
