import streamlit as st
import streamlit.components.v1 as components

from config import THEME_COLORS
from lib import auth


# Dummy sidebar to disable left navigation UI globally when assigned.
class _DummyExpander:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class _DummySidebar:
    def markdown(self, *args, **kwargs):
        return None
    def title(self, *args, **kwargs):
        return None
    def write(self, *args, **kwargs):
        return None
    def expander(self, *args, **kwargs):
        return _DummyExpander()
    def page_link(self, *args, **kwargs):
        return None
    def button(self, *args, **kwargs):
        return False
    def radio(self, label, options, index=0, key=None):
        try:
            return options[index]
        except Exception:
            return options[0] if options else None
    def text_input(self, label, value="", key=None, type=None):
        return value
    def selectbox(self, label, options, index=0, key=None):
        try:
            return options[index]
        except Exception:
            return options[0] if options else None
    def error(self, *args, **kwargs):
        return None
    def success(self, *args, **kwargs):
        return None

# Replace Streamlit sidebar with dummy to suppress left navigation globally.
try:
    st.sidebar = _DummySidebar()
except Exception:
    pass


def apply_theme_css(include_code_styles: bool = False) -> None:
    """Apply shared UI styles across pages."""
    css = f"""
<style>
    .stApp {{ background-color: {THEME_COLORS['background']}; }}
    .stButton > button {{
        background-color: {THEME_COLORS['primary']};
        color: white;
        border: none;
        border-radius: 4px;
    }}
    .stButton > button:hover {{
        background-color: {THEME_COLORS['secondary']};
        color: white;
    }}
    .stSelectbox > div > div {{
        background-color: {THEME_COLORS['background']};
        border: 1px solid {THEME_COLORS['primary']};
    }}
    .stSidebar {{ background-color: {THEME_COLORS['background']}; }}
    h1, h2, h3 {{ color: {THEME_COLORS['primary']}; }}
    .stInfo {{
        background-color: rgba(195, 20, 45, 0.1);
        border: 1px solid {THEME_COLORS['primary']};
    }}
    .stWarning {{ background-color: rgba(255, 160, 122, 0.2); }}

    .tool-card {{
        background-color: white;
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
        min-height: 110px;
    }}
    .tool-title {{
        font-weight: 600;
        font-size: 1.05rem;
        margin-bottom: 4px;
    }}
    .tool-subtitle {{
        color: #4b5563;
        font-size: 0.9rem;
        line-height: 1.3;
    }}
    /* Improved expander form layout: use stable data-testid selectors and flexbox */
    [data-testid='stExpanderDetails'] [data-testid='stHorizontalBlock'] {{
        display: flex !important;
        gap: 16px !important;
        align-items: flex-start !important;
        flex-wrap: wrap !important;
    }}

    /* Each column inside an expander should take equal space but remain responsive */
    [data-testid='stExpanderDetails'] .stColumn {{
        flex: 1 1 45% !important;
        min-width: 220px !important;
        box-sizing: border-box !important;
    }}

    /* Vertical blocks inside expanders: consistent spacing */
    [data-testid='stExpanderDetails'] .stVerticalBlock {{
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* Ensure element containers have padding so labels and inputs don't overlap */
    [data-testid='stExpanderDetails'] .stElementContainer {{
        padding: 6px 4px !important;
    }}

    /* Style labels and inputs inside expanders for clarity and accessibility */
    [data-testid='stExpanderDetails'] label[data-testid='stWidgetLabel'] {{
        display: block !important;
        margin-bottom: 6px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        line-height: 1.25 !important;
        color: #111827 !important;
    }}

    [data-testid='stExpanderDetails'] [data-baseweb='input'] input[type='text'],
    [data-testid='stExpanderDetails'] textarea,
    [data-testid='stExpanderDetails'] select {{
        width: 100% !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
        padding: 8px 10px !important;
        border: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        font-size: 0.95rem !important;
        background-color: #ffffff !important;
    }}

    /* Prevent text clipping in markdown inside expander headers/details */
    [data-testid='stExpanderDetails'] [data-testid='stMarkdownContainer'] p {{
        margin: 0 !important;
        padding: 0 !important;
        word-break: break-word !important;
        white-space: normal !important;
    }}

    /* Small screens: stack columns vertically */
    @media (max-width: 720px) {{
        [data-testid='stExpanderDetails'] .stColumn {{
            flex: 1 1 100% !important;
            min-width: 0 !important;
        }}
    }}
</style>
"""

    if include_code_styles:
        css += f"""
<style>
    .code-block {{
        background-color: {THEME_COLORS['background']};
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 16px;
        margin: 10px 0;
        font-family: "Courier New", monospace;
    }}

    .tool-badge {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin: 5px 0;
        background-color: #0969da;
        color: white;
    }}

    .output-section {{
        background-color: {THEME_COLORS['background']};
        border-left: 3px solid {THEME_COLORS['primary']};
        padding: 12px;
        margin: 10px 0;
    }}
</style>
"""

    st.markdown(css, unsafe_allow_html=True)

    # Extra global rules to hide Streamlit's automatic pages navigation/sidebar
    hide_sidebar_css = """
<style>
    /* Aggressively hide Streamlit's sidebar/navigation across versions and themes */
    section[data-testid='stSidebar'],
    section[aria-expanded='true'],
    [data-testid='stSidebarNav'],
    [data-testid='stSidebarContent'],
    [data-testid='stSidebarHeader'],
    [data-testid='stSidebarUserContent'],
    aside[aria-label='Sidebar'],
    aside[aria-label='Main navigation'],
    div[data-testid*='Sidebar'],
    button[data-testid='stSidebarNavViewButton'],
    .stSidebar,
    .css-1ag1mib, /* fallback Streamlit sidebar class */
    .css-1d391kg {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
    }

    /* Reclaim main layout width, center content, and ensure responsive padding */
    .appview-container, .main, .block-container {
        margin: 0 !important;
        padding-left: 5% !important;
        padding-right: 5% !important;
        max-width: none !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Make horizontal columns expand to fill available width (reduces right-side blank space) */
    [data-testid='stHorizontalBlock'] .stColumn,
    .stHorizontalBlock .stColumn {
        flex: 1 1 0% !important;
        max-width: 100% !important;
        min-width: 0 !important;
    }

    /* Ensure charts and wide widgets use the reclaimed space */
    .streamlit-expander, .stPlotlyChart, .stImage { max-width: 100% !important; }

    /* Small screens: reduce fixed topbar offsets so centered elements stay visible */
    @media (max-width: 900px) {
        .topbar-auth-center { top: 48px !important; left: 50% !important; transform: translateX(-50%) !important; }
    }
</style>
"""

    try:
        st.markdown(hide_sidebar_css, unsafe_allow_html=True)
    except Exception:
        # If injection fails, continue without breaking app
        pass

    # Try removing sidebar DOM nodes via client-side JS for robustness across Streamlit versions
    try:
        components.html(
            """
            <script>
            (function(){
                try {
                    const selectors = [
                        'section[data-testid="stSidebar"]',
                        'section[aria-expanded="true"]',
                        '[data-testid="stSidebarContent"]',
                        '[data-testid="stSidebarNav"]',
                        '[data-testid="stSidebarHeader"]',
                        '[data-testid="stSidebarUserContent"]',
                        'aside[aria-label="Sidebar"]',
                        'aside[aria-label="Main navigation"]',
                        'div[data-testid*="Sidebar"]',
                        'button[data-testid="stSidebarNavViewButton"]',
                        '.css-1d391kg',
                        '.css-1y4p8pa',
                        '.stSidebar'
                    ];
                    for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    }
                } catch(e){}
            })();
            </script>
            """,
            height=0,
        )
    except Exception:
        pass

    # Ensure the topbar auth links are rendered whenever theming is applied.
    try:
        render_topbar_auth_links()
    except Exception:
        # Avoid breaking pages if render fails for any reason
        pass


