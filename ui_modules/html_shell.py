
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def _topbar_markup(subtitle: str) -> str:
    upload_active = " is-active" if subtitle in {"Upload & Run", "Uploaded Data Preview"} else ""
    analysis_active = " is-active" if ("Experiment Results" in subtitle or subtitle == "Run Detail") else ""
    policy_active = " is-active" if ("Policy Comparison" in subtitle or "Policy Trade-off" in subtitle or "Policy Comparison Workspace" in subtitle) else ""
    logo_path = ROOT / "logo_small.png"
    logo_src = f"/local-file?{urlencode({'path': logo_path})}"
    return f"""
      <header class="topbar-shell app-header-shell">
        <div class="topbar-inner app-brand-row">
          <div class="brand-lockup">
            <div class="brand-badge brand-logo-frame" aria-label="CoRenew logo">
              <img class="brand-logo-img" src="{logo_src}" alt="CoRenew logo" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';" />
              <span class="brand-logo-fallback">CO</span>
            </div>
            <div class="brand-copy">
              <h1 class="app-title">CoRenew</h1>
              <div class="app-subtitle">Negotiation playback, policy comparison, and result analysis dashboard</div>
            </div>
          </div>
          <div class="topbar-aside">
            <div class="topbar-viz" aria-hidden="true">
              <svg class="negotiation-svg" viewBox="0 0 360 112" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="16" y="23" width="92" height="62" rx="18" class="viz-node viz-node-owners"/>
                <rect x="132" y="12" width="92" height="62" rx="18" class="viz-node viz-node-planner"/>
                <rect x="248" y="27" width="92" height="62" rx="18" class="viz-node viz-node-developer"/>
                <text x="34" y="44" class="viz-overline">Owners</text>
                <text x="34" y="66" class="viz-value">Households</text>
                <text x="150" y="33" class="viz-overline">Planner</text>
                <text x="150" y="55" class="viz-value">Policy</text>
                <text x="266" y="48" class="viz-overline">Developer</text>
                <text x="266" y="70" class="viz-value">Offer</text>
                <path d="M94 54 C128 18 176 18 246 42" class="viz-route"/>
                <path d="M94 58 C138 96 188 96 264 70" class="viz-route viz-route-soft"/>
                <path d="M178 45 C214 18 258 18 308 46" class="viz-route"/>
                <circle cx="95" cy="54" r="3.6" class="viz-anchor"/>
                <circle cx="179" cy="45" r="3.6" class="viz-anchor"/>
                <circle cx="262" cy="59" r="3.6" class="viz-anchor"/>
                <g class="mini-person person-amber">
                  <circle cx="0" cy="-6" r="4" fill="currentColor"/>
                  <path d="M0 -1 L0 8 M-5 2 L0 -1 L5 2 M-4 11 L0 8 L4 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <animateMotion dur="6.2s" repeatCount="indefinite" path="M94 54 C128 18 176 18 246 42" />
                </g>
                <g class="mini-person person-teal">
                  <circle cx="0" cy="-6" r="4" fill="currentColor"/>
                  <path d="M0 -1 L0 8 M-5 2 L0 -1 L5 2 M-4 11 L0 8 L4 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <animateMotion dur="7.8s" repeatCount="indefinite" path="M264 70 C216 92 168 92 112 58" />
                </g>
                <g class="mini-person person-slate">
                  <circle cx="0" cy="-6" r="4" fill="currentColor"/>
                  <path d="M0 -1 L0 8 M-5 2 L0 -1 L5 2 M-4 11 L0 8 L4 11" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  <animateMotion dur="5.6s" repeatCount="indefinite" path="M178 45 C214 18 258 18 308 46" />
                </g>
              </svg>
            </div>
            <div class="mode-pill">Local Mode</div>
          </div>
        </div>
        <nav class="topbar-nav app-page-tabs" aria-label="Primary pages">
          <a class="{upload_active}" href="/run/setup">Upload &amp; Run</a>
          <a class="{analysis_active}" href="/phase2/global?{urlencode({'phase2_root': _default_output_dir_ui()})}">Experiment Results Analysis</a>
          <a class="{policy_active}" href="/phase2/compare?{urlencode({'phase2_root': _default_output_dir_ui(), 'mode': 'aggregate_policy'})}">Policy Comparison</a>
        </nav>
      </header>
    """


