# IITB Awaaz - Voice-First Campus Grievance Platform

A multilingual, voice-first campus grievance platform built for IIT Bombay students, powered by **Sarvam AI**.

Students can speak complaints in their own language (**Telugu, Hindi, Marathi, Hinglish, or English**). The platform transcribes the speech, automatically structures the grievance into a clear English post, routes it to the designated campus authority, and synthesizes a spoken confirmation in the student's language.

---

## Architecture & Sarvam AI Pipeline

```
[Student Voice Recording (Telugu/Hindi/Marathi/English)]
                       │
                       ▼
         Sarvam Saaras STT (`saaras:v3`)
         - Multilingual & Code-mixed speech transcription
                       │
                       ▼
         Sarvam 105B Chat (`sarvam-105b`)
         - Structures complaint into 11-field JSON
         - Removes emotional venting & maintains neutrality
         - Auto-detects hostel/department/scope & routing office
         - Flags sensitive cases (harassment/ragging/safety)
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   [Public Feed]          [Private Sensitive Queue]
   (Filtered by Hostel/   (Quarantined for ICC,
    Dept/Batch tabs with   Anti-Ragging, Wellness Centre,
    "Me Too" upvotes)      or Security Office)
                       │
                       ▼
         Sarvam Bulbul TTS (`bulbul:v3`)
         - Synthesizes voice confirmation in student's language
```

---

## Key Features

1. **Multilingual Voice Recording**:
   - In-browser microphone audio capture with automatic format handling (`webm` / `mp4`).
   - Powered by Sarvam Saaras (`saaras:v3`) supporting Indian code-mixed speech.
2. **Intelligent Scope & Hostel Detection**:
   - Automatically extracts hostel names spoken in any language (e.g. *"హోస్టల్ 3 లో..."* $\to$ `Hostel 3`).
   - If a hostel issue is spoken without naming a hostel, a 1-tap clarification prompt lets students select their hostel without re-recording.
3. **Public Feed & "Me Too" Upvotes**:
   - Tabbed views: *All*, *My Hostel*, *My Department*, *My Batch*, *Clubs & Events*, and *Institute-wide*.
   - Filter by Category, Urgency, and Status.
   - Upvoting increments the *"X students affected"* count.
4. **Duplicate Merging**:
   - When a student reports an existing issue in the same scope, the platform links the reports and increments the affected student counter.
5. **Private Sensitive Queue**:
   - Harassment, ragging, discrimination, mental health, or safety reports **never appear on public feeds**.
   - Confidential routing to Anti-Ragging Committee, Internal Complaints Committee (ICC), Student Wellness Centre, or Security Office.
6. **Role Management (No real login required)**:
   - Header dropdown allows switching between **Student**, **Hostel Warden** (scoped to their hostel), **Department Head** (scoped to their department), and **Admin**.
7. **Bulbul Spoken Confirmation**:
   - Real-time TTS confirmation audio generated and played back upon submission.

---

## Setup & Running Locally

### 1. Clone the repository
```bash
git clone https://github.com/sanjana-607/sarvam-campus-grievance.git
cd sarvam-campus-grievance
```

### 2. Set up virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API Key
Create a `.env` file in the project root:
```env
SARVAM_API_KEY=your_sarvam_api_key_here
```

### 4. Run the application
```bash
python app.py
```
Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

---
