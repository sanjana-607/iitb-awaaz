import base64
import json
import os
from dotenv import load_dotenv

load_dotenv()

from sarvamai import SarvamAI
from step1_structure_complaints import process_complaint

client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

SAMPLE_AUDIO_PATH = "sample_complaint.wav"
SAMPLE_TEXT = "Hostel B ka geyser teen din se kharab hai, bahut thanda paani aata hai"

def ensure_sample_audio():
    """Generates a realistic sample audio file using Sarvam Bulbul TTS if not present."""
    if os.path.exists(SAMPLE_AUDIO_PATH) and os.path.getsize(SAMPLE_AUDIO_PATH) > 0:
        print(f"Using existing audio file: {SAMPLE_AUDIO_PATH}")
        return

    print(f"Generating realistic code-mixed audio sample using Bulbul TTS...")
    print(f"Spoken text: \"{SAMPLE_TEXT}\"")
    tts_response = client.text_to_speech.convert(
        text=SAMPLE_TEXT,
        language_code="hi-IN",
        speaker="aditya",
        model="bulbul:v3",
        output_audio_codec="wav",
    )

    audio_bytes = base64.b64decode(tts_response.audios[0])
    with open(SAMPLE_AUDIO_PATH, "wb") as f:
        f.write(audio_bytes)
    print(f"Saved audio sample ({len(audio_bytes)} bytes) to {SAMPLE_AUDIO_PATH}")

def transcribe_audio():
    print("=" * 60)
    print("STEP 2: SAARAS SPEECH TO TEXT TRANSCRIBE")
    print("=" * 60)

    ensure_sample_audio()

    print(f"\nSending {SAMPLE_AUDIO_PATH} to Sarvam Saaras STT...")
    with open(SAMPLE_AUDIO_PATH, "rb") as audio_file:
        stt_response = client.speech_to_text.transcribe(
            file=audio_file,
            model="saaras:v3",
        )

    print("\n--- Saaras STT Result ---")
    print(f"Transcript: \"{stt_response.transcript}\"")
    print(f"Detected Language Code: {stt_response.language_code}")
    print(f"Language Probability: {stt_response.language_probability}")

    print("\n--- Piping Transcript into sarvam-105b (End-to-End Pipeline) ---")
    structured = process_complaint(stt_response.transcript)
    print("Structured Grievance Post:")
    print(json.dumps(structured, indent=2))

if __name__ == "__main__":
    transcribe_audio()
