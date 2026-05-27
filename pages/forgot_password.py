import streamlit as st
from config import APP_NAME
from lib import auth
from lib import email as emailer
from lib.ui import apply_theme_css, render_topbar_auth_links, safe_rerun


st.set_page_config(page_title=f"Forgot Password - {APP_NAME}", page_icon='assets/favicon.png')
apply_theme_css()
render_topbar_auth_links()


def main():
    st.markdown(f"# Reset your {APP_NAME} password")

    if "user" in st.session_state and st.session_state["user"]:
        display = auth.get_display_name(st.session_state["user"]) or st.session_state["user"]
        st.success(f"Already signed in as {display}")
        if st.button("Sign out"):
            st.session_state.pop("user", None)
            safe_rerun()
        return

    # Step 1: request reset by email
    if "password_reset_email" not in st.session_state:
        st.session_state["password_reset_email"] = ""

    with st.form("request_reset_form"):
        email = st.text_input("Enter the email address for your account")
        submitted = st.form_submit_button("Send verification code")

    if submitted:
        if not email:
            st.error("Please enter an email address.")
        else:
            found = auth.find_user_by_email(email)
            if not found:
                st.error("No account found with that email address.")
            else:
                ok, payload = auth.create_password_reset(email)
                if not ok:
                    st.error(payload)
                else:
                    # try to send email
                    subject = f"{APP_NAME} password reset code"
                    body = f"Your password reset code is: {payload}\nThis code expires in 15 minutes."
                    sent_ok, sent_msg = emailer.send_email(email, subject, body)
                    st.session_state["password_reset_email"] = email
                    if sent_ok:
                        st.success("Verification code sent — check your email.")
                    else:
                        # For local/dev UX, show the code when email sending fails
                        st.warning("Failed to send email automatically. Use the code below to reset your password for testing.")
                        st.info(f"Reset code (dev): {payload}")

    # If we have an email in progress, show the code entry form
    if st.session_state.get("password_reset_email"):
        st.markdown("---")
        st.markdown("<div class='tool-card'>", unsafe_allow_html=True)
        with st.form("perform_reset_form"):
            code = st.text_input("Enter verification code")
            new_pass = st.text_input("New password", type="password")
            confirm = st.text_input("Confirm new password", type="password")
            submitted2 = st.form_submit_button("Reset password")
        st.markdown("</div>", unsafe_allow_html=True)

        if submitted2:
            if not code or not new_pass:
                st.error("Please provide the verification code and a new password.")
            elif new_pass != confirm:
                st.error("Passwords do not match.")
            else:
                ok, msg = auth.verify_password_reset(st.session_state["password_reset_email"], code, new_pass)
                if ok:
                    # auto-login
                    username = auth.find_user_by_email(st.session_state["password_reset_email"])
                    if username:
                        st.session_state["user"] = username
                    st.success("Password reset successful. You are now signed in.")
                    # clear
                    st.session_state.pop("password_reset_email", None)
                    safe_rerun()
                else:
                    st.error(msg)


if __name__ == "__main__":
    main()
