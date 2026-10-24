# AI Meeting Scheduler

A voice-first mobile assistant for Google Calendar (Google Workspace). It works in Tamil and English.

- **Reminders.** It reads your meetings and sends a push notification before each one (30 and 10 minutes by default). It also sends a morning briefing with the day's meetings. Tap a notification to hear it read aloud.
- **Schedule by voice.** Say "Schedule a meeting with ravi@company.com tomorrow at 3 PM for 30 minutes". The assistant checks for clashes and reads the details back. After you say yes, it creates the event with a Google Meet link and sends the invites.
- **Free-time answers.** Ask "அடுத்த வாரம் எந்த நாள் ஃப்ரீ?" or "Am I free on Tuesday?" and it tells you which days or times are free, within your working hours.
- **Voice everywhere.** Push-to-talk speech recognition (`ta-IN` / `en-IN`). Replies are spoken back in the language you used.

```
mobile/   Expo (React Native, TypeScript) app: Android and iOS
backend/  FastAPI service: Claude agent, Google Calendar, reminder scheduler
docs/     Prompts used to design the agent
```

## How it works

```
 Phone (Expo app)                       Backend (FastAPI)                     External
 ───────────────                        ─────────────────                     ────────
 Google Sign-In ── serverAuthCode ───▶  /auth/google ── exchange code ─────▶  Google OAuth
                                        stores encrypted refresh token
 Mic → speech-to-text ── text ──────▶  /agent/chat ── tool-use loop ──────▶  Claude API
 Text-to-speech ◀── reply ───────────   │   list_events / find_free_slots
                                        └── create / update / cancel ──────▶  Google Calendar
 Push notification ◀──────────────────  Reminder job (every minute) ───────▶  Expo Push
```

- The Claude API key and Google refresh tokens stay on the backend. The phone holds only a session token in the secure store.
- The agent must read the details back and get a "yes" before it creates, changes or cancels a meeting. The tools also refuse to run unless `user_confirmed` is true.
- Free time is calculated with Google's free/busy API inside your working hours. You set those hours in Settings.

## 1. Google Cloud setup

1. Create a project at <https://console.cloud.google.com> and enable the **Google Calendar API**.
2. Configure the **OAuth consent screen**. Add the scopes `.../auth/calendar.events` and `.../auth/calendar.readonly`. While the app is in testing, add your Google account as a test user.
3. Under **Credentials**, create these OAuth client IDs:
   - **Web application**. Its client ID and secret go in `backend/.env`. The same client ID goes in `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`.
   - **Android**. Use package `com.example.meetingassistant` (or your own) and the SHA-1 of your signing key. Get the SHA-1 from `npx eas-cli credentials` or `keytool`.
   - **iOS** (optional). Use bundle ID `com.example.meetingassistant`. Put its client ID in `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`. Put its reversed client ID in `app.json` under `iosUrlScheme`.

## 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # fill in ANTHROPIC_API_KEY, GOOGLE_*, JWT_SECRET, TOKEN_ENCRYPTION_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
pytest                  # unit tests
```

Or use Docker with Postgres: `docker compose up --build`. Run it from the repo root after you create `backend/.env`.

To run in production, deploy the backend anywhere that serves HTTPS, such as Cloud Run, Render or Railway. Run one worker, because the reminder scheduler runs inside the API process.

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/google` | Exchange the Google `serverAuthCode` for a session token |
| GET | `/me` | Current user and settings |
| PUT | `/me/settings` | Reminder minutes, working hours, language, timezone, morning briefing |
| POST | `/me/push-token` | Register the device's Expo push token |
| GET | `/events/upcoming?days=7` | Upcoming meetings |
| POST | `/agent/chat` | `{message, conversation_id?}` → `{conversation_id, reply}` |

## 3. Mobile app

The app uses native modules for Google Sign-In and speech recognition, so it needs a **development build**. Expo Go will not work.

```bash
cd mobile
npm install
cp .env.example .env    # EXPO_PUBLIC_API_URL must be reachable from the phone (LAN IP or HTTPS URL)

# Option A: build in the cloud (no Android Studio / Xcode needed)
npx eas-cli@latest build --profile development --platform android
# Option B: build locally
npx expo run:android    # or: npx expo run:ios

npx expo start          # then open the installed dev build
```

Push reminders need a physical device. For remote push on Android, set up FCM credentials with `npx eas-cli credentials`. For an installable APK to share, run `npx eas-cli build --profile preview --platform android`.

Checks: `npx tsc --noEmit` and `npx expo lint`.

## Things to say

| Tamil | English |
|---|---|
| நாளைக்கு என்ன மீட்டிங் இருக்கு? | What meetings do I have tomorrow? |
| வெள்ளிக்கிழமை 11 மணிக்கு priya@company.com கூட ஒரு மணி நேரம் மீட்டிங் வை | Schedule a one-hour meeting with priya@company.com on Friday at 11 |
| அடுத்த வாரம் எந்த நாள் ஃப்ரீ? | Which days am I free next week? |
| 3 மணி மீட்டிங்கை 4 மணிக்கு மாத்து | Move my 3 PM meeting to 4 PM |
| 15 நிமிஷம் முன்னாடி ரிமைண்ட் பண்ணு | Remind me 15 minutes before meetings |

## Configuration notes

- **Model.** Set it with `ANTHROPIC_MODEL` (default `claude-opus-5-5`). Effort is `ANTHROPIC_EFFORT=low` so spoken replies come back quickly.
- **Refusal fallback.** Requests use Claude's server-side fallback (`fallbacks: "default"`). If the model declines a request, the API retries it on a suitable model inside the same call. To turn this off, remove `betas` and `fallbacks` from `backend/app/agent/runner.py`.
- **Prompt caching.** The system prompt and tools never change for a user, so they are cached. The current date and time are added to each user message instead.
