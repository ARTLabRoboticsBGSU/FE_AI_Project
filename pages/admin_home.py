import streamlit as st
from lib import home_views, auth
from lib import analytics_helpers

from config import PAGE_ICON
from lib.ui import apply_theme_css
from pathlib import Path
import subprocess
from config import PROJECT_ROOT

st.set_page_config(page_title="Admin Home - FE-AI", page_icon=PAGE_ICON)
# Apply shared theme CSS (also hides Streamlit's left sidebar/navigation)
apply_theme_css()

def main():
    user = st.session_state.get("user")
    admin_override = st.session_state.get("_admin_override", False)
    if not user:
        st.warning("Not signed in.")
        return

    # mark current page so topbar can adapt (hide the navigation toggle on admin)
    try:
        st.session_state['cur_page'] = 'admin_home'
    except Exception:
        pass

    if not auth.is_admin(user) and not admin_override:
        st.warning("You are not an admin. Redirecting to student home...")
        home_views.student_home()
        return

    # Either the user is marked admin in users.json or an override was set at login.
    try:
        with st.spinner('Refreshing Bloom analytics (this may call the local LLM)...'):
            analytics_helpers.refresh_bloom_counts()
    except Exception:
        # Fail silently; professor_home will fall back to local inference if needed.
        pass
    # Also regenerate error files from logs so Misconception charts are current
    try:
        scripts_dir = Path(PROJECT_ROOT) / 'scripts'
        compute_script = scripts_dir / 'compute_errors.py'
        if compute_script.exists():
            subprocess.run(['python3', str(compute_script)], cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    home_views.professor_home(user)


if __name__ == "__main__":
    main()
