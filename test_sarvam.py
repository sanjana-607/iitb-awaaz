import json
import os
from dotenv import load_dotenv

load_dotenv()

from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key=os.environ.get("SARVAM_API_KEY"))

sample_complaint = (
    "Hostel 3 me paani nahi aa raha subah se, and exam starts tomorrow morning! "
    "Please fix the pump urgently, washrooms are completely dry."
)

system_prompt = """You are an AI that structures student grievances for a campus platform.
Given a student complaint, extract and return a valid JSON object with the following fields:
- title: A concise, descriptive title
- summary: A clear summary of the issue
- category: One of ["Facilities", "Academics", "Hostel", "Safety", "Administration", "Other"]
- urgency: One of ["Low", "Medium", "High", "Critical"]
- department: The campus department responsible
- sensitive: Boolean (true if harassment, ragging, or personal safety concern, false otherwise)

Return ONLY valid JSON with no additional markdown formatting or explanation."""

response = client.chat.completions(
    model="sarvam-105b",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": sample_complaint},
    ],
    temperature=0.2,
)

content = response.choices[0].message.content
print("Model Response:")
print(content)
