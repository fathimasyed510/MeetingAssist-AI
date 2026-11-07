
import streamlit as st
import os
import io
import re
import json
import sqlite3
import tempfile
import subprocess
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq
import imageio_ffmpeg

# Hindsight is the long-term memory layer for saved meetings.
try:
    from hindsight_client import Hindsight
except ImportError:
    Hindsight = None

from pypdf import PdfReader
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from xml.sax.saxutils import escape

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="MeetingAssist AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
WHISPER_MODEL = "whisper-large-v3"
AI_MODEL = "openai/gpt-oss-120b"
DB_NAME = "meetings.db"
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_API_URL = os.getenv(
    "HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io"
)
HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "meetingassist")

if not API_KEY:
    st.error(
        "Groq API key not found. Check that your .env file "
        "contains GROQ_API_KEY=your_key"
    )
    st.stop()

client = Groq(api_key=API_KEY)

# --------------------------------------------------
# HINDSIGHT LONG-TERM MEETING MEMORY
# --------------------------------------------------

@st.cache_resource
def get_hindsight_client():
    """Create one reusable Hindsight client for this Streamlit session."""
    if Hindsight is None or not HINDSIGHT_API_KEY:
        return None

    hindsight = Hindsight(
        base_url=HINDSIGHT_API_URL,
        api_key=HINDSIGHT_API_KEY
    )
    # Creating an existing bank may return an API error; in that case
    # the existing bank remains usable, so continue with the client.
    try:
        hindsight.create_bank(
            bank_id=HINDSIGHT_BANK_ID,
            name="MeetingAssist AI Meeting Memory"
        )
    except Exception:
        pass
    return hindsight


def retain_meeting_in_hindsight(title, created_at, source_type, transcript, analysis):
    """Store a processed meeting in Hindsight for future recall and reflection."""
    hindsight = get_hindsight_client()
    if hindsight is None:
        return False

    memory_content = f"""
MEETING TITLE: {title}
DATE: {created_at}
SOURCE: {source_type}
SUMMARY: {analysis.get('summary', '')}
KEY DISCUSSION POINTS: {json.dumps(analysis.get('key_points', []), ensure_ascii=False)}
DECISIONS: {json.dumps(analysis.get('decisions', []), ensure_ascii=False)}
ACTION ITEMS: {json.dumps(analysis.get('action_items', []), ensure_ascii=False)}
TOPICS: {json.dumps(analysis.get('topics', []), ensure_ascii=False)}
FOLLOW-UP: {json.dumps(analysis.get('follow_up', []), ensure_ascii=False)}
TRANSCRIPT: {transcript[:30000]}
""".strip()

    hindsight.retain(
        bank_id=HINDSIGHT_BANK_ID,
        content=memory_content,
        context=f"MeetingAssist meeting: {title}",
        metadata={"meeting_title": title, "meeting_date": created_at, "source_type": source_type}
    )
    return True


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def setup_database():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT,
            source_type TEXT,
            transcript TEXT,
            summary TEXT,
            analysis_json TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_meeting(title, source_type, transcript, analysis):
    conn = get_connection()
    conn.execute("""
        INSERT INTO meetings
        (title, created_at, source_type, transcript, summary, analysis_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        title,
        datetime.now().strftime("%d %b %Y, %I:%M %p"),
        source_type,
        transcript,
        analysis.get("summary", ""),
        json.dumps(analysis, ensure_ascii=False)
    ))
    conn.commit()
    conn.close()

def get_meetings():
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, title, created_at, source_type,
               transcript, summary, analysis_json
        FROM meetings
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows

def get_meeting(meeting_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT id, title, created_at, source_type,
               transcript, summary, analysis_json
        FROM meetings WHERE id = ?
    """, (meeting_id,)).fetchone()
    conn.close()
    return row

setup_database()

# --------------------------------------------------
# DESIGN
# --------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #0b1020;
    color: #f2f4ff;
}

[data-testid="stSidebar"] {
    background: #11182b;
    border-right: 1px solid #26314c;
}

.hero {
    padding: 30px;
    border-radius: 22px;
    background: linear-gradient(120deg, #182c50, #34215b, #172b46);
    border: 1px solid #43517d;
    margin-bottom: 25px;
}

.hero h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 38px;
    margin: 0;
    color: white;
}

