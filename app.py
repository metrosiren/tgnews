"""
Telegram Group Monitor — Live Message Feed  (v2)

Features:
  • Live SSE-streamed messages from monitored Telegram groups
  • OpenAI GPT-4o severity rating: Noise / Low / Medium / High / Critical
  • Pushover push-notifications (optional, toggle from UI settings)
  • Telegram-style message bubbles with **bold** support
  • Settings panel persisted to settings.json

Setup:
  1. Get api_id + api_hash from https://my.telegram.org
  2. Put them in  .env  next to this file
  3. pip install flask telethon python-dotenv openai httpx
  4. python app.py          (first run asks for phone number in terminal)
  5. Open http://localhost:5050
"""

import os, json, asyncio, threading, time, re, httpx
from pathlib import Path
from datetime import datetime, timezone
from collections import deque

from flask import Flask, request, jsonify, Response, render_template_string
from dotenv import load_dotenv

# ── Env ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
SETTINGS_FILE = BASE_DIR / "settings.json"
load_dotenv(ENV_FILE)

API_ID       = os.getenv("TELEGRAM_API_ID", "")
API_HASH     = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME = os.getenv("TELEGRAM_SESSION", "tg_session")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

# ── Flask ───────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Shared state ────────────────────────────────────────────────────
monitored_groups: dict = {}
global_feed: deque     = deque(maxlen=5000)
lock                   = threading.Lock()
sse_subscribers: list  = []

tg_client = None
tg_loop   = None

# ── Settings (loaded from disk) ─────────────────────────────────────
DEFAULT_SETTINGS = {
    "pushover_enabled": False,
    "pushover_app_token": "",
    "pushover_user_key": "",
    "openai_api_key": OPENAI_KEY,
    "notify_min_severity": "Medium",
    "severity_instructions": "",
    "instruction_presets": [],
    "channel_presets": [
        {"name": "Geopolitics", "links": [
            "https://t.me/BBCWorldoffl",
            "https://t.me/GeoPWatch",
            "https://t.me/aljazeeraglobal",
            "https://t.me/Middle_East_Spectator"
        ]}
    ],
}

def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                saved = json.load(f)
            # saved values override defaults (shallow is fine — all values are top-level)
            merged = {**DEFAULT_SETTINGS, **saved}
            # Always prefer the .env key — the saved key may be stale
            if OPENAI_KEY:
                merged["openai_api_key"] = OPENAI_KEY
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def _reload_settings():
    """Re-read settings.json from disk into the global settings dict.
    This ensures hand-edits to the file are always picked up."""
    global settings
    fresh = _load_settings()
    settings.clear()
    settings.update(fresh)

