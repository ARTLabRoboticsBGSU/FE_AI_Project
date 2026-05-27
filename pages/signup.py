import streamlit as st
from config import APP_NAME, THEME_COLORS
from lib import auth
from lib.ui import apply_theme_css, render_topbar_auth_links, safe_rerun


st.set_page_config(page_title=f"Sign Up - {APP_NAME}", page_icon='assets/favicon.png')
apply_theme_css()
render_topbar_auth_links()


def main():
    # Render title inside the same styled card so it aligns with the form
    # st.markdown("<div class='tool-card'>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='margin:0 0 12px 0; color: {THEME_COLORS['primary']};'>Create an account for {APP_NAME}</h2>", unsafe_allow_html=True)

    if "user" in st.session_state and st.session_state["user"]:
        display = auth.get_display_name(st.session_state["user"]) or st.session_state["user"]
        st.success(f"Already signed in as {display}")
        if st.button("Sign out"):
            st.session_state.pop("user", None)
            safe_rerun()
        return

    # Initialize form variables (avoid UnboundLocalError on reruns)
    username = ""
    email = ""
    display_name = ""
    password = ""
    confirm = ""
    submitted = False

    with st.form("signup_form"):
        username = st.text_input("Choose a username")
        email = st.text_input("Email address")
        display_name = st.text_input("Display name (optional)")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not username or not password or not email:
            st.error("Please provide a username, email, and password.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            ok, msg = auth.create_user(username, password, display_name or None, email=email)
            if ok:
                st.session_state["user"] = username
                st.success("Account created and signed in.")
                safe_rerun()
            else:
                st.error(msg)

    # Navigation back to login
    st.markdown("---")
    # Navigation back to login (anchor link for reliable navigation)
    st.markdown("---")
    st.markdown(
        "<a href='/login' target='_self' style='display:inline-block;padding:8px 12px;border-radius:6px;background:#f5f5f5;border:1px solid #e6e6e6;text-decoration:none;color:#333;font-weight:600;'>Already have an account? Log in</a>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