.hero p {
    color: #d3d9f5;
    font-size: 16px;
    margin-bottom: 0;
}

.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 23px;
    font-weight: 700;
    margin: 15px 0;
    color: #ffffff;
}

.metric-card {
    background: #151f35;
    border: 1px solid #2d3b5c;
    border-radius: 16px;
    padding: 20px;
    min-height: 115px;
}

.metric-label {
    color: #aab6d3;
    font-size: 13px;
}

.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 30px;
    font-weight: 700;
    color: white;
    margin-top: 7px;
}

.feature-card {
    background: #151f35;
    border: 1px solid #2d3b5c;
    padding: 20px;
    border-radius: 16px;
    min-height: 140px;
}

.feature-card h3 {
    color: white;
    font-size: 17px;
}

.feature-card p {
    color: #aab6d3;
    font-size: 13px;
}

div.stButton > button {
    border-radius: 10px;
    border: 1px solid #6678e8;
    background: linear-gradient(90deg, #5968d9, #8158d8);
    color: white;
    font-weight: 600;
    min-height: 42px;
}

div.stButton > button:hover {
    border-color: #a9b4ff;
    color: white;
}

.stDownloadButton button {
    border-radius: 10px;
    background: #263a58;
    color: white;
    border: 1px solid #52688d;
}

[data-testid="stExpander"] {
    border: 1px solid #2d3b5c;
    border-radius: 12px;
    background: #121b30;
}

.stTextInput input, .stTextArea textarea {
    background: #121b30;
    color: white;
    border: 1px solid #354565;
}

hr {
    border-color: #293653;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# FILE EXTRACTION
# --------------------------------------------------

VIDEO_FORMATS = ["mp4", "mov", "mkv", "avi", "webm"]
AUDIO_FORMATS = [
    "mp3", "wav", "m4a", "aac", "mpeg",
    "mpga", "flac", "ogg", "webm"
]
TEXT_FORMATS = [
    "txt", "md", "pdf", "docx", "csv", "srt", "vtt"
]

def extract_text_from_file(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    data = uploaded_file.getvalue()

    if extension in ["txt", "md", "csv", "srt", "vtt"]:
        return data.decode("utf-8", errors="replace")

    if extension == "pdf":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

    if extension == "docx":
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError("Unsupported text document format.")

def extract_audio_from_media(uploaded_file):
    """
    Converts audio or video into a compressed MP3.
    This also handles AAC files and extracts audio from videos.
    """

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(
            temp_dir, "input." + extension
        )
        output_path = os.path.join(
            temp_dir, "meeting_audio.mp3"
        )

        with open(input_path, "wb") as file:
            file.write(uploaded_file.getvalue())

        command = [
            ffmpeg_exe,
            "-y",
            "-i", input_path,
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-b:a", "64k",
            output_path
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0 or not os.path.exists(output_path):
            raise ValueError(
                "Could not extract audio. Check that the file "
                "is valid and contains an audio track."
            )

        with open(output_path, "rb") as file:
            audio_data = file.read()

    if len(audio_data) > 24 * 1024 * 1024:
        raise ValueError(
            "The converted audio is still too large for one "
            "transcription request. Try a shorter recording."
        )

    return audio_data

def get_transcript(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension in TEXT_FORMATS:
        transcript = extract_text_from_file(uploaded_file)

        if not transcript.strip():
            raise ValueError(
                "No readable text was found in this document."
            )

        return transcript, "Text document"

    if extension in AUDIO_FORMATS or extension in VIDEO_FORMATS:
        audio_data = extract_audio_from_media(uploaded_file)

        result = client.audio.transcriptions.create(
            file=("meeting_audio.mp3", audio_data),
            model=WHISPER_MODEL,
            response_format="text"
        )

        transcript = (
            result if isinstance(result, str)
            else result.text
        )

        if not transcript.strip():
            raise ValueError("No speech was detected.")

        source_type = (
            "Video recording"
            if extension in VIDEO_FORMATS
            else "Audio recording"
        )

        return transcript, source_type

    raise ValueError("This file format is not supported.")

# --------------------------------------------------
# AI MEETING ANALYSIS
# --------------------------------------------------

def ask_groq(prompt, system_message=None):
    messages = []

    if system_message:
        messages.append({
            "role": "system",
            "content": system_message
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
        temperature=0.2
    )

    return response.choices[0].message.content

def analyse_meeting(transcript):
    prompt = f"""
Analyse the following meeting transcript carefully.

Return ONLY valid JSON. Do not include markdown code fences.

Use exactly this structure:

{{
  "summary": "A clear and detailed meeting summary",
  "key_points": [
    "Important discussion point"
  ],
  "decisions": [
    "Decision made"
  ],
  "action_items": [
    {{
      "task": "Task to complete",
      "owner": "Person responsible, or Not specified",
      "deadline": "Deadline, or Not specified"
    }}
  ],
  "topics": [
    "Main topic discussed"
  ],
  "follow_up": [
    "Suggested follow-up"
  ]
}}

Rules:
- Do not invent facts, names, owners or deadlines.
- If something is not mentioned, write Not specified.
- Separate actual decisions from suggestions.
- If there are no action items, return an empty list.
- Make the summary useful and easy to understand.

MEETING TRANSCRIPT:
{transcript[:45000]}
"""

    raw = ask_groq(
        prompt,
        "You are MeetingAssist AI, a careful professional meeting analyst."
    )

    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON found")

        data = json.loads(match.group())

        defaults = {
            "summary": "Summary unavailable.",
            "key_points": [],
            "decisions": [],
            "action_items": [],
            "topics": [],
            "follow_up": []
        }

        for key, value in defaults.items():
            if key not in data:
                data[key] = value

        return data

    except Exception:
        return {
            "summary": raw,
            "key_points": [],
            "decisions": [],
            "action_items": [],
            "topics": [],
            "follow_up": []
        }

# --------------------------------------------------
# PDF REPORT
# --------------------------------------------------

def create_pdf(title, created_at, source_type, transcript, analysis):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    heading = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#263D70"),
        spaceAfter=12
    )

    subheading = ParagraphStyle(
        "CustomSubheading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#4B5F92"),
        spaceBefore=12,
        spaceAfter=7
    )

    body = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=7
    )

    story = [
        Paragraph("MeetingAssist AI", heading),
        Paragraph("Meeting Report", subheading),
        Paragraph(f"<b>Meeting:</b> {escape(str(title))}", body),
        Paragraph(f"<b>Date:</b> {escape(str(created_at))}", body),
        Paragraph(f"<b>Source:</b> {escape(str(source_type))}", body),
        Spacer(1, 12),
        Paragraph("Executive Summary", subheading),
        Paragraph(
            escape(str(analysis.get("summary", ""))).replace("\n", "<br/>"),
            body
        )
    ]

    sections = [
        ("Key Discussion Points", "key_points"),
        ("Decisions Made", "decisions"),
        ("Topics Discussed", "topics"),
        ("Follow-up Suggestions", "follow_up")
    ]

    for heading_text, key in sections:
        story.append(Paragraph(heading_text, subheading))

        items = analysis.get(key, [])
        if items:
            for item in items:
                story.append(Paragraph(
                    "• " + escape(str(item)), body
                ))
        else:
            story.append(Paragraph("None recorded.", body))

    story.append(Paragraph("Action Items", subheading))

    actions = analysis.get("action_items", [])
    if actions:
        for item in actions:
            story.append(Paragraph(
                f"<b>Task:</b> {escape(str(item.get('task', '')))}<br/>"
                f"<b>Owner:</b> {escape(str(item.get('owner', 'Not specified')))}<br/>"
                f"<b>Deadline:</b> {escape(str(item.get('deadline', 'Not specified')))}",
                body
            ))
    else:
        story.append(Paragraph("No action items recorded.", body))

    story.append(Paragraph("Full Transcript", subheading))
    safe_transcript = escape(str(transcript)).replace("\n", "<br/>")
    story.append(Paragraph(safe_transcript, body))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --------------------------------------------------
# REUSABLE DISPLAY FUNCTIONS
# --------------------------------------------------

def show_analysis(analysis):
    st.markdown("### ✨ Executive Summary")
    st.write(analysis.get("summary", "No summary available."))

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💡 Key Discussion Points")
        points = analysis.get("key_points", [])
        if points:
            for point in points:
                st.markdown(f"- {point}")
        else:
            st.caption("No key points recorded.")

    with col2:
        st.markdown("### ✅ Decisions Made")
        decisions = analysis.get("decisions", [])
        if decisions:
            for decision in decisions:
                st.markdown(f"- {decision}")
        else:
            st.caption("No decisions recorded.")

    st.markdown("### 📌 Action Items")

    actions = analysis.get("action_items", [])

    if actions:
        for index, item in enumerate(actions, 1):
            with st.container(border=True):
                st.markdown(f"**{index}. {item.get('task', '')}**")
                a, b = st.columns(2)
                a.caption(
                    "👤 Owner: " +
                    str(item.get("owner", "Not specified"))
                )
                b.caption(
                    "📅 Deadline: " +
                    str(item.get("deadline", "Not specified"))
                )
    else:
        st.info("No action items were identified.")

    st.markdown("### 🔄 Follow-up Suggestions")
    for item in analysis.get("follow_up", []):
        st.markdown(f"- {item}")

    st.markdown("### 🗂️ Topics Discussed")
    topics = analysis.get("topics", [])
    if topics:
        st.write(" • ".join(topics))
    else:
        st.caption("No topics recorded.")

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.markdown("## 🎙️ MeetingAssist AI")
    st.caption("Your intelligent meeting companion")
    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Dashboard",
            "Upload Meeting",
            "Meeting History",
            "Ask Your Meetings"
        ],
        label_visibility="visible"
    )

    st.divider()
    st.markdown("### ✨ AI Capabilities")
    st.caption("🎧 Audio Transcription")
    st.caption("🎬 Video Audio Extraction")
    st.caption("📝 Document Processing")
    st.caption("🧠 AI Meeting Summaries")
    st.caption("📌 Action Item Detection")
    st.caption("💬 Interactive Meeting Q&A")

    st.divider()
    st.caption("Powered by Groq AI")

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == "Dashboard":
    meetings = get_meetings()

    st.markdown("""
    <div class="hero">
        <h1>🎙️ MeetingAssist AI</h1>
        <p>Your meetings. Understood, organised and remembered.</p>
        <p>Turn conversations into summaries, decisions and actionable tasks.</p>
    </div>
    """, unsafe_allow_html=True)

    # Calculate live statistics from saved meetings.
    total_meetings = len(meetings)
    total_actions = 0
    total_completed = 0

    for meeting in meetings:
        try:
            data = json.loads(meeting[6] or "{}")
            action_items = data.get("action_items", [])
            total_actions += len(action_items)
            for task in action_items:
                if isinstance(task, dict) and (
                    task.get("completed", False)
                    or str(task.get("status", "")).lower() == "completed"
                ):
                    total_completed += 1
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    pending_tasks = max(total_actions - total_completed, 0)

    # Dashboard cards. Keep the HTML in one unsafe_allow_html block so
    # Streamlit renders the cards instead of displaying the markup as code.
    st.markdown(f"""
    <style>
    .ma-total-card {{
        background: #19263D;
        border: 1px solid #344766;
        border-radius: 16px;
        padding: 14px 17px;
        min-height: 122px;
        box-sizing: border-box;
    }}
    .ma-total-title {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 800;
        line-height: 1.2;
        margin: 0 0 7px 0;
    }}
    .ma-total-number {{
        color: #FFFFFF;
        font-size: 38px;
        font-weight: 800;
        line-height: 1.05;
        margin: 0 0 4px 0;
    }}
    .ma-total-caption {{
        color: #C5D2E8;
        font-size: 14px;
        line-height: 1.25;
        margin: 0;
    }}
    .ma-stats-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 13px;
        margin: 0 0 27px 0;
        align-items: stretch;
    }}
    .ma-stat-card {{
        background: #19263D;
        border: 1px solid #344766;
        border-radius: 16px;
        padding: 14px 17px;
        min-height: 112px;
        box-sizing: border-box;
    }}
    .ma-stat-number {{
        color: #FFFFFF;
        font-size: 34px;
        font-weight: 800;
        line-height: 1.05;
        margin: 5px 0 0 0;
    }}
    .ma-stat-label {{
        color: #C5D2E8;
        font-size: 15px;
        font-weight: 600;
        line-height: 1.25;
        margin: 0;
    }}
    .ma-feature-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 16px;
        margin-top: 8px;
    }}
    .ma-feature-card {{
        background: linear-gradient(135deg, #1b3158, #202a43);
        border: 1px solid #52678f;
        border-radius: 18px;
        padding: 20px 22px;
        min-height: 142px;
        box-sizing: border-box;
    }}
    .ma-feature-title {{
        color: #FFFFFF;
        font-size: 18px;
        font-weight: 750;
        line-height: 1.25;
        margin: 0 0 10px 0;
    }}
    .ma-feature-description {{
        color: #E0E6F5;
        font-size: 14px;
        line-height: 1.5;
        margin: 0;
    }}
    @media (max-width: 760px) {{
        .ma-stats-grid {{ grid-template-columns: 1fr; }}
        .ma-feature-grid {{ grid-template-columns: 1fr; }}
    }}
    </style>

    <div class="ma-stats-grid">
        <div class="ma-total-card">
            <div class="ma-total-title">Total Meetings</div>
            <div class="ma-total-number">{total_meetings}</div>
            <p class="ma-total-caption">Meetings processed</p>
        </div>
        <div class="ma-stat-card">
            <p class="ma-stat-label">Tasks Identified</p>
            <div class="ma-stat-number">{total_actions}</div>
        </div>
        <div class="ma-stat-card">
            <p class="ma-stat-label">Tasks Completed</p>
            <div class="ma-stat-number">{total_completed}</div>
        </div>
        <div class="ma-stat-card">
            <p class="ma-stat-label">Pending Tasks</p>
            <div class="ma-stat-number">{pending_tasks}</div>
        </div>
    </div>

    <div class="section-title">Explore your workspace</div>
    <div class="ma-feature-grid">
        <div class="ma-feature-card">
            <div class="ma-feature-title">📥 Smart Meeting Upload</div>
            <p class="ma-feature-description">Upload audio, video recordings or meeting documents. Get an organised meeting report.</p>
        </div>
        <div class="ma-feature-card">
            <div class="ma-feature-title">📚 Meeting Memory</div>
            <p class="ma-feature-description">Keep a searchable history of your processed meetings in your local database.</p>
        </div>
        <div class="ma-feature-card">
            <div class="ma-feature-title">🧠 AI Meeting Intelligence</div>
            <p class="ma-feature-description">Understand summaries, discussion points, decisions and follow-up tasks.</p>
        </div>
        <div class="ma-feature-card">
            <div class="ma-feature-title">💬 Ask Your Meetings</div>
            <p class="ma-feature-description">Ask questions about saved meeting transcripts and get AI-generated answers.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Add clear breathing room between the four feature cards and this message.
    st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
    st.info("Your meeting workspace is ready. Upload your meeting")


# --------------------------------------------------
# UPLOAD MEETING
# --------------------------------------------------

elif page == "Upload Meeting":
    
        

    st.markdown("""
    <div class="hero">
        <h1>📥 Upload a Meeting</h1>
        <p> Let AI organise the conversation.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Meeting details")

    meeting_title = st.text_input(
        "Meeting title",
        placeholder="Example: Project Planning Meeting"
    )

    st.markdown("### Upload your recording or document")

    uploaded_file = st.file_uploader(
        "Choose an audio, video or text document",
        type=VIDEO_FORMATS + AUDIO_FORMATS + TEXT_FORMATS,
        help="Supported: MP3, WAV, M4A, AAC, MP4, MOV, MKV, AVI, WEBM, PDF, DOCX, TXT, MD, CSV, SRT and VTT."
    )

    if uploaded_file:
        extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

        st.success(f"Selected: {uploaded_file.name}")

        if extension in VIDEO_FORMATS:
            st.info("🎬 Video detected. Its audio will be extracted for transcription.")
        elif extension in AUDIO_FORMATS:
            st.info("🎧 Audio detected. Ready for transcription.")
        else:
            st.info("📝 Document detected. Its text will be analysed.")

        st.caption(
            f"File size: {uploaded_file.size / (1024 * 1024):.2f} MB"
        )

        if uploaded_file.size > 200 * 1024 * 1024:
            st.error("Please upload a file smaller than 200 MB.")

        elif st.button("🚀 Process Meeting with AI", use_container_width=True):

            if not meeting_title.strip():
                st.warning("Please enter a meeting title.")

            else:
                try:
                    with st.spinner("Processing your meeting..."):
                        transcript, source_type = get_transcript(uploaded_file)

                    st.success("Transcript successfully prepared!")

                    with st.spinner("AI is analysing your meeting..."):
                        analysis = analyse_meeting(transcript)

                    save_meeting(
                        meeting_title.strip(),
                        source_type,
                        transcript,
                        analysis
                    )

                    saved_date = datetime.now().strftime("%d %b %Y, %I:%M %p")
                    try:
                        hindsight_saved = retain_meeting_in_hindsight(
                            meeting_title.strip(), saved_date, source_type,
                            transcript, analysis
                        )
                    except Exception as hindsight_error:
                        hindsight_saved = False
                        st.warning(f"Meeting saved locally, but Hindsight memory sync failed: {hindsight_error}")

                    st.session_state["latest_transcript"] = transcript
                    st.session_state["latest_analysis"] = analysis
                    st.session_state["latest_title"] = meeting_title.strip()
                    st.session_state["latest_source"] = source_type
                    st.session_state["latest_date"] = saved_date

                    st.success("Your meeting has been saved successfully!")
                    if hindsight_saved:
                        st.success("🧠 Hindsight: meeting memory retained successfully.")
                    else:
                        st.info("Hindsight is not connected yet. Add its API key to .env to enable long-term memory.")

                except Exception as error:
                    st.error(f"Something went wrong: {error}")

    if "latest_analysis" in st.session_state:
        st.divider()
        st.markdown("## 🎉 Meeting Analysis")

        show_analysis(st.session_state["latest_analysis"])

        with st.expander("📄 View Full Transcript"):
            st.text_area(
                "Transcript",
                st.session_state["latest_transcript"],
                height=300
            )

        pdf_data = create_pdf(
            st.session_state["latest_title"],
            st.session_state["latest_date"],
            st.session_state["latest_source"],
            st.session_state["latest_transcript"],
            st.session_state["latest_analysis"]
        )

        st.download_button(
            "📥 Download Complete Meeting Report (PDF)",
            data=pdf_data,
            file_name="MeetingAssist_Report.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# --------------------------------------------------
# MEETING HISTORY
# --------------------------------------------------

elif page == "Meeting History":

    st.markdown("""
    <div class="hero">
        <h1>📚 Meeting History</h1>
        <p>Your previous meetings, organised in one place.</p>
    </div>
    """, unsafe_allow_html=True)

    meetings = get_meetings()

    if not meetings:
        st.info("No meetings saved yet. Process a meeting to see it here.")

    else:
        search_text = st.text_input(
            "🔍 Search meetings",
            placeholder="Search by meeting title or summary..."
        )

        filtered = [
            m for m in meetings
            if search_text.lower() in (
                str(m[1]) + " " + str(m[5])
            ).lower()
        ]

        st.caption(f"{len(filtered)} meeting(s) found")

        for meeting in filtered:
            with st.expander(
                f"📅 {meeting[1]}  •  {meeting[2]}  •  {meeting[3]}"
            ):
                st.markdown("### Executive Summary")
                st.write(meeting[5])

                try:
                    analysis = json.loads(meeting[6])
                except Exception:
                    analysis = {}

                show_analysis(analysis)

                with st.expander("View transcript"):
                    st.text_area(
                        "Meeting transcript",
                        meeting[4],
                        height=250,
                        key=f"transcript_{meeting[0]}"
                    )

                pdf_data = create_pdf(
                    meeting[1],
                    meeting[2],
                    meeting[3],
                    meeting[4],
                    analysis
                )

                st.download_button(
                    "📥 Download PDF report",
                    data=pdf_data,
                    file_name=f"Meeting_{meeting[0]}_Report.pdf",
                    mime="application/pdf",
                    key=f"pdf_{meeting[0]}"
                )

# --------------------------------------------------
# ASK YOUR MEETINGS
# --------------------------------------------------

elif page == "Ask Your Meetings":

    st.markdown("""
    <div class="hero">
        <h1>💬 Ask Your Meetings</h1>
        <p>Your AI meeting memory. Ask questions and find information
        from previous conversations.</p>
    </div>
    """, unsafe_allow_html=True)

    meetings = get_meetings()

    if not meetings:
        st.info("Process and save a meeting before asking questions.")
    else:
        meeting_options = {
            f"{m[1]} — {m[2]}": m[0]
            for m in meetings
        }

        selected = st.selectbox(
            "Choose a meeting",
            ["All saved meetings"] + list(meeting_options.keys())
        )

        question = st.text_area(
            "Ask a question",
            placeholder=(
                "Example: What decisions were made?\n"
                "Who is responsible for the next task?\n"
                "What was discussed about the project?"
            ),
            height=110
        )

        if st.button("✨ Ask MeetingAssist AI", use_container_width=True):

            if not question.strip():
                st.warning("Please enter a question.")

            else:
                if selected == "All saved meetings":
                    selected_meetings = meetings[:10]
                else:
                    meeting_id = meeting_options[selected]
                    chosen = get_meeting(meeting_id)
                    selected_meetings = [chosen] if chosen else []

                context_parts = []

                for m in selected_meetings:
                    context_parts.append(
                        f"""
                        MEETING: {m[1]}
                        DATE: {m[2]}
                        SUMMARY: {m[5]}
                        TRANSCRIPT:
                        {m[4][:12000]}
                        """
                    )

                context = "\n\n".join(context_parts)

                prompt = f"""
                Answer the user's question using only the meeting
                information below.

                If the answer is not available, clearly say that
                the meeting records do not contain that information.
                Do not invent names, decisions or deadlines.

                MEETING INFORMATION:
                {context}

                USER QUESTION:
                {question}
                """

                try:
                    hindsight = get_hindsight_client()
                    if hindsight is None:
                        st.error(
                            "Hindsight is not connected. Add HINDSIGHT_API_KEY to your .env file "
                            "and install hindsight-client to use long-term meeting memory."
                        )
                    else:
                        # Recall retrieves relevant stored meeting memories; Reflect
                        # reasons across those memories to answer the user's question.
                        memory_query = question
                        if selected != "All saved meetings":
                            selected_title = selected.split(" — ", 1)[0]
                            memory_query = (
                                f"For the meeting titled '{selected_title}', "
                                f"answer this question: {question}"
                            )

                        with st.spinner("Recalling and reasoning over your Hindsight meeting memories..."):
                            recalled = hindsight.recall(
                                bank_id=HINDSIGHT_BANK_ID,
                                query=memory_query,
                                max_tokens=5000,
                                budget="mid"
                            )

                            recalled_text = "\n\n".join(
                                f"- {memory.text}" for memory in recalled.results
                            )

                            answer = hindsight.reflect(
                                bank_id=HINDSIGHT_BANK_ID,
                                query=(
                                    memory_query
                                    + "\nUse only information stored in the meeting memory bank. "
                                    "If the answer is not present, say that the saved meetings do not contain it. "
                                    "Do not invent names, decisions, owners, or deadlines."
                                ),
                                context=(
                                    "User selected: " + selected + "\n"
                                    "Relevant memories returned by Recall:\n"
                                    + (recalled_text if recalled_text else "No matching memories were returned.")
                                )
                            ).text

                        st.markdown("### 🤖 MeetingAssist AI Answer")
                        st.caption("Memory source: Hindsight long-term meeting memory (Recall + Reflect)")
                        st.markdown(answer)

                except Exception as error:
                    st.error(f"Could not get an answer: {error}")

    st.divider()
    st.caption(
        "Answers use Hindsight long-term memories retained from your processed meetings."
    )

# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("---")
st.markdown(
    "<center style='color:#8998bb;'>"
    "🎙️ MeetingAssist AI | Intelligent Meeting Management"
    "</center>",
    unsafe_allow_html=True
)
