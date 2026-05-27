import os
import json
import time
import warnings
from pathlib import Path

# Suppress Pydantic V1 compatibility warning (LangChain internal - not fixable in user code)
warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality")

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_option_menu import option_menu
import streamlit.components.v1 as components
import requests
# Import runtime HTTP guard early to prevent any outbound HTTP calls when
# DISABLE_EXTERNAL_HTTP is set (default = '1'). This monkeypatches common
# HTTP libraries to raise on network attempts.
try:
    from lib import disable_http  # noqa: F401
except Exception:
    pass
from requests.adapters import HTTPAdapter
from typing import Optional


# ---------------------- your config & modules ----------------------

# Must define: OPENAI_API_KEY, OPENAI_REALTIME_MODEL, DEFAULT_REALTIME_VOICE, REALTIME_VOICES,
# APP_NAME, VERSION, DATE, PAGE_CONFIG, THEME_COLORS, PAGES, FEATURES, MODELS,
# validate_api_keys, get_system_info
from config import *

# Local modules (unchanged)
from lib.ui import apply_theme_css, render_topbar_auth_links
# Import other local modules after ui so sidebar is disabled early
from lib import chatpdf, chatgeneration, sidebar, auth  # noqa: F401
from lib import home_views
from lib.enhanced_usage_logger import log_page_visit, log_session_action, migrate_from_csv


# -----------------------------------------------------------------------------
# Manage page tracking and associated session state
# -----------------------------------------------------------------------------
THIS_PAGE = "chatgpt"
st.session_state.cur_page = THIS_PAGE
# -----------------------------------------------------------------------------

# ---------------------- Streamlit setup ----------------------
# st.set_page_config(**PAGE_CONFIG)
st.set_page_config(page_title="FE-AI Home", page_icon='assets/favicon.png')
# Replace the default favicon with the Bowling Green Falcons logo provided.
# Use a small JS snippet to update the favicon at runtime so no file changes
# are required. This works across Streamlit deployments.
components.html("""
<script>
    (function(){
        try {
            // Use a local app asset for the favicon to avoid external network requests.
            const url = '/assets/favicon.png';
            let link = document.querySelector("link[rel*='icon']");
            if (!link) {
                link = document.createElement('link');
                link.rel = 'icon';
                document.getElementsByTagName('head')[0].appendChild(link);
            }
            link.href = url;
        } catch (e) { console.error('favicon set failed', e); }
    })();
</script>
""", height=0)
apply_theme_css()
from lib.ui import render_topbar_auth_links
render_topbar_auth_links()

load_dotenv(override=True)

# Restore session from `sid` query param when present (or from localStorage via redirect)
try:
    from lib import sessions
    params = st.experimental_get_query_params()
    sid_list = params.get("sid") or params.get("session_id")
    if sid_list:
        sid = sid_list[0]
        s = sessions.get_session(sid)
        if s:
            st.session_state["user"] = s.get("user")
            st.session_state["full_name"] = s.get("user")
            st.session_state["session_id"] = sid
            # set localStorage so subsequent reloads can redirect to ?sid=...
            try:
                components.html(f"<script>localStorage.setItem('session_id','{sid}');</script>", height=0)
            except Exception:
                pass
except Exception:
    pass

# If no user but a session_id exists in localStorage, client-side JS will
# redirect to `/?sid=...` so the above block can restore the session.
if not st.session_state.get("user"):
    try:
        components.html(
            """
            <script>
            (function(){
                try {
                    const sid = localStorage.getItem('session_id');
                    if (sid && !window.location.search.includes('sid=')) {
                        window.location.href = '/?sid=' + encodeURIComponent(sid);
                    }
                } catch(e){}
            })();
            </script>
            """,
            height=0,
        )
    except Exception:
        pass

# If no minimal user info present, redirect new sessions to the simplified login page
try:
    if not st.session_state.get("full_name") and not st.session_state.get("user"):
        # Prefer server-side switch when available
        try:
            if hasattr(st, "switch_page"):
                st.switch_page("pages/login.py")
        except Exception:
            pass

        # Fallback to client-side redirect to the login route
        try:
            components.html("<script>window.location.href='/login'</script>", height=0)
        except Exception:
            pass
except Exception:
    # Do not let redirect logic break the main app
    pass

