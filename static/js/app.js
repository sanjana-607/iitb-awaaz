// IIT Bombay Campus Grievance Platform - Frontend Controller

let mediaRecorder = null;
let audioChunks = [];
let recordedAudioBlob = null;
let recordingTimerInterval = null;
let recordingSeconds = 0;

// ==========================================
// VOICE RECORDING CONTROLS (MediaRecorder API)
// ==========================================

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Pick compatible mime type
    let mimeType = 'audio/webm';
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus';
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      mimeType = 'audio/mp4';
    }

    mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
    audioChunks = [];
    recordedAudioBlob = null;

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = () => {
      recordedAudioBlob = new Blob(audioChunks, { type: mimeType });
      const audioUrl = URL.createObjectURL(recordedAudioBlob);
      const audioPreview = document.getElementById("audio-preview");
      if (audioPreview) {
        audioPreview.src = audioUrl;
        document.getElementById("audio-preview-container").classList.remove("hidden");
      }
      // Stop all mic tracks
      stream.getTracks().forEach(track => track.stop());
    };

    mediaRecorder.start();

    // UI state updates
    document.getElementById("start-record-btn").classList.add("hidden");
    document.getElementById("stop-record-btn").classList.remove("hidden");
    
    const micWrapper = document.getElementById("mic-icon-wrapper");
    if (micWrapper) {
      micWrapper.classList.remove("bg-blue-100", "text-blue-600");
      micWrapper.classList.add("bg-rose-100", "text-rose-600", "animate-pulse");
    }

    const statusEl = document.getElementById("recording-status");
    if (statusEl) statusEl.textContent = "Recording in progress... speak now";

    // Timer
    recordingSeconds = 0;
    const timerEl = document.getElementById("recording-timer");
    recordingTimerInterval = setInterval(() => {
      recordingSeconds++;
      const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
      const secs = String(recordingSeconds % 60).padStart(2, '0');
      if (timerEl) timerEl.textContent = `${mins}:${secs}`;
    }, 1000);

  } catch (err) {
    console.error("Mic access denied or error:", err);
    alert("Microphone access could not be established. You can type your complaint in the box below instead.");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  clearInterval(recordingTimerInterval);

  // UI state updates
  document.getElementById("start-record-btn").classList.remove("hidden");
  document.getElementById("stop-record-btn").classList.add("hidden");

  const micWrapper = document.getElementById("mic-icon-wrapper");
  if (micWrapper) {
    micWrapper.classList.remove("bg-rose-100", "text-rose-600", "animate-pulse");
    micWrapper.classList.add("bg-emerald-100", "text-emerald-600");
  }

  const statusEl = document.getElementById("recording-status");
  if (statusEl) statusEl.textContent = "Voice recording captured! Ready to submit.";
}

let currentTranscript = "";

// ==========================================
// SUBMISSION HANDLER (Sarvam AI Pipeline)
// ==========================================

async function submitGrievance() {
  const textInput = document.getElementById("complaint-text").value.trim();

  if (!recordedAudioBlob && !textInput) {
    alert("Please either record your voice complaint or type your issue in the text area.");
    return;
  }

  const formData = new FormData();
  if (recordedAudioBlob) {
    const isMp4 = recordedAudioBlob.type.includes("mp4");
    const filename = isMp4 ? "recording.mp4" : "recording.webm";
    formData.append("audio", recordedAudioBlob, filename);
  }
  if (textInput) {
    formData.append("text", textInput);
  }

  formData.append("hostel", document.getElementById("student-hostel").value);
  formData.append("department", document.getElementById("student-dept").value);
  formData.append("batch", document.getElementById("student-batch").value);
  formData.append("anonymous", document.getElementById("anonymous-toggle").checked);

  // UI loading
  const submitBtn = document.getElementById("submit-btn");
  const indicator = document.getElementById("processing-indicator");
  const stepText = document.getElementById("processing-step");

  submitBtn.disabled = true;
  submitBtn.classList.add("opacity-50", "cursor-not-allowed");
  indicator.classList.remove("hidden");
  document.getElementById("clarification-card").classList.add("hidden");

  stepText.textContent = recordedAudioBlob 
    ? "Step 1/3: Transcribing multilingual audio with Sarvam Saaras..." 
    : "Step 1/2: Structuring grievance post with sarvam-105b...";

  try {
    const response = await fetch("/api/submit", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!data.success) {
      alert("Submission Error: " + (data.error || "Unknown error"));
      return;
    }

    // Hide indicator
    indicator.classList.add("hidden");

    // Check if Hostel clarification is needed
    if (data.needs_clarification && data.clarification_type === "hostel") {
      currentTranscript = data.transcript;
      const clarifyCard = document.getElementById("clarification-card");
      document.getElementById("clarify-transcript").textContent = `"${data.transcript}"`;
      clarifyCard.classList.remove("hidden");
      clarifyCard.scrollIntoView({ behavior: 'smooth' });
      return;
    }

    renderSubmissionResult(data);

  } catch (err) {
    console.error("Submission failed:", err);
    alert("An error occurred during submission. Please try again.");
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
    indicator.classList.add("hidden");
  }
}

