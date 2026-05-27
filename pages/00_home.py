import streamlit as st
from lib import home_views

from config import PAGE_ICON
st.set_page_config(page_title="Home - FE-AI", page_icon=PAGE_ICON)

def main():
    user = st.session_state.get("user")
    if user:
        try:
            from lib import auth
            if auth.is_admin(user):
                home_views.professor_home(user)
                return
        except Exception:
            pass

    # Default: render the student content (delegated to chatgpt's home)
    home_views.student_home()


if __name__ == "__main__":
    main()
