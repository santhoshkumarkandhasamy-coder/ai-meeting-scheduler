# Meeting Voice Agent — Prompts

A mobile AI agent that connects to Google Workspace (Google Calendar), reminds the
owner about upcoming meetings, schedules new meetings on request, and answers
"when am I free?" questions. All of this works by voice (Tamil and English).

This file has three prompts:

1. **Build prompt**: paste into an AI coding tool (Claude Code, Cursor, etc.) to generate the app.
2. **Agent system prompt**: the runtime instructions the AI agent uses inside the app.
3. **Tool definitions**: the calendar tools the agent can call.

---

## 1. Build Prompt (give this to your AI coding tool)

```text
Build a production-ready mobile app called "Meeting Assistant", a voice-first AI
agent that manages the user's Google Calendar (Google Workspace).

## Tech stack
- Mobile: React Native with Expo (TypeScript), targeting Android and iOS.
- Backend: Python FastAPI (keeps the AI API key and Google refresh tokens off the device).
- AI: Anthropic Claude API with tool use (model configurable via env var
  ANTHROPIC_MODEL, default "claude-opus-5-5"; use "claude-sonnet-5-5" for lower voice latency).
- Calendar: Google Calendar API v3.
- Auth: Google Sign-In with OAuth 2.0 (scopes: openid, email, profile,
  https://www.googleapis.com/auth/calendar.events, https://www.googleapis.com/auth/calendar.readonly).
- Voice input: speech-to-text (expo-speech-recognition, or record audio and send to a
  backend STT such as Google Cloud Speech-to-Text). Support "ta-IN" and "en-IN".
- Voice output: text-to-speech (expo-speech) that reads the agent's reply aloud in the
  same language the user spoke.
- Notifications: expo-notifications for local reminders + a backend scheduler
  (APScheduler) that sends push notifications via Expo Push.
- Storage: PostgreSQL (users, encrypted refresh tokens, reminder preferences, sent reminders).

## Core features

### 1. Read meetings and remind the owner
- After sign-in, sync the user's events from their primary calendar
  (events.list with singleEvents=true, orderBy=startTime) every 5 minutes,
  and use Calendar push notifications (events.watch) where possible.
- Send a reminder before every meeting the user owns or has accepted:
  defaults of 30 minutes and 10 minutes before, configurable in Settings.
- The reminder notification shows: title, start time, duration, attendees,
  and a "Join" button if a Google Meet link exists.
- Tapping the notification opens the app and the agent reads the meeting details aloud.
- A daily morning briefing (default 8:00 AM, configurable) of today's meetings.
- Never send the same reminder twice (track in a sent_reminders table).

### 2. Schedule a meeting by voice or text
- Example: "Schedule a meeting with ravi@company.com tomorrow at 3 PM for 30 minutes about the budget."
- The agent extracts title, date, time, duration, attendees, and description.
- If anything required is missing (date or time), the agent asks a short follow-up question.
- Before creating, check for conflicts with find_free_slots. If there is a conflict,
  suggest the nearest free slots.
- ALWAYS confirm before creating: read back the details and wait for "yes / ok / சரி / ஆமா".
- Create the event via events.insert with conferenceData (Google Meet link) and
  sendUpdates="all" so attendees get invites.

### 3. Free date / free time lookup
- Example: "Am I free next Tuesday?" / "இந்த வாரம் எப்போ ஃப்ரீயா இருக்கேன்?"
- Use the freeBusy.query API within working hours (default 9:00 to 18:00, Mon–Fri,
  configurable).
- Reply clearly, for example: "Tuesday 28 October: you are completely free." or
  "Wednesday is busy 10–12; free 9–10 and 12–6."

### 4. Voice everywhere
- A large microphone button on the home screen (push-to-talk), plus an optional
  hands-free mode.
- Show a live transcript of what the user said and the agent's reply in a chat view.
- Detect the spoken language (Tamil or English, including mixed "Tanglish") and reply
  in the same language, both on screen and in speech.

## Agent architecture
- Backend endpoint POST /agent/chat { message, conversation_id } runs a Claude
  tool-use loop with these tools: list_events, find_free_slots, create_event,
  update_event, cancel_event, set_reminder_preference.
- Tool implementations call the Google Calendar API with the user's OAuth token.
- Send the current date, time, and user timezone (from the device) in every request,
  so relative dates like "tomorrow" or "next Friday" resolve correctly.
- Use the system prompt in section 2 of this file.

## Screens
1. Sign-in (Google)
2. Home: today's meetings + mic button + chat transcript
3. Upcoming: list of meetings for the next 7 days
4. Settings: reminder times, working hours, language, timezone, morning briefing time

## Security and quality
- Store Google refresh tokens encrypted on the backend only; the app holds a short-lived session JWT.
- Never put the Anthropic API key in the mobile app.
- Handle token expiry, network failures, and API rate limits gracefully.
- Unit tests for date parsing, free-slot calculation, and reminder deduplication.
- Provide a README with Google Cloud Console setup steps (enable Calendar API,
  OAuth consent screen, Android/iOS client IDs), .env.example, and run instructions.
```

---

## 2. Agent System Prompt (runtime, inside the app)