async function finalizeWithHostel(hostelName) {
  const formData = new FormData();
  formData.append("text", currentTranscript);
  formData.append("confirmed_hostel", hostelName);
  formData.append("department", document.getElementById("student-dept").value);
  formData.append("batch", document.getElementById("student-batch").value);
  formData.append("anonymous", document.getElementById("anonymous-toggle").checked);

  const indicator = document.getElementById("processing-indicator");
  indicator.classList.remove("hidden");
  document.getElementById("processing-step").textContent = `Routing to ${hostelName} Warden & synthesizing voice confirmation...`;
  document.getElementById("clarification-card").classList.add("hidden");

  try {
    const res = await fetch("/api/submit", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (data.success) {
      renderSubmissionResult(data);
    } else {
      alert("Error: " + data.error);
    }
  } catch (err) {
    console.error(err);
    alert("Could not finalize submission.");
  } finally {
    indicator.classList.add("hidden");
  }
}

function renderSubmissionResult(data) {
  // Populate result card
  const resultCard = document.getElementById("result-card");
  const resultTitle = document.getElementById("result-title");
  const resultMsg = document.getElementById("result-message");
  const sensBadge = document.getElementById("result-sensitive-badge");

  resultCard.classList.remove("hidden");
  resultTitle.textContent = data.merged ? "Duplicate Complaint Merged!" : "Grievance Registered";
  resultMsg.textContent = data.message;

  if (data.sensitive) {
    sensBadge.classList.remove("hidden");
  } else {
    sensBadge.classList.add("hidden");
  }

  const post = data.post || {};
  document.getElementById("res-post-title").textContent = post.title || "N/A";
  document.getElementById("res-post-summary").textContent = post.summary || "N/A";
  document.getElementById("res-post-dept").textContent = post.department || "N/A";
  document.getElementById("res-post-meta").textContent = `${post.category || 'Other'} (${post.scope || 'institute'})`;

  // Handle Bulbul Confirmation Audio
  if (data.audio_url) {
    const audioBox = document.getElementById("confirmation-audio-box");
    const audioPlayer = document.getElementById("confirmation-audio-player");
    audioPlayer.src = data.audio_url;
    audioBox.classList.remove("hidden");
    audioPlayer.play().catch(e => console.log("Autoplay blocked, user can click play:", e));
  }

  // Scroll smoothly to results
  resultCard.scrollIntoView({ behavior: 'smooth' });
}

// ==========================================
// UPVOTE ("ME TOO") AJAX HANDLER
// ==========================================

async function upvotePost(postId) {
  try {
    const btn = document.getElementById(`upvote-btn-${postId}`);
    const voteSpan = document.getElementById(`vote-count-${postId}`);
    const affectedSpan = document.getElementById(`affected-count-${postId}`);

    btn.disabled = true;

    const res = await fetch(`/api/upvote/${postId}`, { method: "POST" });
    const data = await res.json();

    if (data.success) {
      voteSpan.textContent = data.upvotes;
      if (affectedSpan) affectedSpan.textContent = data.affected_count;
      btn.classList.add("bg-blue-100", "text-blue-800", "border-blue-400");
    }
  } catch (err) {
    console.error("Upvote failed:", err);
  }
}

// ==========================================
// STATUS UPDATE HANDLER (Admin/Warden/Dept Head)
// ==========================================

async function updatePostStatus(postId, newStatus) {
  try {
    const res = await fetch(`/api/status/${postId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    const data = await res.json();
    if (data.success) {
      // Visual feedback
      console.log(`Updated post #${postId} to ${newStatus}`);
    }
  } catch (err) {
    console.error("Failed to update status:", err);
    alert("Could not update status.");
  }
}

// Audio player helper
function playAudio(url) {
  const audio = new Audio(url);
  audio.play().catch(err => console.error("Playback failed:", err));
}
