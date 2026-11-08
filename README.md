# 🤖 MeetingAssist AI
### Your Intelligent Assistant for Every Meeting

MeetingAssist AI is an AI-powered meeting assistant that transforms meeting recordings and text into meaningful insights. It helps users understand discussions, summarize important points, identify action items, and retrieve information from past meetings.

## ✨ Key Features

- **Audio Upload:** Upload meeting recordings in supported audio formats.
- **Video Upload:** Process meeting videos and extract their audio for transcription.
- **Text Input:** Enter meeting transcripts or meeting notes directly.
- **AI Transcription:** Uses Groq Whisper to convert speech into text.
- **Smart Summarization:** Generates concise and meaningful meeting summaries.
- **Action Items:** Identifies important tasks and follow-up points.
- **Meeting Insights:** Extracts key decisions, topics, and important information.
- **Ask Your Meetings:** Ask questions about your meeting content and receive AI-generated answers.
- **Hindsight Memory:** Retains useful meeting context to support retrieval across meetings.
- **Meeting History:** Save and revisit previously processed meetings.
- **PDF Reports:** Generate downloadable meeting reports.
- **User Authentication:** Secure signup and login using Supabase.
- **Private Meeting Storage:** Supabase authentication and Row Level Security (RLS) help ensure users can access only their own saved meetings.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Streamlit | Web application interface |
| Groq Whisper | Audio transcription |
| Groq AI | AI-powered meeting analysis |
| Supabase | Authentication and database |
| Hindsight | Long-term meeting memory |
| ReportLab | PDF report generation |

## 📂 Project Structure

```text
MeetingAssist/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd MeetingAssist
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project folder using `.env.example` as a template.

Add your own API credentials:

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_publishable_key
HINDSIGHT_API_KEY=your_hindsight_api_key
HINDSIGHT_API_URL=your_hindsight_api_url
```

**Never upload your actual `.env` file or API credentials to GitHub.**

### 5. Run the application

```bash
python -m streamlit run app.py
```

The application will open in your browser.

## 🔐 Privacy and Security

MeetingAssist AI uses Supabase Authentication and Row Level Security (RLS) to separate users' saved meeting records.

- Users can create individual accounts.
- Authentication is handled through Supabase.
- Database policies restrict access to records belonging to the authenticated user.
- API credentials are stored in environment variables or deployment secrets.

## 🚀 Deployment

The application can be deployed using Streamlit Community Cloud.

1. Push the project files to GitHub.
2. Connect the repository to Streamlit Community Cloud.
3. Select `app.py` as the main application file.
4. Configure the required API credentials under Streamlit Secrets.
5. Deploy the application.

## 💡 Example Use Case

Imagine a team conducting a project discussion.

Instead of manually reviewing the entire recording, users can upload the meeting video or audio to MeetingAssist AI.

The application can then:

1. Convert the conversation into text.
2. Generate a meeting summary.
3. Identify decisions and action items.
4. Answer questions about the discussion.
5. Retain useful context through Hindsight for future reference.

## 🎯 Project Goal

The goal of MeetingAssist AI is to make meetings more productive by reducing manual note-taking, simplifying information retrieval, and helping users turn conversations into actionable insights.

---

**MeetingAssist AI — Making Every Meeting More Meaningful.**
