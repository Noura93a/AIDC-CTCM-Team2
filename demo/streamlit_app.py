import html
import os
import time

import requests
import streamlit as st


# ============================================================
# 1) APP CONFIGURATION
#    Edit backend URL, supported files, or model labels here.
# ============================================================

API_DEFAULT = os.getenv(
    "CTCM_API_URL",
    "http://10.0.0.15:30801",
)

SUPPORTED_FILES = [
    "pdf",
    "pptx",
    "xlsx",
    "xls",
    "ipynb",
    "md",
    "txt",
    "docx",
]

MODELS = {
    "GPT-4o-mini · Cloud API": "openai",
    "Qwen2.5-VL-3B · Self-hosted GPU": "qwen",
}


# ============================================================
# 2) STREAMLIT PAGE SETTINGS
#    Keep the Streamlit menu visible because it contains the
#    official System / Light / Dark theme switch.
# ============================================================

st.set_page_config(
    page_title="CTCM | Content Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# 3) SESSION STATE
#    Keeps the latest analysis result after Streamlit reruns.
# ============================================================

st.session_state.setdefault("result", None)
st.session_state.setdefault("elapsed", None)
st.session_state.setdefault("model_label", None)


# ============================================================
# 4) CUSTOM CSS
#    IMPORTANT:
#    - Native Streamlit widgets keep their own official theme.
#    - Custom HTML uses Streamlit CSS theme variables.
#    - This keeps Light, Dark, and System synchronized.
# ============================================================

st.markdown(
    """
    <style>
        :root {
            --ctcm-teal-glow: rgba(20, 184, 166, 0.18);
        }

        /* ----------------------------------------------------
           Page ambience
           ---------------------------------------------------- */
        .stApp {
            background:
                radial-gradient(
                    circle at 10% 3%,
                    color-mix(
                        in srgb,
                        var(--st-primary-color) 18%,
                        transparent
                    ),
                    transparent 30%
                ),
                radial-gradient(
                    circle at 90% 7%,
                    var(--ctcm-teal-glow),
                    transparent 28%
                ),
                var(--st-background-color) !important;

            background-attachment: fixed !important;
        }

        header[data-testid="stHeader"] {
            background: transparent;
        }

        #MainMenu {
            visibility: visible;
        }

        footer {
            visibility: hidden;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.8rem;
            padding-bottom: 3rem;
            animation: page-enter .45s ease both;
        }

        /* ----------------------------------------------------
           Hero card
           Stronger border + shadow so it is clearly visible
           in both Light and Dark themes.
           ---------------------------------------------------- */
/* ====================================================
   HERO CARD
   Strong visible card in both Light and Dark themes.
   ==================================================== */

.ctcm-hero {
    position: relative;
    isolation: isolate;
    overflow: hidden;

    padding: 2.55rem 2.65rem;
    margin-bottom: 1.5rem;

    border-radius: 26px;

    /* Visible purple-tinted border in both themes */
    border: 1px solid
        color-mix(
            in srgb,
            var(--st-primary-color) 35%,
            var(--st-border-color)
        );

    /* Theme-aware card background */
    background:
        var(--st-secondary-background-color);

    /* Strong physical shadow + soft purple glow */
    box-shadow:
        0 18px 45px rgba(15, 23, 42, 0.18),
        0 8px 18px rgba(15, 23, 42, 0.08),
        0 0 38px rgba(109, 93, 251, 0.14);

    transition:
        transform 0.22s ease,
        box-shadow 0.22s ease,
        border-color 0.22s ease;

    animation: hero-enter 0.58s ease both;
}
/* Hero hover animation */
.ctcm-hero:hover {
    transform: translateY(-4px);

    box-shadow:
        0 26px 60px rgba(15, 23, 42, 0.22),
        0 10px 22px rgba(15, 23, 42, 0.10),
        0 0 52px rgba(109, 93, 251, 0.22);
}

        .ctcm-hero::before,
        .ctcm-hero::after {
            content: "";
            position: absolute;
            z-index: -1;
            border-radius: 999px;
            pointer-events: none;
            filter: blur(8px);
        }

        .ctcm-hero::before {
            width: 355px;
            height: 355px;
            left: -120px;
            top: -145px;

            background:
                radial-gradient(
                    circle,
                    color-mix(
                        in srgb,
                        var(--st-primary-color) 34%,
                        transparent
                    ) 0%,
                    transparent 70%
                );

            animation:
                glow-left
                8.5s
                ease-in-out
                infinite
                alternate;
        }

        .ctcm-hero::after {
            width: 315px;
            height: 315px;
            right: -95px;
            top: -105px;

            background:
                radial-gradient(
                    circle,
                    var(--ctcm-teal-glow) 0%,
                    transparent 70%
                );

            animation:
                glow-right
                10s
                ease-in-out
                infinite
                alternate;
        }

        .ctcm-eyebrow {
            color: var(--st-primary-color);
            font-size: .78rem;
            font-weight: 800;
            letter-spacing: .14em;
            text-transform: uppercase;
            margin-bottom: .7rem;
        }

        .ctcm-title {
            color: var(--st-text-color);
            font-size: clamp(2rem, 4vw, 2.9rem);
            line-height: 1.06;
            font-weight: 850;
            margin-bottom: .9rem;
        }

        .ctcm-subtitle {
            color:
                color-mix(
                    in srgb,
                    var(--st-text-color) 72%,
                    transparent
                );

            font-size: 1.03rem;
            max-width: 820px;
            line-height: 1.65;
        }

        /* ----------------------------------------------------
           Result section heading
           ---------------------------------------------------- */
        .ctcm-section-heading {
            display: flex;
            align-items: center;
            gap: .55rem;
            margin: .4rem 0 .8rem 0;
        }

        .ctcm-section-heading h2 {
            margin: 0;
            padding: 0;
        }

        /* ----------------------------------------------------
           Result cards
           Native container border + light polish only.
           ---------------------------------------------------- */
        [class*="st-key-result-"],
        [class*="st-key-process-"] {
            transition:
                transform .18s ease,
                box-shadow .18s ease;
        }

        [class*="st-key-result-"]:hover,
        [class*="st-key-process-"]:hover {
            transform: translateY(-2px);
        }

        [class*="st-key-result-metric-"],
        [class*="st-key-process-metric-"] {
            min-height: 120px;
        }

        .st-key-result-file,
        .st-key-result-model {
            min-height: 120px;
        }

        .ctcm-card-label {
            color:
                color-mix(
                    in srgb,
                    var(--st-text-color) 60%,
                    transparent
                );

            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .09em;
            text-transform: uppercase;
            margin-bottom: .45rem;
        }

        .ctcm-metric-value {
            color: var(--st-text-color);
            font-size: clamp(1.15rem, 1.8vw, 1.55rem);
            line-height: 1.15;
            font-weight: 760;
            letter-spacing: -0.02em;
            overflow-wrap: anywhere;
            margin-top: .1rem;
        }

        .ctcm-detail-value {
            color: var(--st-text-color);
            font-size: .98rem;
            line-height: 1.58;
            font-weight: 520;
            overflow-wrap: anywhere;
        }

        /* ----------------------------------------------------
           Footer
           ---------------------------------------------------- */
        .ctcm-footer {
            color:
                color-mix(
                    in srgb,
                    var(--st-text-color) 52%,
                    transparent
                );

            text-align: center;
            font-size: .82rem;
            line-height: 1.8;
            margin-top: 2.7rem;
            padding-top: 1rem;
        }

        /* ----------------------------------------------------
           Animations
           ---------------------------------------------------- */
        @keyframes page-enter {
            from {
                opacity: 0;
                transform: translateY(4px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes hero-enter {
            from {
                opacity: 0;
                transform:
                    translateY(9px)
                    scale(.995);
            }

            to {
                opacity: 1;
                transform:
                    translateY(0)
                    scale(1);
            }
        }

        @keyframes glow-left {
            from {
                transform:
                    translate(0, 0)
                    scale(1);
            }

            to {
                transform:
                    translate(38px, 18px)
                    scale(1.09);
            }
        }

        @keyframes glow-right {
            from {
                transform:
                    translate(0, 0)
                    scale(1);
            }

            to {
                transform:
                    translate(-30px, 24px)
                    scale(1.11);
            }
        }

        @media (max-width: 700px) {
            .ctcm-hero {
                padding: 1.7rem 1.45rem;
            }

            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .block-container,
            .ctcm-hero,
            .ctcm-hero::before,
            .ctcm-hero::after {
                animation: none !important;
                transition: none !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 5) HELPER FUNCTIONS
#    Reusable rendering helpers for cards and values.
# ============================================================

def escape_text(value):
    """Escape user/model text before rendering it inside HTML."""
    return html.escape("" if value is None else str(value))


def split_pipe(value):
    """Convert a pipe-separated API string into a clean list."""
    if not value:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    return [
        item.strip()
        for item in str(value).split("|")
        if item.strip()
    ]


def render_metric_tile(column, key, label, value):
    """Render a compact metric tile without truncating long text."""
    with column:
        with st.container(
            border=True,
            key=key,
        ):
            st.html(
                f'<div class="ctcm-card-label">'
                f'{escape_text(label)}'
                f'</div>'
                f'<div class="ctcm-metric-value">'
                f'{escape_text(value)}'
                f'</div>'
            )


def render_detail_card(key, label, value):
    """Render one full information card."""
    with st.container(
        border=True,
        key=key,
    ):
        st.html(
            f'<div class="ctcm-card-label">'
            f'{escape_text(label)}'
            f'</div>'
            f'<div class="ctcm-detail-value">'
            f'{escape_text(value)}'
            f'</div>'
        )


def render_badge_card(key, label, items, color):
    """Render a card containing theme-aware Streamlit badges."""
    with st.container(
        border=True,
        key=key,
    ):
        st.html(
            f'<div class="ctcm-card-label">'
            f'{escape_text(label)}'
            f'</div>'
        )

        if not items:
            st.caption("No results returned")
            return

        for item in items:
            st.badge(
                str(item),
                color=color,
            )


# ============================================================
# 6) BACKEND HEALTH CHECK
#    Cached briefly to avoid unnecessary health requests.
# ============================================================

@st.cache_data(
    ttl=10,
    show_spinner=False,
)
def check_health(api_url):
    """Return backend online state and health JSON."""
    try:
        response = requests.get(
            f"{api_url.rstrip('/')}/health",
            timeout=3,
        )

        if response.status_code != 200:
            return False, None

        return True, response.json()

    except Exception:
        return False, None


# ============================================================
# 7) HERO SECTION
# ============================================================

st.html(
    '<div class="ctcm-hero">'
    '<div class="ctcm-eyebrow">'
    'AI Data Center Capstone · Team 2'
    '</div>'
    '<div class="ctcm-title">'
    'Content Tagging & Competency Mapping'
    '</div>'
    '<div class="ctcm-subtitle">'
    'Turn learning content into structured intelligence. '
    'Upload educational material and use AI to summarize it, '
    'classify difficulty, identify topics, and map competency skills.'
    '</div>'
    '</div>'
)


# ============================================================
# 8) THEME INFO
#    Streamlit owns System / Light / Dark switching.
# ============================================================

st.caption(
    "Theme: use ⋮ in the top-right corner to switch "
    "System / Light / Dark."
)


# ============================================================
# 9) ADVANCED SETTINGS
# ============================================================

api_url = API_DEFAULT

with st.expander(
    "Advanced settings"
):
    api_url = st.text_input(
        "Backend API endpoint",
        value=API_DEFAULT,
    )

    if st.button(
        "Refresh backend status",
        key="refresh_backend",
    ):
        check_health.clear()


# ============================================================
# 10) BACKEND STATUS
# ============================================================

is_online, health_data = check_health(
    api_url
)

if is_online:
    model_count = len(
        (health_data or {}).get(
            "models",
            [],
        )
    )

    st.success(
        f"Backend Online · {model_count} models available"
    )
else:
    st.warning(
        "Backend Busy / Unreachable"
    )


# ============================================================
# 11) INPUT AREA
# ============================================================

left_column, right_column = st.columns(
    [1.55, 1],
    gap="large",
)

with left_column:
    st.markdown(
        "**1 · LEARNING CONTENT**"
    )

    uploaded_file = st.file_uploader(
        "Upload learning content",
        type=SUPPORTED_FILES,
        label_visibility="collapsed",
        help=(
            "Supported: PDF, PPTX, XLSX, XLS, "
            "IPYNB, MD, TXT, DOCX"
        ),
    )

with right_column:
    st.markdown(
        "**2 · AI MODEL**"
    )

    selected_model_label = st.selectbox(
        "AI model",
        list(MODELS.keys()),
        label_visibility="collapsed",
    )

    selected_model_key = MODELS[
        selected_model_label
    ]

    if selected_model_key == "openai":
        st.caption(
            "Cloud API · Does not use the local GPU."
        )
    else:
        st.caption(
            "Self-hosted · Uses the team's deployed NVIDIA GPU workload."
        )


# ============================================================
# 12) ANALYZE BUTTON
# ============================================================

analyze_clicked = st.button(
    "Analyze Content",
    type="primary",
    disabled=uploaded_file is None,
    use_container_width=True,
)

if uploaded_file is None:
    st.caption(
        "Upload a learning file to enable analysis."
    )


# ============================================================
# 13) API REQUEST
# ============================================================

if analyze_clicked and uploaded_file is not None:
    endpoint = (
        f"{api_url.rstrip('/')}/v1/tag/upload"
    )

    request_files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type
            or "application/octet-stream",
        )
    }

    started_at = time.perf_counter()

    try:
        with st.spinner(
            f"Analyzing {uploaded_file.name} "
            f"with {selected_model_label}..."
        ):
            response = requests.post(
                endpoint,
                files=request_files,
                data={
                    "model": selected_model_key
                },
                timeout=600,
            )

        client_elapsed = (
            time.perf_counter()
            - started_at
        )

        if response.status_code != 200:
            st.error(
                "Analysis failed with "
                f"HTTP {response.status_code}."
            )

            with st.expander(
                "Backend response"
            ):
                st.code(
                    response.text
                )

            st.stop()

        result = response.json()

        st.session_state.result = result
        st.session_state.elapsed = client_elapsed
        st.session_state.model_label = (
            selected_model_label
        )

        check_health.clear()

    except requests.exceptions.Timeout:
        st.error(
            "The request timed out after 10 minutes."
        )
        st.stop()

    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to the CTCM backend."
        )
        st.stop()

    except requests.exceptions.RequestException as exc:
        st.error(
            f"Backend request failed: {exc}"
        )
        st.stop()

    except ValueError:
        st.error(
            "The backend returned invalid JSON."
        )
        st.stop()


# ============================================================
# 14) RESULTS SECTION
# ============================================================

result = st.session_state.result

if result:
    st.markdown(
        "## ✨ Analysis Results"
    )

    st.success(
        "Analysis completed successfully."
    )

    # --------------------------------------------------------
    # 14A) Main overview metrics
    # --------------------------------------------------------

    confidence = result.get(
        "confidence"
    )

    confidence_text = (
        f"{confidence * 100:.0f}%"
        if isinstance(
            confidence,
            (int, float),
        )
        else "N/A"
    )

    difficulty_text = (
        result.get(
            "difficulty_level"
        )
        or "N/A"
    )

    content_type_text = (
        result.get(
            "content_type"
        )
        or "N/A"
    )

    end_to_end_text = (
        f"{(st.session_state.elapsed or 0):.1f}s"
    )

    overview_columns = st.columns(
        4,
        gap="medium",
    )

    render_metric_tile(
        overview_columns[0],
        "result-metric-difficulty",
        "Difficulty",
        difficulty_text,
    )

    render_metric_tile(
        overview_columns[1],
        "result-metric-confidence",
        "Confidence",
        confidence_text,
    )

    render_metric_tile(
        overview_columns[2],
        "result-metric-content-type",
        "Content type",
        content_type_text,
    )

    render_metric_tile(
        overview_columns[3],
        "result-metric-e2e",
        "End-to-end time",
        end_to_end_text,
    )

    # --------------------------------------------------------
    # 14B) File and model
    # --------------------------------------------------------

    info_left, info_right = st.columns(
        2,
        gap="medium",
    )

    with info_left:
        render_detail_card(
            "result-file",
            "File",
            result.get(
                "file_name"
            )
            or "Unknown",
        )

    with info_right:
        render_detail_card(
            "result-model",
            "Model used",
            result.get(
                "model_name"
            )
            or st.session_state.model_label
            or "Unknown",
        )

    # --------------------------------------------------------
    # 14C) Content summary
    # --------------------------------------------------------

    render_detail_card(
        "result-summary",
        "Content summary",
        result.get(
            "content_summary"
        )
        or "No summary returned.",
    )

    # --------------------------------------------------------
    # 14D) Tags and competency skills
    # --------------------------------------------------------

    tags_column, skills_column = st.columns(
        2,
        gap="medium",
    )

    with tags_column:
        render_badge_card(
            "result-tags",
            "Predicted tags",
            split_pipe(
                result.get(
                    "predicted_tags"
                )
            ),
            "violet",
        )

    with skills_column:
        render_badge_card(
            "result-skills",
            "Predicted skills",
            split_pipe(
                result.get(
                    "predicted_skills"
                )
            ),
            "green",
        )

    # --------------------------------------------------------
    # 14E) Learning notes / objectives
    # --------------------------------------------------------

    if result.get(
        "notes"
    ):
        render_detail_card(
            "result-objectives",
            "Learning notes / objectives",
            result[
                "notes"
            ],
        )

    # --------------------------------------------------------
    # 14F) Processing details
    # --------------------------------------------------------

    st.markdown(
        "### ⚙️ Processing Details"
    )

    backend_latency = result.get(
        "latency_sec"
    )

    total_tokens = result.get(
        "total_tokens"
    )

    generation_speed = result.get(
        "tokens_per_sec"
    )

    estimated_cost = result.get(
        "est_cost_usd"
    )

    latency_text = (
        f"{backend_latency:.2f}s"
        if isinstance(
            backend_latency,
            (int, float),
        )
        else "N/A"
    )

    token_text = (
        f"{total_tokens:,}"
        if isinstance(
            total_tokens,
            (int, float),
        )
        else "N/A"
    )

    speed_text = (
        f"{generation_speed:.2f} tok/s"
        if isinstance(
            generation_speed,
            (int, float),
        )
        else "N/A"
    )

    cost_text = (
        f"${estimated_cost:.4f}"
        if isinstance(
            estimated_cost,
            (int, float),
        )
        else "N/A"
    )

    process_columns = st.columns(
        4,
        gap="medium",
    )

    render_metric_tile(
        process_columns[0],
        "process-metric-latency",
        "Model latency",
        latency_text,
    )

    render_metric_tile(
        process_columns[1],
        "process-metric-tokens",
        "Total tokens",
        token_text,
    )

    render_metric_tile(
        process_columns[2],
        "process-metric-speed",
        "Generation speed",
        speed_text,
    )

    render_metric_tile(
        process_columns[3],
        "process-metric-cost",
        "Estimated cost",
        cost_text,
    )

    # --------------------------------------------------------
    # 14G) Technical details
    # --------------------------------------------------------

    with st.expander(
        "Technical details"
    ):
        technical_left, technical_right = st.columns(
            2,
            gap="medium",
        )

        with technical_left:
            st.markdown(
                "**Structured output valid**  \n"
                f"{result.get('is_valid_output', 'N/A')}"
            )

            st.markdown(
                "**Prompt tokens**  \n"
                f"{result.get('prompt_tokens', 0)}"
            )

        with technical_right:
            st.markdown(
                "**Completion tokens**  \n"
                f"{result.get('completion_tokens', 0)}"
            )

            st.markdown(
                "**Hallucinated skills detected**  \n"
                f"{result.get('n_hallucinated_skills', 0)}"
            )

        st.markdown(
            "#### Raw API response"
        )

        st.json(
            result
        )

    # --------------------------------------------------------
    # 14H) Clear results
    # --------------------------------------------------------

    if st.button(
        "Clear Results",
        key="clear_results",
    ):
        st.session_state.result = None
        st.session_state.elapsed = None
        st.session_state.model_label = None
        st.rerun()


# ============================================================
# 15) FOOTER
# ============================================================

st.html(
    '<div class="ctcm-footer">'
    'CTCM · Content Tagging & Competency Mapping '
    '· AI Data Center Capstone · Team 2<br>'
    'Hadeel · Noura · Shurooq · Duaa'
    '</div>'
)
