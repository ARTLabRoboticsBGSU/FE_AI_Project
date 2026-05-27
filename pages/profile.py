import streamlit as st
from lib import auth
from lib.ui import apply_theme_css, render_topbar_auth_links, safe_rerun


st.set_page_config(page_title="Profile", page_icon='assets/favicon.png')
apply_theme_css()
render_topbar_auth_links()


def main():
    user = st.session_state.get("user")
    if not user:
        st.info("You are not signed in. Please log in first.")
        return

    display = auth.get_display_name(user) or user
    st.markdown(f"# Profile — {display}")

    st.markdown("**Username:** " + user)
    st.markdown("**Display name:** " + (display or ""))

    st.markdown("---")
    if st.button("Sign out"):
        st.session_state.pop("user", None)
        safe_rerun()


if __name__ == '__main__':
    main()
