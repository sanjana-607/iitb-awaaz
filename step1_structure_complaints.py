import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

SYSTEM_PROMPT = """You are an AI assistant structuring student grievances for the IIT Bombay campus platform.
Given a student complaint (which may be in code-mixed Hindi/Marathi/Telugu/English), analyze and return strictly a valid JSON object with the following fields:

- title: short, clean English title (max 10 words). Never include names of individual students or staff.
- summary: 1-2 neutral, factual sentences with anger and insults removed. Never include names of individual students or staff.
- scope: one of ["hostel", "mess", "academic_department", "course", "batch", "club_or_committee", "institute", "other"].
  If the complaint names a specific place or group, use that scope. If many places are affected, use "institute".
- scope_name: specific hostel, mess, department, course, batch, club, or committee (e.g. "Hostel B", "Computer Science", "CS101", "2025 batch", "WnCC"), or null if institute-wide.
- category: one of ["Hostel", "Mess/Food", "Academics", "Wifi/IT", "Infrastructure/Maintenance", "Library", "Transport", "Sports/Gym", "Health/Medical", "Safety/Security", "Administration/Fees", "Placement/Career", "Clubs/Events", "Other"].
- department: the office that should handle it, strictly one of:
  ["Hostel Warden Office", "Mess Committee", "Dean of Academic Affairs", "Head of Department", "Course Instructor/Coordinator", "IT/Network Cell", "Estate/Maintenance Office", "Central Library", "Transport Office", "Institute Sports Council", "Institute Cultural Council", "Institute Technical Council", "Hostel Affairs Council", "Institute Hospital", "DoSA (Dean of Student Affairs)", "Accounts/Fees Office", "Training & Placement Cell", "Anti-Ragging Committee", "Internal Complaints Committee", "Student Wellness Centre", "Security Office"].
  Routing rules:
  * Hostel problems -> "Hostel Warden Office"
  * Department problems -> "Head of Department"
  * Course problems -> "Course Instructor/Coordinator"
  * Mess problems -> "Mess Committee"
  * Club (e.g. WnCC) or technical events -> "Institute Technical Council"
  * Cultural / sports events -> "Institute Cultural Council" / "Institute Sports Council"
  * Institute-wide IT / Wifi -> "IT/Network Cell"
  * Harassment / ragging / mental health -> "Internal Complaints Committee", "Anti-Ragging Committee", "Student Wellness Centre", or "Security Office"
- location: block, wing, room, lab, or building if mentioned, otherwise null.
- urgency: one of ["low", "medium", "high", "critical"] (critical only for safety, health, harassment, or no water/electricity).
- sensitive: boolean (true for harassment, ragging, discrimination, mental health, or safety complaints; false otherwise).
- detected_language: main language of the complaint (e.g., "Hindi", "Hinglish", "English", "Marathi").
- keywords: array of 3-5 tags.

Return ONLY a valid JSON object. Do not wrap in markdown quotes or add conversational text."""

complaints = [
    "Hostel B ka geyser teen din se kharab hai, bahut thanda paani aata hai",
    "CS department ki lab mein computers kaam nahi kar rahe, practical nahi ho pa raha",
    "Campus mein wifi bahut slow hai, library mein bhi kaam nahi kar raha",
    "WnCC ka meeting room book nahi ho raha, koi reply nahi de raha",
]

def clean_json_text(text: str) -> str:
    if not text:
        return "{}"
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def process_complaint(complaint: str, max_retries: int = 2) -> dict:
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions(
                model="sarvam-105b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": complaint},
                ],
                temperature=0.1,
            )
            raw_content = response.choices[0].message.content
            if not raw_content and hasattr(response.choices[0].message, "reasoning_content"):
                raw_content = response.choices[0].message.reasoning_content

            cleaned = clean_json_text(raw_content)
            parsed = json.loads(cleaned)
            if parsed:
                return parsed
        except Exception as e:
            if attempt == max_retries:
                raise e
    return {}

def main():
    print("=" * 60)
    print("IIT BOMBAY GRIEVANCE PLATFORM - STEP 1 EVALUATION")
    print("Testing 4 Code-Mixed Complaints with sarvam-105b")
    print("=" * 60)

    for i, complaint in enumerate(complaints, 1):
        print(f"\n--- Complaint #{i} ---")
        print(f"Input: \"{complaint}\"")
        try:
            parsed = process_complaint(complaint)
            formatted = json.dumps(parsed, indent=2)
            print("Output JSON:")
            print(formatted)
        except Exception as e:
            print(f"Error processing complaint {i}: {e}")

if __name__ == "__main__":
    main()
