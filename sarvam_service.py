import base64
import json
import os
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

SYSTEM_PROMPT = """You are an AI assistant structuring student grievances for the IIT Bombay campus platform.
Given a student complaint (which may be spoken in Telugu, Hindi, Marathi, Hinglish, or English), analyze and return strictly a valid JSON object with the following fields:

- title: short, clean English title (max 10 words). Never include names of individual students or staff.
- summary: 1-2 neutral, factual sentences in English with anger and insults removed. Never include names of individual students or staff.
- scope: one of ["hostel", "mess", "academic_department", "course", "batch", "club_or_committee", "institute", "other"].
  If the complaint mentions a specific hostel, department, course, or club, use that scope.
  If many places are affected or institute facilities like main wifi/hospital/library are mentioned, use "institute".
- scope_name: specific hostel, mess, department, course, batch, club, or committee (e.g. "Hostel 3", "Hostel B", "Computer Science", "CS101", "2025 batch", "WnCC"), or null if institute-wide or not mentioned.
  IMPORTANT MULTILINGUAL HOSTEL EXTRACTION:
  * Telugu: "హోస్టల్ 3" / "హాస్టల్ 4" -> "Hostel 3" / "Hostel 4"
  * Hindi: "होस्टल 5" / "हॉस्टल बी" -> "Hostel 5" / "Hostel B"
  * Abbreviations: "H1" to "H18" -> "Hostel 1" to "Hostel 18"
  * If the student names their hostel in ANY language, extract it into scope_name.
  * If no hostel is mentioned and it's a general hostel issue without a specific hostel named, set scope_name to null.
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
  * Harassment / ragging / mental health / safety -> route to "Anti-Ragging Committee", "Internal Complaints Committee", "Student Wellness Centre", or "Security Office"
- location: block, wing, room, lab, or building if mentioned, otherwise null.
- urgency: one of ["low", "medium", "high", "critical"] (critical only for safety, health, harassment, or no water/electricity).
- sensitive: boolean (true for harassment, ragging, discrimination, mental health, or safety complaints; false otherwise).
- detected_language: main language of the complaint (e.g., "Telugu", "Hindi", "Hinglish", "Marathi", "English").
- keywords: array of 3-5 tags.

Rules:
- Never include names of individual students or staff in the title or summary.
- Return ONLY a valid JSON object. No markdown ticks, no preamble."""

def clean_json_text(text: Optional[str]) -> str:
    if not text:
        return "{}"
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def structure_complaint(text: str, student_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Uses sarvam-105b to extract structured post details from code-mixed complaint."""
    prompt_content = f"Student Complaint: {text}\n"
    if student_profile:
        prompt_content += (
            f"Student Profile Fallback Context: Hostel={student_profile.get('hostel')}, "
            f"Department={student_profile.get('department')}, Batch={student_profile.get('batch')}\n"
        )

    for attempt in range(2):
        try:
            response = client.chat.completions(
                model="sarvam-105b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_content},
                ],
                temperature=0.1,
            )
            raw = response.choices[0].message.content
            if not raw and hasattr(response.choices[0].message, "reasoning_content"):
                raw = response.choices[0].message.reasoning_content

            cleaned = clean_json_text(raw)
            data = json.loads(cleaned)
            if data and "title" in data:
                return data
        except Exception as e:
            if attempt == 1:
                print(f"[Sarvam Error] Failed to structure complaint: {e}")
                # Fallback structure if API fails
    # If retries did not yield a valid title, return safe structured fallback
    return {
        "title": text[:60] + "..." if len(text) > 60 else text,
        "summary": text,
        "scope": "other",
        "scope_name": student_profile.get("hostel") if student_profile else None,
        "category": "Other",
        "department": "DoSA (Dean of Student Affairs)",
        "location": None,
        "urgency": "medium",
        "sensitive": False,
        "detected_language": "Unknown",
        "keywords": ["grievance", "campus"]
    }

def transcribe_audio_file(audio_path: str) -> Dict[str, Any]:
    """Uses Sarvam Saaras (saaras:v3) to transcribe code-mixed audio into text."""
    try:
        filename = os.path.basename(audio_path)
        with open(audio_path, "rb") as f:
            stt_response = client.speech_to_text.transcribe(
                file=(filename, f),
                model="saaras:v3",
            )
        return {
            "success": True,
            "transcript": stt_response.transcript,
            "language_code": stt_response.language_code,
            "language_probability": stt_response.language_probability,
        }
    except Exception as e:
        print(f"[Sarvam STT Error] {e}")
        return {
            "success": False,
            "error": str(e),
            "transcript": "",
        }

def generate_confirmation_audio(complaint_data: Dict[str, Any], output_path: str) -> Optional[str]:
    """
    Uses Sarvam Bulbul TTS (bulbul:v3) to synthesize a voice confirmation
    in the student's language (Hindi/Hinglish/English).
    """
    title = complaint_data.get("title", "shikayat")
    department = complaint_data.get("department", "Prashasan")
    detected_lang = (complaint_data.get("detected_language") or "").lower()

    if "marathi" in detected_lang:
        confirmation_text = f"Tumchi takrar nondavli geli aahe: {title}. Sambandhit vibhag {department} la kalavle jaail."
        lang_code = "mr-IN"
        speaker = "rupali"
    elif "telugu" in detected_lang:
        confirmation_text = f"Mee complaint record cheyabadindi: {title}. Sambandhita department {department} ki pampabaduthundi."
        lang_code = "te-IN"
        speaker = "kavitha"
    elif "english" in detected_lang and "hinglish" not in detected_lang:
        confirmation_text = f"Your grievance has been registered: {title}. It has been forwarded to the {department}."
        lang_code = "en-IN"
        speaker = "aditya"
    else:
        # Default Hinglish/Hindi
        confirmation_text = f"Aapki shikayat darj kar li gayi hai: {title}. Sambandhit vibhag, {department}, ko bhej diya gaya hai."
        lang_code = "hi-IN"
        speaker = "aditya"

    try:
        tts_response = client.text_to_speech.convert(
            text=confirmation_text,
            language_code=lang_code,
            speaker=speaker,
            model="bulbul:v3",
            output_audio_codec="wav",
        )
        if tts_response.audios:
            audio_bytes = base64.b64decode(tts_response.audios[0])
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            return output_path
    except Exception as e:
        print(f"[Sarvam TTS Error] Could not generate Bulbul confirmation: {e}")
    return None