# Hide Streamlit's automatic pages navigation (we use a minimal UI with a single page)
st.markdown(f"""
<style>
    /* Hide Streamlit page navigation and related sidebar containers */
    [data-testid='stSidebarNav'],
    [data-testid='stSidebarContent'],
    [data-testid='stSidebarHeader'],
    [data-testid='stSidebarUserContent'],
    button[data-testid='stSidebarNavViewButton'] {{
        display: none !important;
        background-color: {THEME_COLORS['background']} !important;
    }}

    /* Also collapse the sidebar area to reclaim layout space and ensure its
       background matches the main application body so no faded grey shows. */
    .css-1d391kg {{ display: none !important; background-color: {THEME_COLORS['background']} !important; }}

    /* In case any leftover sidebar-like containers remain visible, ensure their
       background matches the app body color. */
    [data-testid='stSidebarContent'], aside[aria-label='Sidebar'], div[data-testid*='Sidebar'] {{
        background-color: {THEME_COLORS['background']} !important;
    }}
</style>
""", unsafe_allow_html=True)

# Also remove sidebar DOM nodes via a small JS snippet for robustness
components.html(
        """
        <script>
        (function(){
            const selectors = [
                '[data-testid="stSidebarContent"]',
                '[data-testid="stSidebarNav"]',
                '[data-testid="stSidebarHeader"]',
                '[data-testid="stSidebarUserContent"]',
                'button[data-testid="stSidebarNavViewButton"]',
                'aside[aria-label="Sidebar"]'
            ];
            for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => el.remove());
            }
        })();
        </script>
        """,
        height=0,
)


# ---------------------- pooled HTTP session (bursts) ----------------------
_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=32, pool_maxsize=128)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
OPENAI_RT_SESS_URL = "https://api.openai.com/v1/realtime/sessions"

def mint_realtime_client_secret(model: str, voice: str, instructions: str | None = None) -> dict:
    """
    Server-side mint of ephemeral Realtime session token.
    Returns: {client_secret, expires_at, session_id, model, voice}
    """
    # Prevent external HTTP usage by default
    if os.getenv('DISABLE_EXTERNAL_HTTP', '1') == '1':
        raise RuntimeError("External HTTP calls are disabled (DISABLE_EXTERNAL_HTTP=1). Realtime minting requires network access.")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing (set in config.py or .env)")

    default_instructions = (
        "You are a helpful AI assistant for FE-AI, an educational platform. "
        "Speak naturally and professionally. Keep responses clear and concise. "
        "You are designed to help students with their educational needs."
    )

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "voice": voice,
        "modalities": ["audio", "text"],
        "instructions": instructions or default_instructions,
    }
    resp = _session.post(OPENAI_RT_SESS_URL, headers=headers, json=payload, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"OpenAI Realtime session error {resp.status_code}: {resp.text}")

    j = resp.json()
    return {
        "client_secret": (j.get("client_secret", {}) or {}).get("value") or j.get("client_secret"),
        "expires_at": j.get("expires_at"),
        "session_id": j.get("id"),
        "model": model,
        "voice": voice,
    }


# ---------------------- minimal WebRTC launcher (front-end) ----------------------
RTC_HTML = """
<script>
async function startRealtime(clientSecret, model) {
  // Peer connection
  const pc = new RTCPeerConnection();
  const audioEl = document.getElementById("realtime-audio");
  pc.ontrack = (event) => { audioEl.srcObject = event.streams[0]; };

  // Mic
  const ms = await navigator.mediaDevices.getUserMedia({ audio: true });

  for (const track of ms.getTracks()) pc.addTrack(track, ms);

  // Optional data channel (events/control)
  const dc = pc.createDataChannel("oai-events");
  dc.onmessage = (e) => console.log("OAI:", e.data);

  // SDP offer
  const offer = await pc.createOffer({ offerToReceiveAudio: true });
  await pc.setLocalDescription(offer);

  // SDP exchange with OpenAI Realtime (Authorization: Bearer <clientSecret>)
  const sdpResponse = await fetch("https://api.openai.com/v1/realtime?model=" + encodeURIComponent(model), {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + clientSecret,
      "Content-Type": "application/sdp"
    },
    body: offer.sdp
  });

  if (!sdpResponse.ok) {
    const errText = await sdpResponse.text();
    throw new Error("Realtime SDP exchange failed: " + sdpResponse.status + " " + errText);
  }

  const answerSdp = await sdpResponse.text();
  await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

  // Expose for debugging/stop
  window._oai_pc = pc;
}

async function stopRealtime() {
  const pc = window._oai_pc;

  if (pc) {
    pc.getSenders().forEach(s => { try { s.track && s.track.stop(); } catch(_){} });
    pc.getReceivers().forEach(r => { try { r.track && r.track.stop(); } catch(_){} });
    pc.close();
    window._oai_pc = null;
  }
}
</script>


<div style="display:flex;gap:8px;align-items:center;">
  <button id="startBtn">Start Realtime</button>
  <button id="stopBtn">Stop</button>
  <audio id="realtime-audio" autoplay></audio>
</div>

<script>
(() => {
  const startBtn = document.getElementById("startBtn");
  const stopBtn  = document.getElementById("stopBtn");
  startBtn.onclick = async () => {
    const payload = JSON.parse(decodeURIComponent(window.location.hash.slice(1)));
    await startRealtime(payload.client_secret, payload.model).catch(err => alert(err.message));
  };
  stopBtn.onclick = async () => { await stopRealtime(); };
})();
</script>
"""