def _html_shell(title: str, body: str, embedded: bool = False) -> str:
    body_class = "embedded-body" if embedded else ""
    topbar_html = "" if embedded else _topbar_markup(title)
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>{title}</title>
      <style>
        :root {{
          --space-1: 4px;
          --space-2: 8px;
          --space-3: 12px;
          --space-4: 16px;
          --space-5: 24px;
          --space-6: 32px;
          --space-7: 40px;
          --space-8: 48px;
          --space-9: 64px;
          --container-mobile: 16px;
          --container-tablet: 24px;
          --container-desktop: 32px;
          --content-max: 1020px;
          --grid-gutter: 24px;
          --app-bg: #ffffff;
          --surface: #ffffff;
          --surface-soft: #ffffff;
          --border: #e4e4e7;
          --border-strong: #d4d4d8;
          --text: #09090b;
          --muted: #71717a;
          --accent: #36AABF;
          --shadow-soft: 0 1px 2px rgba(0, 0, 0, 0.04);
          --shadow-card: 0 2px 10px rgba(0, 0, 0, 0.06);
          --radius-xl: 28px;
          --radius-lg: 22px;
          --radius-md: 16px;
          --radius-sm: 12px;
        }}
        body {{
          margin: 0;
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: var(--app-bg);
          color: var(--text);
        }}
        .topbar-shell {{
          background: #ffffff;
          border-bottom: 1px solid #dbe3ef;
          box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02);
        }}
        .topbar-inner,
        .topbar-nav {{
          max-width: 1500px;
          margin: 0 auto;
          padding-left: var(--container-desktop);
          padding-right: var(--container-desktop);
        }}
        .topbar-inner {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
          min-height: 112px;
          padding-top: 18px;
          padding-bottom: 18px;
        }}
        .brand-lockup {{
          display: flex;
          align-items: center;
          gap: 20px;
          min-width: 0;
          flex: 1 1 auto;
        }}
        .brand-badge {{
          width: 74px;
          height: 74px;
          border-radius: 18px;
          background: #ffffff;
          color: #0f172a;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
          font-weight: 800;
          flex: 0 0 auto;
          overflow: hidden;
          border: 1px solid #e2e8f0;
          box-shadow: 0 6px 18px rgba(15,23,42,0.08);
        }}
        .brand-logo-frame {{
          padding: 0;
        }}
        .brand-logo-img {{
          width: 100%;
          height: 100%;
          object-fit: contain;
          display: block;
        }}
        .brand-logo-fallback {{
          display: none;
          width: 100%;
          height: 100%;
          align-items: center;
          justify-content: center;
          color: #ffffff;
          background: linear-gradient(145deg, #111827 0%, #1f2937 100%);
        }}
        .brand-copy {{
          min-width: 0;
        }}
        .app-title {{
          margin: 0 0 6px 0;
          font-size: 32px;
          line-height: 1.05;
          color: var(--text);
          font-weight: 850;
          letter-spacing: -0.02em;
        }}
        .app-subtitle {{
          color: var(--muted);
          font-size: 17px;
          line-height: 1.35;
        }}
        .topbar-aside {{
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 0 0 auto;
          min-width: 0;
          padding: 10px 12px;
          border: 1px solid #E8F4F9;
          border-radius: 28px;
          background: linear-gradient(135deg, #f8fbff 0%, #F3FAFC 100%);
          box-shadow: 0 14px 36px rgba(54, 170, 191, 0.10);
        }}
        .topbar-viz {{
          width: min(390px, 28vw);
          min-width: 280px;
          border: 0;
          border-radius: 22px;
          background: rgba(255,255,255,0.72);
          padding: 6px 10px;
          box-shadow: inset 0 0 0 1px rgba(147,197,253,0.32);
        }}
        .topbar-nav {{
          display: flex;
          align-items: stretch;
          gap: 28px;
          overflow-x: auto;
          scrollbar-width: none;
          min-height: 56px;
        }}
        .topbar-nav::-webkit-scrollbar {{
          display: none;
        }}
        .topbar-nav a {{
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 56px;
          padding: 0;
          border: 0;
          border-radius: 0;
          background: transparent;
          color: #0f172a;
          text-decoration: none;
          font-size: 20px;
          font-weight: 650;
          white-space: nowrap;
        }}
        .topbar-nav a::after {{
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          bottom: -1px;
          height: 3px;
          border-radius: 999px 999px 0 0;
          background: transparent;
        }}
        .topbar-nav a:hover,
        .topbar-nav a.is-active {{
          color: #36AABF;
        }}
        .topbar-nav a.is-active::after {{
          background: #36AABF;
        }}
        .negotiation-svg {{
          width: 100%;
          height: 86px;
          display: block;
        }}
        .viz-node {{
          fill: #ffffff;
          stroke: #d4d4d8;
          stroke-width: 1.2;
        }}
        .viz-node-owners {{ fill: #F3FAFC; }}
        .viz-node-planner {{ fill: #E8F4F9; }}
        .viz-node-developer {{ fill: #f8fbff; }}
        .viz-overline {{
          fill: #71717a;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }}
        .viz-value {{
          fill: #111827;
          font-size: 14px;
          font-weight: 800;
        }}
        .viz-route {{
          stroke: #B2DBE4;
          stroke-width: 2.2;
          stroke-linecap: round;
          stroke-dasharray: 6 8;
          animation: route-flow 14s linear infinite;
        }}
        .viz-route-soft {{
          stroke: #CFEAF0;
          stroke-width: 1.8;
          animation-duration: 18s;
        }}
        .viz-anchor {{
          fill: #84CDDA;
          animation: pulse-anchor 2.8s ease-in-out infinite;
        }}
        .mini-person {{
          transform-box: fill-box;
          transform-origin: center;
        }}
        .person-amber {{ color: #36AABF; }}
        .person-teal {{ color: #0284c7; }}
        .person-slate {{ color: #1e3a8a; }}
        .mode-pill {{
          flex: 0 0 auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 44px;
          padding: 0 18px 0 14px;
          border-radius: 999px;
          border: 1px solid #CFEAF0;
          background: #ffffff;
          color: #268CA0;
          font-size: 15px;
          font-weight: 760;
          box-shadow: 0 8px 18px rgba(54,170,191,0.10);
        }}
        .mode-pill::before {{
          content: "";
          width: 8px;
          height: 8px;
          border-radius: 999px;
          background: #36AABF;
          box-shadow: 0 0 0 4px rgba(54,170,191,0.12);
          margin-right: 8px;
        }}
        @media (max-width: 980px) {{
          .topbar-inner {{ flex-direction: column; align-items: flex-start; }}
          .topbar-aside {{ width: 100%; justify-content: space-between; }}
          .topbar-viz {{ width: min(100%, 430px); min-width: 0; }}
        }}
        @media (max-width: 640px) {{
          .topbar-inner, .topbar-nav {{ padding-left: var(--container-mobile); padding-right: var(--container-mobile); }}
          .brand-badge {{ width: 56px; height: 56px; font-size: 22px; border-radius: 14px; }}
          .app-title {{ font-size: 26px; }}
          .app-subtitle {{ font-size: 14px; }}
          .topbar-nav a {{ font-size: 17px; }}
          .topbar-viz {{ display: none; }}
        }}
        @keyframes route-flow {{
          to {{
            stroke-dashoffset: -140;
          }}
        }}
        @keyframes pulse-anchor {{
          0%, 100% {{
            opacity: 0.55;
            transform: scale(1);
          }}
          50% {{
            opacity: 1;
            transform: scale(1.18);
          }}
        }}
        .shell {{ max-width: 1500px; margin: 0 auto; padding: var(--space-5) var(--container-desktop) var(--space-8); }}
        body.embedded-body,
        body.iframe-embedded {{
          background: transparent;
        }}
        body.embedded-body .shell,
        body.iframe-embedded .shell {{
          max-width: none;
          padding: 0;
          margin: 0;
        }}
        body.iframe-embedded .topbar-shell {{
          display: none;
        }}
        .panel {{
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-xl);
          padding: var(--space-5);
          margin-bottom: var(--space-5);
          box-shadow: var(--shadow-card);
        }}
        .hero {{
          background: var(--surface);
        }}
        h1 {{ margin: 0 0 8px 0; font-size: 32px; line-height: 1.08; }}
        h2 {{ margin: 0 0 12px 0; font-size: 24px; line-height: 1.2; }}
        h3 {{ margin: 0 0 14px 0; font-size: 20px; line-height: 1.25; }}
        .section-head {{ margin: 0 0 var(--space-4) 0; }}
        .section-head.compact {{ margin: 0 0 var(--space-3) 0; }}
        .section-title {{ font-size: 26px; line-height: 1.16; font-weight: 850; color: var(--text); margin-bottom: 8px; letter-spacing: -0.02em; }}
        .card-title, .panel-title {{ font-size: 26px; line-height: 1.16; font-weight: 850; color: var(--text); letter-spacing: -0.02em; }}
        .button.action-primary,
        button.action-primary {{ background: #36AABF; border-color: #36AABF; color: #ffffff; box-shadow: 0 6px 16px rgba(54,170,191,0.18); }}
        .button.action-secondary,
        button.action-secondary {{ background: #ffffff; border-color: #dbe3ef; color: #0f172a; }}
        .button.action-tertiary,
        button.action-tertiary {{ background: #f8fafc; border-color: #e2e8f0; color: #475569; }}
        .button.action-primary:hover,
        button.action-primary:hover {{ background: #268CA0; border-color: #268CA0; box-shadow: 0 12px 24px rgba(54,170,191,0.22); }}
        .button.action-secondary:hover,
        button.action-secondary:hover,
        .button.action-tertiary:hover,
        button.action-tertiary:hover {{ border-color: #cbd5e1; background: #f8fafc; }}

        .section-copy {{ color: var(--muted); font-size: 15px; line-height: 1.6; }}
        .meta {{ color: var(--muted); margin-bottom: var(--space-3); font-size: 15px; line-height: 1.55; }}
        .row {{ display: grid; grid-template-columns: minmax(320px, 0.95fr) minmax(0, 1.05fr); gap: var(--grid-gutter); align-items: start; }}
        .row-wide {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--grid-gutter); align-items: start; }}
        section > h3 {{ margin-bottom: 18px; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; border: 1px solid var(--border); border-radius: 18px; overflow: hidden; }}
        .data-table th, .data-table td {{ border-bottom: 1px solid var(--border); padding: 16px 16px; text-align: left; vertical-align: top; }}
        .data-table th {{ background: var(--surface-soft); color: #6b7280; font-weight: 600; position: sticky; top: 0; }}
        .map-img {{ width: 100%; border-radius: 18px; border: 1px solid var(--border); background: #fff; }}
        .map-shell {{
          position: relative;
        }}
        .map-canvas {{
          position: relative;
          z-index: 1;
        }}
        .map-overlay-card {{
          position: absolute;
          z-index: 450;
          background: rgba(255, 255, 255, 0.96);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(226, 232, 240, 0.95);
          box-shadow: 0 18px 48px rgba(15, 23, 42, 0.12);
          border-radius: 18px;
          padding: 14px 16px;
        }}
        .map-distribution-card {{
          top: 18px;
          left: 18px;
          width: min(320px, calc(100% - 36px));
        }}
        .map-legend-card {{
          left: 18px;
          bottom: 18px;
          width: min(260px, calc(100% - 36px));
        }}
        .map-overlay-head {{
          display: flex;
          flex-direction: column;
          gap: 4px;
          margin-bottom: 10px;
        }}
        .map-overlay-title {{
          font-size: 13px;
          font-weight: 800;
          color: var(--text);
        }}
        .map-overlay-copy {{
          font-size: 12px;
          line-height: 1.45;
          color: var(--muted);
        }}
        .map-legend-stack {{
          display: grid;
          gap: 10px;
        }}
        .map-legend-row {{
          display: grid;
          grid-template-columns: 16px minmax(0, 1fr);
          align-items: center;
          gap: 10px;
          font-size: 12px;
          color: var(--text);
          font-weight: 600;
        }}
        .map-legend-row.is-gradient {{
          grid-template-columns: 1fr;
          gap: 8px;
        }}
        .map-swatch {{
          width: 16px;
          height: 16px;
          border-radius: 999px;
          background: #d1d5db;
          border: 1px solid #cbd5e1;
        }}
        .map-swatch.is-empty {{
          background: #d1d5db;
        }}
        .map-gradient-bar {{
          display: block;
          width: 100%;
          height: 12px;
          border-radius: 999px;
          border: 1px solid rgba(148, 163, 184, 0.26);
        }}
        .map-gradient-labels {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          font-size: 12px;
          color: var(--muted);
          font-weight: 700;
        }}
        .map-distribution-plot {{
          min-height: 156px;
        }}
        .map-mini-empty {{
          min-height: 120px;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px dashed var(--border);
          border-radius: 14px;
          color: var(--muted);
          font-size: 12px;
          text-align: center;
        }}
        .toolbar {{ display: flex; gap: 14px; flex-wrap: wrap; align-items: end; }}
        .toolbar label {{ display: flex; flex-direction: column; gap: 8px; font-size: 14px; font-weight: 600; color: var(--text); }}
        .toolbar select, .toolbar input {{
          padding: 14px 16px;
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          min-width: 180px;
          min-height: 52px;
          background: var(--surface);
          box-shadow: none;
        }}
        .toolbar button, .toolbar a.button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 18px;
          height: 52px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--accent);
          background: var(--accent);
          color: white;
          text-decoration: none;
          cursor: pointer;
          box-sizing: border-box;
          appearance: none;
          -webkit-appearance: none;
          line-height: 1;
          white-space: nowrap;
          font-family: inherit;
          font-weight: 700;
          font-size: 15px;
        }}
        .button,
        button.button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 44px;
          padding: 0 16px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--text);
          text-decoration: none;
          cursor: pointer;
          box-sizing: border-box;
          appearance: none;
          -webkit-appearance: none;
          line-height: 1;
          white-space: nowrap;
          font-family: inherit;
          font-size: 14px;
          font-weight: 700;
        }}
        .button.primary,
        button.button.primary {{
          background: var(--accent);
          border-color: var(--accent);
          color: #ffffff;
        }}
        .button.secondary,
        button.button.secondary {{
          background: var(--surface);
          color: var(--text);
          border-color: var(--border);
        }}
        .button.ghost,
        button.button.ghost {{
          background: var(--surface-soft);
          color: var(--text);
          border-color: var(--border);
        }}
        .button:hover,
        button.button:hover {{
          box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
          transform: translateY(-1px);
        }}
        .button.primary:hover,
        button.button.primary:hover {{
          box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
        }}
        .toolbar.top-toolbar {{
          align-items: center;
          gap: 16px;
        }}
        .toolbar.compact-toolbar {{
          align-items: center;
          gap: 10px;
        }}
        .toolbar-field {{
          display: flex;
          flex-direction: column;
          gap: 8px;
        }}
        .toolbar-label {{
          font-size: 14px;
          font-weight: 600;
          color: var(--text);
        }}
        .metric-field {{
          min-width: 320px;
        }}
        .metric-field .seg-group {{
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          width: 100%;
        }}

        .metric-field .seg-button {{
          flex: 1 1 calc(50% - 3px);
          min-width: 0;
          white-space: normal;
          word-break: break-word;
          text-align: center;
          line-height: 1.15;
          padding: 8px 10px;
          font-size: 12px;
        }}
        .toolbar-actions {{
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          align-items: stretch;
          margin-left: auto;
        }}
        .toolbar-actions > * {{
          flex: 0 0 auto;
        }}
        .toolbar a.button.secondary {{
          background: var(--surface);
          color: var(--text);
          border-color: var(--border);
        }}
        .toolbar a.button.ghost {{
          background: var(--surface-soft);
          color: var(--text);
          border-color: var(--border);
        }}
        .toolbar a.button.disabled {{
          background: var(--surface-soft);
          color: var(--muted);
          border-color: var(--border);
          pointer-events: none;
        }}
        .seg-group {{
          display: inline-flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }}
        .seg-button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px;
          padding: 0 14px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--muted);
          text-decoration: none;
          font-size: 14px;
          font-weight: 600;
        }}
        .seg-button.active {{
          background: var(--accent);
          border-color: var(--accent);
          color: #ffffff;
        }}
        .metric-switch-list {{
          display: grid !important;
          grid-template-columns: 1fr !important;
          gap: 8px !important;
          width: 100% !important;
        }}
        .metric-switch-list .seg-button {{
          width: 100% !important;
          justify-content: flex-start !important;
          text-align: left !important;
          white-space: normal !important;
          overflow: visible !important;
          text-overflow: clip !important;
          line-height: 1.25 !important;
          border-radius: 14px !important;
          padding: 9px 12px !important;
        }}
        .stats-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: var(--space-4);
          margin-bottom: var(--space-4);
        }}
        .stat-card {{
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: 20px 20px 18px 20px;
          box-shadow: var(--shadow-card);
        }}
        .stat-label {{
          font-size: 14px;
          font-weight: 600;
          color: var(--muted);
          margin-bottom: 12px;
        }}
        .stat-value {{
          font-size: 34px;
          line-height: 1.08;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 8px;
        }}
        .stat-value.is-compact {{
          font-size: 22px;
          line-height: 1.35;
          font-weight: 700;
        }}
        .stat-hint {{
          font-size: 14px;
          line-height: 1.55;
          color: var(--muted);
        }}
        .page-head {{
          display: flex;
          gap: 16px;
          align-items: center;
          justify-content: space-between;
        }}
        .detail-topbar-panel {{
          padding: var(--space-4) var(--space-5);
        }}
        .detail-topbar-row {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: var(--space-4);
          align-items: center;
        }}
        .detail-title-block {{
          min-width: 0;
          max-width: 760px;
        }}
        .detail-overline {{
          margin-bottom: 6px;
          font-size: 11px;
          line-height: 1.2;
          font-weight: 800;
          color: var(--muted);
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }}
        .detail-title-block h1 {{
          margin: 0 0 4px 0;
          font-size: 23px;
          line-height: 1.08;
        }}
        .detail-title-block .meta {{
          margin-bottom: 0;
          max-width: 680px;
          font-size: 12px;
          line-height: 1.45;
        }}
        .detail-controlbar {{
          display: flex;
          align-items: center;
          justify-content: flex-end;
          min-width: 0;
          justify-self: end;
        }}
        .detail-control-panel {{
          display: inline-flex;
          align-items: end;
          gap: 0;
          padding: var(--space-2) var(--space-3);
          border: 1px solid var(--border);
          border-radius: 16px;
          background: var(--surface-soft);
          box-shadow: var(--shadow-soft);
        }}
        .detail-inline-form {{
          display: grid;
          grid-template-columns: minmax(180px, 220px) minmax(112px, 132px) auto;
          gap: var(--space-2);
          align-items: end;
          flex: 0 0 auto;
          min-width: 0;
        }}
        .detail-inline-form.is-run {{
          grid-template-columns: minmax(220px, 260px) auto;
        }}
        .detail-inline-form label {{
          gap: 4px;
          font-size: 11px;
          font-weight: 700;
          color: var(--muted);
          min-width: 0;
        }}
        .detail-inline-form select,
        .detail-inline-form input {{
          min-width: 0;
          min-height: 40px;
          height: 40px;
          padding: 8px 12px;
          font-size: 13px;
        }}
        .detail-inline-form .toolbar-actions {{
          display: flex;
          align-items: center;
          margin-left: 0;
          gap: 8px;
        }}
        .detail-toolbar-actions {{
          align-self: end;
        }}
        .detail-inline-form .toolbar-actions > button,
        .detail-inline-form .toolbar-actions > a {{
          min-height: 40px;
          height: 40px;
          padding: 0 14px;
          font-size: 13px;
        }}
        .detail-back-button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px !important;
          height: 40px !important;
          padding: 0 14px !important;
          border-radius: 12px !important;
          border: 1px solid var(--border) !important;
          background: var(--surface) !important;
          color: var(--text) !important;
          text-decoration: none !important;
          font-size: 13px !important;
          font-weight: 700 !important;
          line-height: 1 !important;
          box-sizing: border-box;
          appearance: none;
          -webkit-appearance: none;
          margin: 0;
          white-space: nowrap;
        }}
        .detail-back-button:hover {{
          background: #ffffff !important;
          border-color: var(--border-strong) !important;
        }}
        .detail-main-stack {{
          display: grid;
          grid-auto-flow: row;
          gap: var(--space-4);
          align-content: start;
        }}
        .detail-main-stack > * {{
          margin: 0;
        }}
        .detail-summary-grid {{
          display: grid;
          grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
          gap: var(--space-4);
          align-items: start;
          grid-auto-rows: auto;
        }}
        .detail-summary-grid .panel {{
          margin-bottom: 0;
          min-width: 0;
          overflow: hidden;
        }}
        .detail-summary-panel,
        .detail-current-panel {{
          display: flex;
          flex-direction: column;
          align-self: stretch;
          min-height: 0;
          padding: var(--space-4);
        }}
        .detail-summary-panel .section-head.compact,
        .detail-current-panel .section-head.compact {{
          margin-bottom: 10px;
        }}
        .detail-summary-panel .section-title,
        .detail-current-panel .section-title {{
          font-size: 19px;
          line-height: 1.15;
          margin-bottom: 0;
        }}
        .detail-summary-panel .stats-grid {{
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: var(--space-2);
          margin-bottom: 0;
          align-content: start;
        }}
        .detail-current-panel .kv-grid {{
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: var(--space-2);
          margin-bottom: 0;
          align-content: start;
        }}
        .detail-summary-panel .stat-card,
        .detail-current-panel .kv-item {{
          min-height: 0;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          padding: 12px 12px 10px 12px;
          border-radius: 14px;
        }}
        .detail-current-panel .kv-item {{
          background: var(--surface);
          box-shadow: var(--shadow-card);
        }}
        .detail-summary-panel .stat-label,
        .detail-current-panel .kv-label {{
          font-size: 12px;
          line-height: 1.4;
          font-weight: 700;
          color: var(--muted);
          margin-bottom: 5px;
        }}
        .detail-summary-panel .stat-value,
        .detail-current-panel .kv-value {{
          font-size: 21px;
          line-height: 1.06;
          font-weight: 800;
          color: var(--text);
          letter-spacing: -0.02em;
          font-variant-numeric: tabular-nums;
          margin-bottom: 2px;
        }}
        .detail-summary-panel .stat-hint {{
          font-size: 11px;
          line-height: 1.35;
        }}
        .detail-current-panel .kv-value {{
          word-break: break-word;
        }}
        @media (min-width: 1320px) {{
          .detail-current-panel .kv-grid {{
            grid-template-columns: repeat(5, minmax(0, 1fr));
          }}
        }}
        .header-actions {{
          display: flex;
          gap: 12px;
          align-items: center;
          flex-wrap: wrap;
        }}
        .header-actions .button.secondary {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 48px;
          padding: 0 16px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--text);
          text-decoration: none;
          font-weight: 600;
        }}
        .kv-grid {{
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 14px;
        }}
        .kv-item {{
          padding: 18px 18px 16px 18px;
          border-radius: 18px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
        }}
        .kv-label {{
          font-size: 13px;
          color: var(--muted);
          font-weight: 600;
          margin-bottom: 8px;
        }}
        .kv-value {{
          font-size: 18px;
          color: var(--text);
          line-height: 1.45;
          font-weight: 700;
          word-break: break-word;
        }}
        .playback-topbar {{
          display: grid;
          grid-template-columns: minmax(220px, 0.9fr) minmax(360px, 1.1fr);
          gap: var(--space-3);
          align-items: center;
          margin-bottom: var(--space-1);
        }}
        .playback-head {{
          margin-bottom: 0;
        }}
        .detail-playback-panel {{
          position: relative;
          z-index: 0;
          padding: var(--space-4);
          margin-top: var(--space-1);
          clear: both;
        }}
        .timeline-shell {{
          display: grid;
          grid-template-columns: auto minmax(260px, 1fr) auto;
          gap: var(--space-2);
          align-items: center;
          margin-bottom: 0;
          padding: var(--space-2) var(--space-3);
          border: 1px solid var(--border);
          border-radius: 14px;
          background: var(--surface-soft);
        }}
        .timeline-play {{
          min-height: 36px;
          padding: 0 12px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--accent);
          background: var(--accent);
          color: #fff;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
        }}
        .timeline-play:hover {{
          transform: translateY(-1px);
          box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
        }}
        .timeline-slider {{
          width: 100%;
          min-width: 180px;
          accent-color: var(--accent);
          cursor: pointer;
        }}
        .timeline-badge {{
          min-width: 92px;
          min-height: 34px;
          padding: 0 10px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--text);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          font-weight: 700;
        }}
        .timeline-pills {{
          display: flex;
          flex-wrap: nowrap;
          gap: var(--space-2);
          margin-bottom: var(--space-2);
          overflow-x: auto;
          padding-bottom: 2px;
          scrollbar-width: thin;
        }}
        .round-pill {{
          min-height: 30px;
          padding: 0 9px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--muted);
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
          transition: background 140ms ease, border-color 140ms ease, color 140ms ease, transform 140ms ease;
        }}
        .round-pill:hover {{
          transform: translateY(-1px);
          border-color: #cbd5e1;
          color: var(--text);
        }}
        .round-pill.active {{
          background: var(--accent);
          border-color: var(--accent);
          color: #fff;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
        }}
        .chart-grid {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-4);
        }}
        .detail-chart-grid {{
          grid-template-columns: minmax(0, 0.92fr) minmax(0, 0.92fr) minmax(0, 1.18fr);
          gap: var(--space-3);
        }}
        .chart-card {{
          border: 1px solid var(--border);
          border-radius: 22px;
          background: var(--surface);
          padding: 14px 16px 12px;
          box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);
          display: flex;
          flex-direction: column;
          min-height: 0;
        }}
        .chart-card-rich {{
          min-width: 0;
        }}
        .chart-head {{
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-bottom: 6px;
        }}
        .chart-title {{
          font-size: 14px;
          font-weight: 700;
          color: var(--text);
          margin-bottom: 0;
          line-height: 1.3;
        }}
        .chart-legend {{
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px 10px;
          min-height: 20px;
        }}
        .chart-legend-item {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          min-height: 24px;
          padding: 0;
          color: var(--muted);
          font-size: 11px;
          font-weight: 700;
          white-space: normal;
          line-height: 1.35;
        }}
        .chart-legend-dot {{
          width: 10px;
          height: 10px;
          border-radius: 999px;
          flex: 0 0 auto;
          border: 1px solid rgba(255,255,255,0.85);
          box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08);
        }}
        .chart-legend-label {{
          color: var(--muted);
        }}
        .plot-frame {{
          min-height: 320px;
        }}
        .detail-playback-panel .plot-frame {{
          min-height: 186px;
          flex: 1 1 auto;
        }}
        .chart-empty {{
          min-height: 260px;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px dashed var(--border-strong);
          border-radius: 18px;
          color: var(--muted);
          font-size: 15px;
        }}
        .table-toolbar {{
          display: flex;
          justify-content: flex-end;
          margin-bottom: 14px;
        }}
        .table-search {{
          width: min(360px, 100%);
          padding: 12px 14px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          background: var(--surface);
        }}
        .table-wrap {{
          width: 100%;
          overflow: auto;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: var(--surface);
        }}
        .interactive-table {{
          width: 100%;
          min-width: 860px;
          border-collapse: collapse;
        }}
        .interactive-table thead th {{
          position: sticky;
          top: 0;
          background: var(--surface-soft);
          z-index: 1;
        }}
        .interactive-table th,
        .interactive-table td {{
          padding: 12px 14px;
          border-bottom: 1px solid var(--border);
          text-align: left;
          vertical-align: middle;
          font-size: 13px;
        }}
        .table-header {{
          color: #6b7280;
          font-weight: 700;
          cursor: pointer;
          user-select: none;
          white-space: nowrap;
        }}
        .table-header.is-sorted {{
          color: var(--text);
        }}
        .table-row:hover {{
          background: #fafafa;
        }}
        .table-row[data-round] {{
          cursor: pointer;
        }}
        .table-row.is-active {{
          background: #f4f4f5;
        }}
        .table-row.is-active td:first-child {{
          box-shadow: inset 3px 0 0 var(--accent);
        }}
        .table-cell.align-right {{
          text-align: right;
          font-variant-numeric: tabular-nums;
        }}
        .table-empty {{
          color: var(--muted);
          text-align: center !important;
          padding: 22px !important;
        }}
        .detail-lower-grid {{
          display: grid;
          grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.3fr);
          gap: var(--space-4);
          align-items: stretch;
        }}
        .detail-table-panel {{
          display: flex;
          flex-direction: column;
          min-height: 0;
          padding: 14px 16px 12px 16px;
        }}
        .detail-table-toolbar {{
          margin-bottom: 10px;
          justify-content: flex-start;
        }}
        .detail-table-toolbar .table-search {{
          width: 100%;
          max-width: none;
          min-height: 42px;
          padding: 10px 12px;
        }}
        #round-table,
        #resident-table {{
          min-height: 0;
          flex: 1 1 auto;
        }}
        #round-table .table-wrap,
        #resident-table .table-wrap {{
          height: 320px;
          min-height: 320px;
        }}
        .linkline {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; }}
        .linkline a {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 48px;
          padding: 0 16px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--text);
          text-decoration: none;
          font-weight: 600;
        }}
        .chip-row {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }}
        .chip {{
          display:inline-flex;
          align-items:center;
          gap:8px;
          padding:8px 12px;
          border-radius:999px;
          background: var(--surface-soft);
          color: var(--muted);
          border: 1px solid var(--border);
          font-size: 13px;
          font-weight: 600;
        }}
        .compare-form {{
          display: grid;
          gap: var(--space-4);
        }}
        .compare-top-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: var(--space-4);
        }}
        .compare-top-grid label,
        .compare-select-grid label {{
          display: flex;
          flex-direction: column;
          gap: 8px;
          font-size: 14px;
          font-weight: 600;
          color: var(--text);
        }}
        .compare-top-grid input,
        .compare-top-grid select,
        .compare-select-grid select {{
          padding: 14px 16px;
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
          background: var(--surface);
          min-height: 52px;
        }}
        .compare-select-grid {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: var(--space-4);
        }}
        .multi-check-card {{
          border: 1px solid var(--border);
          border-radius: 18px;
          background: var(--surface);
          overflow: hidden;
        }}
        .multi-check-toolbar {{
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px;
          border-bottom: 1px solid var(--border);
          background: var(--surface-soft);
        }}
        .multi-check-search {{
          flex: 1 1 auto;
          min-height: 40px !important;
          padding: 8px 12px !important;
          border: 1px solid var(--border) !important;
          border-radius: 10px !important;
          background: var(--surface) !important;
        }}
        .multi-check-actions {{
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }}
        .mini-button {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 36px;
          padding: 0 12px;
          border-radius: 10px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--text);
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          box-sizing: border-box;
          transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease, border-color 140ms ease;
        }}
        .mini-button:hover {{
          transform: translateY(-1px);
          box-shadow: 0 8px 18px rgba(15, 23, 42, 0.07);
          border-color: var(--border-strong);
        }}
        .multi-check-summary {{
          padding: 10px 12px 0;
          color: var(--muted);
          font-size: 12px;
          font-weight: 700;
        }}
        .multi-check-list {{
          max-height: 250px;
          overflow: auto;
          padding: 8px 12px 12px;
          display: grid;
          gap: 8px;
        }}
        .multi-check-item {{
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 12px;
          background: var(--surface-soft);
          cursor: pointer;
          transition: border-color 140ms ease, background 140ms ease;
        }}
        .multi-check-item:hover {{
          border-color: #cbd5e1;
          background: #ffffff;
        }}
        .multi-check-item.is-hidden {{
          display: none;
        }}
        .multi-check-item input {{
          width: 16px;
          height: 16px;
          margin: 0;
          accent-color: var(--accent);
          flex: 0 0 auto;
        }}
        .multi-check-copy {{
          font-size: 13px;
          line-height: 1.45;
          font-weight: 600;
          color: var(--text);
        }}
        .compare-weight-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px;
          padding: 14px;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: var(--surface-soft);
        }}
        .compare-weight-grid label {{
          display: flex;
          flex-direction: column;
          gap: 8px;
          font-size: 13px;
          font-weight: 600;
          color: var(--text);
        }}
        .compare-weight-grid input {{
          min-height: 44px;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 12px;
          background: var(--surface);
        }}
        .compare-footer-bar {{
          display: flex;
          gap: 16px;
          align-items: flex-end;
          justify-content: space-between;
          flex-wrap: wrap;
        }}
        .compare-footer-bar .toolbar-actions {{
          gap: 10px;
          align-items: center;
          margin-left: 0;
        }}
        .compare-footer-bar .toolbar-actions > * {{
          flex: 0 0 auto;
        }}
        .compare-filter-bar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 14px;
          flex-wrap: wrap;
          padding: 14px 16px;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: var(--surface-soft);
        }}
        .compare-filter-summary {{
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          min-width: 0;
        }}
        .compare-filter-note {{
          color: var(--muted);
          font-size: 13px;
          line-height: 1.5;
        }}
        .filter-apply-button {{
          min-height: 44px;
          padding: 0 16px;
          white-space: nowrap;
        }}
        .compare-chip-row {{
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }}
        .compare-visual-grid {{
          display: grid;
          grid-template-columns: minmax(0, 1.6fr) minmax(300px, 0.9fr);
          gap: var(--grid-gutter);
          align-items: start;
          margin-bottom: var(--space-5);
        }}
        .compare-plot {{
          min-height: 520px;
        }}
        .multiobjective-grid {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
          gap: var(--grid-gutter);
          align-items: start;
        }}
        .multiobjective-stack {{
          display: grid;
          gap: 16px;
        }}
        .multiobjective-highlight {{
          margin-bottom: 0;
        }}
        .multiobjective-note {{
          color: var(--muted);
          font-size: 13px;
          line-height: 1.5;
          margin-top: 10px;
        }}
        .compare-plot-toolbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          margin-bottom: 14px;
        }}
        .plot-action-button {{
          min-height: 42px;
          padding: 0 14px;
          border-radius: 12px;
          border: 1px solid var(--accent);
          background: var(--accent);
          color: #fff;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
        }}
        .plot-action-button:hover {{
          transform: translateY(-1px);
          box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
        }}
        .plot-action-button.is-active {{
          background: #268CA0;
          border-color: #268CA0;
        }}
        .compare-plot-note {{
          color: var(--muted);
          font-size: 13px;
          line-height: 1.5;
        }}
        .objective-list {{
          display: grid;
          gap: 12px;
        }}
        .objective-highlight {{
          margin-bottom: 14px;
          padding: 16px;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: #fafafa;
        }}
        .objective-highlight-label {{
          font-size: 12px;
          font-weight: 700;
          color: var(--muted);
          text-transform: uppercase;
          letter-spacing: 0.02em;
          margin-bottom: 8px;
        }}
        .objective-highlight-value {{
          font-size: 18px;
          line-height: 1.4;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 6px;
        }}
        .objective-highlight-hint {{
          font-size: 14px;
          line-height: 1.5;
          color: var(--muted);
        }}
        .objective-item {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 14px;
          padding: 14px 16px;
          border: 1px solid var(--border);
          border-radius: 16px;
          background: var(--surface-soft);
        }}
        .objective-name {{
          font-size: 14px;
          font-weight: 700;
          color: var(--text);
        }}
        .objective-goal {{
          font-size: 13px;
          font-weight: 700;
          color: var(--muted);
        }}
        .inline-table-link {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 34px;
          padding: 0 12px;
          border-radius: 10px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--text);
          font-weight: 700;
          text-decoration: none;
          white-space: nowrap;
        }}
        ul {{ margin: 8px 0; padding-left: 20px; color: var(--muted); }}
        li, p {{ line-height: 1.7; color: var(--muted); font-size: 15px; }}
        .leaflet-container {{ border-radius: 18px; }}
        @media (max-width: 960px) {{
          .topbar-shell {{ padding: 0 var(--container-mobile); }}
          .topbar-nav {{ width: 100%; gap: 22px; justify-content: flex-start; }}
          .topbar-nav a {{ min-height: 56px; font-size: 17px; }}
          .shell {{ padding: var(--space-4) var(--container-mobile) var(--space-6); }}
          .row, .row-wide {{ grid-template-columns: 1fr; }}
          .stats-grid,
          .kv-grid,
          .chart-grid,
          .detail-summary-grid,
          .compare-top-grid,
          .compare-select-grid,
          .compare-visual-grid,
          .multiobjective-grid,
          .detail-lower-grid,
          .detail-chart-grid,
          .detail-topbar-row,
          .playback-topbar,
          .detail-inline-form {{
            grid-template-columns: 1fr;
          }}
          .detail-summary-panel .stats-grid,
          .detail-current-panel .kv-grid {{
            grid-template-columns: 1fr;
          }}
          .map-overlay-card {{
            position: static;
            width: auto;
            margin-top: var(--space-3);
          }}
          .page-head,
          .timeline-shell {{
            grid-template-columns: 1fr;
            flex-direction: column;
            align-items: flex-start;
          }}
          .detail-controlbar {{
            justify-content: stretch;
          }}
          .detail-control-panel {{
            width: 100%;
            flex-direction: column;
            align-items: stretch;
          }}
          .detail-inline-form.is-run {{
            grid-template-columns: 1fr;
          }}
          #round-table .table-wrap,
          #resident-table .table-wrap {{
            height: auto;
            min-height: 0;
          }}
          .toolbar-actions {{
            margin-left: 0;
          }}
          .panel {{ padding: var(--space-5) var(--space-4); }}
          .app-title {{ font-size: 28px; }}
        }}
      </style>
    </head>
    <body class="{body_class}">
      {topbar_html}
      <div class="shell">{body}</div>
      <script>
        (function() {{
          try {{
            if (window.self !== window.top && !document.body.classList.contains("embedded-body")) {{
              document.body.classList.add("iframe-embedded");
            }}
          }} catch (_error) {{
            document.body.classList.add("iframe-embedded");
          }}
        }})();
      </script>
    </body>
    </html>
    """
