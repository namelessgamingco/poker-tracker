# sidebar.py — global sidebar visible on every page

import os
import streamlit as st
from auth import sign_out  # only sign_out; do NOT import require_auth here

APP_ENV = os.getenv("APP_ENV", "prod")


def render_sidebar():
    """
    Renders the global sidebar (Signed in block + Testing Mode toggle).

    We still rely on Streamlit's built-in multipage nav, but:
      - we style it nicely
      - for non-admins, we hide the last 3 nav items
        (97_Supabase_Debug, 98_QA_Checklist, 99_Admin)
    """

    # ---- Environment-aware UI tweaks ----

    # Hide Streamlit branding (toolbar, footer, deploy button) in ALL environments
    st.markdown(
        """
        <style>
          div[data-testid="stToolbar"] {
            display: none !important;
          }
          header[data-testid="stHeader"] {
            height: 0rem !important;
          }
          footer {
            visibility: hidden !important;
          }
          .stDeployButton {
            display: none !important;
          }
          [data-testid="stDecoration"] {
            display: none !important;
          }
          /* Hide "Made with Streamlit" footer */
          .viewerBadge_container__r5tak {
            display: none !important;
          }
          /* Hide bottom-right badges */
          .styles_viewerBadge__CvC9N {
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # DEV badge so we never confuse environments
    if APP_ENV == "dev":
        st.sidebar.markdown(
            """
            <div style="
                background-color:#ef4444;
                color:white;
                padding:4px 10px;
                border-radius:999px;
                font-size:12px;
                font-weight:700;
                display:inline-block;
                margin-bottom:10px;
                box-shadow:0 2px 8px rgba(0,0,0,0.45);
            ">
                DEV ENVIRONMENT
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Figure out if this user is admin (require_auth has already run on the page)
    is_admin = bool(st.session_state.get("is_admin", False))

    # --- Base nav styling (for everyone) ---
    st.markdown(
        """
        <style>
          /* Sidebar nav items (built-in) */
          section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            border-radius: 6px;
            padding: 6px 10px;
            color: #d1d5db !important;
            font-weight: 500;
          }
          section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
            background: rgba(255,255,255,0.06);
            color: #f9fafb !important;
          }
          /* Active page */
          section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: rgba(59,130,246,0.15);
            color: #ffffff !important;
            font-weight: 700;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Hide admin-only pages from non-admins ---
    # Assumes the admin-only pages are the LAST 3 entries in the multipage nav:
    #   97_Supabase_Debug, 98_QA_Checklist, 99_Admin
    if not is_admin:
        st.markdown(
            """
            <style>
              section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul li:nth-last-child(-n+3) {
                display: none !important;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )

    # --- Account block ---
    st.sidebar.markdown("### Account")
    email = st.session_state.get("email", "unknown")
    st.sidebar.markdown(f"**Signed in:** {email}")

    # 💬 Need help button → Discord ticket channel
    st.sidebar.markdown(
        """
        <a href="https://discord.com/channels/1169748589522718770/1268729463500439553"
           target="_blank"
           style="
             display:block;
             text-align:center;
             padding:8px 12px;
             background:#1f2937;
             border:1px solid #374151;
             border-radius:6px;
             color:white;
             text-decoration:none;
             font-weight:600;
             margin:6px 0 10px 0;
           ">
           💬 Need Help?
        </a>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Sign out"):
        sign_out()

    # --- Global controls ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Global Controls")

    if "testing_mode" not in st.session_state:
        st.session_state.testing_mode = False

    st.session_state.testing_mode = st.sidebar.toggle(
        "Testing Mode",
        value=bool(st.session_state.testing_mode),
        help="When on, sessions don't count toward weekly P/L.",
    )

    mode_note = "ON" if st.session_state.testing_mode else "OFF"
    st.sidebar.caption(f"Testing Mode is **{mode_note}**")

    # No custom page links here — we rely on the built-in list above.
