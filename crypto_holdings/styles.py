"""Futuristic but readable Streamlit presentation."""

APP_CSS = r"""
<style>
    :root {
        --bg: #070B14;
        --panel: rgba(16, 23, 40, 0.86);
        --panel-2: rgba(20, 29, 50, 0.72);
        --stroke: rgba(137, 159, 204, 0.16);
        --text: #E8EDF8;
        --muted: #8C99B3;
        --cyan: #56E0E0;
        --violet: #846CFF;
    }
    html, body, [class*="css"] { font-family: Inter, "Segoe UI", ui-sans-serif, system-ui, sans-serif; }
    .stApp {
        background:
            radial-gradient(circle at 18% -10%, rgba(71, 83, 190, .24), transparent 38%),
            radial-gradient(circle at 88% 0%, rgba(31, 190, 177, .14), transparent 32%),
            linear-gradient(180deg, #080C16 0%, #070B14 55%, #090D18 100%);
        color: var(--text);
    }
    [data-testid="stHeader"] { background: rgba(7,11,20,.72); backdrop-filter: blur(16px); }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(13,19,34,.98), rgba(8,12,22,.98));
        border-right: 1px solid var(--stroke);
    }
    .block-container { max-width: 1540px; padding-top: 2.2rem; padding-bottom: 5rem; }
    h1, h2, h3 { font-family: "Segoe UI", Inter, sans-serif; letter-spacing: -0.035em; }
    h1 { font-size: clamp(2.1rem, 5vw, 4.6rem) !important; line-height: .98 !important; }
    h2 { font-size: 1.45rem !important; }
    p, label, .stMarkdown { color: var(--text); }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(20,29,50,.92), rgba(11,17,30,.92));
        border: 1px solid var(--stroke);
        border-radius: 18px;
        padding: 1.05rem 1.2rem;
        min-height: 118px;
        box-shadow: 0 16px 42px rgba(0,0,0,.17);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { font-family: "Space Grotesk", sans-serif; color: #F4F7FF; }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap: wrap; }
    [data-testid="stColumn"]:has([data-testid="stMetric"]) {
        flex: 1 1 178px !important;
        min-width: 178px !important;
        width: auto !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        min-height: 180px;
        border: 1px dashed rgba(86,224,224,.45);
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(86,224,224,.06), rgba(132,108,255,.08));
    }
    div[data-testid="stPlotlyChart"] {
        background: linear-gradient(160deg, rgba(16,23,40,.82), rgba(9,14,26,.82));
        border: 1px solid var(--stroke);
        border-radius: 20px;
        padding: .55rem;
        overflow: hidden;
        box-shadow: 0 18px 50px rgba(0,0,0,.18);
    }
    iframe[title="streamlit_plotly_events.plotly_events"] {
        border: 1px solid var(--stroke) !important;
        border-radius: 20px;
        background: linear-gradient(160deg, rgba(16,23,40,.82), rgba(9,14,26,.82));
        box-shadow: 0 18px 50px rgba(0,0,0,.18);
    }
    [data-testid="stDataFrame"] { border: 1px solid var(--stroke); border-radius: 16px; overflow: hidden; }
    [data-testid="stExpander"] {
        background: rgba(15,22,38,.66);
        border: 1px solid var(--stroke);
        border-radius: 16px;
    }
    .hero-shell {
        position: relative;
        padding: clamp(1.3rem, 4vw, 3.2rem) 0 1.8rem;
        overflow: hidden;
    }
    .hero-kicker, .section-kicker {
        display: inline-flex; align-items: center; gap: .55rem;
        color: #69E6DD; font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
    }
    .hero-kicker::before { content:""; width: 28px; height: 1px; background: #69E6DD; box-shadow: 0 0 12px #69E6DD; }
    .hero-title { max-width: 980px; margin: 1.1rem 0 1rem; }
    .hero-title .gradient {
        background: linear-gradient(90deg, #F4F7FF 5%, #75E8E0 53%, #A58CFF 95%);
        -webkit-background-clip: text; color: transparent;
    }
    .hero-sub { max-width: 760px; color: #A8B2C8; font-size: 1.05rem; line-height: 1.75; }
    .feature-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1rem; margin:1.6rem 0 2rem; }
    .feature-card {
        padding: 1.2rem; min-height: 145px; border: 1px solid var(--stroke); border-radius: 18px;
        background: linear-gradient(145deg, rgba(18,27,47,.88), rgba(10,15,27,.8));
    }
    .feature-icon { color:#6BE4DB; font-family:"Space Grotesk"; font-size:.78rem; letter-spacing:.1em; }
    .feature-card h3 { font-size:1rem; margin:.75rem 0 .4rem; }
    .feature-card p { color:var(--muted); font-size:.85rem; line-height:1.55; margin:0; }
    .dashboard-head { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin-bottom:.65rem; }
    .dashboard-title { margin:0; font-size:2rem !important; }
    .as-of { color:var(--muted); font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; }
    .section-copy { color:var(--muted); margin-top:-.4rem; margin-bottom:1rem; max-width:820px; font-size:.9rem; }
    .status-pill {
        display:inline-flex; padding:.3rem .62rem; border-radius:999px; font-size:.7rem; font-weight:700;
        border:1px solid rgba(86,224,224,.28); color:#76E6DE; background:rgba(86,224,224,.08);
    }
    .micro-note { color:var(--muted); font-size:.76rem; line-height:1.5; }
    .warn-panel { border-left:3px solid #FFB454; padding:.75rem 1rem; background:rgba(255,180,84,.07); border-radius:0 12px 12px 0; }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 12px; border: 1px solid rgba(112,226,220,.32);
        background: linear-gradient(135deg, rgba(38,118,127,.35), rgba(91,74,170,.35)); color:#F5F7FF;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover { border-color:#65DED7; color:white; }
    @media (max-width: 800px) {
        .feature-grid { grid-template-columns:1fr; }
        .dashboard-head { align-items:flex-start; flex-direction:column; }
        .block-container { padding-left:1rem; padding-right:1rem; }
    }
</style>
"""