def render_topbar_auth_links():
    """Render small Login / Sign Up links in the top-right of the app header.

    Hides the links when a user is already signed in.
    """
    # Streamlit apps are server-driven; use session_state for dynamic UI
    user = st.session_state.get("user")

    # Render a single floating topbar container; its inner HTML changes depending on auth state.
    top = st.container()
    left, right = top.columns([9, 1])

    # Small navigation toggle on the left of the topbar. Navigation is hidden
    # by default and only appears when the user explicitly toggles it.
    with left:
        # Navigation toggle removed globally; no control rendered here.
        pass

    with right:
        if user:
            display = auth.get_display_name(user) or user
            initials = "".join([p[0].upper() for p in (display.split() or [user]) if p])[:2]
            safe_display = display.replace('"', "'")

            html_template = """
<style>
@media (max-width: 600px) {{ .topbar-auth {{ display: none; }} }}
.topbar-auth-container {{ position: fixed; top: 56px; right: 12px; z-index: 20000; }}
.topbar-auth-widget {{ background: rgba(255,255,255,0.95); padding:8px 10px; border-radius:8px; border:1px solid #eee; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display:inline-block; }}
.topbar-auth-widget .avatar {{ width:30px;height:30px;border-radius:50%;background: {PRIMARY}; color:white; display:inline-flex; align-items:center; justify-content:center; font-weight:700; }}
.topbar-auth-widget .display {{ margin-left:8px; font-weight:600; color:#333; display:inline-block }}
.topbar-auth-widget .menu {{ margin-top:6px; display:none; text-align:right }}
.topbar-auth-widget a {{ color: {SECONDARY}; text-decoration:none; font-weight:600 }}
/* Show menu on hover for more reliable UX */
.topbar-auth-widget:hover .menu {{ display: block !important; }}
</style>
<div class="topbar-auth-container">
    <div class="topbar-auth-widget" id="topbar-auth-widget">
        <div style="cursor:default; display:flex; align-items:center; gap:8px;">
            <div class="avatar">{INITIALS}</div>
            <div class="display">{DISPLAY}</div>
        </div>
        <div class="menu" id="topbar-auth-menu">
            <a href="/profile" style="margin-right:8px;" target="_self">Profile</a>
            <a href="/logout" target="_self">Logout</a>
        </div>
    </div>
</div>
"""

            html = html_template.format(
                INITIALS=initials,
                DISPLAY=safe_display,
                PRIMARY=THEME_COLORS["primary"],
                SECONDARY=THEME_COLORS["secondary"],
            )

            st.markdown(html, unsafe_allow_html=True)
        else:
            # Render centered Log in / Sign up links under the top header (below "Deploy")
            html = f"""
<style>
@media (max-width: 600px) {{ .topbar-auth-center {{ display: none; }} }}
.topbar-auth-center {{ position: fixed; top: 56px; left: 50%; transform: translateX(-50%); z-index: 20000; background: rgba(255,255,255,0.95); padding:6px 10px; border-radius:6px; border:1px solid #eee; box-shadow: 0 2px 6px rgba(0,0,0,0.08); display:inline-block; }}
.topbar-auth-center a {{ color: {THEME_COLORS['secondary']}; text-decoration: none; font-weight: 600; margin: 0 8px; }}
</style>
<div class="topbar-auth-center">
    <a href="/login" target="_self">Log in</a>
    <a href="/signup" target="_self">Sign up</a>
</div>
"""

            st.markdown(html, unsafe_allow_html=True)


def safe_rerun():
    """Rerun the Streamlit app in a way that's compatible across Streamlit versions.

    Tries `st.experimental_rerun()` first; if not available, falls back to a client-side reload.
    """
    try:
        # Preferred method when available
        rerun = getattr(st, "experimental_rerun", None)
        if callable(rerun):
            rerun()
            return
    except Exception:
        pass

    # Fallback: client-side reload via injected JS
    try:
        components.html("<script>window.location.reload();</script>", height=0)
    except Exception:
        # Last-resort: no-op
        return