# ---------------------- main/home UI ----------------------
def home():
    log_page_visit("home", {
        "version": VERSION,
        "total_models": len(MODELS),
        "available_models": len(validate_api_keys()["available_models"]),
        "features_enabled": sum(1 for f in FEATURES.values() if f)
    })

    # If a user is signed in, route to professor vs student home
    user = st.session_state.get("user")
    if user:
        try:
            from lib import auth as _auth
            if _auth.is_admin(user):
                return home_views.professor_home(user)
        except Exception:
            # If any error reading users, fall back to default student home
            pass

    st.markdown(f'<h2 style="color: {THEME_COLORS["primary"]};">Welcome to {APP_NAME}</h2>', unsafe_allow_html=True)
    st.markdown(f"*Version {VERSION} - {DATE}*")

    st.markdown("""
    **Your AI-powered educational assistant** featuring six specialized modules designed to enhance your academic journey.
    Developed at Miami University's Farmer School of Business, FE-AI provides free access to cutting-edge AI technology
    to support student success in programming, projects, exam preparation, interview practice, code execution, and AI model comparison.
    """)

    # Single-module app: immediately open the Coding Companion (only page supported)
    try:
        st.session_state.cur_page = "coding_companion"
        if hasattr(st, "switch_page"):
            st.switch_page("pages/01_coding_companion.py")
            return
    except Exception:
        # Fallback UI when switch_page is unavailable — provide a button to continue
        st.markdown("### Open Coding Companion")
        if st.button("Open Coding Companion"):
            try:
                st.session_state.cur_page = "coding_companion"
                if hasattr(st, "switch_page"):
                    st.switch_page("pages/01_coding_companion.py")
                    return
                else:
                    st.experimental_rerun()
            except Exception:
                st.warning("Unable to open Coding Companion automatically.")

    key_validation = validate_api_keys()
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total Models", len(MODELS))
    with c2: st.metric("Available Modules", "6")
    with c3:
        status = "Ready" if key_validation["all_keys_present"] else "Limited"
        st.metric("System Status", status)

    with st.expander("Available Models & Pricing", expanded=False):
        st.markdown("### Model Summary")
        rows = []
        for _, cfg in MODELS.items():
            rows.append({
                "Model": cfg["display_name"],
                "Provider": cfg["provider"].title(),
                "Input ($/1M tokens)": f"${cfg['cost_per_1k_input']*1000:.2f}",
                "Output ($/1M tokens)": f"${cfg['cost_per_1k_output']*1000:.2f}",
                "Max Tokens": f"{cfg['max_tokens']:,}",
                "Vision": "Yes" if cfg["supports_vision"] else "No",
                "Functions": "Yes" if cfg["supports_function_calling"] else "No",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    sidebar.render_sidebar()


def professor_home(username: str):
    """Home page for professors / admins."""
    st.markdown(f'<h2 style="color: {THEME_COLORS["primary"]};">Instructor Dashboard</h2>', unsafe_allow_html=True)
    display = auth.get_display_name(username) or username
    st.markdown(f"**Signed in as:** {display}")

    st.info("This is the professor (admin) home. You can manage class-level resources here.")

    # Small admin utilities
    st.markdown("---")
    st.markdown("**User accounts**")
    try:
        users = []
        for uname, meta in __import__('json').loads((PROJECT_ROOT / 'data' / 'users.json').read_text()).items():
            users.append({
                "username": uname,
                "display_name": meta.get("display_name"),
                "email": meta.get("email"),
                "isadmin": meta.get("isadmin", False),
            })
        import pandas as _pd
        st.dataframe(_pd.DataFrame(users), width="stretch")
    except Exception:
        st.warning("Unable to load users list from disk.")


def student_home():
    """(unused) kept for symmetry — student content is rendered by main home() body."""
    pass



# ---------------------- run ----------------------
migrate_from_csv()
system_info = get_system_info()

if system_info["missing_api_keys"]:
    st.warning(f"Warning: Missing API keys: {', '.join(system_info['missing_api_keys'])}")

# Call home() directly
home()
