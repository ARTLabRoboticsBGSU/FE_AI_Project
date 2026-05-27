import streamlit as st
import streamlit.components.v1 as components

def main():
    # Clear user session and redirect to home
    if "user" in st.session_state:
        st.session_state.pop("user", None)

    # Also clear other auth-related session keys if present
    for k in ("full_name", "cur_page", "show_navigation"):
        if k in st.session_state:
            st.session_state.pop(k, None)

    # Remove persistent session if one exists
    try:
        from lib import sessions
        sid = st.session_state.get("session_id")
        if sid:
            sessions.delete_session(sid)
            st.session_state.pop("session_id", None)
    except Exception:
        pass

    # Prefer server-side switch when available so the login page is rendered.
    try:
        if hasattr(st, "switch_page"):
            st.switch_page("pages/login.py")
            return
    except Exception:
        pass

    # Fallback: clear the browser cookie and localStorage entry for `session_id`, then client-side redirect
    try:
        components.html("<script>document.cookie='session_id=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'; try{localStorage.removeItem('session_id')}catch(e){}; window.location.href='/login';</script>", height=0)
        return
    except Exception:
        pass


if __name__ == '__main__':
    main()
