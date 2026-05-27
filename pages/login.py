import streamlit as st
from config import APP_NAME, THEME_COLORS, PAGE_ICON
from lib import auth
from lib.ui import apply_theme_css, render_topbar_auth_links, safe_rerun
from lib import sessions


st.set_page_config(page_title=f"Login - {APP_NAME}", page_icon=PAGE_ICON)
apply_theme_css()
render_topbar_auth_links()


def main():
    """Simplified login: collect Full name and Course, then redirect."""
    st.markdown(f"<h2 style='margin:0 0 12px 0; color: {THEME_COLORS['primary']};'>Welcome to {APP_NAME}</h2>", unsafe_allow_html=True)

    # Initialize defaults to avoid key errors on rerun
    full_name = st.session_state.get("full_name", "")
    course = st.session_state.get("course", None)

    with st.form("simple_login_form"):
        full_name = st.text_input("Full name", value=full_name, placeholder="Your full name")
        # Added SYE as an available course option
        course_options = ["ECE", "ROBO", "SYE"]
        try:
            default_index = 0 if course is None else course_options.index(course) if course in course_options else 0
        except Exception:
            default_index = 0
        course = st.selectbox("Course", options=course_options, index=default_index)
        submitted = st.form_submit_button("Continue")

    if submitted:
        if not (full_name or "").strip():
            st.error("Please enter your full name.")
            return

        # Save minimal session info and create a persistent session
        name_val = full_name.strip()
        st.session_state["full_name"] = name_val
        st.session_state["course"] = course
        st.session_state["selected_course_tab"] = course

        # Set in-memory user for immediate server-side checks and create
        # a persistent session so reloads survive.
        st.session_state["user"] = name_val
        sid = sessions.create_session(name_val)
        st.session_state["session_id"] = sid

        # Special-case: admin shortcut
        if name_val.lower() == "admin":
            st.session_state["_admin_override"] = True
            st.success("Admin detected — redirecting to Admin Analytics...")
            target = "/admin_home?sid=" + sid
            try:
                if hasattr(st, "switch_page"):
                    st.switch_page("pages/admin_home.py")
                    return
            except Exception:
                pass
                try:
                    import streamlit.components.v1 as components
                    # Persist sid to localStorage then navigate
                    components.html(f"<script>localStorage.setItem('session_id','{sid}'); window.location.href='/admin_home?sid={sid}';</script>", height=0)
                    return
                except Exception:
                    st.info("Please navigate to the Admin page from the menu.")

        st.success("Information saved — redirecting to Coding Companion...")

        # Try using Streamlit's switch_page when available
        # Redirect with the session id so the main app can pick it up on load
        target = "/?sid=" + sid
        if hasattr(st, "switch_page"):
            try:
                st.switch_page("pages/01_coding_companion.py")
                return
            except Exception:
                pass

        # Fallback: client-side redirect to root with sid query param
        try:
                import streamlit.components.v1 as components
                # Persist sid in browser localStorage and navigate (avoids cookie read on server)
                components.html(f"<script>localStorage.setItem('session_id','{sid}'); window.location.href='{target}';</script>", height=0)
                return
        except Exception:
            st.info("Please navigate to the Coding Companion page from the menu.")


if __name__ == "__main__":
    main()