def _save_settings(s: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

settings = _load_settings()


# ══════════════════════════════════════════════════════════════════════
#                         OPENAI RATING
# ══════════════════════════════════════════════════════════════════════

SEVERITY_LEVELS = ["Noise", "Low", "Medium", "High", "Critical"]

_RATING_PROMPT = """You are a news severity classifier for a geopolitical / financial news monitoring dashboard.

Given a Telegram message, classify it into EXACTLY ONE of these severity levels:
- **Noise**: Not news. Opinions, commentary, jokes, chatter, reactions, or off-topic content.
- **Low**: Minor news with little immediate impact.
- **Medium**: Noteworthy news — policy changes, diplomatic moves, moderate events.
- **High**: Major breaking news — military actions, significant geopolitical shifts, major economic events.
- **Critical**: Extreme urgency — active military escalation, large-scale attacks, existential threats, emergency declarations.

Also determine if this is an actual news event report (is_news=true) or just commentary/opinion/reaction (is_news=false).

Respond ONLY with valid JSON, no markdown fences:
{"severity": "<level>", "is_news": true/false}"""


def _rate_message(text: str) -> dict:
    """Call OpenAI GPT-4o to rate severity. Returns {severity, is_news}."""
    api_key = settings.get("openai_api_key", "")
    if not api_key:
        return {"severity": "Low", "is_news": True}
    # Build prompt — append user's custom instructions if provided
    prompt = _RATING_PROMPT
    custom = settings.get("severity_instructions", "").strip()
    if custom:
        prompt += f"\n\nAdditional user instructions for rating:\n{custom}"
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o",
                "temperature": 0.1,
                "max_tokens": 60,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:1500]},
                ],
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            err_msg = data["error"].get("message", data["error"])
            print(f"[OpenAI] API error: {err_msg}")
            return {"severity": "Low", "is_news": True}
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```json\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        result = json.loads(content)
        sev = result.get("severity", "Low")
        if sev not in SEVERITY_LEVELS:
            sev = "Low"
        return {"severity": sev, "is_news": bool(result.get("is_news", True))}
    except Exception as e:
        print(f"[OpenAI] Rating error: {e}")
        return {"severity": "Low", "is_news": True}


# ══════════════════════════════════════════════════════════════════════
#                          PUSHOVER
# ══════════════════════════════════════════════════════════════════════

SEVERITY_PUSHOVER_PRIORITY = {
    "Noise": -2, "Low": -1, "Medium": 0, "High": 1, "Critical": 2,
}

def _should_notify(severity: str, is_news: bool) -> bool:
    if not is_news:
        return False
    if not settings.get("pushover_enabled"):
        return False
    if not settings.get("pushover_app_token") or not settings.get("pushover_user_key"):
        return False
    min_sev = settings.get("notify_min_severity", "Medium")
    min_idx = SEVERITY_LEVELS.index(min_sev) if min_sev in SEVERITY_LEVELS else 2
    cur_idx = SEVERITY_LEVELS.index(severity) if severity in SEVERITY_LEVELS else 1
    return cur_idx >= min_idx

def _send_pushover(title: str, body: str, severity: str):
    try:
        priority = SEVERITY_PUSHOVER_PRIORITY.get(severity, 0)
        payload = {
            "token": settings["pushover_app_token"],
            "user":  settings["pushover_user_key"],
            "title": f"[{severity}] {title}",
            "message": body[:1024],
            "priority": priority,
            "sound": "cosmic" if priority >= 1 else "pushover",
        }
        if priority == 2:
            payload["retry"] = 60
            payload["expire"] = 600
        httpx.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
    except Exception as e:
        print(f"[Pushover] Error: {e}")


# ══════════════════════════════════════════════════════════════════════
#                        TELEGRAM LAYER
# ══════════════════════════════════════════════════════════════════════

def _parse_group_input(raw: str):
    raw = raw.strip()
    m = re.match(r"https?://t\.me/\+?([\w\-]+)", raw)
    if m:
        path = raw.split("t.me/")[1]
        return path
    if raw.startswith("@"):
        return raw[1:]
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


async def _resolve_entity(client, identifier):
    from telethon import functions
    if isinstance(identifier, str) and identifier.startswith("+"):
        try:
            updates = await client(functions.messages.ImportChatInviteRequest(identifier[1:]))
            return updates.chats[0]
        except Exception:
            pass
    return await client.get_entity(identifier)


# Map Telethon event chat_id → our canonical group id
_chatid_to_gid: dict = {}

async def _add_group(identifier_raw: str) -> dict:
    global tg_client
    if tg_client is None:
        raise RuntimeError("Telegram client not connected yet.")

    identifier = _parse_group_input(identifier_raw)
    entity = await _resolve_entity(tg_client, identifier)
    eid = entity.id
    title = getattr(entity, "title", None) or getattr(entity, "first_name", str(eid))

    # Telethon events report chat_id as the "full" id (negative for channels)
    # whereas entity.id is always positive. Compute the event-facing id.
    from telethon.utils import get_peer_id
    try:
        peer_id = get_peer_id(entity)
    except Exception:
        peer_id = eid

    with lock:
        if eid in monitored_groups:
            return {"id": eid, "name": title, "already": True}
        monitored_groups[eid] = {"name": title, "messages": deque(maxlen=1000)}
        _chatid_to_gid[peer_id] = eid
        _chatid_to_gid[eid] = eid       # also map positive id

    # Fetch history
    msgs = []
    async for msg in tg_client.iter_messages(entity, limit=15):
        m = _msg_to_dict(msg, title)
        if m:
            msgs.append(m)
    msgs.reverse()

    # Rate history in background thread
    def _rate_batch():
        for m in msgs:
            r = _rate_message(m["text"])
            m["severity"] = r["severity"]
            m["is_news"]  = r["is_news"]
            _broadcast({"_update": True, "id": m["id"], "group_id": m["group_id"],
                         "severity": m["severity"], "is_news": m["is_news"]})
    threading.Thread(target=_rate_batch, daemon=True).start()

    with lock:
        for m in msgs:
            m["group_id"] = eid          # normalise to positive entity id
            monitored_groups[eid]["messages"].append(m)
            global_feed.append(m)
    for m in msgs:
        _broadcast(m)

    return {"id": eid, "name": title, "already": False, "history_count": len(msgs)}


async def _remove_group(eid: int):
    with lock:
        monitored_groups.pop(eid, None)


# Regex to strip decorative emoji that look broken outside Telegram
_EMOJI_STRIP_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"   # Regional indicator symbols (flags like \U0001F1F1\U0001F1E7)
    "\U0001F3F4"               # Black flag / sub-region flag base
    "\U000E0061-\U000E007A"   # Tag characters used in sub-region flags
    "\U000E007F"               # Cancel tag
    "\u2600-\u26FF"            # Misc symbols (\u26A1 lightning etc)
    "\u2700-\u27BF"            # Dingbats
    "\U0001F300-\U0001F5FF"   # Misc symbols & pictographs
    "\U0001F680-\U0001F6FF"   # Transport & map symbols
    "\U0001F900-\U0001F9FF"   # Supplemental symbols
    "\U0001FA00-\U0001FA6F"   # Chess, extended-A
    "\U0001FA70-\U0001FAFF"   # Extended-B
    "\U00002702-\U000027B0"   # Dingbats
    "\U0000FE00-\U0000FE0F"   # Variation selectors
    "\U0000200D"               # Zero-width joiner
    "\U0000203C-\U00003299"   # CJK / enclosed / misc
    "]+"
)

def _clean_text(text: str) -> str:
    """Remove decorative emoji / flag sequences that look broken outside Telegram."""
    text = _EMOJI_STRIP_RE.sub("", text)
    # Collapse multiple spaces / leading-trailing whitespace per line
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _apply_entities(raw: str, entities) -> str:
    """Apply Telethon entities to raw_text and return HTML.

    CRITICAL: offsets only work on the *exact* original raw_text.
    We must not modify the string before applying offsets.
    """
    if not entities:
        return _html_escape(raw)

    from telethon.tl.types import (
        MessageEntityBold, MessageEntityItalic, MessageEntityCode,
        MessageEntityPre, MessageEntityStrike, MessageEntityUnderline,
        MessageEntitySpoiler, MessageEntityUrl, MessageEntityTextUrl,
        MessageEntityMention, MessageEntityMentionName,
    )

    # Build a list of (offset, length, open_tag, close_tag) — sorted by offset
    tags: list[tuple[int, int, str, str]] = []
    for ent in entities:
        o, l = ent.offset, ent.length
        if isinstance(ent, MessageEntityBold):
            tags.append((o, l, "<b>", "</b>"))
        elif isinstance(ent, MessageEntityItalic):
            tags.append((o, l, "<i>", "</i>"))
        elif isinstance(ent, MessageEntityCode):
            tags.append((o, l, "<code>", "</code>"))
        elif isinstance(ent, MessageEntityPre):
            tags.append((o, l, "<pre>", "</pre>"))
        elif isinstance(ent, MessageEntityStrike):
            tags.append((o, l, "<s>", "</s>"))
        elif isinstance(ent, MessageEntityUnderline):
            tags.append((o, l, "<u>", "</u>"))
        elif isinstance(ent, MessageEntitySpoiler):
            tags.append((o, l, '<span class="spoiler">', "</span>"))
        elif isinstance(ent, MessageEntityTextUrl):
            url = _html_escape(ent.url or "")
            tags.append((o, l, f'<a href="{url}" target="_blank" rel="noopener">', "</a>"))
        elif isinstance(ent, MessageEntityUrl):
            # The URL is the text itself — we'll wrap it in an <a> tag
            url_text = raw[o:o + l]
            safe_url = _html_escape(url_text)
            tags.append((o, l, f'<a href="{safe_url}" target="_blank" rel="noopener">', "</a>"))
        elif isinstance(ent, MessageEntityMention):
            # @username — link to t.me/username
            mention = raw[o:o + l].lstrip("@")
            tags.append((o, l, f'<a href="https://t.me/{_html_escape(mention)}" target="_blank" rel="noopener">', "</a>"))
        elif isinstance(ent, MessageEntityMentionName):
            tags.append((o, l, "<b>", "</b>"))  # Can't link by ID in browser

    if not tags:
        return _html_escape(raw)

    # Sort by offset; process from end to start so earlier offsets stay valid
    tags.sort(key=lambda t: t[0], reverse=True)

    # We work on a list of *characters* from the raw string,
    # HTML-escaping each segment between tags.
    # Strategy: split raw into segments, escape each, then insert tags.
    result_parts: list[str] = []
    end_cursor = len(raw)

    # Process tags from rightmost to leftmost
    # We'll build the result right-to-left then reverse
    pieces: list[str] = []  # collected right-to-left

    for offset, length, open_tag, close_tag in tags:
        ent_end = offset + length
        # Text AFTER this entity up to current cursor
        if ent_end < end_cursor:
            pieces.append(_html_escape(raw[ent_end:end_cursor]))
        # The entity itself
        pieces.append(close_tag)
        pieces.append(_html_escape(raw[offset:ent_end]))
        pieces.append(open_tag)
        end_cursor = offset

    # Remaining text before the first entity
    if end_cursor > 0:
        pieces.append(_html_escape(raw[0:end_cursor]))

    pieces.reverse()
    return "".join(pieces)


def _msg_to_dict(msg, group_name: str = "") -> dict | None:
    if msg is None:
        return None
    sender = ""
    if msg.sender:
        sender = getattr(msg.sender, "first_name", "") or ""
        last = getattr(msg.sender, "last_name", "") or ""
        if last:
            sender += f" {last}"
        if not sender:
            sender = getattr(msg.sender, "title", "") or str(msg.sender_id)

    raw = msg.raw_text or ""

    # 'html' is for display — entities applied on the EXACT raw_text
    html = _apply_entities(raw, msg.entities) if raw else ""

    # 'text' is for AI rating + search — clean plain text, no HTML
    text = _clean_text(raw)

    if msg.media and not text:
        text = f"[Media: {type(msg.media).__name__}]"
        html = html or _html_escape(text)
    if not text:
        return None

    return {
        "id": msg.id,
        "group_id": msg.chat_id,
        "group": group_name,
        "sender": sender,
        "text": text,
        "html": html,
        "date": msg.date.astimezone(timezone.utc).isoformat(),
        "ts": msg.date.timestamp(),
        "severity": None,
        "is_news": None,
    }


def _broadcast(msg_dict: dict):
    data = json.dumps(msg_dict)
    dead = []
    for q in sse_subscribers:
        try:
            q.append(data)
        except Exception:
            dead.append(q)
    for q in dead:
        sse_subscribers.remove(q)


def _process_new_message(m: dict):
    """Rate via AI + send Pushover if warranted. Runs in background thread."""
    r = _rate_message(m["text"])
    m["severity"] = r["severity"]
    m["is_news"]  = r["is_news"]
    _broadcast({"_update": True, "id": m["id"], "group_id": m["group_id"],
                "severity": m["severity"], "is_news": m["is_news"]})
    if _should_notify(m["severity"], m["is_news"]):
        _send_pushover(m["group"], m["text"][:400], m["severity"])


def _telethon_thread():
    global tg_client, tg_loop
    from telethon import TelegramClient, events

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tg_loop = loop

    client = TelegramClient(
        str(BASE_DIR / SESSION_NAME), int(API_ID), API_HASH, loop=loop,
    )

    async def main():
        global tg_client
        await client.start()
        tg_client = client
        print("[Telegram] ✓ Connected as", (await client.get_me()).first_name)

        @client.on(events.NewMessage)
        async def handler(event):
            cid = event.chat_id
            with lock:
                gid = _chatid_to_gid.get(cid)
                grp = monitored_groups.get(gid) if gid else None
            if grp is None:
                return
            m = _msg_to_dict(event.message, grp["name"])
            if m is None:
                return
            # Normalize group_id to our canonical eid
            m["group_id"] = gid
            with lock:
                grp["messages"].append(m)
                global_feed.append(m)
            _broadcast(m)
            threading.Thread(target=_process_new_message, args=(m,), daemon=True).start()

        print("[Telegram] Listening for new messages…")
        await client.run_until_disconnected()

    loop.run_until_complete(main())


# ══════════════════════════════════════════════════════════════════════
#                         FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/api/groups", methods=["GET"])
def list_groups():
    with lock:
        out = [{"id": gid, "name": g["name"]} for gid, g in monitored_groups.items()]
    return jsonify(out)

@app.route("/api/groups", methods=["POST"])
def add_group_route():
    data = request.get_json(force=True)
    raw = data.get("group", "").strip()
    if not raw:
        return jsonify({"error": "group is required"}), 400
    future = asyncio.run_coroutine_threadsafe(_add_group(raw), tg_loop)
    try:
        return jsonify(future.result(timeout=30))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/groups/<int:gid>", methods=["DELETE"])
def remove_group_route(gid):
    asyncio.run_coroutine_threadsafe(_remove_group(gid), tg_loop)
    return jsonify({"ok": True})

@app.route("/api/messages")
def get_messages():
    limit = int(request.args.get("limit", 200))
    with lock:
        msgs = list(global_feed)[-limit:]
    return jsonify(msgs)

@app.route("/api/stream")
def stream():
    q: deque = deque(maxlen=500)
    sse_subscribers.append(q)
    def generate():
        try:
            while True:
                while q:
                    yield f"data: {q.popleft()}\n\n"
                time.sleep(0.25)
        except GeneratorExit:
            pass
        finally:
            if q in sse_subscribers:
                sse_subscribers.remove(q)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Channel Presets API ──────────────────────────────────────────────
@app.route("/api/channel-presets", methods=["GET"])
def list_channel_presets():
    _reload_settings()
    return jsonify(settings.get("channel_presets", []))

@app.route("/api/channel-presets", methods=["POST"])
def save_channel_preset():
    _reload_settings()
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    links = data.get("links", [])
    if not name:
        return jsonify({"error": "name is required"}), 400
    presets = settings.get("channel_presets", [])
    for p in presets:
        if p["name"] == name:
            p["links"] = links
            break
    else:
        presets.append({"name": name, "links": links})
    settings["channel_presets"] = presets
    _save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/channel-presets/<name>", methods=["DELETE"])
def delete_channel_preset(name):
    _reload_settings()
    presets = settings.get("channel_presets", [])
    settings["channel_presets"] = [p for p in presets if p["name"] != name]
    _save_settings(settings)
    return jsonify({"ok": True})

# ── Settings API ────────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
def get_settings():
    _reload_settings()
    return jsonify(dict(settings))

@app.route("/api/settings", methods=["POST"])
def update_settings():
    _reload_settings()
    data = request.get_json(force=True)
    for key in DEFAULT_SETTINGS:
        if key in data:
            settings[key] = data[key]
    _save_settings(settings)
    return jsonify({"ok": True})


# ── Instruction Presets API ──────────────────────────────────────────
@app.route("/api/instruction-presets", methods=["GET"])
def list_instruction_presets():
    _reload_settings()
    return jsonify(settings.get("instruction_presets", []))

@app.route("/api/instruction-presets", methods=["POST"])
def save_instruction_preset():
    _reload_settings()
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    text = data.get("text", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    presets = settings.get("instruction_presets", [])
    # Update existing or append new
    for p in presets:
        if p["name"] == name:
            p["text"] = text
            break
    else:
        presets.append({"name": name, "text": text})
    settings["instruction_presets"] = presets
    _save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/instruction-presets/<name>", methods=["DELETE"])
def delete_instruction_preset(name):
    _reload_settings()
    presets = settings.get("instruction_presets", [])
    settings["instruction_presets"] = [p for p in presets if p["name"] != name]
    _save_settings(settings)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════
#                         HTML  TEMPLATE
# ══════════════════════════════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Telegram Monitor</title>
<style>
/* ─── VARIABLES ────────────────────────────────────────────── */
:root {
  --bg: #0e1621;
  --surface: #17212b;
  --surface2: #1e2c3a;
  --surface3: #242f3d;
  --border: #0e1621;
  --text: #f5f5f5;
  --text2: #708499;
  --accent: #6ab2f2;
  --accent-h: #8ac4ff;
  --green: #4fae4e;
  --red: #e05d56;
  --orange: #e09b40;
  --bubble: #182533;
  --sev-noise: #556575;
  --sev-low: #4fae4e;
  --sev-med: #e09b40;
  --sev-high: #e0823e;
  --sev-crit: #e05d56;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* ─── LAYOUT ───────────────────────────────────────────────── */
.app{display:grid;grid-template-columns:320px 1fr;grid-template-rows:52px 1fr;height:100vh}

/* ─── HEADER ───────────────────────────────────────────────── */
header{grid-column:1/-1;background:var(--surface);border-bottom:none;display:flex;align-items:center;padding:0 18px;gap:11px}
header .logo{width:28px;height:28px;background:var(--accent);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:15px}
header h1{font-size:15px;font-weight:600;letter-spacing:-.3px}
header .spacer{flex:1}
header .status{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text2)}
header .dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s ease-in-out infinite}
header .status.disconnected .dot{background:var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.settings-btn{background:none;border:none;color:var(--text2);cursor:pointer;font-size:18px;padding:4px 7px;border-radius:6px;transition:all .12s;display:flex;align-items:center}
.settings-btn:hover{color:var(--text);background:var(--surface2)}

/* ─── SIDEBAR ──────────────────────────────────────────────── */
.sidebar{background:var(--surface);border-right:none;display:flex;flex-direction:column;overflow:hidden}
.sidebar-header{padding:10px 12px;background:var(--surface)}
.sidebar-header h2{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.7px;color:var(--text2);margin-bottom:8px}
.add-group{display:flex;gap:5px}
.add-group input{flex:1;background:var(--bg);border:1px solid transparent;border-radius:20px;padding:7px 14px;color:var(--text);font-size:12px;outline:none;transition:border-color .15s}
.add-group input:focus{border-color:var(--accent)}
.add-group input::placeholder{color:var(--text2)}
.add-group button{background:var(--accent);color:#fff;border:none;border-radius:20px;padding:7px 14px;font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;transition:background .12s}
.add-group button:hover{background:var(--accent-h)}
.add-group button:disabled{opacity:.5;cursor:not-allowed}
.input-hint{font-size:9px;color:var(--text2);margin-top:4px;line-height:1.4;padding-left:4px}
.preset-row{display:flex;gap:4px;margin-top:6px}
.preset-row select{flex:1;background:var(--bg);border:1px solid transparent;border-radius:20px;padding:6px 12px;color:var(--text);font-size:11px;outline:none;font-family:inherit;cursor:pointer}
.preset-row select:focus{border-color:var(--accent)}
.preset-row button{background:var(--accent);color:#fff;border:none;border-radius:20px;padding:5px 12px;font-size:10px;font-weight:600;cursor:pointer;white-space:nowrap;transition:opacity .12s}
.preset-row button:hover{opacity:.85}
.preset-row button:disabled{opacity:.4;cursor:not-allowed}
.preset-row button.danger{background:var(--red);padding:5px 9px;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center}
.preset-row button.danger:hover{opacity:.9}
.group-list{flex:1;overflow-y:auto;padding:4px 0}
.group-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:0;cursor:pointer;transition:background .12s}
.group-item:hover{background:var(--surface2)}
.group-item.selected{background:var(--accent);background:rgba(106,178,242,.22)}
.group-item .avatar{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#fff;flex-shrink:0}
.group-item .info{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}
.group-item .info .top-row{display:flex;align-items:baseline;gap:6px}
.group-item .info .name{font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.group-item .info .count{font-size:11.5px;color:var(--text2);white-space:nowrap}
.group-item .info .preview{font-size:12px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.group-item .remove{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:none;border:none;color:var(--text2);cursor:pointer;font-size:11px;opacity:0;transition:all .1s;flex-shrink:0}
.group-item:hover .remove{opacity:1}
.group-item .remove:hover{background:rgba(224,93,86,.15);color:var(--red)}
.no-groups{text-align:center;padding:30px 14px;color:var(--text2);font-size:11px;line-height:1.5}

/* ─── FEED ─────────────────────────────────────────────────── */
.feed{display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.feed-toolbar{padding:8px 16px;border-bottom:none;display:flex;align-items:center;gap:8px;background:var(--surface);flex-wrap:wrap}
.feed-toolbar h2{font-size:14px;font-weight:600}
.msg-count{margin-left:auto;font-size:10px;color:var(--text2);background:var(--surface2);padding:2px 9px;border-radius:9px}
.filter-input{background:var(--bg);border:1px solid var(--border);border-radius:5px;padding:4px 9px;color:var(--text);font-size:11px;outline:none;width:170px;transition:border-color .15s}
.filter-input:focus{border-color:var(--accent)}
.filter-input::placeholder{color:var(--text2)}

/* severity filter pills */
.sev-filters{display:flex;gap:3px}
.sev-pill{font-size:9px;font-weight:700;padding:2px 7px;border-radius:9px;cursor:pointer;border:1px solid transparent;transition:all .12s;text-transform:uppercase;letter-spacing:.3px;opacity:.4;user-select:none}
.sev-pill.active{opacity:1}
.sev-pill[data-sev="all"]{color:var(--text2);border-color:var(--text2)}
.sev-pill.active[data-sev="all"]{background:rgba(139,148,158,.12)}
.sev-pill[data-sev="Noise"]{color:var(--sev-noise);border-color:var(--sev-noise)}
.sev-pill.active[data-sev="Noise"]{background:rgba(85,93,107,.15)}
.sev-pill[data-sev="Low"]{color:var(--sev-low);border-color:var(--sev-low)}
.sev-pill.active[data-sev="Low"]{background:rgba(63,185,80,.1)}
.sev-pill[data-sev="Medium"]{color:var(--sev-med);border-color:var(--sev-med)}
.sev-pill.active[data-sev="Medium"]{background:rgba(210,153,34,.1)}
.sev-pill[data-sev="High"]{color:var(--sev-high);border-color:var(--sev-high)}
.sev-pill.active[data-sev="High"]{background:rgba(240,136,62,.12)}
.sev-pill[data-sev="Critical"]{color:var(--sev-crit);border-color:var(--sev-crit)}
.sev-pill.active[data-sev="Critical"]{background:rgba(248,81,73,.1)}

.messages{flex:1;overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:4px;background:#0e1621}

/* ─── TELEGRAM-STYLE BUBBLE ────────────────────────────────── */
.msg{
  background:#182533;
  border-radius:12px;
  padding:7px 12px 6px;
  max-width:620px;
  animation:fadeIn .15s ease-out;
  position:relative;
  transition:background .1s;
}
.msg:hover{background:#1e2f42}
@keyframes fadeIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}

.msg-head{display:flex;align-items:baseline;gap:8px;margin-bottom:2px}
.msg-group-name{font-size:13px;font-weight:600}
.msg-sender-name{font-size:11.5px;font-weight:500;color:var(--text2)}
.msg-sev-badge{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:1px 5px;border-radius:3px;margin-left:auto;white-space:nowrap}
.msg-sev-badge.loading{color:var(--text2);background:rgba(139,148,158,.15)}
.msg-sev-badge[data-sev="Noise"]{color:#777;background:rgba(85,93,107,.18)}
.msg-sev-badge[data-sev="Low"]{color:var(--sev-low);background:rgba(63,185,80,.1)}
.msg-sev-badge[data-sev="Medium"]{color:var(--sev-med);background:rgba(210,153,34,.1)}
.msg-sev-badge[data-sev="High"]{color:var(--sev-high);background:rgba(240,136,62,.13)}
.msg-sev-badge[data-sev="Critical"]{color:var(--sev-crit);background:rgba(248,81,73,.13)}

.msg-body{font-size:13.5px;line-height:1.55;color:var(--text);word-break:break-word;white-space:pre-wrap}
.msg-body b,.msg-body strong{font-weight:700;color:#fff}
.msg-body a{color:#6ab2f2;text-decoration:none}
.msg-body a:hover{text-decoration:underline}
.msg-body .quote{border-left:2px solid #6ab2f2;padding:3px 8px;margin:3px 0;background:rgba(106,178,242,.06);border-radius:0 4px 4px 0;font-style:italic;color:var(--text2)}

.msg-footer{display:flex;justify-content:flex-end;align-items:center;gap:6px;margin-top:2px}
.msg-time{font-size:10px;color:rgba(134,159,183,.7)}

/* ── per-group color (cycle) ─── */
.gc0 .msg-group-name{color:#6ab2f2}
.gc1 .msg-group-name{color:#e06c75}
.gc2 .msg-group-name{color:#6ec87a}
.gc3 .msg-group-name{color:#d4a94b}
.gc4 .msg-group-name{color:#b39ddb}
.gc5 .msg-group-name{color:#f48fb1}
.gc6 .msg-group-name{color:#80cbc4}
.gc7 .msg-group-name{color:#81c784}

.msg-not-news{opacity:.45}
.msg-not-news .msg-sev-badge::after{content:" · opinion";font-weight:500;letter-spacing:0}

/* ─── EMPTY STATE ──────────────────────────────────────────── */
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text2);gap:8px;padding:40px;text-align:center}
.empty-state .icon{font-size:40px;opacity:.4}
.empty-state p{font-size:12px;line-height:1.6;max-width:320px}

/* ─── TOAST ────────────────────────────────────────────────── */
.toast-container{position:fixed;bottom:18px;right:18px;display:flex;flex-direction:column;gap:5px;z-index:9999}
.toast{background:var(--surface2);border:1px solid var(--border);border-radius:7px;padding:9px 15px;font-size:11.5px;color:var(--text);max-width:320px;animation:slideIn .18s ease-out}
.toast.error{border-left:3px solid var(--red)}
.toast.success{border-left:3px solid var(--green)}
@keyframes slideIn{from{opacity:0;transform:translateX(14px)}to{opacity:1;transform:translateX(0)}}

/* ─── SETTINGS OVERLAY ─────────────────────────────────────── */
.settings-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9000;display:none;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
.settings-overlay.open{display:flex}
.settings-panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;width:460px;max-height:85vh;overflow-y:auto;box-shadow:0 16px 50px rgba(0,0,0,.5)}
.sp-header{display:flex;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border)}
.sp-header h2{font-size:15px;font-weight:600;flex:1}
.sp-close{background:none;border:none;color:var(--text2);cursor:pointer;font-size:18px;padding:2px 6px;border-radius:5px;transition:all .1s}
.sp-close:hover{color:var(--text);background:var(--surface2)}
.sp-body{padding:18px 20px}
.sp-section{margin-bottom:20px}
.sp-section h3{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:10px}
.field{margin-bottom:12px}
.field label{display:block;font-size:11.5px;font-weight:500;color:var(--text);margin-bottom:4px}
.field input[type="text"],.field input[type="password"],.field select,.field textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:5px;padding:7px 10px;color:var(--text);font-size:12px;outline:none;font-family:inherit;transition:border-color .12s;box-sizing:border-box}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--accent)}
.field input::placeholder,.field textarea::placeholder{color:var(--text2)}
.field textarea{resize:vertical;min-height:60px;line-height:1.45}
.field .hint{font-size:9.5px;color:var(--text2);margin-top:3px}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0}
.toggle-row .label{font-size:12.5px;font-weight:500}
.toggle-row .sublabel{font-size:10px;color:var(--text2);margin-top:1px}
.switch{position:relative;width:38px;height:22px;flex-shrink:0}
.switch input{opacity:0;width:0;height:0}
.switch .slider{position:absolute;inset:0;background:var(--border);border-radius:22px;cursor:pointer;transition:background .18s}
.switch .slider::before{content:"";position:absolute;width:16px;height:16px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:transform .18s}
.switch input:checked+.slider{background:var(--accent)}
.switch input:checked+.slider::before{transform:translateX(16px)}
.settings-save{background:var(--accent);color:#fff;border:none;border-radius:7px;padding:9px 20px;font-size:12px;font-weight:600;cursor:pointer;width:100%;transition:background .12s;margin-top:4px}
.settings-save:hover{background:var(--accent-h)}
.pushover-creds{display:none;margin-top:10px}
.pushover-creds.visible{display:block}
.instr-preset-row{display:flex;gap:6px;margin-bottom:8px;align-items:center}
.instr-preset-row select{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:5px;padding:6px 8px;color:var(--text);font-size:11.5px;font-family:inherit;outline:none}
.instr-preset-row select:focus{border-color:var(--accent)}
.instr-preset-row button{background:var(--surface2);border:1px solid var(--border);border-radius:5px;padding:5px 10px;color:var(--text);font-size:11px;cursor:pointer;white-space:nowrap;font-family:inherit;transition:background .12s}
.instr-preset-row button:hover{background:var(--border)}
.instr-preset-row button.danger{color:#f85149}
.instr-preset-row button.danger:hover{background:#f8514922}

/* ─── SCROLLBAR ────────────────────────────────────────────── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text2)}

/* ─── RESPONSIVE ───────────────────────────────────────────── */
@media(max-width:768px){
  .app{grid-template-columns:1fr;grid-template-rows:52px auto 1fr}
  .sidebar{max-height:220px;border-right:none;border-bottom:1px solid var(--border)}
  .filter-input{width:100px}
  .settings-panel{width:94vw}
  .sev-filters{flex-wrap:wrap}
}
</style>
</head>
<body>
<div class="app">

  <!-- Header -->
  <header>
    <div class="logo">📡</div>
    <h1>Telegram Monitor</h1>
    <div class="spacer"></div>
    <div class="status" id="connStatus">
      <div class="dot"></div>
      <span>Live</span>
    </div>
    <button class="settings-btn" onclick="openSettings()" title="Settings">⚙</button>
  </header>

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <h2>Monitored Groups</h2>
      <div class="add-group">
        <input type="text" id="groupInput" placeholder="Group link or username…"
               onkeydown="if(event.key==='Enter') addGroup()">
        <button id="addBtn" onclick="addGroup()">Add</button>
      </div>
      <div class="input-hint">
        <b>@username</b> · <b>https://t.me/group</b> · <b>t.me/+hash</b> · <b>chat&nbsp;ID</b>
      </div>
      <div class="preset-row">
        <select id="chPresetSelect"><option value="">— channel presets —</option></select>
        <button onclick="loadChPreset()" title="Load all channels from this preset">Load</button>
        <button onclick="saveChPreset()" title="Save current groups as a preset">Save</button>
        <button class="danger" onclick="deleteChPreset()" title="Delete selected preset">✕</button>
      </div>
    </div>
    <div class="group-list" id="groupList">
      <div class="no-groups">No groups yet.<br>Add one above to start.</div>
    </div>
  </aside>

  <!-- Feed -->
  <main class="feed">
    <div class="feed-toolbar">
      <h2>All Groups</h2>
      <div class="sev-filters" id="sevFilters">
        <span class="sev-pill active" data-sev="all" onclick="toggleSev(this)">All</span>
        <span class="sev-pill active" data-sev="Critical" onclick="toggleSev(this)">Critical</span>
        <span class="sev-pill active" data-sev="High" onclick="toggleSev(this)">High</span>
        <span class="sev-pill active" data-sev="Medium" onclick="toggleSev(this)">Medium</span>
        <span class="sev-pill active" data-sev="Low" onclick="toggleSev(this)">Low</span>
        <span class="sev-pill active" data-sev="Noise" onclick="toggleSev(this)">Noise</span>
      </div>
      <input type="text" class="filter-input" id="filterInput"
             placeholder="🔍 Filter…" oninput="applyFilter()">
      <div class="msg-count" id="msgCount">0 messages</div>
    </div>
    <div class="messages" id="messages">
      <div class="empty-state" id="emptyState">
        <div class="icon">💬</div>
        <p>Add a Telegram group from the sidebar to start seeing live messages here.</p>
      </div>
    </div>
  </main>

</div>

<!-- Settings overlay -->
<div class="settings-overlay" id="settingsOverlay" onclick="if(event.target===this)closeSettings()">
  <div class="settings-panel">
    <div class="sp-header">
      <h2>⚙ Settings</h2>
      <button class="sp-close" onclick="closeSettings()">✕</button>
    </div>
    <div class="sp-body">

      <!-- OpenAI -->
      <div class="sp-section">
        <h3>OpenAI — Severity Rating</h3>
        <div class="field">
          <label>API Key</label>
          <input type="password" id="setOpenaiKey" placeholder="sk-…">
          <div class="hint">GPT-4o rates each message as Noise / Low / Medium / High / Critical and flags non-news.</div>
        </div>
        <div class="field">
          <label>Custom Severity Instructions</label>
          <div class="instr-preset-row">
            <select id="instrPresetSelect"><option value="">— saved presets —</option></select>
            <button onclick="loadInstrPreset()">Load</button>
            <button onclick="saveInstrPreset()">Save As…</button>
            <button class="danger" onclick="deleteInstrPreset()">Delete</button>
          </div>
          <textarea id="setSevInstructions" rows="5" placeholder="e.g. Anything about crypto or Bitcoin should be rated High. Ignore sports news entirely (Noise). I care most about Fed rate decisions and US-China relations."></textarea>
          <div class="hint">Write your custom criteria, then save as a named preset. Load or switch presets anytime.</div>
        </div>
      </div>

      <!-- Pushover -->
      <div class="sp-section">
        <h3>Pushover Notifications</h3>
        <div class="toggle-row">
          <div>
            <div class="label">Enable Pushover</div>
            <div class="sublabel">Push alerts to your phone for important news</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="setPushoverEnabled" onchange="togglePoCreds()">
            <span class="slider"></span>
          </label>
        </div>
        <div class="pushover-creds" id="pushoverCreds">
          <div class="field">
            <label>App Token</label>
            <input type="password" id="setPushoverToken" placeholder="azGDORePK8gM…">
          </div>
          <div class="field">
            <label>User Key</label>
            <input type="password" id="setPushoverUser" placeholder="uQiRzpo4DXghD…">
          </div>
          <div class="field">
            <label>Minimum Severity</label>
            <select id="setNotifyMinSev">
              <option value="Noise">Noise (everything)</option>
              <option value="Low">Low</option>
              <option value="Medium" selected>Medium</option>
              <option value="High">High</option>
              <option value="Critical">Critical only</option>
            </select>
            <div class="hint">Only actual news at or above this level triggers a push. Opinions are always excluded.</div>
          </div>
        </div>
      </div>

      <button class="settings-save" onclick="saveSettings()">Save Settings</button>
    </div>
  </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
// ── State ──────────────────────────────────────────────
const allMessages = [];
const groups = {};
const gcMap = {};
let gcIdx = 0;
let filterText = "";
let activeSev = new Set(["all","Critical","High","Medium","Low","Noise"]);
let selectedGid = null;

const $msgs  = document.getElementById("messages");
const $gList = document.getElementById("groupList");
const $mCnt  = document.getElementById("msgCount");
const $conn  = document.getElementById("connStatus");
const $feedTitle = document.querySelector(".feed-toolbar h2");

const GC_COLORS = ["#2f81f7","#da3633","#3fb950","#d29922","#a371f7","#f778ba","#79c0ff","#56d364"];
function gc(gid){ if(!(gid in gcMap)){gcMap[gid]=gcIdx%8;gcIdx++} return gcMap[gid]; }

// ── Group selection ────────────────────────────────────
function selectGroup(gid){
  selectedGid = gid;
  if(gid===null){
    $feedTitle.textContent="All Groups";
  } else {
    $feedTitle.textContent=groups[gid]?groups[gid].name:"Group";
  }
  renderGL();
  applyFilter();
}

// ── SSE ────────────────────────────────────────────────
function connectSSE(){
  const es = new EventSource("/api/stream");
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if(d._update) updateSev(d); else pushMsg(d);
  };
  es.onopen = ()=>{ $conn.classList.remove("disconnected"); $conn.querySelector("span").textContent="Live"; };
  es.onerror = ()=>{ $conn.classList.add("disconnected"); $conn.querySelector("span").textContent="Reconnecting…"; };
}

function updateSev(u){
  const m = allMessages.find(x=>x.id===u.id && x.group_id===u.group_id);
  if(!m) return;
  m.severity=u.severity; m.is_news=u.is_news;
  const el = $msgs.querySelector(`.msg[data-uid="${m.group_id}_${m.id}"]`);
  if(!el) return;
  const b = el.querySelector(".msg-sev-badge");
  if(b){ b.className="msg-sev-badge"; b.dataset.sev=m.severity; b.textContent=m.severity; }
  if(!m.is_news) el.classList.add("msg-not-news"); else el.classList.remove("msg-not-news");
  if(!matchF(m)) el.style.display="none"; else el.style.display="";
}

// ── Messages ───────────────────────────────────────────
function pushMsg(m){
  if(allMessages.find(x=>x.id===m.id&&x.group_id===m.group_id)) return;
  allMessages.push(m);
  if(groups[m.group_id]) groups[m.group_id].count=(groups[m.group_id].count||0)+1;
  const es=document.getElementById("emptyState"); if(es) es.remove();
  applyFilter();
  renderGL();
}

function matchF(m){
  if(selectedGid!==null && m.group_id!=selectedGid) return false;
  if(!activeSev.has("all")){ const s=m.severity||"Low"; if(!activeSev.has(s)) return false; }
  if(filterText){ const q=filterText.toLowerCase();
    if(!(m.text||"").toLowerCase().includes(q)&&!(m.sender||"").toLowerCase().includes(q)&&!(m.group||"").toLowerCase().includes(q)) return false;
  }
  return true;
}

function fmtText(m){
  // Use pre-formatted HTML from backend (entities applied on raw_text)
  let t = m.html || escH(m.text || "");
  // Linkify any remaining plain URLs not already inside <a> tags
  t=t.replace(/(^|[^"=])(https?:\/\/[^\s<]+)/g, (match,pre,url)=>{
    return pre+'<a href="'+url+'" target="_blank" rel="noopener">'+url+'</a>';
  });
  // Quote styling
  t=t.replace(/^([\u2018\u2019'\u201C\u201D"].+?[\u2018\u2019'\u201C\u201D"])/gm,'<span class="quote">$1</span>');
  return t;
}

function addEl(m){
  const el=document.createElement("div");
  const ci=gc(m.group_id);
  el.className=`msg gc${ci}`+(m.is_news===false?" msg-not-news":"");
  el.dataset.uid=`${m.group_id}_${m.id}`;

  const t=new Date(m.date);
  const ts=t.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});

  const sev=m.severity;
  const badge=sev
    ?`<span class="msg-sev-badge" data-sev="${sev}">${sev}</span>`
    :`<span class="msg-sev-badge loading">rating…</span>`;

  el.innerHTML=`<div class="msg-head">
    <span class="msg-group-name">${escH(m.group)}</span>
    <span class="msg-sender-name">${escH(m.sender)}</span>
    ${badge}
  </div>
  <div class="msg-body">${fmtText(m)}</div>
  <div class="msg-footer"><span class="msg-time">${ts}</span></div>`;

  $msgs.appendChild(el);
  if($msgs.scrollHeight-$msgs.scrollTop-$msgs.clientHeight<200)
    $msgs.scrollTop=$msgs.scrollHeight;
}

function applyFilter(){
  filterText=document.getElementById("filterInput").value;
  $msgs.innerHTML="";
  allMessages.filter(matchF).sort((a,b)=>new Date(a.date)-new Date(b.date)).forEach(addEl);
  updCnt();
  $msgs.scrollTop=$msgs.scrollHeight;
}
function updCnt(){
  const v=allMessages.filter(matchF).length;
  $mCnt.textContent=v!==allMessages.length?`${v} / ${allMessages.length}`:`${allMessages.length} messages`;
}
function escH(t){ const d=document.createElement("div"); d.textContent=t||""; return d.innerHTML; }

// ── Severity filters ───────────────────────────────────
function toggleSev(p){
  const s=p.dataset.sev;
  if(s==="all"){
    const on=p.classList.contains("active");
    document.querySelectorAll(".sev-pill").forEach(x=>{
      if(on){x.classList.remove("active");activeSev.delete(x.dataset.sev)}
      else{x.classList.add("active");activeSev.add(x.dataset.sev)}
    });
  } else {
    p.classList.toggle("active");
    if(p.classList.contains("active")) activeSev.add(s);
    else{ activeSev.delete(s); activeSev.delete("all"); document.querySelector('.sev-pill[data-sev="all"]').classList.remove("active"); }
    if(["Critical","High","Medium","Low","Noise"].every(x=>activeSev.has(x))){
      activeSev.add("all"); document.querySelector('.sev-pill[data-sev="all"]').classList.add("active");
    }
  }
  applyFilter();
}

// ── Groups ─────────────────────────────────────────────
async function addGroupByLink(link){
  if(!link) return;
  const btn=document.getElementById("addBtn");
  btn.disabled=true;btn.textContent="Adding…";
  try{
    const r=await fetch("/api/groups",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({group:link})});
    const d=await r.json();
    if(!r.ok){toast(d.error||"Failed","error");return}
    if(d.already){toast(`"${d.name}" already monitored`,"error");return}
    groups[d.id]={name:d.name,count:d.history_count||0};
    renderGL(); toast(`Added "${d.name}" — ${d.history_count||0} msgs`,"success");
  }catch(e){toast("Network error","error")}
  finally{btn.disabled=false;btn.textContent="Add"}
}

async function addGroup(){
  const inp=document.getElementById("groupInput"),raw=inp.value.trim();
  if(!raw) return;
  await addGroupByLink(raw);
  inp.value="";
}

async function removeGroup(gid){
  await fetch(`/api/groups/${gid}`,{method:"DELETE"});
  delete groups[gid];
  if(selectedGid==gid) selectedGid=null;
  for(let i=allMessages.length-1;i>=0;i--) if(allMessages[i].group_id==gid) allMessages.splice(i,1);
  renderGL();applyFilter();
  if(selectedGid===null) $feedTitle.textContent="All Groups";
  if(!allMessages.length) $msgs.innerHTML=`<div class="empty-state" id="emptyState"><div class="icon">💬</div><p>Add a group to start.</p></div>`;
  toast("Group removed","success");
}

function renderGL(){
  const ids=Object.keys(groups);
  if(!ids.length){$gList.innerHTML=`<div class="no-groups">No groups yet.<br>Add one above.</div>`;return}
  const lastMsg={};
  for(let i=allMessages.length-1;i>=0;i--){
    const m=allMessages[i];
    if(!lastMsg[m.group_id]) lastMsg[m.group_id]={text:m.text,sender:m.sender};
  }
  let html=`<div class="group-item${selectedGid===null?" selected":""}" onclick="selectGroup(null)">
    <div class="avatar" style="background:#3e546a">All</div>
    <div class="info">
      <div class="top-row"><span class="name">All Groups</span><span class="count">${allMessages.length}</span></div>
      <div class="preview">${ids.length} channels monitored</div>
    </div>
  </div>`;
  html+=ids.map(gid=>{
    const g=groups[gid],ci=gc(parseInt(gid)),c=GC_COLORS[ci];
    const sel=selectedGid==gid?" selected":"";
    const lm=lastMsg[gid];
    const prev=lm?escH((lm.sender?lm.sender+": ":"")+lm.text).slice(0,60):"No messages yet";
    return`<div class="group-item${sel}" onclick="selectGroup(${gid})">
      <div class="avatar" style="background:${c}">${(g.name||"?")[0].toUpperCase()}</div>
      <div class="info">
        <div class="top-row"><span class="name">${escH(g.name)}</span><span class="count">${g.count||0}</span></div>
        <div class="preview">${prev}</div>
      </div>
      <button class="remove" onclick="event.stopPropagation();removeGroup(${gid})" title="Remove">✕</button>
    </div>`;
  }).join("");
  $gList.innerHTML=html;
}

// ── Channel Presets ────────────────────────────────────
let _chPresets=[];
async function refreshChPresets(){
  try{
    const r=await fetch("/api/channel-presets");
    _chPresets=await r.json();
    const sel=document.getElementById("chPresetSelect");
    sel.innerHTML='<option value="">— channel presets —</option>';
    _chPresets.forEach(p=>{
      const o=document.createElement("option");
      o.value=p.name; o.textContent=`${p.name} (${p.links.length})`;
      sel.appendChild(o);
    });
  }catch(e){}
}
async function loadChPreset(){
  const name=document.getElementById("chPresetSelect").value;
  if(!name){toast("Pick a preset first","error");return}
  const preset=_chPresets.find(p=>p.name===name);
  if(!preset||!preset.links.length){toast("Preset is empty","error");return}
  toast(`Loading ${preset.links.length} channels…`,"success");
  for(const link of preset.links){
    await addGroupByLink(link);
  }
  toast(`Preset "${name}" loaded`,"success");
}
async function saveChPreset(){
  const ids=Object.keys(groups);
  if(!ids.length){toast("No groups to save","error");return}
  const name=prompt("Preset name:");
  if(!name||!name.trim()) return;
  // We need the links — fetch from server
  try{
    const r=await fetch("/api/groups");
    const list=await r.json();
    const links=list.map(g=>g.name); // use name as identifier
    const r2=await fetch("/api/channel-presets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name.trim(),links})});
    if(r2.ok){toast(`Preset "${name.trim()}" saved`,"success");await refreshChPresets();document.getElementById("chPresetSelect").value=name.trim()}
    else toast("Failed","error");
  }catch(e){toast("Error","error")}
}
async function deleteChPreset(){
  const name=document.getElementById("chPresetSelect").value;
  if(!name){toast("Pick a preset to delete","error");return}
  if(!confirm(`Delete preset "${name}"?`)) return;
  try{
    await fetch(`/api/channel-presets/${encodeURIComponent(name)}`,{method:"DELETE"});
    toast(`Deleted "${name}"`,"success");
    await refreshChPresets();
  }catch(e){toast("Error","error")}
}

// ── Instruction Presets ─────────────────────────────────
async function refreshInstrPresets(){
  try{
    const r=await fetch("/api/instruction-presets");
    const list=await r.json();
    const sel=document.getElementById("instrPresetSelect");
    sel.innerHTML='<option value="">— saved presets —</option>';
    list.forEach(p=>{
      const o=document.createElement("option");
      o.value=p.name; o.textContent=p.name;
      sel.appendChild(o);
    });
    sel._presets=list;
  }catch(e){}
}
function loadInstrPreset(){
  const sel=document.getElementById("instrPresetSelect");
  const name=sel.value;
  if(!name){toast("Pick a preset first","error");return}
  const list=sel._presets||[];
  const p=list.find(x=>x.name===name);
  if(p) document.getElementById("setSevInstructions").value=p.text;
}
async function saveInstrPreset(){
  const text=document.getElementById("setSevInstructions").value.trim();
  if(!text){toast("Write instructions first","error");return}
  const name=prompt("Preset name:");
  if(!name||!name.trim()) return;
  try{
    const r=await fetch("/api/instruction-presets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name.trim(),text})});
    if(r.ok){toast(`Preset "${name.trim()}" saved`,"success");await refreshInstrPresets();document.getElementById("instrPresetSelect").value=name.trim()}
    else toast("Failed to save","error");
  }catch(e){toast("Error","error")}
}
async function deleteInstrPreset(){
  const sel=document.getElementById("instrPresetSelect");
  const name=sel.value;
  if(!name){toast("Pick a preset to delete","error");return}
  if(!confirm(`Delete preset "${name}"?`)) return;
  try{
    await fetch(`/api/instruction-presets/${encodeURIComponent(name)}`,{method:"DELETE"});
    toast(`Deleted "${name}"`,"success");
    await refreshInstrPresets();
  }catch(e){toast("Error","error")}
}

// ── Settings ───────────────────────────────────────────
function openSettings(){
  fetch("/api/settings").then(r=>r.json()).then(s=>{
    document.getElementById("setOpenaiKey").value=s.openai_api_key||"";
    document.getElementById("setSevInstructions").value=s.severity_instructions||"";
    document.getElementById("setPushoverEnabled").checked=!!s.pushover_enabled;
    document.getElementById("setPushoverToken").value=s.pushover_app_token||"";
    document.getElementById("setPushoverUser").value=s.pushover_user_key||"";
    document.getElementById("setNotifyMinSev").value=s.notify_min_severity||"Medium";
    togglePoCreds();
  });
  refreshInstrPresets();
  document.getElementById("settingsOverlay").classList.add("open");
}
function closeSettings(){document.getElementById("settingsOverlay").classList.remove("open")}
function togglePoCreds(){
  document.getElementById("pushoverCreds").classList.toggle("visible",document.getElementById("setPushoverEnabled").checked);
}
async function saveSettings(){
  const p={
    openai_api_key:document.getElementById("setOpenaiKey").value.trim(),
    severity_instructions:document.getElementById("setSevInstructions").value.trim(),
    pushover_enabled:document.getElementById("setPushoverEnabled").checked,
    pushover_app_token:document.getElementById("setPushoverToken").value.trim(),
    pushover_user_key:document.getElementById("setPushoverUser").value.trim(),
    notify_min_severity:document.getElementById("setNotifyMinSev").value,
  };
  try{
    const r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});
    if(r.ok){toast("Settings saved","success");closeSettings()}else toast("Failed","error");
  }catch(e){toast("Error","error")}
}

// ── Toasts ─────────────────────────────────────────────
function toast(m,type="success"){
  const el=document.createElement("div");el.className=`toast ${type}`;el.textContent=m;
  document.getElementById("toasts").appendChild(el);setTimeout(()=>el.remove(),4000);
}

// ── Init ───────────────────────────────────────────────
async function init(){
  connectSSE();
  refreshChPresets();
  try{const r=await fetch("/api/groups");(await r.json()).forEach(g=>{groups[g.id]={name:g.name,count:0}});renderGL()}catch(e){}
  try{const r=await fetch("/api/messages?limit=20");(await r.json()).forEach(pushMsg)}catch(e){}
}
init();
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════
#                           MAIN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import webbrowser

    if not API_ID or not API_HASH:
        print("=" * 60)
        print("  Telegram API credentials not found!")
        print()
        print("  1. Go to https://my.telegram.org → API Development Tools")
        print("  2. Create an app → get api_id and api_hash")
        print(f"  3. Fill in {ENV_FILE}")
        print("=" * 60)
        if not ENV_FILE.exists():
            ENV_FILE.write_text("TELEGRAM_API_ID=\nTELEGRAM_API_HASH=\nTELEGRAM_SESSION=tg_session\n")
        raise SystemExit(1)

    t = threading.Thread(target=_telethon_thread, daemon=True)
    t.start()
    time.sleep(2)
    webbrowser.open("http://localhost:5050")
    print("[Server] http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