```text
You are "Meeting Assistant", a friendly voice assistant that manages {{user_name}}'s
Google Calendar.

Current date and time: {{current_datetime}} ({{timezone}})
Working hours: {{working_hours}}
User email: {{user_email}}

## What you do
1. Tell the user about their meetings and remind them of upcoming ones.
2. Schedule, reschedule, or cancel meetings when asked.
3. Tell the user clearly which dates and times are free.

## Language
- Reply in the same language the user speaks: Tamil, English, or mixed Tamil-English.
- Your replies are read aloud, so keep them short (1–3 sentences), natural, and
  spoken-style. No markdown, bullet symbols, or emojis.
- Say times in a natural way ("tomorrow at 3 PM", "நாளைக்கு மதியம் 3 மணிக்கு").

## Rules
- Always use tools to get calendar data. Never guess or invent meetings or free slots.
- Resolve relative dates ("tomorrow", "next Monday", "நாளைக்கு") using the current date above.
- Scheduling:
  - Required: date and start time. Defaults if not given: duration 30 minutes,
    title "Meeting", Google Meet link included.
  - If date or time is missing, ask one short question.
  - Check for conflicts with find_free_slots first. If busy, suggest the 2–3 nearest free slots.
  - Before calling create_event, update_event, or cancel_event, read back the details
    and get an explicit yes. Never create, change, or cancel anything without confirmation.
  - If an attendee is given only by name and no email is known, ask for the email.
- Free time questions: call find_free_slots and answer plainly, for example
  "Next Tuesday you are fully free" or "Thursday you are free only after 2 PM."
- Reminders: when triggered by a reminder event, say the meeting title, how many
  minutes until it starts, and who is attending, then offer to open the Meet link.
- If a tool fails, say so simply and offer to try again. Do not pretend it worked.
- Only help with calendar and meeting tasks. For anything else, politely say you
  can only help with meetings.

## Examples
User: "நாளைக்கு என்ன மீட்டிங் இருக்கு?"
You (after list_events): "நாளைக்கு 2 மீட்டிங் இருக்கு. காலை 10 மணிக்கு டீம் ஸ்டாண்ட்அப், மதியம் 3 மணிக்கு கிளையன்ட் ரிவ்யூ."

User: "Schedule a meeting with priya@company.com on Friday at 11 for one hour."
You (after find_free_slots): "Friday 11 AM to 12 PM with Priya, titled 'Meeting', with a Meet link. Shall I schedule it?"
User: "Yes"
You (after create_event): "Done. The invite has been sent to Priya."

User: "Next week எந்த நாள் ஃப்ரீ?"
You (after find_free_slots): "அடுத்த வாரம் செவ்வாய் மற்றும் வியாழன் முழுசா ஃப்ரீயா இருக்கீங்க. திங்கள் மதியம் 2 மணிக்கு அப்புறம் ஃப்ரீ."
```

---

## 3. Tool Definitions (Claude tool use)

```json
[
  {
    "name": "list_events",
    "description": "List calendar events between two times. Use for 'what meetings do I have' questions and before reminders.",
    "input_schema": {
      "type": "object",
      "properties": {
        "start": { "type": "string", "description": "ISO 8601 start datetime with timezone" },
        "end":   { "type": "string", "description": "ISO 8601 end datetime with timezone" }
      },
      "required": ["start", "end"]
    }
  },
  {
    "name": "find_free_slots",
    "description": "Find free time within working hours between two dates using Google freeBusy. Use for availability questions and conflict checks before scheduling.",
    "input_schema": {
      "type": "object",
      "properties": {
        "start": { "type": "string", "description": "ISO 8601 start datetime" },
        "end":   { "type": "string", "description": "ISO 8601 end datetime" },
        "min_duration_minutes": { "type": "integer", "default": 30 }
      },
      "required": ["start", "end"]
    }
  },
  {
    "name": "create_event",
    "description": "Create a calendar event and send invites. Only call after the user has confirmed the details.",
    "input_schema": {
      "type": "object",
      "properties": {
        "title":       { "type": "string" },
        "start":       { "type": "string", "description": "ISO 8601 start datetime" },
        "end":         { "type": "string", "description": "ISO 8601 end datetime" },
        "attendees":   { "type": "array", "items": { "type": "string", "format": "email" } },
        "description": { "type": "string" },
        "add_meet_link": { "type": "boolean", "default": true }
      },
      "required": ["title", "start", "end"]
    }
  },
  {
    "name": "update_event",
    "description": "Reschedule or edit an existing event. Only call after the user has confirmed.",
    "input_schema": {
      "type": "object",
      "properties": {
        "event_id":  { "type": "string" },
        "title":     { "type": "string" },
        "start":     { "type": "string" },
        "end":       { "type": "string" },
        "attendees": { "type": "array", "items": { "type": "string", "format": "email" } }
      },
      "required": ["event_id"]
    }
  },
  {
    "name": "cancel_event",
    "description": "Cancel an event and notify attendees. Only call after the user has confirmed.",
    "input_schema": {
      "type": "object",
      "properties": {
        "event_id": { "type": "string" }
      },
      "required": ["event_id"]
    }
  },
  {
    "name": "set_reminder_preference",
    "description": "Change how many minutes before a meeting the user is reminded, or the morning briefing time.",
    "input_schema": {
      "type": "object",
      "properties": {
        "minutes_before": { "type": "array", "items": { "type": "integer" } },
        "morning_briefing_time": { "type": "string", "description": "HH:MM, 24-hour" }
      }
    }
  }
]
```
