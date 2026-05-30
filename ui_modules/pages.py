
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def _option_html(options: list[tuple[str, str]], selected_value: str | None) -> str:
    chunks = []
    for label, value in options:
        selected = " selected" if str(value) == str(selected_value) else ""
        chunks.append(f'<option value="{value}"{selected}>{label}</option>')
    return "\n".join(chunks)


def _phase2_missing_page(phase2_root: str, embedded: bool = False) -> str:
    body = f"""
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Policy Comparison Data Not Found</div>
      </div>
      <p class="section-copy">
        No phase2 policy-search CSV or accumulated negotiation logs were found at
        <code>{html.escape(_display_path(phase2_root))}</code>.
        Run a simulation from <code>/run/setup</code>, then refresh this page to read the generated logs.
      </p>
      <a class="button" href="/run/setup">Open Launch Setup</a>
    </div>
    """
    return _html_shell("Policy Comparison Data Not Found", body, embedded=embedded)


def _file_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/local-file?{urlencode({'path': path})}"


def _build_phase2_global_page(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str | None,
    metric: str,
    seed: str | None,
    embedded: bool = False,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    if global_df.empty or "rule_id" not in global_df.columns:
        return _phase2_missing_page(phase2_root, embedded=embedded)
    rule_choices = _phase2_rule_choices(global_df)
    selected_rule = rule_id if rule_id in set(global_df["rule_id"].tolist()) else str(global_df.iloc[0]["rule_id"])
    selected_rule_row = global_df.loc[global_df["rule_id"] == selected_rule].iloc[0]
    selected_rule_display = _phase2_rule_display_text(selected_rule_row)
    selected_rule_hint = _phase2_rule_hint_text(selected_rule_row)
    summary_df = _summarize_phase2_rule(phase2_root, selected_rule)



    map_df = summary_df.copy()
    map_df["rule_label"] = selected_rule_display
    feature_collection, center, zoom, map_overlay_meta = _leaflet_feature_collection(
        boundary_path,
        map_df,
        metric,
        lambda community_name: _make_phase2_community_url(
            phase2_root,
            boundary_path,
            selected_rule,
            community_name,
            None,
        ),
    )
    communities = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    default_open_community = communities[0] if communities else ""
    total_communities, communities_with_results = _coverage_summary(boundary_path, map_df)
    metric_switch = _metric_switch_html(
        "/phase2/global",
        {
            "phase2_root": phase2_root,
            "boundary_path": boundary_path or "",
            "rule_id": selected_rule,
        },
        metric,
    )
    kpi_cards = [
        {"label": "Current Rule", "value": _phase2_rule_content_text(selected_rule_row), "hint": selected_rule},
        {"label": "Selected Metric", "value": MAP_METRICS.get(metric, metric), "hint": "Mean by rule + community"},
        {"label": "Matched Communities", "value": str(total_communities), "hint": "Boundary matched"},
        {"label": "Communities With Results", "value": f"{communities_with_results}/{max(total_communities, 1)}", "hint": "Simulation output"},
    ]
    kpi_html = "".join(
        f"""
        <div class="analysis-kpi-card" title="{html.escape(card['value'])}">
          <div class="analysis-kpi-label">{html.escape(card['label'])}</div>
          <div class="analysis-kpi-value">{html.escape(card['value'])}</div>
          <div class="analysis-kpi-hint">{html.escape(card['hint'])}</div>
        </div>
        """
        for card in kpi_cards
    )
    open_params = {
        "phase2_root": phase2_root,
        "boundary_path": boundary_path or "",
        "rule_id": selected_rule,
    }
    export_url = _make_phase2_global_export_url(phase2_root, boundary_path, selected_rule, metric, None)
    body = f"""
    <style>
      .analysis-workspace-panel,
      .analysis-workspace-panel *,
      .analysis-workspace,
      .analysis-sidebar,
      .analysis-main-panel,
      .analysis-kpi-strip,
      .analysis-kpi-card,
      .analysis-map-panel,
      .analysis-map-shell {{
        box-sizing: border-box;
      }}
      .analysis-workspace-panel {{
        padding: 18px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow-x: clip;
      }}
      .analysis-workspace {{
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
        gap: 16px;
        align-items: stretch;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-sidebar {{
        display: grid;
        gap: 12px;
        align-content: start;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-sidebar-form {{
        display: grid;
        gap: 12px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-sidebar-card,
      .analysis-main-panel,
      .analysis-map-panel {{
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--surface);
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-sidebar-card {{
        padding: 12px;
        display: grid;
        gap: 10px;
      }}
      .analysis-sidebar-section {{
        display: grid;
        gap: 6px;
      }}
      .analysis-sidebar-section .seg-group {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        width: 100%;
      }}
      .analysis-sidebar-section .seg-button {{
        width: 100%;
        min-height: 40px;
        justify-content: flex-start;
        text-align: left;
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
        line-height: 1.2;
      }}
      .analysis-sidebar-label {{
        font-size: 12px;
        font-weight: 800;
        color: var(--muted-soft);
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
      .analysis-community-label {{
        display: block;
        font-size: 13px;
        font-weight: 700;
        color: var(--text);
        min-width: 0;
        max-width: 100%;
        line-height: 1.3;
      }}
      .analysis-community-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
        align-items: center;
        width: 100%;
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
      }}
      .analysis-community-row > * {{
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
      }}
      .analysis-community-row select {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
      }}
      .analysis-community-open {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 84px;
        max-width: 100%;
        padding: 0 14px;
        white-space: nowrap;
        font-size: 14px !important;
        line-height: 1.2 !important;
        font-weight: 700;
        box-sizing: border-box;
        overflow: hidden;
        text-overflow: ellipsis;
        transform: none !important;
      }}
      .analysis-sidebar-form label {{
        display: grid;
        gap: 6px;
        font-size: 13px;
        font-weight: 700;
        color: var(--text);
        min-width: 0;
        max-width: 100%;
      }}
      .analysis-sidebar-form input,
      .analysis-sidebar-form select {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        padding: 10px 12px;
        min-height: 42px;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface);
      }}
      .analysis-sidebar .seg-group,
      .analysis-sidebar .metric-switch-list {{
        display: grid !important;
        grid-template-columns: 1fr !important;
        gap: 8px !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
      }}
      .analysis-sidebar .seg-button {{
        min-width: 0;
        max-width: 100%;
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        overflow: visible;
        text-overflow: clip;
        white-space: normal;
        line-height: 1.25;
        min-height: 44px;
        padding: 10px 14px;
      }}
      .analysis-source-path {{
        font-size: 12px;
        color: var(--muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
        max-width: 100%;
      }}
      .analysis-actions {{
        display: grid;
        gap: 8px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-actions .button,
      .analysis-actions button {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        min-height: 42px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .analysis-main-panel {{
        padding: 12px;
        display: grid;
        gap: 12px;
        align-content: start;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow: hidden;
      }}
      .analysis-kpi-strip {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-kpi-card {{
        border: 1px solid var(--border);
        border-radius: 14px;
        background: #fff;
        padding: 10px 12px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        display: grid;
        gap: 3px;
        overflow: hidden;
      }}
      .analysis-kpi-label {{
        font-size: 11px;
        font-weight: 800;
        color: var(--muted-soft);
        letter-spacing: 0.04em;
        text-transform: uppercase;
        min-width: 0;
      }}
      .analysis-kpi-value {{
        font-size: 16px;
        line-height: 1.15;
        font-weight: 800;
        color: var(--text);
        min-width: 0;
        max-width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .analysis-kpi-hint {{
        font-size: 11px;
        color: var(--muted);
        min-width: 0;
        max-width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .analysis-map-panel {{
        padding: 10px;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
      }}
      .analysis-map-shell {{
        position: relative;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow: hidden;
      }}
      .analysis-map-shell .map-shell {{
        margin: 0;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow: hidden;
      }}
      .analysis-map-shell .map-canvas {{
        width: 100% !important;
        max-width: 100%;
        min-width: 0;
      }}
      .analysis-map-shell .map-distribution-card {{
        top: 14px;
        left: 14px;
        width: min(280px, calc(100% - 28px));
        padding: 10px 12px;
        max-width: calc(100% - 28px);
        min-width: 0;
      }}
      .analysis-map-shell .map-legend-card {{
        left: 14px;
        bottom: 14px;
        width: min(220px, calc(100% - 28px));
        padding: 10px 12px;
        max-width: calc(100% - 28px);
        min-width: 0;
      }}
      .analysis-map-shell .map-distribution-plot {{
        min-height: 124px;
        width: 100%;
        max-width: 100%;
      }}
      .analysis-map-shell .map-overlay-head {{
        margin-bottom: 8px;
        min-width: 0;
      }}
      .analysis-map-shell .map-overlay-title {{
        font-size: 12px;
        min-width: 0;
      }}
      .analysis-map-shell .map-overlay-copy {{
        font-size: 11px;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      @media (max-width: 1180px) {{
        .analysis-workspace {{
          grid-template-columns: 1fr;
        }}
        .analysis-kpi-strip {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
      }}
      @media (max-width: 720px) {{
        .analysis-kpi-strip {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
    <div class="panel analysis-workspace-panel">
      <div class="analysis-workspace">
        <aside class="analysis-sidebar">
          <form class="analysis-sidebar-form analysis-sidebar-card" method="get" action="/phase2/global">
            <input type="hidden" name="boundary_path" value="{boundary_path or ''}" />
            {'<input type="hidden" name="embedded" value="1" />' if embedded else ''}
            <div class="analysis-sidebar-section">
              <div class="analysis-sidebar-label">Data source</div>
              <label>Experiment Result Directory
                <input type="text" name="phase2_root" value="{phase2_root}" title="{html.escape(phase2_root)}" />
              </label>
              <div class="analysis-source-path" title="{html.escape(phase2_root)}">{html.escape(_display_path(phase2_root))}</div>
            </div>
            <div class="analysis-sidebar-section">
              <div class="analysis-sidebar-label">Rule</div>
              <label>
                <select name="rule_id">{_option_html(rule_choices, selected_rule)}</select>
              </label>
            </div>
            <div class="analysis-sidebar-section">
              <div class="analysis-sidebar-label">Metric</div>
              {metric_switch}
            </div>
            <div class="analysis-sidebar-section">
              <label class="analysis-community-label" for="phase2-community-picker">Quick Open Community</label>
              <div class="analysis-community-row">
                <select id="phase2-community-picker">{_option_html([(c, c) for c in communities], default_open_community)}</select>
                <a class="button secondary analysis-community-open" id="phase2-open-community" href="#">Open</a>
              </div>
            </div>
            <div class="analysis-sidebar-section">
              <div class="analysis-sidebar-label">Actions</div>
              <div class="analysis-actions">
                <button type="submit" class="button action-primary">Refresh analysis</button>
                <a class="button action-secondary" href="{export_url}">Save map image</a>
                <a class="button action-secondary" href="/phase2/compare?{urlencode({'phase2_root': phase2_root, 'mode': 'aggregate_policy', 'rule_ids': [selected_rule]}, doseq=True)}">Open policy comparison</a>
                <a class="button action-tertiary" href="/app">Back</a>
              </div>
            </div>
          </form>
        </aside>
        <section class="analysis-main-panel">
          <div class="analysis-kpi-strip">
            {kpi_html}
          </div>
          <div class="analysis-map-panel">
            <div class="analysis-map-shell">
              {_leaflet_map_block("phase2-global-map", feature_collection, center, zoom, height=760, overlay_meta=map_overlay_meta)}
            </div>
          </div>
        </section>
      </div>
    </div>
    <script>
      (function() {{
        const select = document.getElementById("phase2-community-picker");
        const openLink = document.getElementById("phase2-open-community");
        const baseParams = {json.dumps(open_params, ensure_ascii=False)};
        function updateLink() {{
          const community = select.value || "";
          if (!community) {{
            openLink.setAttribute("href", "#");
            openLink.classList.add("disabled");
            return;
          }}
          const params = new URLSearchParams(baseParams);
          params.set("community_name", community);
          openLink.setAttribute("href", "/phase2/community?" + params.toString());
          openLink.classList.remove("disabled");
        }}
        select.addEventListener("change", updateLink);
        updateLink();
      }})();
    </script>
    """
    return _html_shell("Experiment Results Analysis", body, embedded=embedded)


def _build_phase2_community_page(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    community_name: str | None,
    seed: str | None,
    round_number: str | None,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    if global_df.empty or "rule_id" not in global_df.columns:
        return _phase2_missing_page(phase2_root)
    selected_rule = rule_id if rule_id in set(global_df["rule_id"].tolist()) else str(global_df.iloc[0]["rule_id"])
    selected_rule_row = global_df.loc[global_df["rule_id"] == selected_rule].iloc[0]
    selected_rule_display = _phase2_rule_display_text(selected_rule_row)
    summary_df = _summarize_phase2_rule(phase2_root, selected_rule)
    communities = summary_df["community_name"].astype(str).tolist()
    selected_community = community_name if community_name in communities else (communities[0] if communities else None)
    detail_md, seed_update, round_fig, round_df, round_update, resident_df, _log_json = _phase2_detail_outputs(
        phase2_root,
        selected_rule,
        selected_community,
        seed,
    )
    selected_seed = seed_update.get("value") if isinstance(seed_update, dict) else seed
    seed_df = _load_phase2_seed_results(phase2_root, selected_rule, selected_seed) if selected_seed else pd.DataFrame()
    selected_seed_row_df = seed_df.loc[seed_df["community_name"] == selected_community] if not seed_df.empty else pd.DataFrame()
    selected_seed_row = selected_seed_row_df.iloc[0] if not selected_seed_row_df.empty else None
    selected_round = round_number if round_number in (round_update.get("choices") or []) else round_update.get("value")
    log_index = _index_phase2_logs(phase2_root, selected_rule)
    seed_choices = [(seed_item["seed"], seed_item["seed"]) for seed_item in log_index.get(selected_community or "", [])]
    round_records, resident_by_round = _detail_payload(_log_json, round_df)
    back_url = "/phase2/global?" + urlencode(
        {
            "phase2_root": phase2_root,
            "boundary_path": boundary_path or "",
            "rule_id": selected_rule,
            "metric": "final_agree_ratio",
            "seed": selected_seed or "",
        }
    )
    back_label = "Back To Global Results"
    controls_html = f"""
    <form class="toolbar compact-toolbar detail-inline-form" method="get" action="/phase2/community">
      <input type="hidden" name="phase2_root" value="{phase2_root}" />
      <input type="hidden" name="boundary_path" value="{boundary_path or ''}" />
      <input type="hidden" name="rule_id" value="{selected_rule}" />
      <label>Community
        <select name="community_name">{_option_html([(c, c) for c in communities], selected_community)}</select>
      </label>
      <label>Seed
        <select name="seed">{_option_html(seed_choices, selected_seed)}</select>
      </label>
      <div class="toolbar-actions detail-toolbar-actions">
        <button type="submit">Load Detail</button>
        <a class="button secondary detail-back-button" href="{back_url}">{back_label}</a>
      </div>
    </form>
    """
    summary_cards_html = _stats_cards_html(
        [
            {"label": "Final Agreement Rate", "value": _format_ratio(_log_json.get("final_metrics", {}).get("final_agree_ratio")), "hint": "Final resident agreement share"},
            {"label": "Final Extension Policy", "value": _format_ratio(_log_json.get("final_policy", {}).get("planner", {}).get("extension_ratio")), "hint": "Planner extension ratio in the final round"},
            {"label": "Final Subsidy Policy", "value": _format_ratio(_log_json.get("final_policy", {}).get("planner", {}).get("cash_subsidy_ratio")), "hint": "Planner subsidy ratio in the final round"},
            {"label": "Total Discussion Rounds", "value": str(_safe_int(_log_json.get("rounds"), 0)), "hint": "Negotiation rounds completed"},
            {"label": "Outcome", "value": _humanize_identifier(_log_json.get("outcome")), "hint": "Simulation end state"},
            {"label": "Termination Reason", "value": _humanize_identifier(_log_json.get("termination_reason")), "hint": "Why the negotiation stopped"},
        ]
    )
    result_panel_html = _key_value_panel_html(
        "Current Community Result",
        _phase2_result_pairs(selected_seed_row, _log_json, selected_seed, len(log_index.get(selected_community or "", []))),
    )
    body = _build_interactive_detail_page(
        page_title=selected_community or "Community Detail",
        page_description=f"{selected_rule_display} · Seed {selected_seed or 'N/A'} · Review the negotiation outcome, playback the round-by-round evolution, and inspect resident-level decisions.",
        header_chips=[
            f"Rule: {_phase2_rule_content_text(selected_rule_row)}",
            f"Seed: {selected_seed or 'N/A'}",
            f"Outcome: {_humanize_identifier(_log_json.get('outcome'))}",
        ],
        back_url=back_url,
        back_label=back_label,
        controls_html=controls_html,
        summary_cards_html=summary_cards_html,
        current_result_html=result_panel_html,
        round_records=round_records,
        resident_by_round=resident_by_round,
        initial_round=_safe_int(selected_round, 0),
    )
    return _html_shell("Community Detail", body)


def _build_run_global_page(run_id: str, metric: str) -> str:
    metadata = _load_run_metadata(run_id)
    output_dir = metadata.get("output_dir", "")
    boundary_path = metadata.get("boundary_path")
    summary_df = _collect_latest_run_results(output_dir)
    map_df = summary_df.copy()
    feature_collection, center, zoom, map_overlay_meta = _leaflet_feature_collection(
        boundary_path,
        map_df,
        metric,
        lambda community_name: _make_run_community_url(run_id, community_name),
    )
    communities = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    total_communities, communities_with_results = _coverage_summary(boundary_path, summary_df)
    metric_switch = _metric_switch_html("/run/global", {"run_id": run_id}, metric)
    stats_html = _stats_cards_html(
        [
            {"label": "Current Metric", "value": MAP_METRICS.get(metric, metric), "hint": "Active polygon color mapping"},
            {"label": "Output Directory", "value": Path(output_dir).name if output_dir else "N/A", "hint": "Generated run bundle"},
            {"label": "Matched Communities", "value": str(total_communities), "hint": "Communities found in the boundary layer"},
            {"label": "Communities With Results", "value": f"{communities_with_results}/{max(total_communities, 1)}", "hint": "Communities with generated logs"},
        ]
    )
    export_url = _make_run_global_export_url(run_id, metric)
    body = f"""
    <div class="panel">
      <div class="section-head">
        <div class="section-title">Run Result Analysis</div>
        <div class="section-copy">Inspect the current run output on a polygon map. Hover for metrics and click a polygon to open its community detail page.</div>
      </div>
      <form class="toolbar top-toolbar" method="get" action="/run/global">
        <input type="hidden" name="run_id" value="{run_id}" />
        <label>Quick Open Community
          <select id="run-community-picker">{_option_html([(c, c) for c in communities], communities[0] if communities else '')}</select>
        </label>
        <div class="toolbar-field metric-field">
          <span class="toolbar-label">Color Metric</span>
          {metric_switch}
        </div>
        <div class="toolbar-actions">
          <button type="submit" class="button action-primary">Refresh analysis</button>
          <a class="button action-secondary" href="{export_url}">Save map image</a>
          <a class="button secondary" id="run-open-community" href="#">Open Community</a>
          <a class="button action-tertiary" href="/app">Back</a>
        </div>
      </form>
    </div>
    {stats_html}
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Community Result Map</div>
        <div class="section-copy">The map is the primary analysis surface for the current run.</div>
      </div>
      {_leaflet_map_block("run-global-map", feature_collection, center, zoom, height=860, overlay_meta=map_overlay_meta)}
    </div>
    <div class="panel">{_df_to_html(_run_summary_table(summary_df), "Community Result Summary")}</div>
    <script>
      (function() {{
        const select = document.getElementById("run-community-picker");
        const openLink = document.getElementById("run-open-community");
        function updateLink() {{
          const community = select.value || "";
          if (!community) {{
            openLink.setAttribute("href", "#");
            openLink.classList.add("disabled");
            return;
          }}
          const params = new URLSearchParams({{"run_id": {json.dumps(run_id)}, "community_name": community}});
          openLink.setAttribute("href", "/run/community?" + params.toString());
          openLink.classList.remove("disabled");
        }}
        select.addEventListener("change", updateLink);
        updateLink();
      }})();
    </script>
    """
    return _html_shell("Run Result Analysis", body)


def _build_run_community_page(run_id: str, community_name: str | None, round_number: str | None) -> str:
    metadata = _load_run_metadata(run_id)
    output_dir = metadata.get("output_dir", "")
    boundary_path = metadata.get("boundary_path")
    summary_df = _collect_latest_run_results(output_dir)
    communities = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    selected_community = community_name if community_name in communities else (communities[0] if communities else None)
    detail_md, round_fig, round_df, round_update, resident_df, _log_json = _run_detail_outputs(summary_df, selected_community)
    selected_round = round_number if round_number in (round_update.get("choices") or []) else round_update.get("value")
    resident_df = _build_resident_round_dataframe(_log_json, _safe_int(selected_round, 0))
    row = summary_df.loc[summary_df["community_name"] == selected_community] if not summary_df.empty and "community_name" in summary_df.columns else pd.DataFrame()
    row_series = row.iloc[0] if not row.empty else None
    round_records, resident_by_round = _detail_payload(_log_json, round_df)
    back_url = "/run/global?" + urlencode({"run_id": run_id, "metric": "final_agree_ratio"})
    back_label = "Back To Global Results"
    controls_html = f"""
    <form class="toolbar compact-toolbar detail-inline-form is-run" method="get" action="/run/community">
      <input type="hidden" name="run_id" value="{run_id}" />
      <label>Community
        <select name="community_name">{_option_html([(c, c) for c in communities], selected_community)}</select>
      </label>
      <div class="toolbar-actions detail-toolbar-actions">
        <button type="submit">Load Detail</button>
        <a class="button secondary detail-back-button" href="{back_url}">{back_label}</a>
      </div>
    </form>
    """
    summary_cards_html = _stats_cards_html(
        [
            {"label": "Final Agreement Rate", "value": _format_ratio(_log_json.get("final_metrics", {}).get("final_agree_ratio")), "hint": "Final resident agreement share"},
            {"label": "Final Extension Policy", "value": _format_ratio(_log_json.get("final_policy", {}).get("planner", {}).get("extension_ratio")), "hint": "Planner extension ratio in the final round"},
            {"label": "Final Subsidy Policy", "value": _format_ratio(_log_json.get("final_policy", {}).get("planner", {}).get("cash_subsidy_ratio")), "hint": "Planner subsidy ratio in the final round"},
            {"label": "Total Discussion Rounds", "value": str(_safe_int(_log_json.get("rounds"), 0)), "hint": "Negotiation rounds completed"},
            {"label": "Outcome", "value": _humanize_identifier(_log_json.get("outcome")), "hint": "Simulation end state"},
            {"label": "Termination Reason", "value": _humanize_identifier(_log_json.get("termination_reason")), "hint": "Why the negotiation stopped"},
        ]
    )
    result_panel_html = _key_value_panel_html("Current Community Result", _run_result_pairs(row_series, _log_json))
    body = _build_interactive_detail_page(
        page_title=selected_community or "Community Detail",
        page_description="Review the latest run output, replay the negotiation round by round, and inspect resident-level decisions.",
        header_chips=[
            f"Run ID: {run_id}",
            f"Outcome: {_humanize_identifier(_log_json.get('outcome'))}",
            f"Rounds: {_safe_int(_log_json.get('rounds'), 0)}",
        ],
        back_url=back_url,
        back_label=back_label,
        controls_html=controls_html,
        summary_cards_html=summary_cards_html,
        current_result_html=result_panel_html,
        round_records=round_records,
        resident_by_round=resident_by_round,
        initial_round=_safe_int(selected_round, 0),
    )
    return _html_shell("Run Community Detail", body)


def _build_preview_global_page(
    community_csv_path: str,
    boundary_path: str | None,
) -> str:
    community_df = _read_table(community_csv_path)
    summary_df = pd.DataFrame(
        {
            "community_name": community_df["小区"].astype(str).str.strip(),
            "final_agree_ratio": np.nan,
            "avg_extension_ratio": np.nan,
            "avg_subsidy_ratio": np.nan,
        }
    ).drop_duplicates(subset=["community_name"])
    feature_collection, center, zoom, _map_overlay_meta = _leaflet_feature_collection(
        boundary_path,
        summary_df,
        "final_agree_ratio",
        lambda _community_name: None,
    )
    body = f"""
    <div class="panel hero">
      <h1>Uploaded Data Preview</h1>
      <div class="meta">community: {_display_path(community_csv_path)} | boundary: {_display_path(boundary_path)}</div>
      <div class="chip-row">
        <span class="chip">Current state: boundary preview only</span>
        <span class="chip">Gray communities: simulation not run yet</span>
      </div>
    </div>
    <div class="panel">
      <p>This view shows the uploaded community boundaries. After a simulation run completes, this area will switch to the result map with Final Agreement Rate, Final Extension Policy, and Final Subsidy Policy.</p>
    </div>
    <div class="panel">
      {_leaflet_map_block("preview-global-map", feature_collection, center, zoom)}
    </div>
    """
    return _html_shell("Uploaded Data Preview", body)


def _build_phase2_compare_page(
    phase2_root: str,
    mode: str,
    rule_ids: list[str] | None,
    community_names: list[str] | None,
    x_metric: str,
    y_metric: str,
    evaluation: str,
    metric_weights: dict[str, float],
    embedded: bool = False,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    if global_df.empty or "rule_id" not in global_df.columns:
        return _phase2_missing_page(phase2_root, embedded=embedded)
    pair_df = _load_phase2_policy_community_pairs(phase2_root)
    all_rule_ids = global_df["rule_id"].astype(str).tolist()
    all_communities = sorted(pair_df["community_name"].astype(str).unique().tolist()) if not pair_df.empty else []
    selected_rule_ids = [rule_id for rule_id in (rule_ids or all_rule_ids) if rule_id in set(all_rule_ids)]
    selected_rule_ids = selected_rule_ids or all_rule_ids
    selected_communities = [name for name in (community_names or all_communities) if name in set(all_communities)]
    selected_communities = selected_communities or all_communities

    mode = "aggregate_policy"
    metric_keys = list(COMPARISON_METRICS.keys())
    x_metric = x_metric if x_metric in COMPARISON_METRICS else "final_agree_ratio"
    y_metric = y_metric if y_metric in COMPARISON_METRICS and y_metric != x_metric else "developer_profit"
    evaluation = evaluation if evaluation in {"pareto", "weighted_score"} else "pareto"

    comparison_df = _phase2_comparison_dataset(phase2_root, selected_rule_ids, selected_communities, mode)
    if not comparison_df.empty:
        comparison_df = comparison_df.copy()
        comparison_df["pareto_status"] = _pareto_status(comparison_df, metric_keys)
        comparison_df["pareto_flag"] = comparison_df["pareto_status"].eq("Pareto-optimal")
        comparison_df["weighted_score"] = _weighted_scores(comparison_df, metric_weights)
    else:
        comparison_df["pareto_status"] = pd.Series(dtype=object)
        comparison_df["pareto_flag"] = pd.Series(dtype=bool)
        comparison_df["weighted_score"] = pd.Series(dtype=float)

    if mode == "aggregate_policy":
        comparison_df["row_label"] = comparison_df["rule_content"]
        comparison_df["explore_url"] = comparison_df["rule_id"].map(
            lambda rule_id: "/phase2/global?" + urlencode(
                {
                    "phase2_root": phase2_root,
                    "rule_id": rule_id,
                    "metric": "final_agree_ratio",
                }
            )
        )
        table_columns = [
            {"key": "rule_content", "label": "Policy Rule"},
            {"key": "rule_id", "label": "Rule Key"},
            {"key": "community_count", "label": "Communities"},
            {"key": "final_agree_ratio", "label": "Agreement Rate"},
            {"key": "developer_profit", "label": "Developer Profit"},
            {"key": "resident_mean_utility", "label": "Resident Mean Utility"},
            {"key": "utility_gini", "label": "Utility Gini"},
            {"key": "subsidy_total_cost", "label": "Subsidy Cost"},
            {"key": "extension_ratio_final", "label": "Extension Ratio"},
            {"key": "weighted_score", "label": "Weighted Score"},
            {"key": "pareto_status", "label": "Pareto Status"},
            {"key": "explore_url", "label": "Explore"},
        ]
    else:
        default_seed = "43"
        comparison_df["row_label"] = comparison_df.apply(
            lambda row: f"{row.get('rule_content', row.get('rule_id'))} · {row['community_name']}",
            axis=1,
        )
        comparison_df["explore_url"] = comparison_df.apply(
            lambda row: _make_phase2_community_url(
                phase2_root,
                _resolve_shape_path(None),
                row["rule_id"],
                row["community_name"],
                default_seed,
            ),
            axis=1,
        )
        table_columns = [
            {"key": "rule_content", "label": "Policy Rule"},
            {"key": "rule_id", "label": "Rule Key"},
            {"key": "community_name", "label": "Community"},
            {"key": "sample_count", "label": "Runs Averaged"},
            {"key": "final_agree_ratio", "label": "Agreement Rate"},
            {"key": "developer_profit", "label": "Developer Profit"},
            {"key": "resident_mean_utility", "label": "Resident Mean Utility"},
            {"key": "utility_gini", "label": "Utility Gini"},
            {"key": "subsidy_total_cost", "label": "Subsidy Cost"},
            {"key": "extension_ratio_final", "label": "Extension Ratio"},
            {"key": "weighted_score", "label": "Weighted Score"},
            {"key": "pareto_status", "label": "Pareto Status"},
            {"key": "explore_url", "label": "Explore"},
        ]

    if not comparison_df.empty:
        comparison_df = comparison_df.copy()
        comparison_df["frontier_label"] = comparison_df.apply(
            lambda row: (
                f"[{_safe_float(row.get('extension_cap')) * 100:.0f},{_safe_float(row.get('subsidy_cap')) * 100:.0f}]"
                if not pd.isna(row.get("extension_cap")) and not pd.isna(row.get("subsidy_cap"))
                else str(row.get("row_label") or row.get("rule_id") or "N/A")
            ),
            axis=1,
        )

    comparison_records = _json_ready(
        comparison_df[
            [
                key
                for key in [
                    "rule_id",
                    "rule_display",
                    "rule_content",
                    "community_name",
                    "community_count",
                    "sample_count",
                    "final_agree_ratio",
                    "developer_profit",
                    "resident_mean_utility",
                    "utility_gini",
                    "subsidy_total_cost",
                    "extension_ratio_final",
                    "weighted_score",
                    "pareto_status",
                    "extension_cap",
                    "subsidy_cap",
                    "row_label",
                    "frontier_label",
                    "explore_url",
                ]
                if key in comparison_df.columns
            ]
        ]
    )

    weight_values = {metric: max(_safe_float(metric_weights.get(metric), 1.0), 0.0) for metric in metric_keys}
    weight_total = sum(weight_values.values()) or float(len(weight_values) or 1)
    normalized_weights = {metric: weight_values[metric] / weight_total for metric in metric_keys}
    top_weighted_row = (
        comparison_df.sort_values("weighted_score", ascending=False, na_position="last").iloc[0]
        if not comparison_df.empty and comparison_df["weighted_score"].notna().any()
        else None
    )
    compare_kpi_cards = [
        {
            "label": "Selected Policies",
            "value": str(len(selected_rule_ids)),
            "hint": "Rules in scope",
        },
        {
            "label": "Selected Communities",
            "value": str(len(selected_communities)),
            "hint": "Communities in scope",
        },
    ]
    compare_kpi_html = "".join(
        f"""
        <div class="compare-kpi-card" title="{html.escape(card['value'])}">
          <div class="compare-kpi-label">{html.escape(card['label'])}</div>
          <div class="compare-kpi-value">{html.escape(card['value'])}</div>
          <div class="compare-kpi-hint">{html.escape(card['hint'])}</div>
        </div>
        """
        for card in compare_kpi_cards
    )
    objective_legend_html = "".join(
        (
            f"""
            <span class="compare-objective-chip" title="{html.escape(config['label'])} {'maximize' if config['goal'] == 'max' else 'minimize'}">
              {html.escape(config['label'])} {'↑' if config['goal'] == 'max' else '↓'}
            </span>
            """
            if evaluation == "pareto"
            else f"""
            <span class="compare-objective-chip" title="{html.escape(config['label'])} weight {normalized_weights[metric]:.0%}">
              {html.escape(config['label'])} {normalized_weights[metric]:.0%}
            </span>
            """
        )
        for metric, config in COMPARISON_METRICS.items()
    )
    weight_inputs_html = "".join(
        f"""
        <label>{html.escape(config['label'])}
          <input type="number" name="weight_{metric}" value="{weight_values[metric]:.2f}" min="0" step="0.1" />
        </label>
        """
        for metric, config in COMPARISON_METRICS.items()
    )
    weighted_panel_html = (
        f"""
        <div class="compare-weight-grid">
          {weight_inputs_html}
        </div>
        """
        if evaluation == "weighted_score"
        else ""
    )
    policy_selector_html = _multi_checklist_html(
        "policy-checklist",
        "rule_ids",
        _phase2_rule_choices(global_df),
        selected_rule_ids,
        "Search policies",
    )
    community_selector_html = _multi_checklist_html(
        "community-checklist",
        "community_names",
        [(name, name) for name in all_communities],
        selected_communities,
        "Search communities",
    )
    top_weighted_chip = ""
    if evaluation == "weighted_score" and top_weighted_row is not None:
        top_weighted_chip = f"""
        <span class="compare-objective-chip is-highlight" title="{html.escape(str(top_weighted_row['row_label']))}">
          Top weighted: {html.escape(str(top_weighted_row['row_label']))} · {_format_comparison_value('weighted_score', top_weighted_row['weighted_score'])}
        </span>
        """
    controls_body = f"""
    <style>
      .compare-workspace-panel,
      .compare-workspace-panel *,
      .compare-workspace,
      .compare-sidebar,
      .compare-sidebar-card,
      .compare-main-panel,
      .compare-kpi-strip,
      .compare-kpi-card,
      .compare-main-grid,
      .compare-scatter-panel,
      .compare-scatter-meta,
      .compare-objective-legend {{
        box-sizing: border-box;
      }}
      .compare-workspace-panel {{
        padding: 12px;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow-x: clip;
      }}
      .compare-workspace {{
        display: grid;
        grid-template-columns: 332px minmax(0, 1fr);
        gap: 12px;
        align-items: start;
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .compare-sidebar {{
        min-width: 0;
        max-width: 100%;
      }}
      .compare-sidebar-card {{
        display: grid;
        gap: 8px;
        padding: 10px;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: var(--surface);
        width: 100%;
        max-width: 100%;
        min-width: 0;
        max-height: calc(100vh - 132px);
        overflow: auto;
        align-content: start;
      }}
      .compare-sidebar-section {{
        display: grid;
        gap: 5px;
        min-width: 0;
      }}
      .compare-sidebar-label {{
        font-size: 11px;
        font-weight: 800;
        color: var(--muted-soft);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .compare-sidebar-card label {{
        display: grid;
        gap: 6px;
        min-width: 0;
        font-size: 13px;
        font-weight: 700;
        color: var(--text);
      }}
      .compare-sidebar-card input,
      .compare-sidebar-card select {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        padding: 8px 10px;
        min-height: 38px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--surface);
      }}
      .compare-source-details {{
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface-soft);
        padding: 8px 10px;
      }}
      .compare-source-details summary {{
        cursor: pointer;
        font-size: 12px;
        font-weight: 700;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .compare-source-details[open] {{
        display: grid;
        gap: 8px;
      }}
      .compare-source-path {{
        font-size: 12px;
        color: var(--muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }}
      .compare-sidebar .seg-group,
      .compare-sidebar .metric-switch-list {{
        display: grid !important;
        grid-template-columns: 1fr !important;
        gap: 8px !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
      }}
      .compare-sidebar .seg-button {{
        width: 100% !important;
        min-width: 0;
        overflow: visible;
        text-overflow: clip;
        white-space: normal;
        justify-content: flex-start;
        text-align: left;
      }}
      .compare-sidebar .multi-check-card {{
        border-radius: 14px;
      }}
      .compare-sidebar .multi-check-toolbar {{
        gap: 6px;
        padding: 6px 8px;
        flex-wrap: nowrap;
      }}
      .compare-sidebar .multi-check-search {{
        min-width: 0;
        min-height: 32px !important;
        padding: 6px 9px !important;
      }}
      .compare-sidebar .multi-check-actions {{
        display: flex;
        flex-wrap: nowrap;
        gap: 4px;
        flex: 0 0 auto;
      }}
      .compare-sidebar .mini-button {{
        min-height: 28px;
        padding: 0 8px;
        font-size: 11px;
        white-space: nowrap;
      }}
      .compare-sidebar .multi-check-summary {{
        padding: 6px 8px 0;
        font-size: 11px;
      }}
      .compare-sidebar .multi-check-list {{
        max-height: 112px;
        padding: 6px 8px 8px;
        gap: 4px;
      }}
      .compare-sidebar .multi-check-item {{
        padding: 5px 8px;
        border-radius: 9px;
      }}
      .compare-sidebar .multi-check-item input {{
        width: 14px;
        height: 14px;
        transform: scale(0.82);
        transform-origin: center;
      }}
      .compare-sidebar .multi-check-copy {{
        font-size: 11px;
        line-height: 1.25;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .compare-sidebar-actions {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
      }}
      .compare-sidebar-actions .button,
      .compare-sidebar-actions button {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        min-height: 36px;
        padding: 0 10px;
        font-size: 12px;
      }}
      .compare-main-panel {{
        display: grid;
        gap: 6px;
        min-width: 0;
        max-width: 100%;
        align-content: start;
      }}
      .compare-sidebar-kpis {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
      }}
      .compare-objective-bar {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        min-width: 0;
        max-width: 100%;
        margin-bottom: 6px;
      }}
      .compare-objective-control {{
        display: grid;
        gap: 4px;
        min-width: 0;
      }}
      .compare-objective-control label {{
        font-size: 11px;
        font-weight: 800;
        color: var(--muted-soft);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .compare-objective-control select {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        padding: 8px 10px;
        min-height: 38px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--surface);
        font-size: 13px;
      }}
      .compare-kpi-strip {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        min-width: 0;
        max-width: 100%;
      }}
      .compare-kpi-card {{
        border: 1px solid var(--border);
        border-radius: 14px;
        background: var(--surface);
        padding: 8px 10px;
        min-width: 0;
        display: grid;
        gap: 2px;
        overflow: hidden;
      }}
      .compare-kpi-label {{
        font-size: 10px;
        font-weight: 800;
        color: var(--muted-soft);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .compare-kpi-value {{
        font-size: 14px;
        line-height: 1.1;
        font-weight: 800;
        color: var(--text);
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .compare-kpi-hint {{
        font-size: 10px;
        color: var(--muted);
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .compare-main-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 12px;
        align-items: start;
        min-width: 0;
        max-width: 100%;
      }}
      .compare-scatter-panel {{
        min-width: 0;
        max-width: 100%;
      }}
      .compare-scatter-title-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-width: 0;
      }}
      .compare-scatter-title-row .section-head.compact {{
        margin-bottom: 0;
        min-width: 0;
        flex: 0 1 auto;
      }}
      .compare-scatter-head {{
        display: grid;
        gap: 4px;
        margin-bottom: 2px;
        min-width: 0;
      }}
      .compare-scatter-meta {{
        display: grid;
        gap: 6px;
        margin-bottom: 0;
      }}
      .compare-objective-legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        min-width: 0;
        justify-content: flex-end;
        flex: 1 1 auto;
      }}
      .compare-objective-chip {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--surface-soft);
        font-size: 11px;
        font-weight: 700;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
      }}
      .compare-objective-chip.is-highlight {{
        background: #eef2ff;
        border-color: #c7d2fe;
        color: #3730a3;
      }}
      .compare-scatter-panel .plot-frame,
      .compare-scatter-panel .compare-plot {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      .compare-weight-grid {{
        padding: 8px 10px;
        border-radius: 14px;
      }}
      .compare-weight-grid input {{
        min-height: 38px;
      }}
      .compare-scatter-panel .section-head.compact {{
        margin-bottom: 0;
      }}
      .compare-scatter-panel .section-title {{
        font-size: 18px;
        line-height: 1.05;
      }}
      .compare-plot-toolbar {{
        margin: 2px 0 6px;
        gap: 8px;
      }}
      .compare-plot-toolbar .plot-action-button {{
        min-height: 34px;
        padding: 0 12px;
        font-size: 12px;
      }}
      .compare-plot-note {{
        font-size: 11px;
        line-height: 1.25;
      }}
      .compare-scatter-panel .plot-frame {{
        min-height: min(58vh, 520px);
      }}
      .multiobjective-grid {{
        grid-template-columns: minmax(360px, 0.95fr) minmax(420px, 1.05fr);
        gap: 18px;
        align-items: stretch;
      }}
      .multiobjective-stack {{
        display: flex;
        flex-direction: column;
        gap: 18px;
        height: 100%;
        min-height: 0;
      }}
      .multiobjective-stack .chart-card,
      .multiobjective-grid > .chart-card {{
        flex: 1 1 auto;
        height: 100%;
        min-height: 0;
      }}
      .multiobjective-grid .chart-card {{
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        border-color: #E8F4F9;
      }}
      .multiobjective-grid .plot-frame {{
        flex: 1 1 auto;
        min-height: 0;
      }}
      #compare-multi-score {{
        min-height: 340px;
      }}
      #compare-parcoords {{
        min-height: 340px;
      }}
      @media (max-width: 1180px) {{
        .compare-workspace {{
          grid-template-columns: 1fr;
        }}
        .compare-sidebar-card {{
          max-height: none;
        }}
        .compare-kpi-strip {{ grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }}
      }}
      @media (max-width: 720px) {{
        .compare-kpi-strip {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .compare-objective-bar {{
          grid-template-columns: 1fr;
        }}
        .compare-scatter-title-row {{
          flex-direction: column;
          align-items: flex-start;
        }}
        .compare-objective-legend {{
          justify-content: flex-start;
        }}
        .compare-sidebar-actions {{
          grid-template-columns: 1fr;
        }}
        .compare-sidebar-actions > :first-child {{
          grid-column: auto;
        }}
      }}
      @media (max-width: 560px) {{
        .compare-kpi-strip {{
          grid-template-columns: 1fr;
        }}
        .compare-sidebar .multi-check-toolbar {{
          flex-wrap: wrap;
        }}
      }}
    </style>
    <div class="panel compare-workspace-panel">
      <div class="compare-workspace">
        <aside class="compare-sidebar">
          <form id="compare-filter-form" class="compare-form compare-sidebar-card" method="get" action="/phase2/compare">
            {'<input type="hidden" name="embedded" value="1" />' if embedded else ''}
            <input type="hidden" name="mode" value="{html.escape(mode)}" />
            <input type="hidden" name="evaluation" value="{html.escape(evaluation)}" />
            <input type="hidden" name="phase2_root" value="{html.escape(phase2_root)}" />
            {weighted_panel_html}
            <div class="compare-sidebar-section">
              <div class="compare-sidebar-label">Policies</div>
              {policy_selector_html}
            </div>
            <div class="compare-sidebar-section">
              <div class="compare-sidebar-label">Communities</div>
              {community_selector_html}
            </div>
            <div class="compare-sidebar-section">
              <div class="compare-sidebar-label">Actions</div>
              <div class="compare-sidebar-actions">
                <button type="submit" class="button action-primary">Apply filters</button>
                <button type="submit" class="button action-secondary">Refresh workspace</button>
              </div>
            </div>
            <div class="compare-sidebar-section">
              <div class="compare-sidebar-kpis">
                {compare_kpi_html}
              </div>
            </div>
          </form>
        </aside>
        <section class="compare-main-panel">
          <div class="compare-main-grid">
            <div class="panel compare-scatter-panel">
              <div class="compare-scatter-head">
                <div class="compare-scatter-title-row">
                  <div class="section-head compact">
                    <div class="section-title">Pareto Trade-off Scatter</div>
                  </div>
                  <div class="compare-objective-legend">
                    {objective_legend_html}
                    {top_weighted_chip}
                  </div>
                </div>
                <div class="compare-objective-bar">
                  <div class="compare-objective-control">
                    <label for="compare-objective-1">Objective 1</label>
                    <select id="compare-objective-1" name="x_metric" form="compare-filter-form">
                      {_option_html([(cfg['label'], key) for key, cfg in COMPARISON_METRICS.items()], x_metric)}
                    </select>
                  </div>
                  <div class="compare-objective-control">
                    <label for="compare-objective-2">Objective 2</label>
                    <select id="compare-objective-2" name="y_metric" form="compare-filter-form">
                      {_option_html([(cfg['label'], key) for key, cfg in COMPARISON_METRICS.items()], y_metric)}
                    </select>
                  </div>
                </div>
              </div>
              <div class="compare-plot-toolbar">
                <button type="button" id="compare-frontier-toggle" class="plot-action-button action-primary">Compute Pareto frontier</button>
                <div class="compare-plot-note">Labels use policy caps when available.</div>
              </div>
              <div id="compare-scatter" class="plot-frame compare-plot"></div>
            </div>
          </div>
        </section>
      </div>
    </div>
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Multi-objective Comparison</div>
        <div class="section-copy">This workspace uses all objectives together instead of only the two axes above. It highlights the strongest overall candidate under the current evaluation lens and reveals where each policy is strong or weak across the full objective set.</div>
      </div>
      <div class="multiobjective-grid">
        <div class="multiobjective-stack">
          <div id="compare-multi-highlight" class="objective-highlight multiobjective-highlight"></div>
          <div class="chart-card">
            <div class="chart-title">Composite Multi-objective Ranking</div>
            <div id="compare-multi-score" class="plot-frame"></div>
            <div id="compare-multi-score-note" class="multiobjective-note"></div>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-title">Objective Score Heatmap</div>
          <div id="compare-parcoords" class="plot-frame compare-plot"></div>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Comparison Table</div>
        <div class="section-copy">Sort by any metric to inspect policy trade-offs across the current selection.</div>
      </div>
      <div class="table-toolbar">
        <input id="compare-search" class="table-search" type="search" placeholder="Search rule, community, policy content, or Pareto status" />
      </div>
      <div id="compare-table"></div>
    </div>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
      (function() {{
        const rows = {json.dumps(comparison_records, ensure_ascii=False)};
        const metricConfig = {{
          ...{json.dumps(COMPARISON_METRICS, ensure_ascii=False)},
          weighted_score: {{ label: "Weighted Score", format: "score" }},
        }};
        const xMetric = {json.dumps(x_metric, ensure_ascii=False)};
        const yMetric = {json.dumps(y_metric, ensure_ascii=False)};
        const evaluation = {json.dumps(evaluation, ensure_ascii=False)};
        const objectiveKeys = {json.dumps(metric_keys, ensure_ascii=False)};
        const normalizedWeights = {json.dumps(normalized_weights, ensure_ascii=False)};
        const tableColumns = {json.dumps(table_columns, ensure_ascii=False)};
        const sortState = evaluation === "weighted_score"
          ? {{ key: "weighted_score", dir: "desc" }}
          : {{ key: "pareto_status", dir: "asc" }};
        const searchInput = document.getElementById("compare-search");
        const frontierToggle = document.getElementById("compare-frontier-toggle");
        const policyCountEl = document.getElementById("filter-policy-count");
        const communityCountEl = document.getElementById("filter-community-count");
        const objective1Select = document.getElementById("compare-objective-1");
        const objective2Select = document.getElementById("compare-objective-2");
        const objectiveOptions = objectiveKeys.map((key) => ({{ value: key, label: metricConfig[key]?.label || key }}));
        let showFrontier = false;

        function initChecklist(rootId) {{
          const root = document.getElementById(rootId);
          if (!root) return null;
          const search = root.querySelector(".multi-check-search");
          const countEl = root.querySelector(".multi-check-count");
          const boxes = Array.from(root.querySelectorAll('input[type="checkbox"]'));
          const items = Array.from(root.querySelectorAll(".multi-check-item"));
          const selectAll = root.querySelector('[data-action="all"]');
          const clearAll = root.querySelector('[data-action="clear"]');

          function updateCount() {{
            const checkedCount = boxes.filter((box) => box.checked).length;
            if (countEl) countEl.textContent = String(checkedCount);
          }}

          function applyFilter() {{
            const query = String(search?.value || "").trim().toLowerCase();
            items.forEach((item) => {{
              const haystack = item.dataset.filter || "";
              item.classList.toggle("is-hidden", !!query && !haystack.includes(query));
            }});
          }}

          boxes.forEach((box) => box.addEventListener("change", updateCount));
          search?.addEventListener("input", applyFilter);
          selectAll?.addEventListener("click", () => {{
            boxes.forEach((box) => {{ box.checked = true; }});
            updateCount();
            root.dispatchEvent(new CustomEvent("selectionchange"));
          }});
          clearAll?.addEventListener("click", () => {{
            boxes.forEach((box) => {{ box.checked = false; }});
            updateCount();
            root.dispatchEvent(new CustomEvent("selectionchange"));
          }});
          updateCount();
          applyFilter();
          return {{
            getCount() {{
              return boxes.filter((box) => box.checked).length;
            }},
          }};
        }}

        function syncFilterSummary(policyList, communityList) {{
          if (policyCountEl && policyList) policyCountEl.textContent = String(policyList.getCount());
          if (communityCountEl && communityList) communityCountEl.textContent = String(communityList.getCount());
        }}

        function formatValue(key, value) {{
          if (value === null || value === undefined || value === "") return "N/A";
          const config = metricConfig[key];
          if (!config) return String(value);
          if (typeof value !== "number") return String(value);
          if (config.format === "ratio") return (value * 100).toFixed(1) + "%";
          if (config.format === "currency") return "¥" + new Intl.NumberFormat("en-US", {{ maximumFractionDigits: 0 }}).format(value);
          if (config.format === "float") return value.toFixed(3);
          if (config.format === "score") return (value * 100).toFixed(1) + "/100";
          return new Intl.NumberFormat("en-US", {{ maximumFractionDigits: 3 }}).format(value);
        }}

        function compareValues(left, right, key, dir) {{
          const factor = dir === "desc" ? -1 : 1;
          const paretoOrder = {{ "Pareto-optimal": 0, "Dominated": 1, "Incomplete": 2 }};
          if (key === "pareto_status") {{
            return ((paretoOrder[left] ?? 99) - (paretoOrder[right] ?? 99)) * factor;
          }}
          if (typeof left === "number" && typeof right === "number") return (left - right) * factor;
          return String(left ?? "").localeCompare(String(right ?? ""), undefined, {{ numeric: true, sensitivity: "base" }}) * factor;
        }}

        function filteredRows() {{
          const search = (searchInput.value || "").trim().toLowerCase();
          if (!search) return [...rows];
          return rows.filter((row) =>
            Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(search))
          );
        }}

        function sortedRows() {{
          const cloned = filteredRows();
          cloned.sort((left, right) => compareValues(left[sortState.key], right[sortState.key], sortState.key, sortState.dir));
          return cloned;
        }}

        function buildObjectiveOptionHtml(options, selectedValue) {{
          return options.map((option) => {{
            const selected = option.value === selectedValue ? " selected" : "";
            return `<option value="${{option.value}}"${{selected}}>${{option.label}}</option>`;
          }}).join("");
        }}

        function syncObjectiveSelects() {{
          if (!objective1Select || !objective2Select) return;
          const selectedObjective1 = objective1Select.value || objectiveOptions[0]?.value || "";
          const availableObjective2 = objectiveOptions.filter((option) => option.value !== selectedObjective1);
          let nextObjective2 = objective2Select.value;
          if (!availableObjective2.some((option) => option.value === nextObjective2)) {{
            nextObjective2 = availableObjective2[0]?.value || "";
          }}
          objective2Select.innerHTML = buildObjectiveOptionHtml(availableObjective2, nextObjective2);
        }}

        function pointDominates(left, right, objectiveKeys) {{
          const epsilon = 1e-12;
          let betterOrEqual = true;
          let strictlyBetter = false;
          for (const key of objectiveKeys) {{
            const goal = metricConfig[key]?.goal || "max";
            const leftValue = left[key];
            const rightValue = right[key];
            if (typeof leftValue !== "number" || typeof rightValue !== "number") return false;
            if (goal === "max") {{
              if (leftValue + epsilon < rightValue) {{
                betterOrEqual = false;
                break;
              }}
              if (leftValue > rightValue + epsilon) strictlyBetter = true;
            }} else {{
              if (leftValue > rightValue + epsilon) {{
                betterOrEqual = false;
                break;
              }}
              if (leftValue + epsilon < rightValue) strictlyBetter = true;
            }}
          }}
          return betterOrEqual && strictlyBetter;
        }}

        function computeFrontierRows(sourceRows) {{
          const candidates = sourceRows.filter((row) => typeof row[xMetric] === "number" && typeof row[yMetric] === "number");
          const objectiveKeys = [xMetric, yMetric];
          const frontier = candidates.filter((candidate, index) =>
            !candidates.some((other, otherIndex) => otherIndex !== index && pointDominates(other, candidate, objectiveKeys))
          );
          frontier.sort((left, right) => (left[xMetric] ?? 0) - (right[xMetric] ?? 0));
          return frontier;
        }}

        function escapeHtml(value) {{
          return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
        }}

        function renderScatterFallback() {{
          const target = document.getElementById("compare-scatter");
          if (!target) return;
          const validRows = rows.filter((row) => typeof row[xMetric] === "number" && typeof row[yMetric] === "number");
          if (!validRows.length) {{
            target.innerHTML = '<div class="chart-empty">No numeric values are available for the selected objectives.</div>';
            return;
          }}
          const width = 760;
          const height = 430;
          const margin = {{ left: 68, right: 24, top: 28, bottom: 64 }};
          const xValues = validRows.map((row) => row[xMetric]);
          const yValues = validRows.map((row) => row[yMetric]);
          const minX = Math.min(...xValues);
          const maxX = Math.max(...xValues);
          const minY = Math.min(...yValues);
          const maxY = Math.max(...yValues);
          const pad = (min, max) => {{
            const span = max - min;
            if (Math.abs(span) <= 1e-12) return [min - 0.5, max + 0.5];
            return [min - span * 0.08, max + span * 0.08];
          }};
          const [x0, x1] = pad(minX, maxX);
          const [y0, y1] = pad(minY, maxY);
          const plotW = width - margin.left - margin.right;
          const plotH = height - margin.top - margin.bottom;
          const sx = (value) => margin.left + ((value - x0) / (x1 - x0 || 1)) * plotW;
          const sy = (value) => margin.top + plotH - ((value - y0) / (y1 - y0 || 1)) * plotH;
          const ticks = (min, max, count = 5) => Array.from({{ length: count }}, (_, index) => min + ((max - min) * index) / Math.max(count - 1, 1));
          const xTicks = ticks(x0, x1);
          const yTicks = ticks(y0, y1);
          const circles = validRows.map((row) => {{
            const isPareto = row.pareto_status === "Pareto-optimal";
            const color = isPareto ? "#36AABF" : (row.pareto_status === "Dominated" ? "#B2DBE4" : "#e2e8f0");
            const radius = isPareto ? 7 : 6;
            const label = escapeHtml(row.row_label || row.rule_id || "Policy");
            const detail = `${{label}}\n${{metricConfig[xMetric]?.label || xMetric}}: ${{formatValue(xMetric, row[xMetric])}}\n${{metricConfig[yMetric]?.label || yMetric}}: ${{formatValue(yMetric, row[yMetric])}}\n${{row.pareto_status || "N/A"}}`;
            return `<a href="${{escapeHtml(row.explore_url || "#")}}"><circle cx="${{sx(row[xMetric]).toFixed(1)}}" cy="${{sy(row[yMetric]).toFixed(1)}}" r="${{radius}}" fill="${{color}}" stroke="#ffffff" stroke-width="1.8" opacity="0.92"><title>${{escapeHtml(detail)}}</title></circle></a>`;
          }}).join("");
          const xGrid = xTicks.map((tick) => {{
            const x = sx(tick);
            return `<line x1="${{x.toFixed(1)}}" y1="${{margin.top}}" x2="${{x.toFixed(1)}}" y2="${{margin.top + plotH}}" stroke="#f1f5f9" /><text x="${{x.toFixed(1)}}" y="${{height - 28}}" text-anchor="middle" font-size="11" fill="#64748b">${{escapeHtml(formatValue(xMetric, tick))}}</text>`;
          }}).join("");
          const yGrid = yTicks.map((tick) => {{
            const y = sy(tick);
            return `<line x1="${{margin.left}}" y1="${{y.toFixed(1)}}" x2="${{margin.left + plotW}}" y2="${{y.toFixed(1)}}" stroke="#f1f5f9" /><text x="${{margin.left - 10}}" y="${{(y + 4).toFixed(1)}}" text-anchor="end" font-size="11" fill="#64748b">${{escapeHtml(formatValue(yMetric, tick))}}</text>`;
          }}).join("");
          target.innerHTML = `
            <svg class="fallback-scatter" viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="Pareto trade-off scatter" style="width:100%;height:100%;min-height:430px;display:block;">
              <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="#ffffff" />
              ${{xGrid}}
              ${{yGrid}}
              <line x1="${{margin.left}}" y1="${{margin.top + plotH}}" x2="${{margin.left + plotW}}" y2="${{margin.top + plotH}}" stroke="#cbd5e1" />
              <line x1="${{margin.left}}" y1="${{margin.top}}" x2="${{margin.left}}" y2="${{margin.top + plotH}}" stroke="#cbd5e1" />
              ${{circles}}
              <text x="${{margin.left + plotW / 2}}" y="${{height - 6}}" text-anchor="middle" font-size="13" fill="#475569">${{escapeHtml(metricConfig[xMetric]?.label || xMetric)}}</text>
              <text x="18" y="${{margin.top + plotH / 2}}" transform="rotate(-90 18 ${{margin.top + plotH / 2}})" text-anchor="middle" font-size="13" fill="#475569">${{escapeHtml(metricConfig[yMetric]?.label || yMetric)}}</text>
            </svg>
          `;
        }}

        function objectiveExtents(sourceRows) {{
          const extents = {{}};
          objectiveKeys.forEach((key) => {{
            const values = sourceRows
              .map((row) => row[key])
              .filter((value) => typeof value === "number" && !Number.isNaN(value));
            extents[key] = values.length
              ? {{ min: Math.min(...values), max: Math.max(...values) }}
              : null;
          }});
          return extents;
        }}

        function normalizedObjectiveScore(value, metricKey, extents) {{
          if (typeof value !== "number" || Number.isNaN(value)) return null;
          const extent = extents[metricKey];
          if (!extent) return null;
          const span = extent.max - extent.min;
          if (span <= 1e-12) return 1;
          return (metricConfig[metricKey]?.goal || "max") === "max"
            ? (value - extent.min) / span
            : (extent.max - value) / span;
        }}

        function multiObjectiveRows(sourceRows) {{
          const extents = objectiveExtents(sourceRows);
          return sourceRows
            .map((row) => {{
              const objectiveScores = {{}};
              let weightedSum = 0;
              let weightTotal = 0;
              objectiveKeys.forEach((metricKey) => {{
                const score = normalizedObjectiveScore(row[metricKey], metricKey, extents);
                objectiveScores[metricKey] = score;
                if (score === null) return;
                const weight = evaluation === "weighted_score"
                  ? Number(normalizedWeights[metricKey] || 0)
                  : (1 / Math.max(objectiveKeys.length, 1));
                weightedSum += score * weight;
                weightTotal += weight;
              }});
              const fallbackComposite = weightTotal > 0 ? weightedSum / weightTotal : null;
              return {{
                ...row,
                _objective_scores: objectiveScores,
                _multi_score: evaluation === "weighted_score" && typeof row.weighted_score === "number"
                  ? row.weighted_score
                  : fallbackComposite,
              }};
            }})
            .filter((row) => typeof row._multi_score === "number" && !Number.isNaN(row._multi_score))
            .sort((left, right) => right._multi_score - left._multi_score);
        }}

        function renderScatter() {{
          if (!rows.length) {{
            document.getElementById("compare-scatter").innerHTML = '<div class="chart-empty">No comparison rows available for the current selection.</div>';
            return;
          }}
          if (typeof Plotly === "undefined") {{
            renderScatterFallback();
            return;
          }}
          const categories = [
            {{ status: "Dominated", color: "#B2DBE4", size: 12 }},
            {{ status: "Pareto-optimal", color: "#36AABF", size: 15 }},
            {{ status: "Incomplete", color: "#e2e8f0", size: 11 }},
          ];
          const traces = categories.map((category) => {{
            const subset = rows.filter((row) => row.pareto_status === category.status && row[xMetric] !== null && row[yMetric] !== null);
            return {{
              x: subset.map((row) => row[xMetric]),
              y: subset.map((row) => row[yMetric]),
              text: subset.map((row) => row.row_label),
              customdata: subset.map((row) => [row.pareto_status, row.explore_url, row.community_count ?? row.sample_count ?? "N/A"]),
              type: "scatter",
              mode: "markers",
              name: category.status,
              marker: {{
                size: category.size,
                color: category.color,
                line: {{ color: "#ffffff", width: category.status === "Pareto-optimal" ? 2.2 : 1.2 }},
                opacity: category.status === "Incomplete" ? 0.45 : 0.9
              }},
              hovertemplate:
                "<b>%{{text}}</b><br>" +
                "{html.escape(COMPARISON_METRICS[x_metric]['label'])}: %{{x}}<br>" +
                "{html.escape(COMPARISON_METRICS[y_metric]['label'])}: %{{y}}<br>" +
                "Pareto Status: %{{customdata[0]}}<br>Communities averaged: %{{customdata[2]}}<extra></extra>",
            }};
          }}).filter((trace) => trace.x.length);

          if (showFrontier) {{
            const frontierRows = computeFrontierRows(rows);
            if (frontierRows.length) {{
              traces.push({{
                x: frontierRows.map((row) => row[xMetric]),
                y: frontierRows.map((row) => row[yMetric]),
                text: frontierRows.map((row) => row.frontier_label || row.row_label),
                customdata: frontierRows.map((row) => [row.pareto_status, row.explore_url, row.community_count ?? row.sample_count ?? "N/A"]),
                type: "scatter",
                mode: "lines+markers+text",
                name: "Pareto Frontier",
                textposition: "top center",
                textfont: {{
                  size: 12,
                  color: "#1e3a8a",
                  family: "Microsoft YaHei, PingFang SC, sans-serif",
                }},
                line: {{
                  color: "#268CA0",
                  width: 2.4,
                }},
                marker: {{
                  size: 12,
                  color: "#36AABF",
                  line: {{ color: "#ffffff", width: 1.8 }},
                }},
                hovertemplate:
                  "<b>%{{text}}</b><br>" +
                  "{html.escape(COMPARISON_METRICS[x_metric]['label'])}: %{{x}}<br>" +
                  "{html.escape(COMPARISON_METRICS[y_metric]['label'])}: %{{y}}<br>" +
                  "Communities averaged: %{{customdata[2]}}<br>2D Pareto frontier under current objectives<extra></extra>",
              }});
            }}
          }}

          Plotly.react("compare-scatter", traces, {{
            margin: {{ l: 56, r: 20, t: 20, b: 50 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: {json.dumps(COMPARISON_METRICS[x_metric]['label'])}, gridcolor: "#f1f5f9", zeroline: false }},
            yaxis: {{ title: {json.dumps(COMPARISON_METRICS[y_metric]['label'])}, gridcolor: "#f1f5f9", zeroline: false }},
            hovermode: "closest",
            legend: {{ orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "left", x: 0 }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 13, color: "#4b5563" }},
          }}, {{ displayModeBar: false, responsive: true }});

          const chart = document.getElementById("compare-scatter");
          if (chart && chart.on && chart.dataset.boundCompareClick !== "true") {{
            chart.on("plotly_click", (event) => {{
              const target = event.points && event.points.length ? event.points[0].customdata?.[1] : null;
              if (target) window.location.href = target;
            }});
            chart.dataset.boundCompareClick = "true";
          }}
        }}

        function syncMultiObjectiveCardHeights() {{
          const grid = document.querySelector(".multiobjective-grid");
          const left = document.querySelector(".multiobjective-stack");
          const right = document.querySelector(".multiobjective-grid > .chart-card");
          if (!grid || !left || !right) return;
          left.style.minHeight = "";
          right.style.minHeight = "";
          if (window.innerWidth <= 900) return;
          window.requestAnimationFrame(() => {{
            const maxHeight = Math.max(left.getBoundingClientRect().height, right.getBoundingClientRect().height);
            if (maxHeight > 0) {{
              left.style.minHeight = `${{Math.ceil(maxHeight)}}px`;
              right.style.minHeight = `${{Math.ceil(maxHeight)}}px`;
            }}
          }});
        }}

        function renderMultiObjective() {{
          const rankingRoot = document.getElementById("compare-multi-score");
          const parallelRoot = document.getElementById("compare-parcoords");
          const highlightRoot = document.getElementById("compare-multi-highlight");
          const noteRoot = document.getElementById("compare-multi-score-note");
          if (typeof Plotly === "undefined") {{
            if (rankingRoot) rankingRoot.innerHTML = '<div class="chart-empty">Plotly is unavailable; charts will render after the plotting library loads.</div>';
            if (parallelRoot) parallelRoot.innerHTML = '<div class="chart-empty">Plotly is unavailable; charts will render after the plotting library loads.</div>';
            if (highlightRoot) highlightRoot.innerHTML = '<div class="objective-highlight-label">Best Multi-objective Candidate</div><div class="objective-highlight-value">N/A</div><div class="objective-highlight-hint">Plotly is unavailable.</div>';
            if (noteRoot) noteRoot.textContent = "";
            syncMultiObjectiveCardHeights();
            return;
          }}
          const rankedRows = multiObjectiveRows(rows);
          if (!rankedRows.length) {{
            if (rankingRoot) rankingRoot.innerHTML = '<div class="chart-empty">No complete multi-objective rows are available for the current selection.</div>';
            if (parallelRoot) parallelRoot.innerHTML = '<div class="chart-empty">No multi-objective profile can be drawn.</div>';
            if (highlightRoot) highlightRoot.innerHTML = '<div class="objective-highlight-label">Best Multi-objective Candidate</div><div class="objective-highlight-value">N/A</div><div class="objective-highlight-hint">No complete row available under the current selection.</div>';
            if (noteRoot) noteRoot.textContent = "";
            syncMultiObjectiveCardHeights();
            return;
          }}

          const bestRow = rankedRows[0];
          const scoreLabel = evaluation === "weighted_score" ? "Weighted composite score" : "Equal-weight reference score";
          if (highlightRoot) {{
            highlightRoot.innerHTML = `
              <div class="objective-highlight-label">Best Multi-objective Candidate</div>
              <div class="objective-highlight-value">${{bestRow.row_label || bestRow.rule_id || "N/A"}}</div>
              <div class="objective-highlight-hint">${{scoreLabel}}: ${{formatValue("weighted_score", bestRow._multi_score)}} · Pareto: ${{bestRow.pareto_status || "N/A"}}</div>
            `;
          }}
          if (noteRoot) {{
            noteRoot.textContent = evaluation === "weighted_score"
              ? "Ranking uses the current weight settings across all objectives."
              : "Ranking uses an equal-weight reference score across all objectives so you can pick a single candidate without replacing Pareto analysis.";
          }}

          const rankingRows = [...rankedRows.slice(0, Math.min(rankedRows.length, 10))].reverse();
          Plotly.react("compare-multi-score", [{{
            type: "bar",
            orientation: "h",
            x: rankingRows.map((row) => row._multi_score * 100),
            y: rankingRows.map((row) => row.row_label),
            customdata: rankingRows.map((row) => [row.explore_url]),
            marker: {{
              color: rankingRows.map((row) => row.pareto_status === "Pareto-optimal" ? "#36AABF" : "#B2DBE4"),
              line: {{ color: "#ffffff", width: 1.2 }},
            }},
            hovertemplate: "<b>%{{y}}</b><br>Composite Score: %{{x:.1f}}/100<extra></extra>",
          }}], {{
            margin: {{ l: 150, r: 18, t: 10, b: 40 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: "Composite Score", range: [0, 100], gridcolor: "#f1f5f9", zeroline: false }},
            yaxis: {{ title: "", automargin: true }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 13, color: "#4b5563" }},
            showlegend: false,
          }}, {{ displayModeBar: false, responsive: true }});

          const profileRows = rankedRows.slice(0, Math.min(rankedRows.length, 10));
          const metricLabels = objectiveKeys.map((metricKey) => metricConfig[metricKey]?.label || metricKey);
          const profileLabels = profileRows.map((row, index) => {{
            const base = row.frontier_label || row.row_label || row.rule_id || `Policy ${{index + 1}}`;
            return `${{index + 1}}. ${{base}}`;
          }});
          const heatmapValues = profileRows.map((row) =>
            objectiveKeys.map((metricKey) => Math.round((row._objective_scores?.[metricKey] ?? 0) * 1000) / 10)
          );
          const heatmapHover = profileRows.map((row) =>
            objectiveKeys.map((metricKey) => [row.row_label || row.rule_id || "Policy", scoreLabel, formatValue("weighted_score", row._multi_score)])
          );
          Plotly.react("compare-parcoords", [{{
            type: "heatmap",
            z: heatmapValues,
            x: metricLabels,
            y: profileLabels,
            text: heatmapValues.map((values) => values.map((value) => `${{value.toFixed(1)}}`)),
            texttemplate: "%{{text}}",
            textfont: {{ size: 11, color: "#0f172a" }},
            customdata: heatmapHover,
            hovertemplate: "<b>%{{customdata[0]}}</b><br>%{{x}}: %{{z:.1f}}/100<br>%{{customdata[1]}}: %{{customdata[2]}}<extra></extra>",
            colorscale: [[0, "#F3FAFC"], [0.35, "#CFEAF0"], [0.7, "#84CDDA"], [1, "#268CA0"]],
            zmin: 0,
            zmax: 100,
            colorbar: {{
              title: "Objective score",
              tickformat: ".0f",
              ticksuffix: "/100",
              thickness: 12,
            }},
          }}], {{
            margin: {{ l: 245, r: 68, t: 16, b: 92 }},
            paper_bgcolor: "rgba(255,255,255,0)",
            plot_bgcolor: "rgba(255,255,255,0)",
            xaxis: {{
              side: "bottom",
              tickangle: -28,
              automargin: true,
              gridcolor: "rgba(219,234,254,0.7)",
              tickfont: {{ size: 11, color: "#334155" }},
            }},
            yaxis: {{
              automargin: true,
              tickfont: {{ size: 11, color: "#475569" }},
            }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 12, color: "#334155" }},
          }}, {{ displayModeBar: false, responsive: true }});

          const rankingChart = document.getElementById("compare-multi-score");
          if (rankingChart && rankingChart.on && rankingChart.dataset.boundMultiClick !== "true") {{
            rankingChart.on("plotly_click", (event) => {{
              const target = event.points && event.points.length ? event.points[0].customdata?.[0] : null;
              if (target) window.location.href = target;
            }});
            rankingChart.dataset.boundMultiClick = "true";
          }}
          syncMultiObjectiveCardHeights();
        }}

        window.addEventListener("resize", () => {{
          window.clearTimeout(window.__compareMultiObjectiveResizeTimer);
          window.__compareMultiObjectiveResizeTimer = window.setTimeout(syncMultiObjectiveCardHeights, 120);
        }});

        function renderTable() {{
          const container = document.getElementById("compare-table");
          const rowsToRender = sortedRows();
          const headerHtml = tableColumns.map((column) => {{
            const active = sortState.key === column.key ? ` is-sorted sort-${{sortState.dir}}` : "";
            return `<th class="table-header${{active}}" data-key="${{column.key}}">${{column.label}}</th>`;
          }}).join("");
          const bodyHtml = rowsToRender.map((row) => {{
            const rowClass = row.pareto_status === "Pareto-optimal" ? "table-row is-active" : "table-row";
            const cells = tableColumns.map((column) => {{
              if (column.key === "explore_url") {{
                return row.explore_url
                  ? `<td class="table-cell"><a class="inline-table-link" href="${{row.explore_url}}">Open</a></td>`
                  : `<td class="table-cell">N/A</td>`;
              }}
              const align = metricConfig[column.key] || column.key === "community_count" || column.key === "sample_count" ? " align-right" : "";
              const displayValue = metricConfig[column.key] ? formatValue(column.key, row[column.key]) : String(row[column.key] ?? "N/A");
              return `<td class="table-cell${{align}}">${{displayValue}}</td>`;
            }}).join("");
            return `<tr class="${{rowClass}}">${{cells}}</tr>`;
          }}).join("") || `<tr><td class="table-empty" colspan="${{tableColumns.length}}">No rows available for the current selection.</td></tr>`;
          container.innerHTML = `<div class="table-wrap"><table class="interactive-table"><thead><tr>${{headerHtml}}</tr></thead><tbody>${{bodyHtml}}</tbody></table></div>`;
          container.querySelectorAll("th[data-key]").forEach((header) => {{
            header.addEventListener("click", () => {{
              const key = header.dataset.key;
              if (sortState.key === key) {{
                sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
              }} else {{
                sortState.key = key;
                sortState.dir = "asc";
              }}
              renderTable();
            }});
          }});
        }}

        searchInput.addEventListener("input", renderTable);
        frontierToggle?.addEventListener("click", () => {{
          showFrontier = !showFrontier;
          frontierToggle.textContent = showFrontier ? "Hide Pareto frontier" : "Compute Pareto frontier";
          frontierToggle.classList.toggle("is-active", showFrontier);
          renderScatter();
        }});
        objective1Select?.addEventListener("change", syncObjectiveSelects);
        const policyChecklist = initChecklist("policy-checklist");
        const communityChecklist = initChecklist("community-checklist");
        document.getElementById("policy-checklist")?.addEventListener("change", () => syncFilterSummary(policyChecklist, communityChecklist));
        document.getElementById("community-checklist")?.addEventListener("change", () => syncFilterSummary(policyChecklist, communityChecklist));
        document.getElementById("policy-checklist")?.addEventListener("selectionchange", () => syncFilterSummary(policyChecklist, communityChecklist));
        document.getElementById("community-checklist")?.addEventListener("selectionchange", () => syncFilterSummary(policyChecklist, communityChecklist));
        syncFilterSummary(policyChecklist, communityChecklist);
        syncObjectiveSelects();
        renderScatter();
        renderMultiObjective();
        renderTable();
      }})();
    </script>
    """
    return _html_shell("Policy Comparison Workspace", controls_body, embedded=embedded)


def _build_run_setup_page(embedded: bool = False) -> str:
    api_defaults = load_local_api_defaults()
    utility_category_defs_json = json.dumps(UTILITY_CATEGORY_DEFS, ensure_ascii=False)
    utility_field_defs_json = json.dumps(UTILITY_FIELD_DEFS, ensure_ascii=False)
    default_selected_categories_json = json.dumps(DEFAULT_SELECTED_UTILITY_CATEGORIES, ensure_ascii=False)
    initial_default_community = _display_path(DEFAULT_COMMUNITY_CSV if DEFAULT_COMMUNITY_CSV.exists() else _default_community_csv())
    initial_default_boundary = _display_path(DEFAULT_BOUNDARY_SHP if DEFAULT_BOUNDARY_SHP.exists() else (_resolve_shape_path(None) or ""))
    embedded_defaults_json = json.dumps(
        {
            "community_file": initial_default_community,
            "boundary_path": initial_default_boundary,
            "output_dir": _default_output_dir_ui(),
            "agents_output_dir": _default_agents_output_dir_ui(),
            "model_name": api_defaults.get("model") or _default_model_name(),
            "rounds": 8,
            "agreement_mode": "by_build_year",
            "agreement_fixed_ratio": 1.0,
            "agreement_current_year": _system_current_year(),
            "max_extension_ratio": 0.3,
            "cash_subsidy_cap": 0.1,
            "developer_min_profit_rate": DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
            "planner_soft_policy_text": "",
            "residents_per_household": DEFAULT_RESIDENTS_PER_HOUSEHOLD,
            "vacancy_ratio": DEFAULT_VACANCY_RATIO,
            "representatives_per_community": DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
            "hardship_quantile": DEFAULT_HARDSHIP_QUANTILE,
            "api_key": "",
            "api_base_url": api_defaults.get("base_url") or _default_llm_base_url(),
            "repeat_count": 1,
            "api_key_loaded": bool(api_defaults.get("api_key")),
            "api_key_masked": api_defaults.get("api_key_masked", ""),
            "api_key_source": api_defaults.get("api_key_source", "manual"),
            "agreement_rules_table": DEFAULT_AGREEMENT_RULE_ROWS.to_dict(orient="records"),
            "selected_utility_categories": DEFAULT_SELECTED_UTILITY_CATEGORIES,
            "configured_utility_fields": _default_configured_utility_fields(DEFAULT_SELECTED_UTILITY_CATEGORIES),
            "community_csv_columns": _community_csv_columns_for_path(initial_default_community),
        },
        ensure_ascii=False,
    )
    body = f"""
    <style>
      .setup-top-grid {{
        display: grid;
        gap: 22px;
        grid-template-columns: minmax(360px, 0.92fr) minmax(460px, 1.05fr) minmax(560px, 1.25fr);
        align-items: stretch;
        grid-auto-rows: 1fr;
        margin-bottom: 8px;
      }}
      .run-setup-workflow-surface {{
        position: relative;
        display: grid;
        gap: 8px;
      }}
      .setup-launch-grid {{
        display: grid;
        gap: 18px;
        grid-template-columns: 5fr 2fr;
      }}
      @media (max-width: 1500px) {{
        .setup-top-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        #panel-step3 {{
          grid-column: 1 / -1;
        }}
      }}
      @media (max-width: 1100px) {{
        .setup-top-grid, .setup-launch-grid {{ grid-template-columns: 1fr; }}
        #panel-step3 {{ grid-column: auto; }}
      }}
      .setup-panel {{
        display: flex;
        flex-direction: column;
        gap: 0;
        align-content: start;
        height: auto;
      }}
      .setup-top-grid > .panel,
      .setup-top-grid > .setup-panel,
      #panel-step1, #panel-step2, #panel-step3 {{
        min-width: 0;
        margin-bottom: 0;
      }}
      #panel-step1, #panel-step2, #panel-step3 {{
        padding: 18px 20px;
        height: 100%;
        box-sizing: border-box;
      }}
      .setup-field-grid {{
        display: grid;
        gap: 10px;
      }}
      .setup-chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }}
      .setup-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
        font-size: 12px;
        font-weight: 800;
        color: #334155;
      }}
      .setup-status-grid {{
        display: grid;
        gap: 8px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }}
      .setup-status {{
        border: 1px dashed #e4e4e7;
        background: #fafafa;
        padding: 10px 12px;
        border-radius: 12px;
        font-size: 13px;
        color: #334155;
      }}
      .setup-field {{
        border: 1px solid #e2e8f0;
        background: #fff;
        padding: 10px 12px;
        border-radius: 10px;
      }}
      .setup-field label {{
        display: block;
        font-size: 12px;
        font-weight: 700;
        color: #475569;
        margin-bottom: 4px;
      }}
      .setup-field input,
      .setup-field select,
      .setup-field textarea {{
        width: 100%;
        border: 1px solid #dce1ea;
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
        color: #0f172a;
        background: #fff;
      }}
      .setup-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }}
      .setup-note {{
        font-size: 12px;
        line-height: 1.5;
        color: #64748b;
      }}
      .run-upload-row {{
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
        padding: 12px 14px;
        display: grid;
        gap: 10px;
        min-width: 0;
      }}
      .upload-card-head {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        flex-wrap: wrap;
      }}
      .upload-card-title {{
        font-size: 15px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.35;
        min-width: 0;
        max-width: 100%;
      }}
      .upload-card-controls {{
        display: grid;
        grid-template-columns: 220px minmax(0, 1fr);
        align-items: center;
        gap: 12px;
        min-width: 0;
      }}
      .upload-card-footer {{
        display: grid;
        gap: 4px;
        min-width: 0;
      }}
      .upload-file-summary {{
        min-width: 0;
        font-size: 13px;
        font-weight: 600;
        color: #334155;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .upload-source-note {{
        font-size: 12px;
        color: #64748b;
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .upload-card-helper {{
        font-size: 12px;
        color: #475569;
      }}
      .file-row-inline-shell {{
        display: grid;
        gap: 4px;
        min-width: 0;
      }}
      .file-row-inline-title {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 700;
        color: #0f172a;
      }}
      .file-row-label {{ font-weight: 700; }}
      .file-row-chip {{
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        border: 1px solid #e2e8f0;
      }}
      .file-row-chip.required {{ background: #fef2f2; color: #b91c1c; border-color: #fecdd3; }}
      .file-row-chip.optional {{ background: #eef2ff; color: #4338ca; border-color: #c7d2fe; }}
      .file-row-inline-meta {{ font-size: 12px; color: #475569; }}
      .file-row-inline-meta,
      #community-status,
      #boundary-status-text,
      #community-file-summary,
      #boundary-file-summary,
      .status-text {{
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .file-picker-inline {{
        width: 320px;
        min-width: 320px;
        max-width: 320px;
        overflow: hidden;
        position: relative;
        display: flex;
        justify-content: flex-end;
      }}
      .file-picker-inline input {{
        padding: 6px 0;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        cursor: pointer;
      }}
      .file-picker-inline input::file-selector-button {{
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
        color: #0f172a;
        font-weight: 700;
        cursor: pointer;
      }}
      .file-native-input {{
        position: absolute;
        inline-size: 1px;
        block-size: 1px;
        opacity: 0;
        overflow: hidden;
        pointer-events: none;
      }}
      .file-picker-inline {{
        width: auto;
        min-width: 0;
        max-width: 100%;
        justify-content: flex-start;
        align-items: center;
        gap: 8px;
      }}
      .file-picker-button {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 34px;
        padding: 0 12px;
        border: 1px solid #dbe3ef;
        border-radius: 10px;
        background: #ffffff;
        color: #0f172a;
        font-size: 12px;
        font-weight: 800;
        cursor: pointer;
        white-space: nowrap;
      }}
      .file-picker-button:hover {{
        border-color: #cbd5e1;
        background: #f8fafc;
      }}
      .file-picker-caption {{
        min-width: 0;
        max-width: 160px;
        color: #64748b;
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .path-browse-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: center;
      }}
      .path-browse-row input {{
        width: 100%;
        min-width: 0;
      }}
      .directory-browse-btn {{
        min-height: 34px;
        padding-inline: 12px;
        border-radius: 10px;
        font-size: 12px;
      }}
      .directory-modal-overlay {{
        position: fixed;
        inset: 0;
        z-index: 130;
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: rgba(15, 23, 42, 0.18);
        backdrop-filter: blur(3px);
      }}
      .directory-modal-overlay.is-open {{
        display: flex;
      }}
      .directory-modal-card {{
        width: min(640px, calc(100vw - 48px));
        max-height: min(78vh, 680px);
        border: 1px solid #dbe3ef;
        border-radius: 18px;
        background: #ffffff;
        box-shadow: 0 28px 72px rgba(15,23,42,0.22);
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }}
      .directory-modal-head {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        padding: 14px 16px;
        border-bottom: 1px solid #e2e8f0;
        background: #f8fafc;
      }}
      .directory-modal-title {{
        font-size: 16px;
        font-weight: 900;
        color: #0f172a;
      }}
      .directory-current-path {{
        margin-top: 4px;
        font-size: 12px;
        color: #64748b;
        max-width: 480px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .directory-modal-body {{
        padding: 12px 16px 16px;
        display: grid;
        gap: 10px;
        min-height: 0;
      }}
      .directory-toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .directory-list {{
        display: grid;
        gap: 6px;
        max-height: 360px;
        overflow: auto;
        padding: 2px;
      }}
      .directory-list button {{
        width: 100%;
        justify-content: flex-start;
        min-height: 38px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
      }}
      .directory-modal-footer {{
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        padding: 12px 16px;
        border-top: 1px solid #e2e8f0;
      }}
      .button.action-primary,
      button.action-primary {{
        background: #36AABF;
        border-color: #36AABF;
        color: #ffffff;
        box-shadow: 0 6px 16px rgba(54,170,191,0.18);
      }}
      .button.action-primary:hover,
      button.action-primary:hover {{
        background: #268CA0;
        border-color: #268CA0;
        box-shadow: 0 10px 22px rgba(54,170,191,0.22);
      }}
      .button.action-secondary,
      button.action-secondary,
      .file-picker-button.action-secondary {{
        background: #ffffff;
        border-color: #dbe3ef;
        color: #0f172a;
      }}
      .button.action-tertiary,
      button.action-tertiary {{
        background: #f8fafc;
        border-color: #e2e8f0;
        color: #475569;
      }}
      .template-download-row {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 2px;
        flex-wrap: wrap;
      }}
      .run-inline-note {{
        font-size: 12px;
        color: #64748b;
      }}
      .inline-error {{
        color: #b91c1c;
        font-size: 12px;
        margin-top: 4px;
      }}
      .status-text {{
        font-size: 12px;
        color: #475569;
        margin-top: 6px;
      }}
      .is-disabled {{
        opacity: 0.55;
        cursor: not-allowed !important;
      }}
      .run-upload-row {{
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
        padding: 8px 10px;
        display: grid;
        gap: 5px;
      }}
      .run-upload-row-inline {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) 220px;
        align-items: start;
        gap: 12px;
        min-width: 0;
      }}
      .file-row-inline-shell {{
        display: grid;
        gap: 4px;
        min-width: 0;
      }}
      .file-row-inline-title {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 700;
        color: #0f172a;
      }}
      .file-row-label {{ font-weight: 700; }}
      .file-row-chip {{
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        border: 1px solid #e2e8f0;
      }}
      .file-row-chip.required {{ background: #fef2f2; color: #b91c1c; border-color: #fecdd3; }}
      .file-row-chip.optional {{ background: #eef2ff; color: #4338ca; border-color: #c7d2fe; }}
      .file-row-inline-meta {{ font-size: 12px; color: #475569; }}
      .template-download-row {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 8px;
        flex-wrap: wrap;
      }}
      .run-inline-note {{
        font-size: 12px;
        color: #64748b;
      }}
      .validation-summary-box {{
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #f8fafc;
        padding: 10px 12px;
        display: grid;
        gap: 6px;
      }}
      .validation-summary-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      .validation-summary-title {{
        font-size: 13px;
        font-weight: 800;
        color: #0f172a;
      }}
      .validation-chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }}
      .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        border: 1px solid #e2e8f0;
        background: #fff;
        color: #334155;
      }}
      .status-pill.success, .status-badge.success {{ background: #F3FAFC; color: #268CA0; border-color: #CFEAF0; }}
      .status-pill.warning, .status-badge.warning {{ background: #fffbeb; color: #b45309; border-color: #fcd34d; }}
      .status-pill.error, .status-badge.error {{ background: #fef2f2; color: #b91c1c; border-color: #fecaca; }}
      .status-pill.neutral, .status-badge.neutral {{ background: #f8fafc; color: #475569; border-color: #e2e8f0; }}
      .validation-compact-bar {{
        border: 1px solid #dbe4ef;
        border-radius: 14px;
        background: #f8fafc;
        padding: 10px 12px;
        display: grid;
        gap: 6px;
      }}
      .validation-compact-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      .validation-compact-title {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        font-weight: 850;
        color: #0f172a;
        min-width: 0;
      }}
      .validation-compact-line {{
        font-size: 12px;
        line-height: 1.45;
        color: #475569;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .validation-details-toggle {{
        border: 0;
        background: transparent;
        color: #36AABF;
        font-size: 12px;
        font-weight: 800;
        cursor: pointer;
        padding: 2px 0;
        white-space: nowrap;
      }}
      .validation-details-toggle:hover {{
        text-decoration: underline;
      }}
      .validation-details-panel {{
        display: none;
        border-top: 1px solid #e2e8f0;
        padding-top: 8px;
        margin-top: 2px;
      }}
      .validation-details-panel.is-open {{
        display: block;
      }}
      .validation-checklist {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
      }}
      .validation-item {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 7px 9px;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #fff;
        min-height: 34px;
      }}
      .validation-item-copy {{
        min-width: 0;
      }}
      .validation-item-label {{
        font-size: 12px;
        font-weight: 750;
        color: #0f172a;
        line-height: 1.2;
      }}
      .validation-item-note {{
        display: none;
      }}
      .status-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 3px 8px;
        border-radius: 999px;
        border: 1px solid #e2e8f0;
        font-size: 10.5px;
        font-weight: 850;
        white-space: nowrap;
      }}
      .csv-workflow {{
        display: grid;
        gap: 12px;
      }}
      .csv-workflow-head {{
        display: grid;
        gap: 4px;
      }}
      .csv-workflow-title {{
        font-size: 15px;
        font-weight: 850;
        color: #0f172a;
      }}
      .csv-workflow-copy {{
        font-size: 12px;
        color: #64748b;
        line-height: 1.45;
      }}
      .csv-mode-question {{
        font-size: 12px;
        font-weight: 800;
        color: #334155;
        margin-bottom: 6px;
      }}
      .csv-mode-toggle {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .csv-mode-button {{
        min-height: 38px;
        border: 1px solid #dbe4ef;
        border-radius: 12px;
        background: #ffffff;
        color: #334155;
        font-size: 13px;
        font-weight: 850;
        cursor: pointer;
      }}
      .csv-mode-button.is-active {{
        border-color: #84CDDA;
        background: #F3FAFC;
        color: #268CA0;
        box-shadow: 0 0 0 2px rgba(54, 170, 191, 0.10);
      }}
      .csv-mode-panel {{
        display: none;
        gap: 10px;
      }}
      .csv-mode-panel.is-active {{
        display: grid;
      }}
      .csv-info-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 8px;
      }}
      .csv-info-row {{
        display: grid;
        grid-template-columns: minmax(150px, 0.36fr) minmax(0, 1fr);
        align-items: center;
        gap: 10px;
        padding: 9px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
      }}
      .csv-info-label {{
        font-size: 12px;
        font-weight: 850;
        color: #334155;
      }}
      .csv-info-value {{
        font-size: 12px;
        color: #64748b;
        min-width: 0;
      }}
      .csv-info-value strong {{
        color: #0f172a;
      }}
      .csv-path-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 8px;
      }}
      .csv-primary-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 8px;
      }}
      .csv-primary-row .button {{
        width: 100%;
        min-height: 44px;
        border-radius: 14px;
        font-size: 14px;
        font-weight: 850;
      }}
      .csv-result-card {{
        display: none;
        gap: 10px;
        padding: 12px;
        border: 1px solid #CFEAF0;
        border-radius: 14px;
        background: #F3FAFC;
      }}
      .csv-result-card.is-visible {{
        display: grid;
      }}
      .csv-result-title {{
        font-size: 14px;
        font-weight: 900;
        color: #268CA0;
      }}
      .csv-result-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px 12px;
        font-size: 12px;
        color: #334155;
      }}
      .csv-result-grid .wide {{
        grid-column: 1 / -1;
      }}
      .csv-result-actions {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(132px, 0.34fr);
        gap: 8px;
      }}
      .csv-result-actions .button {{
        width: 100%;
        min-height: 40px;
        border-radius: 12px;
        font-weight: 850;
      }}
      .prompt-status-text.is-ready {{ color: #268CA0; font-weight: 800; }}
      .prompt-status-text.is-warning {{ color: #b45309; font-weight: 800; }}
      .prompt-status-text.is-error {{ color: #b91c1c; font-weight: 800; }}
      .advanced-action-stack {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
      }}
      .advanced-action-stack .button {{
        min-height: 38px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 800;
      }}
      .advanced-action-note {{
        grid-column: 1 / -1;
        font-size: 11px;
        color: #64748b;
        line-height: 1.45;
      }}
      .advanced-panel-stack {{
        display: grid;
        gap: 10px;
      }}
      .advanced-panel-card {{
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        background: #ffffff;
        padding: 12px;
        display: grid;
        gap: 10px;
      }}
      .advanced-panel-head {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }}
      .advanced-panel-title {{
        font-size: 13px;
        font-weight: 900;
        color: #0f172a;
      }}
      .advanced-panel-copy {{
        margin-top: 2px;
        font-size: 11px;
        line-height: 1.45;
        color: #64748b;
      }}
      .advanced-panel-tag {{
        flex: 0 0 auto;
        padding: 3px 8px;
        border-radius: 999px;
        background: #f1f5f9;
        color: #475569;
        font-size: 10px;
        font-weight: 900;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }}
      .advanced-debug-actions {{
        background: #fbfcfe;
      }}
      .advanced-summary-main {{
        display: flex;
        flex-direction: column;
        gap: 2px;
      }}
      .advanced-summary-title {{
        font-size: 13px;
        font-weight: 900;
        color: #0f172a;
      }}
      .advanced-summary-hint {{
        font-size: 11px;
        color: #64748b;
        font-weight: 500;
      }}
      .path-field input {{
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
        padding: 7px 9px;
      }}
      .field-hint {{
        font-size: 11px;
        color: #64748b;
        line-height: 1.4;
      }}
      .step-card.step-waiting {{
        opacity: 0.72;
      }}
      .step-card.step-current {{
        box-shadow: 0 0 0 1px rgba(14,165,233,0.16), 0 10px 24px rgba(15,23,42,0.06);
      }}
      .step-card.step-completed {{
        box-shadow: 0 0 0 1px rgba(54,170,191,0.16), 0 10px 24px rgba(15,23,42,0.05);
      }}
      .step-kicker-row {{
        display: flex;
        align-items: center;
        gap: 8px;
      }}
      .step-card {{
        position: relative;
        display: flex;
        flex-direction: column;
        height: auto;
        min-height: 0;
        overflow: visible;
        justify-content: flex-start;
      }}
      .step-card-header {{
        display: grid;
        gap: 4px;
        padding-bottom: 6px;
      }}
      .step-card-body {{
        flex: 0 0 auto;
        min-height: 0;
        display: grid;
        gap: 8px;
        align-content: start;
        align-items: start;
        grid-auto-rows: min-content;
      }}
      .step-card-footer {{
        margin-top: 8px;
        padding-top: 0;
        display: grid;
        gap: 6px;
        align-content: start;
        overflow: visible;
      }}
      .step-footer-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        overflow: visible;
      }}
      .step-popover-shell {{
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        flex: 0 0 auto;
      }}
      .step-drawer-trigger {{
        font-size: 12px;
        font-weight: 700;
      }}
      .advanced-modal-overlay {{
        position: fixed;
        inset: 0;
        z-index: 120;
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: rgba(15, 23, 42, 0.18);
        backdrop-filter: blur(3px);
      }}
      .advanced-modal-overlay.is-open {{
        display: flex;
      }}
      .advanced-modal-card {{
        width: min(680px, calc(100vw - 48px));
        max-width: 100%;
        max-height: min(86vh, 760px);
        display: flex;
        flex-direction: column;
        gap: 0;
        padding: 0;
        border: 1px solid #dbe3ef;
        border-radius: 18px;
        background: rgba(255,255,255,0.99);
        box-shadow: 0 28px 72px rgba(15,23,42,0.22);
        overflow: hidden;
      }}
      .advanced-modal-card.is-step3 {{
        width: min(940px, calc(100vw - 48px));
        max-height: min(88vh, 820px);
      }}
      .step-drawer {{
        display: none;
        min-width: 0;
      }}
      .step-drawer.is-open {{
        display: block;
      }}
      .step-drawer-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 14px 16px 12px;
        border-bottom: 1px solid #e2e8f0;
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      }}
      .step-drawer-title {{
        font-size: 16px;
        font-weight: 900;
        color: #0f172a;
      }}
      .step-drawer-copy {{
        margin-top: 2px;
        font-size: 12px;
        line-height: 1.4;
        color: #64748b;
      }}
      .advanced-modal-close {{
        width: 30px;
        min-width: 30px;
        height: 30px;
        padding: 0;
        border-radius: 999px;
        border: 1px solid rgba(226, 232, 240, 0.95);
        background: #ffffff;
        color: #64748b;
        font-size: 18px;
        line-height: 1;
        box-shadow: none;
      }}
      .advanced-modal-close:hover {{
        color: #0f172a;
        background: #f8fafc;
      }}
      .step-drawer-body {{
        min-height: 0;
        overflow: auto;
        display: grid;
        gap: 10px;
        align-content: start;
        align-items: start;
        padding: 12px 14px 14px;
        background: #f8fafc;
      }}
      .step-drawer-body > * {{
        align-self: start;
      }}
      .step-drawer .config-row,
      .step-drawer .policy-row,
      .step-drawer .value-flow-controls,
      .step-drawer .custom-field-builder-grid,
      .step-drawer .utility-field-grid,
      .step-drawer .utility-category-list {{
        align-items: start;
        align-content: start;
        grid-auto-rows: min-content;
      }}
      .step-drawer .run-field {{
        gap: 3px;
        align-content: start;
        height: auto;
      }}
      .step-drawer .run-field input,
      .step-drawer .run-field select {{
        padding: 7px 9px;
      }}
      .step-drawer .field-hint {{
        font-size: 10px;
        line-height: 1.3;
      }}
      .advanced-drawer-form-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px 10px;
        align-items: start;
        align-content: start;
      }}
      .advanced-drawer-stack {{
        display: grid;
        gap: 8px;
        align-items: start;
        align-content: start;
      }}
      .step-state-badge {{
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 800;
        border: 1px solid #e2e8f0;
        color: #64748b;
        background: #f8fafc;
      }}
      .config-row {{
        display: grid;
        gap: 10px;
      }}
      .configure-row-top {{ grid-template-columns: 2fr 2fr 1fr; }}
      .configure-row-mid {{ grid-template-columns: 2fr 1fr 2fr; align-items: start; gap: 8px; }}
      .configure-row-fixed {{ grid-template-columns: 1fr; max-width: 240px; }}
      .configure-row-policy-text {{ grid-template-columns: 1fr; }}
      .policy-row {{ grid-template-columns: 1fr 1fr; }}
      .output-row {{ grid-template-columns: auto 1fr; align-items: center; }}
      .run-field {{
        display: grid;
        gap: 4px;
        font-size: 13px;
      }}
      .run-field label {{
        font-size: 12px;
        font-weight: 700;
        color: #475569;
      }}
      .run-field input,
      .run-field select,
      .run-field textarea {{
        padding: 8px 10px;
        border: 1px solid #dce1ea;
        border-radius: 8px;
        font-size: 13px;
      }}
      .run-field textarea {{
        min-height: 108px;
        resize: vertical;
        font-family: inherit;
      }}
      #panel-step3 #planner-soft-policy-text {{
        min-height: 32px;
      }}
      #panel-step3,
      #panel-step3 *,
      #panel-step3 .config-row,
      #panel-step3 .run-field,
      #panel-step3 .step-footer-bar {{
        box-sizing: border-box;
      }}
      #panel-step3 .config-row,
      #panel-step3 .run-field,
      #panel-step3 .step-card-body,
      #panel-step3 .step-card-footer,
      #panel-step3 .step-footer-bar,
      #panel-step3 .step-footer-bar > *,
      #panel-step3 .field-hint,
      #panel-step3 .section-copy {{
        min-width: 0;
        max-width: 100%;
      }}
      #panel-step3 .configure-target-row {{
        grid-template-columns: minmax(0, 1fr);
      }}
      #panel-step3 .configure-row-top {{
        grid-template-columns: minmax(0, 1.35fr) minmax(112px, 0.55fr) minmax(0, 1fr);
        gap: 10px;
      }}
      #panel-step3 .configure-row-mid {{
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
      }}
      #panel-step3 .configure-service-row {{
        grid-template-columns: minmax(0, 1fr) minmax(110px, 0.34fr);
        gap: 10px;
      }}
      .api-base-repeat-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(96px, 118px);
        gap: 8px;
        align-items: end;
      }}
      .repeat-count-field {{
        gap: 4px;
      }}
      .target-community-field {{
        position: relative;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 8px;
        background: #f8fafc;
        gap: 6px;
        overflow: visible;
      }}
      .target-community-native {{
        display: none !important;
      }}
      .target-community-toolbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        min-width: 0;
      }}
      .target-community-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        justify-content: flex-end;
      }}
      .target-mini-button {{
        min-height: 26px;
        padding: 0 9px;
        border: 1px solid #dce1ea;
        border-radius: 999px;
        background: #fff;
        color: #334155;
        font-size: 11px;
        font-weight: 800;
        cursor: pointer;
      }}
      .target-mini-button:hover {{
        border-color: #94a3b8;
        background: #f1f5f9;
      }}
      .target-community-combobox {{
        position: relative;
        min-width: 0;
        width: 100%;
      }}
      .target-community-trigger {{
        width: 100%;
        min-height: 34px;
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 5px 9px;
        border: 1px solid #dce1ea;
        border-radius: 10px;
        background: #fff;
        color: #0f172a;
        cursor: pointer;
        text-align: left;
        box-shadow: 0 1px 1px rgba(15,23,42,0.02);
      }}
      .target-community-trigger:hover {{
        border-color: #cbd5e1;
      }}
      .target-community-field.is-open .target-community-trigger {{
        border-color: #84CDDA;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.14);
      }}
      .target-community-trigger-main {{
        display: grid;
        gap: 1px;
        min-width: 0;
        flex: 1 1 auto;
      }}
      .target-community-trigger-label {{
        font-size: 12px;
        font-weight: 800;
        line-height: 1.25;
        color: #0f172a;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .target-community-trigger-hint {{
        font-size: 10px;
        font-weight: 700;
        color: #64748b;
        line-height: 1.2;
      }}
      .target-community-count {{
        flex: 0 0 auto;
        max-width: 88px;
        padding: 2px 8px;
        border-radius: 999px;
        background: #F3FAFC;
        border: 1px solid #CFEAF0;
        color: #268CA0;
        font-size: 10px;
        font-weight: 800;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .target-community-caret {{
        flex: 0 0 auto;
        color: #64748b;
        font-size: 12px;
        transition: transform 0.16s ease;
      }}
      .target-community-field.is-open .target-community-caret {{
        transform: rotate(180deg);
      }}
      .target-community-dropdown {{
        position: absolute;
        top: calc(100% + 6px);
        left: 0;
        right: 0;
        z-index: 40;
        display: none;
        padding: 8px;
        border: 1px solid #dce1ea;
        border-radius: 12px;
        background: #fff;
        box-shadow: 0 14px 32px rgba(15,23,42,0.14);
      }}
      .target-community-field.is-open .target-community-dropdown {{
        display: grid;
        gap: 7px;
      }}
      .target-community-search {{
        width: 100%;
        min-width: 0;
        min-height: 32px;
        border-radius: 9px !important;
        background: #fff;
        font-size: 12px !important;
        padding: 6px 9px !important;
      }}
      .target-community-list {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 4px;
        max-height: 188px;
        overflow: auto;
        padding: 1px;
      }}
      .target-community-option {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        padding: 7px 8px;
        border: 1px solid transparent;
        border-radius: 9px;
        background: #fff;
        color: #0f172a;
        font-size: 12px;
        font-weight: 700;
        line-height: 1.2;
        cursor: pointer;
      }}
      .target-community-option:hover {{
        border-color: #e2e8f0;
        background: #f8fafc;
      }}
      .target-community-option.is-selected {{
        border-color: #B2DBE4;
        background: #F3FAFC;
        color: #268CA0;
      }}
      .target-community-option input {{
        width: 14px !important;
        height: 14px;
        min-width: 14px !important;
        margin: 0;
        padding: 0;
      }}
      .target-community-option span {{
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .target-community-summary {{
        display: none;
        min-height: 0;
        color: #64748b;
      }}
      #panel-step3 .policy-row {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      #panel-step3 .configure-row-policy-text {{
        grid-template-columns: minmax(0, 1fr);
      }}
      #panel-step3 .output-row {{
        grid-template-columns: minmax(128px, 152px) minmax(0, 1fr);
        align-items: center;
        gap: 10px;
      }}
      #panel-step3 .configure-row-top .run-field label,
      #panel-step3 .configure-row-mid .run-field label,
      #panel-step3 .configure-service-row .run-field label {{
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      #panel-step3 .run-field input,
      #panel-step3 .run-field select,
      #panel-step3 .run-field textarea {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
      }}
      #panel-step3 .run-field input,
      #panel-step3 .run-field select,
      #panel-step3 .run-field textarea {{
        padding: 7px 9px;
      }}
      #panel-step3 .configure-row-top .run-field,
      #panel-step3 .configure-row-mid .run-field,
      #panel-step3 .configure-service-row .run-field,
      #panel-step3 .policy-row .run-field {{
        align-content: start;
      }}
      #panel-step3 #rounds,
      #panel-step3 #min-profit {{
        text-align: left;
      }}
      #panel-step3 .path-field input {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
      }}
      #panel-step3 .output-row .section-copy {{
        white-space: nowrap;
      }}
      #panel-step3 #output-dir-hint {{
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      #panel-step3 .field-hint,
      #panel-step3 .run-inline-note,
      #panel-step3 .section-copy {{
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}
      #panel-step3 .step-footer-bar {{
        flex-wrap: nowrap;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      #panel-step3 .step-footer-bar {{
        display: flex;
        justify-content: flex-end;
        width: 100%;
      }}

      #panel-step3 .step-popover-shell {{
        margin-left: auto;
      }}
      #panel-step3 .step-footer-bar .run-inline-note {{
        flex: 1 1 auto;
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      #panel-step2 .step-card-footer {{
        gap: 4px;
        margin-top: 8px;
        padding-top: 0;
      }}
      #panel-step1 .step-card-footer {{
        margin-top: 8px;
      }}
      #panel-step2 .validation-action-footer {{
        gap: 6px;
        padding-top: 4px;
      }}
      #panel-step2 .output-row {{
        grid-template-columns: minmax(128px, 152px) minmax(0, 1fr);
        align-items: center;
        gap: 10px;
        margin-top: 2px;
      }}
      #panel-step2 .output-row .run-field {{
        margin: 0;
      }}
      #panel-step2 .output-row .run-field input {{
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
      }}
      #panel-step2 .step-footer-bar {{
        justify-content: flex-end;
      }}
      #panel-step2 .setup-note:empty {{
        display: none;
      }}
      #panel-step2 .validation-summary-box {{
        padding: 8px 10px;
        gap: 5px;
      }}
      #panel-step2 .validation-summary-title {{
        font-size: 12.5px;
      }}
      #panel-step2 .validation-chip-row {{
        gap: 5px;
      }}
      #panel-step2 .validation-chip-row .status-pill {{
        padding: 3px 8px;
        font-size: 10.5px;
      }}
      #panel-step2 .validation-checklist {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
        align-items: start;
      }}
      #panel-step2 .existing-bundle-grid {{
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      }}
      #panel-step2 #load-existing-bundle-btn {{
        grid-column: 1 / -1;
        justify-self: end;
        width: min(220px, 100%);
      }}

      #panel-step2 .validation-item {{
        min-height: 40px;
        padding: 7px 9px;
        border-radius: 9px;
        gap: 8px;
        align-items: center;
        justify-content: space-between;
      }}

      #panel-step2 .validation-item-copy {{
        padding-right: 0;
        min-width: 0;
      }}

      #panel-step2 .validation-item-label {{
        font-size: 11.5px;
        line-height: 1.16;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      #panel-step2 .status-badge {{
        position: static;
        right: auto;
        bottom: auto;
        flex: 0 0 auto;
        padding: 2px 8px;
        font-size: 9.5px;
        line-height: 1.15;
      }}
      #panel-step3 #output-dir-hint,
      #panel-step3 .step-footer-bar .run-inline-note {{
        display: none;
      }}
      .validate-summary-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
      }}
      .validate-status-rows {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 8px;
        margin-bottom: 10px;
      }}
      .validate-status-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #fff;
        font-size: 13px;
      }}
      .validate-status-row .file-row-chip {{
        margin-left: 6px;
      }}
      .config-row {{
        display: grid;
        gap: 10px;
      }}
      .configure-row-top {{ grid-template-columns: 2fr 2fr 1fr; }}
      .configure-row-mid {{ grid-template-columns: 2fr 1fr 2fr; }}
      .configure-row-fixed {{ grid-template-columns: 1fr; max-width: 240px; }}
      .configure-row-policy-text {{ grid-template-columns: 1fr; }}
      .policy-row {{ grid-template-columns: 1fr 1fr; }}
      .output-row {{ grid-template-columns: auto 1fr; align-items: center; }}
      .policy-slider {{
        display: grid;
        gap: 4px;
      }}
      .launch-action-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: start;
      }}
      .launch-head-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }}
      .launch-title-inline {{
        display: flex;
        align-items: baseline;
        gap: 8px;
        min-width: 0;
      }}
      .launch-status-badge {{
        padding: 3px 8px;
        font-size: 10px;
        font-weight: 800;
      }}
            #panel-step4 {{
        gap: 4px;
        margin-top: -8px;
        padding-top: 10px;
        padding-bottom: 10px;
      }}

      #panel-step4 .section-head.compact {{
        margin-bottom: 4px;
      }}

      #panel-step4 .section-title {{
        font-size: 22px;
        line-height: 1;
      }}

      #panel-step4 .launch-action-row {{
        gap: 10px;
        align-items: start;
      }}

      #panel-step4 .launch-summary-shell,
      #panel-step4 .launch-action-panel {{
        padding: 8px 10px;
        border-radius: 12px;
      }}

      #panel-step4 .launch-button-row {{
        gap: 8px;
        margin-bottom: 4px;
      }}

      #panel-step4 .launch-block-note {{
        margin-top: 0;
        font-size: 11px;
        line-height: 1.2;
      }}
      .launch-summary-shell {{
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #fff;
        padding: 5px 8px;
        min-width: 0;
      }}
      .launch-summary {{
        display: block;
      }}
      .launch-summary-grid {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }}
      .launch-summary-item {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        padding: 3px 8px;
        border-radius: 999px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
      }}
      .launch-summary-key {{
        font-size: 11px;
        font-weight: 800;
        color: #64748b;
        white-space: nowrap;
      }}
      .launch-summary-value {{
        font-size: 12px;
        font-weight: 700;
        color: #0f172a;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 180px;
      }}
      .launch-action-panel {{
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #f8fafc;
        padding: 6px 8px;
        display: grid;
        gap: 3px;
        align-content: start;
        min-width: 210px;
      }}
      .launch-button-row {{
        display: flex;
        flex-wrap: nowrap;
        gap: 6px;
        align-items: center;
      }}
      .launch-block-note {{
        font-size: 11px;
        color: #64748b;
        line-height: 1.2;
      }}
      .run-progress-panel {{
        margin-top: 10px;
        display: grid;
        gap: 8px;
        border: 1px solid #dbe3ea;
        border-radius: 8px;
        background: #ffffff;
        padding: 10px;
      }}
      .run-progress-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        color: #334155;
        font-size: 12px;
        font-weight: 800;
      }}
      .run-progress-track {{
        height: 8px;
        border-radius: 999px;
        background: #e5e7eb;
        overflow: hidden;
      }}
      .run-progress-fill {{
        height: 100%;
        width: 0%;
        border-radius: inherit;
        background: #36AABF;
        transition: width 0.2s ease;
      }}
      #run-progress-log {{
        max-height: 260px;
        overflow: auto;
        margin: 0;
        padding: 8px;
        border-radius: 6px;
        background: #0f172a;
        color: #e5e7eb;
        font-size: 11px;
        line-height: 1.35;
        white-space: pre-wrap;
      }}
      .save-bundle-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: center;
      }}
      .agreement-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        margin-top: 6px;
      }}
      .agreement-table th, .agreement-table td {{
        border: 1px solid #e2e8f0;
        padding: 6px 8px;
        text-align: left;
      }}
      .override-groups {{
        display: grid;
        gap: 10px;
      }}
      .override-group {{
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px 12px;
        background: #fff;
        display: grid;
        gap: 6px;
      }}
      .override-group label {{
        font-weight: 700;
        font-size: 13px;
      }}
      .override-group .override-options {{
        display: grid;
        gap: 4px;
      }}
      .utility-category-list {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .value-flow-controls {{
        display: grid;
        gap: 10px;
      }}
      .utility-category-shell {{
        gap: 8px;
      }}
      .utility-section-label {{
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
      }}
      .utility-category-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 8px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #fff;
      }}
      .utility-category-row.is-active {{
        border-color: #cbd5e1;
        background: #f8fafc;
      }}
      .utility-category-row-main {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }}
      .utility-category-label {{
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
      }}
      .utility-category-editor-panel {{
        display: grid;
        gap: 10px;
      }}
      .utility-category-editor-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      .utility-category-editor-copy {{
        font-size: 12px;
        color: #64748b;
      }}
      .utility-category-editor-title {{
        font-size: 14px;
        font-weight: 800;
        color: #0f172a;
      }}
      .utility-agent-section {{
        display: grid;
        gap: 8px;
      }}
      .utility-agent-section-title {{
        font-size: 12px;
        font-weight: 800;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .override-group input[type="checkbox"] {{
        margin-right: 6px;
      }}
      .utility-field-list {{
        display: grid;
        gap: 8px;
      }}
      .utility-field-card {{
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px;
        background: #fff;
        display: grid;
        gap: 8px;
      }}
      .utility-field-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8px;
      }}
      .utility-field-actions {{
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
        align-items: center;
      }}
      .utility-field-title {{
        font-size: 13px;
        font-weight: 700;
        color: #0f172a;
      }}
      .utility-field-meta {{
        font-size: 11px;
        color: #64748b;
      }}
      .utility-field-summary {{
        display: grid;
        gap: 6px;
      }}
      .utility-field-summary-row {{
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: center;
      }}
      .utility-field-summary-label {{
        font-size: 12px;
        color: #64748b;
        font-weight: 700;
      }}
      .utility-field-summary-value {{
        font-size: 12px;
        color: #334155;
        text-align: right;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .utility-field-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .utility-field-editor {{
        display: grid;
        gap: 8px;
        padding-top: 2px;
      }}
      .utility-field-inline-note {{
        font-size: 11px;
        color: #b91c1c;
      }}
      .custom-field-builder {{
        display: grid;
        gap: 8px;
      }}
      .custom-field-toggle-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }}
      .custom-field-builder-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }}
      .advanced-subsection {{
        margin: 0;
        padding: 0;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        background: #ffffff;
        overflow: hidden;
      }}
      .advanced-subsection summary {{
        cursor: pointer;
        list-style: none;
        padding: 11px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        border-bottom: 1px solid transparent;
      }}
      .advanced-subsection summary::-webkit-details-marker {{
        display: none;
      }}
      .advanced-subsection summary::after {{
        content: '▾';
        color: #64748b;
        font-size: 12px;
        transition: transform 0.18s ease;
      }}
      .advanced-subsection:not([open]) summary::after {{
        transform: rotate(-90deg);
      }}
      .advanced-subsection[open] summary {{
        border-bottom-color: #e2e8f0;
        background: #fbfcfe;
      }}
      .advanced-subsection-body {{
        padding: 10px 12px 12px;
      }}
      .policy-slider {{
        display: grid;
        gap: 6px;
      }}
      .launch-action-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 10px;
        align-items: center;
      }}
      @media (max-width: 1100px) {{
        .configure-row-top,
        .configure-row-mid,
        .existing-bundle-grid,
        .prompt-action-grid,
        .csv-mode-toggle,
        .csv-info-row,
        .csv-result-grid,
        .csv-result-actions,
        .advanced-action-stack,
        .policy-row,
        .output-row,
        .launch-action-row,
        .upload-card-controls,
        #panel-step2 .validation-checklist,
        #panel-step2 .existing-bundle-grid,
        #panel-step3 .configure-row-top,
        #panel-step3 .configure-row-mid,
        #panel-step3 .configure-service-row,
        #panel-step3 .policy-row,
        #panel-step3 .output-row {{
          grid-template-columns: 1fr;
        }}
        .setup-top-grid {{
          margin-bottom: 14px;
        }}
        .advanced-modal-overlay {{
          padding: 12px;
        }}
        .advanced-modal-card {{
          width: min(100%, calc(100vw - 24px));
          max-height: calc(100vh - 24px);
          border-radius: 14px;
          padding: 12px;
        }}
        .advanced-drawer-form-grid,
        .step-drawer .custom-field-builder-grid,
        .step-drawer .utility-field-grid {{
          grid-template-columns: 1fr;
        }}
        .launch-summary-grid {{
          grid-template-columns: 1fr;
        }}
        .validation-checklist {{
          grid-template-columns: 1fr;
        }}
        .utility-category-list {{
          grid-template-columns: 1fr;
        }}
        .configure-row-fixed {{ max-width: none; }}
        .file-picker-inline {{
          width: 100%;
          min-width: 0;
          max-width: 100%;
          justify-content: flex-start;
        }}
      }}
    </style>
    <div class="run-setup-workflow-surface">
    <div class="setup-top-grid">
      <div class="panel setup-panel step-card step-current" id="panel-step1">
        <div class="step-card-header">
          <div class="section-head compact">
            <div class="step-kicker-row">
              <div class="step-kicker">Step 1</div>
              <div class="step-state-badge" id="step1-state">Current</div>
            </div>
            <div class="section-title">Input</div>
          </div>
        </div>
        <div class="step-card-body">
        <div class="run-upload-row">
          <div class="upload-card-head">
            <span class="upload-card-title">Community File</span>
            <span class="file-row-chip required">Required</span>
          </div>
          <div class="upload-card-controls">
            <div class="file-picker-inline">
              <input class="file-native-input" type="file" id="community-file" accept=".csv,.xlsx,.xls">
              <label class="file-picker-button action-secondary" for="community-file">Choose file</label>
              <span class="file-picker-caption" id="community-file-picker-caption">No upload selected</span>
            </div>
            <div class="upload-file-summary" id="community-file-summary" title="{html.escape(initial_default_community)}">{html.escape(Path(initial_default_community).name if initial_default_community else 'No file selected')}</div>
          </div>
          <div class="run-field path-field" style="margin-top:8px;">
            <label for="community-path" style="display:none;">Community File Path</label>
            <input id="community-path" type="text" value="{html.escape(initial_default_community)}" placeholder="community_example.csv" />
          </div>
          <div class="upload-card-footer">
            <div class="upload-source-note" id="community-status" title="{html.escape(initial_default_community)}">Using default: {html.escape(_display_path(initial_default_community))}</div>
            <div class="upload-card-helper">Upload a CSV or spreadsheet with the community population data.</div>
            <div class="run-inline-note inline-error" id="community-error" style="display:none;"></div>
          </div>
        </div>
        <div class="run-upload-row">
          <div class="upload-card-head">
            <span class="upload-card-title">Boundary Shapefile</span>
            <span class="file-row-chip optional">Optional</span>
          </div>
          <div class="upload-card-controls">
            <div class="file-picker-inline">
              <input class="file-native-input" type="file" id="boundary-files" multiple accept=".shp,.dbf,.shx,.prj,.cpg,.qmd,.qix,.geojson,.gpkg">
              <label class="file-picker-button action-secondary" for="boundary-files">Choose files</label>
              <span class="file-picker-caption" id="boundary-file-picker-caption">No upload selected</span>
            </div>
            <div class="upload-file-summary" id="boundary-file-summary" title="{html.escape(initial_default_boundary)}">{html.escape(Path(initial_default_boundary).name if initial_default_boundary else 'No boundary file selected')}</div>
          </div>
          <div class="run-field path-field" style="margin-top:8px;">
            <label for="boundary-path" style="display:none;">Boundary File Path</label>
            <input id="boundary-path" type="text" value="{html.escape(initial_default_boundary)}" placeholder="data/geodata/residential_area_huadu.shp" />
          </div>
          <div class="upload-card-footer">
            <div class="upload-source-note" id="boundary-status-text" title="{html.escape(initial_default_boundary)}">Using default: {html.escape(_display_path(initial_default_boundary) if initial_default_boundary else 'No boundary available')}</div>
            <div class="upload-card-helper">Visualize the results map.</div>
            <div class="run-inline-note inline-error" id="boundary-error" style="display:none;"></div>
          </div>
        </div>
        </div>
        <div class="step-card-footer">
        <div class="template-download-row">
          <a id="template-link" class="button action-secondary" href="#" download>Download template</a>
          <span class="run-inline-note">Use the template if you want to prepare a new community input file.</span>
        </div>
        </div>
      </div>

      <div class="panel setup-panel step-card step-waiting" id="panel-step2">
        <div class="step-card-header">
          <div class="section-head compact">
            <div class="step-kicker-row">
              <div class="step-kicker">Step 2</div>
              <div class="step-state-badge" id="step2-state">Waiting</div>
            </div>
            <div class="section-title">Prepare CSVs</div>
          </div>
        </div>
        <div class="step-card-body">
          <div class="validation-compact-bar" id="validate-overview">
            <div class="validation-compact-top">
              <div class="validation-compact-title">
                <span>Input validation:</span>
                <span class="status-pill neutral" id="validate-overall-pill">Waiting</span>
              </div>
              <button class="validation-details-toggle" id="validation-details-toggle" type="button" aria-expanded="false">View details</button>
            </div>
            <div class="validation-compact-line" id="validation-summary-line">Waiting for community input validation.</div>
            <div class="validation-details-panel" id="validation-details-panel" aria-hidden="true">
              <div class="validation-checklist">
                <div class="validation-item" id="status-community-file"><div class="validation-item-copy"><div class="validation-item-label">Community file</div></div><span class="status-badge neutral">Waiting</span></div>
                <div class="validation-item" id="status-boundary-file"><div class="validation-item-copy"><div class="validation-item-label">Boundary file</div></div><span class="status-badge neutral">Waiting</span></div>
                <div class="validation-item" id="status-population-fields"><div class="validation-item-copy"><div class="validation-item-label">Population fields</div></div><span class="status-badge neutral">Waiting</span></div>
                <div class="validation-item" id="status-simulation-fields"><div class="validation-item-copy"><div class="validation-item-label">Simulation fields</div></div><span class="status-badge neutral">Waiting</span></div>
                <div class="validation-item" id="status-default-sources"><div class="validation-item-copy"><div class="validation-item-label">Using default community file</div></div><span class="status-badge neutral">Unknown</span></div>
              </div>
            </div>
          </div>

          <div class="csv-workflow" id="csv-workflow">
            <div class="csv-workflow-head">
              <div class="csv-workflow-title">Resident and Representative CSVs</div>
              <div class="csv-workflow-copy">Choose one path: generate new CSVs from the community file, or load two existing CSVs. Prompt fields are checked automatically.</div>
            </div>
            <div>
              <div class="csv-mode-question">How do you want to prepare CSVs?</div>
              <div class="csv-mode-toggle" role="tablist" aria-label="CSV preparation mode">
                <button class="csv-mode-button is-active" id="csv-mode-generate" type="button" role="tab" aria-selected="true">Generate new CSVs</button>
                <button class="csv-mode-button" id="csv-mode-load" type="button" role="tab" aria-selected="false">Load existing CSVs</button>
              </div>
            </div>

            <div class="csv-mode-panel is-active" id="csv-generate-panel">
              <div class="csv-info-grid">
                <div class="csv-info-row">
                  <div class="csv-info-label">CSV save directory</div>
                  <div class="run-field path-field" style="margin:0;">
                    <label for="save-bundle-dir" style="display:none;">CSV Save Directory</label>
                    <input id="save-bundle-dir" type="text" placeholder="data/agents_by_community" />
                  </div>
                </div>
                <div class="csv-info-row">
                  <div class="csv-info-label">Residents CSV</div>
                  <div class="csv-info-value" id="residents-csv-summary">Will be generated automatically</div>
                </div>
                <div class="csv-info-row">
                  <div class="csv-info-label">Representatives CSV</div>
                  <div class="csv-info-value" id="representatives-csv-summary">Will be selected automatically from generated residents</div>
                </div>
              </div>
              <div class="csv-primary-row">
                <button class="button action-primary is-disabled" id="generate-csvs-btn" aria-disabled="true" type="button">Generate residents and representatives</button>
              </div>
            </div>

            <div class="csv-mode-panel" id="csv-load-panel">
              <div class="csv-path-grid">
                <div class="run-field path-field">
                  <label>Residents CSV</label>
                  <input id="existing-residents-csv" type="text" placeholder="path/to/ALL_agents.csv" />
                </div>
                <div class="run-field path-field">
                  <label>Representatives CSV</label>
                  <input id="existing-representatives-csv" type="text" placeholder="path/to/community_representatives.csv" />
                </div>
              </div>
              <div class="csv-primary-row">
                <button class="button action-primary" id="load-existing-bundle-btn" type="button">Load CSVs</button>
              </div>
            </div>

            <div class="inline-error" id="generate-error" style="display:none;"></div>
            <div class="csv-result-card" id="csv-result-card">
              <div class="csv-result-title" id="csv-result-title">Ready to continue</div>
              <div class="csv-result-grid">
                <div><strong>Residents:</strong> <span id="csv-result-residents">—</span></div>
                <div><strong>Representatives:</strong> <span id="csv-result-representatives">—</span></div>
                <div><strong>Prompt fields:</strong> <span id="csv-result-prompts">—</span></div>
                <div class="wide"><strong>Saved to:</strong> <span id="csv-result-saved-to">—</span></div>
              </div>
              <div class="csv-result-actions">
                <button class="button action-primary" id="csv-continue-btn" type="button">Continue</button>
                <button class="button secondary" id="csv-secondary-action-btn" type="button">Regenerate</button>
              </div>
            </div>
            <div class="setup-note" id="save-bundle-status"></div>
          </div>
        </div>
        <div class="step-card-footer">
          <div class="step-footer-bar">
            <div class="step-popover-shell">
              <button class="button action-secondary step-drawer-trigger" id="step2-advanced-trigger" type="button">Advanced settings</button>
            </div>
          </div>
        </div>
      </div>

      <div class="panel setup-panel step-card step-waiting" id="panel-step3">
        <div class="step-card-header">
          <div class="section-head compact">
            <div class="step-kicker-row">
              <div class="step-kicker">Step 3</div>
              <div class="step-state-badge" id="step3-state">Waiting</div>
            </div>
            <div class="section-title">Configure</div>
          </div>
        </div>
        <div class="step-card-body">
        <div class="config-row configure-target-row">
          <div class="run-field target-community-field">
            <div class="target-community-toolbar">
              <label for="target-community-trigger">Target Community</label>
              <div class="target-community-actions">
                <button class="target-mini-button" id="target-select-all-btn" type="button">Select all</button>
                <button class="target-mini-button" id="target-clear-btn" type="button">Use all communities</button>
              </div>
            </div>
            <select id="target-community" class="target-community-native" multiple size="4" aria-hidden="true" tabindex="-1"></select>
            <div class="target-community-combobox">
              <button class="target-community-trigger" id="target-community-trigger" type="button" aria-expanded="false" aria-controls="target-community-dropdown">
                <span class="target-community-trigger-main">
                  <span class="target-community-trigger-label" id="target-community-trigger-text">All communities</span>
                  <span class="target-community-trigger-hint">Click to search and select</span>
                </span>
                <span class="target-community-count" id="target-community-count">All</span>
                <span class="target-community-caret">▾</span>
              </button>
              <div class="target-community-dropdown" id="target-community-dropdown">
                <input id="target-community-search" class="target-community-search" type="search" placeholder="Search communities..." autocomplete="off" />
                <div id="target-community-list" class="target-community-list" role="listbox" aria-label="Target Community"></div>
              </div>
            </div>
            <div class="target-community-summary field-hint" id="target-community-summary">Choose one or more communities to run.</div>
          </div>
        </div>
        <div class="config-row configure-row-top" style="margin-top:5px;">
          <div class="run-field">
            <label>Model Name</label>
            <input id="model-name" type="text" />
          </div>
          <div class="run-field">
            <label>Rounds</label>
            <input id="rounds" type="number" min="1" step="1" />
          </div>
          <div class="run-field">
            <label>Agreement Mode</label>
            <select id="agreement-mode">
              <option value="by_build_year">By Build Year</option>
              <option value="fixed">Fixed Ratio</option>
            </select>
          </div>
        </div>
        <div class="config-row configure-row-mid" style="margin-top:5px;">
          <div class="run-field">
            <label>Min Profit Rate</label>
            <input id="min-profit" type="number" step="0.01" />
          </div>
          <div class="run-field">
            <label>API Key</label>
            <input id="api-key" type="password" placeholder="Required" />
          </div>
          <div class="run-field policy-slider">
            <label>Extension Cap</label>
            <input id="extension-cap" type="number" step="0.01" />
          </div>
          <div class="run-field policy-slider">
            <label>Subsidy Cap</label>
            <input id="subsidy-cap" type="number" step="0.01" />
          </div>
        </div>
        <div class="config-row configure-service-row" style="margin-top:5px;">
          <div class="run-field">
            <label>API Base URL</label>
            <input id="api-base-url" type="text" placeholder="Optional OpenAI-compatible endpoint" />
          </div>
          <div class="run-field repeat-count-field">
            <label>Repeat Runs</label>
            <input id="repeat-count" type="number" min="1" step="1" value="1" />
          </div>
        </div>
        <div class="config-row configure-row-policy-text" style="margin-top:5px;">
          <div class="run-field">
            <label>Natural Language Policy</label>
            <textarea
              id="planner-soft-policy-text"
              rows="1"
              placeholder="optional"
            ></textarea>
          </div>
        </div>
        <div class="config-row configure-row-fixed" style="margin-top:4px;">
          <div class="run-field" id="fixed-ratio-field" style="display:none;">
            <label>Fixed Ratio</label>
            <input id="fixed-ratio" type="number" step="0.01" min="0" max="1" />
          </div>
        </div>
        <div class="config-row output-row" style="margin-top:5px;">
          <div class="section-copy" style="margin:0;font-weight:700;">Output Directory</div>
          <div class="run-field path-field" style="margin:0;">
            <input id="output-dir" type="text" />
            <div class="field-hint" id="output-dir-hint">Run outputs will be saved here.</div>
          </div>
        </div>
        </div>
        <div class="step-card-footer">
          <div class="step-footer-bar">
            <span class="run-inline-note">Policy rules and value-flow customization</span>
            <div class="step-popover-shell">
              <button class="button action-secondary step-drawer-trigger" id="step3-advanced-trigger" type="button">Advanced settings</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="advanced-modal-overlay" id="advanced-settings-modal" aria-hidden="true">
      <div class="advanced-modal-card" role="dialog" aria-modal="true" aria-labelledby="advanced-modal-title">
        <div class="step-drawer-head">
          <div>
            <div class="step-drawer-title" id="advanced-modal-title">Advanced settings</div>
            <div class="step-drawer-copy" id="advanced-modal-copy">Adjust advanced configuration without changing the page layout.</div>
          </div>
          <button class="button ghost advanced-modal-close" id="advanced-modal-close" type="button" aria-label="Close advanced settings dialog" title="Close">×</button>
        </div>
        <div class="step-drawer-body">
          <div class="step-drawer" id="step2-advanced-drawer" aria-hidden="true">
            <div class="advanced-panel-stack">
              <section class="advanced-panel-card">
                <div class="advanced-panel-head">
                  <div>
                    <div class="advanced-panel-title">Generation parameters</div>
                    <div class="advanced-panel-copy">These settings are used by the main Generate residents and representatives button.</div>
                  </div>
                  <span class="advanced-panel-tag">Optional</span>
                </div>
                <div class="advanced-drawer-form-grid">
                  <div class="run-field">
                    <label>Residents per Household</label>
                    <input id="residents-per-household" type="number" step="0.01" min="0" />
                    <div class="field-hint">Average number of residents created for each household.</div>
                  </div>
                  <div class="run-field">
                    <label>Representatives per Community</label>
                    <input id="representatives" type="number" step="1" min="1" />
                    <div class="field-hint">How many representative agents to select for each community.</div>
                  </div>
                  <div class="run-field">
                    <label>Vacant Unit Ratio</label>
                    <input id="vacancy-ratio" type="number" step="0.01" min="0" max="1" />
                    <div class="field-hint">Share of units treated as vacant during resident generation.</div>
                  </div>
                  <div class="run-field">
                    <label>Hardship Quantile</label>
                    <input id="hardship-quantile" type="number" step="0.01" min="0" max="1" />
                    <div class="field-hint">Threshold used to label hardship-sensitive residents.</div>
                  </div>
                </div>
              </section>
              <details class="advanced-subsection advanced-debug-actions">
                <summary>
                  <span class="advanced-summary-main">
                    <span class="advanced-summary-title">Debug actions</span>
                    <span class="advanced-summary-hint">Use only when you need to rerun one CSV sub-step manually.</span>
                  </span>
                </summary>
                <div class="advanced-subsection-body">
                  <div class="advanced-action-stack">
                    <button class="button secondary is-disabled" id="generate-btn" aria-disabled="true" type="button">Generate residents only</button>
                    <button class="button secondary is-disabled" id="select-reps-btn" aria-disabled="true" type="button">Re-select representatives</button>
                    <button class="button secondary is-disabled" id="save-bundle-btn" aria-disabled="true" type="button">Save CSVs manually</button>
                    <div class="advanced-action-note" id="save-bundle-helper">Main workflow saves both CSVs automatically. These controls are for debugging partial runs.</div>
                  </div>
                </div>
              </details>
            </div>
          </div>
          <div class="step-drawer" id="step3-advanced-drawer" aria-hidden="true">
            <div class="advanced-drawer-stack">
              <details open class="advanced-subsection">
                <summary>
                  <span class="advanced-summary-main">
                    <span class="advanced-summary-title">Agreement by build year</span>
                    <span class="advanced-summary-hint">Fine-tune the agreement ratio rules used when Agreement Mode is By Build Year.</span>
                  </span>
                </summary>
                <div class="advanced-subsection-body">
                  <table class="agreement-table">
                    <thead><tr><th>max_age</th><th>ratio</th></tr></thead>
                    <tbody id="agreement-rules-body"></tbody>
                  </table>
                </div>
              </details>
              <details class="advanced-subsection">
                <summary>
                  <span class="advanced-summary-main">
                    <span class="advanced-summary-title">Utility setting</span>
                    <span class="advanced-summary-hint">Review active utility fields, edit categories, or add custom fields.</span>
                  </span>
                </summary>
                <div class="advanced-subsection-body">
                  <div class="run-field" id="value-flow-html"></div>
                  <div class="value-flow-controls" style="margin-top:10px;">
                    <div class="override-group utility-category-shell">
                      <div class="utility-section-label">Utility categories</div>
                      <div class="field-hint">Turn categories on or off, then open a category to edit its fields.</div>
                      <div class="utility-category-list" id="utility-category-options"></div>
                    </div>
                    <div class="override-group utility-category-editor-panel" id="utility-category-editor-panel" style="display:none;">
                      <div class="utility-category-editor-head">
                        <div>
                          <div class="utility-category-editor-title" id="utility-category-editor-title">Category configuration</div>
                          <div class="utility-category-editor-copy" id="utility-category-editor-copy">Open one category at a time to adjust the fields inside it.</div>
                        </div>
                        <button class="button ghost" id="close-utility-category-editor-btn" type="button">Close</button>
                      </div>
                      <div id="utility-category-editor-body"></div>
                    </div>
                    <div class="override-group">
                      <div class="custom-field-toggle-row">
                        <div>
                          <div class="utility-section-label">Custom utility fields</div>
                          <div class="field-hint">Add one-off fields that are not covered by the default categories.</div>
                        </div>
                        <button class="button secondary" id="toggle-custom-field-builder-btn" type="button">Add custom utility field</button>
                      </div>
                      <div class="custom-field-builder" id="custom-field-builder-shell" style="display:none;">
                        <div class="custom-field-builder-grid">
                          <div class="run-field">
                            <label>Label</label>
                            <input id="custom-field-label" type="text" placeholder="e.g. Public service bonus" />
                          </div>
                          <div class="run-field">
                            <label>Agent</label>
                            <select id="custom-field-agent">
                              <option value="planner">Planner</option>
                              <option value="developer">Developer</option>
                              <option value="resident" selected>Resident</option>
                            </select>
                          </div>
                          <div class="run-field">
                            <label>Category</label>
                            <select id="custom-field-category">
                              <option value="base">Base</option>
                              <option value="extension">Extension</option>
                              <option value="parking">Parking</option>
                              <option value="subsidy">Subsidy</option>
                              <option value="custom">Custom</option>
                            </select>
                          </div>
                          <div class="run-field">
                            <label>Direction</label>
                            <select id="custom-field-direction">
                              <option value="inflow">Inflow</option>
                              <option value="outflow">Outflow</option>
                              <option value="neutral">Neutral</option>
                              <option value="input">Input</option>
                            </select>
                          </div>
                          <div class="run-field">
                            <label>Value mode</label>
                            <select id="custom-field-value-mode">
                              <option value="fixed">Fixed value</option>
                              <option value="community_field">Community CSV field</option>
                            </select>
                          </div>
                          <div class="run-field">
                            <label>Fixed value</label>
                            <input id="custom-field-fixed-value" type="number" step="0.01" />
                          </div>
                          <div class="run-field">
                            <label>Community CSV field</label>
                            <select id="custom-field-community-field"></select>
                          </div>
                          <div class="run-field">
                            <label>Impact description</label>
                            <input id="custom-field-impact-description" type="text" placeholder="optional" />
                          </div>
                        </div>
                        <div class="toolbar">
                          <div class="toolbar-actions">
                            <label><input id="custom-field-enabled" type="checkbox" checked> Enabled</label>
                            <button class="button secondary" id="add-custom-field-btn" type="button">Add custom field</button>
                            <button class="button ghost" id="cancel-custom-field-btn" type="button">Cancel</button>
                          </div>
                        </div>
                        <div class="inline-error" id="custom-field-error" style="display:none;"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel setup-panel" id="panel-step4">
      <div class="section-head compact launch-head-row">
        <div class="launch-title-inline">
          <div class="step-kicker">Step 4</div>
          <div class="section-title">Launch</div>
        </div>
        <span class="status-pill neutral launch-status-badge" id="launch-status-badge">Blocked</span>
      </div>
      <div class="launch-action-row">
        <div id="preflight-html" class="launch-summary-shell"></div>
        <div class="launch-action-panel">
          <div class="launch-button-row">
            <button class="button is-disabled" id="launch-btn" aria-disabled="true">Launch Run</button>
            <button class="button secondary is-disabled" id="cancel-run-btn" type="button" aria-disabled="true">Cancel Run</button>
            <button class="button secondary" id="reset-btn" type="button">Reset</button>
          </div>
          <div class="launch-block-note" id="launch-note">Residents bundle not generated</div>
          <div class="inline-error" id="launch-error" style="display:none;"></div>
        </div>
      </div>
      <div class="run-progress-panel" id="run-progress-panel" style="display:none;">
        <div class="run-progress-row">
          <span id="run-progress-label">Queued</span>
          <span id="run-progress-percent">0%</span>
        </div>
        <div class="run-progress-track"><div class="run-progress-fill" id="run-progress-fill"></div></div>
        <pre id="run-progress-log"></pre>
      </div>
      </div>
    </div>

    <script>
const UTILITY_CATEGORY_DEFS = {utility_category_defs_json};
const UTILITY_FIELD_DEFS = {utility_field_defs_json};
const DEFAULT_SELECTED_UTILITY_CATEGORIES = {default_selected_categories_json};
const EMBEDDED_RUN_DEFAULTS = {embedded_defaults_json};
const UTILITY_IMPACT_SPECS = {{
        inflow: ['+', 'Inflow', 'inflow'],
        outflow: ['−', 'Outflow', 'outflow'],
        input: ['●', 'Input', 'input'],
        transfer: ['↔', 'Transfer', 'transfer'],
        neutral: ['—', 'Neutral', 'neutral'],
      }};
const runSetupState = {{
        community_file_token: null,
        boundary_bundle_token: null,
        community_file_path: null,
        boundary_path: null,
        generated_bundle_state: {{}},
        target_community: null,
        defaults: {{}},
        preview_ok: false,
        generated_ok: false,
        planner_components: [],
        developer_components: [],
        resident_components: [],
        planner_options: [],
        developer_options: [],
        resident_options: [],
        agreement_rules_table: [],
        configured_utility_fields: [],
        community_csv_columns: [],
        active_utility_category_editor: null,
        active_utility_editor_key: null,
        active_advanced_modal: null,
        active_directory_target: null,
        directory_browser_state: null,
        csv_prep_mode: 'generate',
        prompt_ready: false,
        prompt_status_message: '',
        csvs_saved_dir: '',
        show_custom_field_builder: false,
        auto_preview_triggered: false,
        active_run_job_id: null,
        selected_utility_categories: [...DEFAULT_SELECTED_UTILITY_CATEGORIES],
      }};

      function compactPathDisplay(path) {{
        if (!path) return '';
        const parts = String(path).split(/[\\\\/]/);
        if (parts.length <= 3) return path;
        return `${{parts[0] ? parts[0] : ''}}…/${{parts.slice(-2).join('/')}}`;
      }}

      function fileNameDisplay(path) {{
        if (!path) return 'No file selected';
        const parts = String(path).split(/[\\\\/]/);
        return parts[parts.length - 1] || path;
      }}

      function setPathDisplay(textId, path, prefix = '') {{
        const el = document.getElementById(textId);
        if (!el) return;
        const compact = compactPathDisplay(path || '');
        el.textContent = prefix ? `${{prefix}}${{compact}}` : compact;
        el.title = path || '';
      }}

      function setPathSummary(textId, path, emptyLabel = 'No file selected') {{
        const el = document.getElementById(textId);
        if (!el) return;
        el.textContent = path ? fileNameDisplay(path) : emptyLabel;
        el.title = path || '';
      }}

      function setPathInputMeta(id) {{
        const el = document.getElementById(id);
        if (!el) return;
        el.title = el.value || '';
      }}

      function getCommunityPath() {{
        const typed = (document.getElementById('community-path')?.value || '').trim();
        return typed || runSetupState.community_file_path || (runSetupState.defaults || {{}}).community_file || '';
      }}

      function getBoundaryPath() {{
        const typed = (document.getElementById('boundary-path')?.value || '').trim();
        return typed || runSetupState.boundary_path || (runSetupState.defaults || {{}}).boundary_path || '';
      }}

      function statusTone(level) {{
        return ['success', 'warning', 'error', 'neutral'].includes(level) ? level : 'neutral';
      }}

      function renderValidationRow(id, label, summary, level, badgeText, title = '') {{
        const el = document.getElementById(id);
        if (!el) return;
        const tooltip = title || summary || label;
        el.title = tooltip;
        el.innerHTML = `
          <div class="validation-item-copy">
            <div class="validation-item-label">${{label}}</div>
          </div>
          <span class="status-badge ${{statusTone(level)}}">${{badgeText}}</span>
        `;
      }}

      function renderValidationState(payload = null) {{
        const validation = payload?.validation_state || null;
        const defaults = runSetupState.defaults || {{}};
        const activeCommunityPath = getCommunityPath();
        const activeBoundaryPath = getBoundaryPath();
        const usingDefaultCommunity = !!activeCommunityPath && activeCommunityPath === defaults.community_file && !runSetupState.community_file_path;
        const usingDefaultBoundary = !!activeBoundaryPath && activeBoundaryPath === defaults.boundary_path && !runSetupState.boundary_path;
        const communitiesCount = validation?.communities_detected ?? 0;
        const populationReady = !!validation?.population_ready;
        const simulationReady = !!validation?.simulation_ready;
        const boundaryReady = validation ? !!validation.boundary_ready : !!activeBoundaryPath;
        const communityReady = validation ? !!validation.community_ready : !!activeCommunityPath;
        const hasValidation = !!validation;
        const inputReady = hasValidation && communityReady && populationReady && simulationReady;
        const hasBlocking = hasValidation && (!communityReady || !populationReady || !simulationReady);
        const overallLevel = inputReady ? 'success' : (hasBlocking ? 'error' : (runSetupState.preview_ok ? 'warning' : 'neutral'));
        const overallText = inputReady ? 'Ready' : (hasBlocking ? 'Needs attention' : (runSetupState.preview_ok ? 'Almost ready' : 'Waiting'));
        const overallPill = document.getElementById('validate-overall-pill');
        if (overallPill) {{
          overallPill.className = `status-pill ${{overallLevel}}`;
          overallPill.textContent = overallText;
        }}
        const summaryLine = document.getElementById('validation-summary-line');
        if (summaryLine) {{
          if (!hasValidation) {{
            summaryLine.textContent = activeCommunityPath
              ? 'Community file selected · Waiting for validation'
              : 'Waiting for community input validation.';
          }} else {{
            const parts = [
              `${{communitiesCount}} communities`,
              boundaryReady ? 'Boundary ready' : 'Boundary optional',
              populationReady ? 'Population fields ready' : 'Population fields missing',
              simulationReady ? 'Simulation fields ready' : 'Simulation fields missing',
            ];
            summaryLine.textContent = parts.join(' · ');
          }}
        }}
        renderValidationRow(
          'status-community-file',
          'Community file',
          usingDefaultCommunity ? 'Default' : (activeCommunityPath ? 'Ready' : 'Missing'),
          communityReady ? (usingDefaultCommunity ? 'warning' : 'success') : 'error',
          communityReady ? (usingDefaultCommunity ? 'Default' : 'Ready') : 'Missing',
          activeCommunityPath,
        );
        renderValidationRow(
          'status-boundary-file',
          'Boundary file',
          usingDefaultBoundary ? 'Default' : (activeBoundaryPath ? 'Ready' : 'Optional'),
          boundaryReady ? (usingDefaultBoundary ? 'warning' : 'success') : 'neutral',
          boundaryReady ? (usingDefaultBoundary ? 'Default' : 'Ready') : 'Optional',
          activeBoundaryPath,
        );
        renderValidationRow(
          'status-population-fields',
          'Population fields',
          validation ? (populationReady ? 'Ready' : 'Missing fields') : 'Waiting',
          validation ? (populationReady ? 'success' : 'error') : 'neutral',
          validation ? (populationReady ? 'Ready' : 'Missing') : 'Waiting',
          validation?.population_message || '',
        );
        renderValidationRow(
          'status-simulation-fields',
          'Simulation fields',
          validation ? (simulationReady ? 'Ready' : 'Missing fields') : 'Waiting',
          validation ? (simulationReady ? 'success' : 'error') : 'neutral',
          validation ? (simulationReady ? 'Ready' : 'Missing') : 'Waiting',
          validation?.simulation_message || '',
        );
        renderValidationRow(
          'status-default-sources',
          'Using default community file',
          usingDefaultCommunity ? 'Yes' : 'No',
          usingDefaultCommunity ? 'warning' : 'success',
          usingDefaultCommunity ? 'Yes' : 'No',
        );
        updateCsvPrepUi();
      }}

      function updateStepProgressState() {{
        const apply = (panelId, stateId, status, label) => {{
          const panel = document.getElementById(panelId);
          const badge = document.getElementById(stateId);
          if (!panel || !badge) return;
          panel.classList.remove('step-current', 'step-completed', 'step-waiting');
          panel.classList.add(`step-${{status}}`);
          badge.textContent = label;
        }};
        const hasActiveCommunity = !!getCommunityPath();
        apply('panel-step1', 'step1-state', runSetupState.preview_ok ? 'completed' : 'current', runSetupState.preview_ok ? 'Completed' : (hasActiveCommunity ? 'Current' : 'Current'));
        apply('panel-step2', 'step2-state', runSetupState.generated_ok ? 'completed' : (runSetupState.preview_ok ? 'current' : 'waiting'), runSetupState.generated_ok ? 'Completed' : (runSetupState.preview_ok ? 'Current' : 'Waiting'));
        apply('panel-step3', 'step3-state', runSetupState.generated_ok ? 'current' : 'waiting', runSetupState.generated_ok ? 'Ready' : 'Waiting');
      }}

      function setBusyState(sectionId, isBusy) {{
        const el = document.getElementById(sectionId);
        if (!el) return;
        el.style.opacity = isBusy ? 0.6 : 1;
      }}

      function setAdvancedModal(stepKey = null) {{
        const overlay = document.getElementById('advanced-settings-modal');
        const card = overlay ? overlay.querySelector('.advanced-modal-card') : null;
        const title = document.getElementById('advanced-modal-title');
        const copy = document.getElementById('advanced-modal-copy');
        const configs = {{
          step2: {{
            title: 'Step 2 Advanced settings',
            copy: 'Optional controls for CSV generation and manual debugging. The main flow still does everything automatically.',
          }},
          step3: {{
            title: 'Step 3 Advanced settings',
            copy: 'Advanced policy and utility settings. Keep these defaults unless you are testing model behavior.',
          }},
        }};
        ['step2', 'step3'].forEach((key) => {{
          const drawer = document.getElementById(`${{key}}-advanced-drawer`);
          const trigger = document.getElementById(`${{key}}-advanced-trigger`);
          const isActive = stepKey === key;
          if (drawer) {{
            drawer.classList.toggle('is-open', isActive);
            drawer.setAttribute('aria-hidden', isActive ? 'false' : 'true');
          }}
          if (trigger) {{
            trigger.setAttribute('aria-expanded', isActive ? 'true' : 'false');
          }}
        }});
        if (overlay) {{
          const isOpen = !!stepKey;
          overlay.classList.toggle('is-open', isOpen);
          overlay.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
        }}
        if (card) {{
          card.classList.toggle('is-step2', stepKey === 'step2');
          card.classList.toggle('is-step3', stepKey === 'step3');
        }}
        if (title) title.textContent = configs[stepKey]?.title || 'Advanced settings';
        if (copy) copy.textContent = configs[stepKey]?.copy || 'Adjust advanced configuration without changing the page layout.';
        runSetupState.active_advanced_modal = stepKey;
      }}

      function closeAdvancedModal() {{
        setAdvancedModal(null);
      }}

      function setFilePickerCaption(id, text) {{
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = text || 'No upload selected';
        el.title = el.textContent;
      }}

      function setDirectoryModal(open) {{
        const overlay = document.getElementById('directory-modal');
        if (!overlay) return;
        overlay.classList.toggle('is-open', !!open);
        overlay.setAttribute('aria-hidden', open ? 'false' : 'true');
        if (!open) {{
          runSetupState.active_directory_target = null;
        }}
      }}

      function closeDirectoryModal() {{
        setDirectoryModal(false);
        showInlineError('directory-error', '');
      }}

      function renderDirectoryBrowser(data) {{
        runSetupState.directory_browser_state = data || null;
        const current = document.getElementById('directory-current-path');
        const list = document.getElementById('directory-list');
        const projectBtn = document.getElementById('directory-project-btn');
        const homeBtn = document.getElementById('directory-home-btn');
        const parentBtn = document.getElementById('directory-parent-btn');
        if (current) {{
          current.textContent = data?.current_path || 'Project folder';
          current.title = data?.absolute_path || data?.current_path || '';
        }}
        if (projectBtn) projectBtn.dataset.path = data?.project_path || '';
        if (homeBtn) homeBtn.dataset.path = data?.home_path || '';
        if (parentBtn) parentBtn.dataset.path = data?.parent_path || '';
        if (!list) return;
        list.innerHTML = '';
        const dirs = data?.directories || [];
        if (!dirs.length) {{
          const empty = document.createElement('div');
          empty.className = 'field-hint';
          empty.textContent = 'No subfolders in this folder.';
          list.appendChild(empty);
          return;
        }}
        dirs.forEach((item) => {{
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'button action-secondary';
          btn.textContent = `📁 ${{item.name}}`;
          btn.title = item.path || item.name;
          btn.addEventListener('click', () => loadDirectoryBrowser(item.path));
          list.appendChild(btn);
        }});
      }}

      async function loadDirectoryBrowser(path) {{
        showInlineError('directory-error', '');
        const params = new URLSearchParams();
        if (path) params.set('path', path);
        try {{
          const res = await fetch(`/api/local/directories?${{params.toString()}}`);
          const data = await res.json();
          if (!res.ok || data.status === 'error') throw new Error(data.message || 'Could not open folder');
          renderDirectoryBrowser(data);
        }} catch (err) {{
          showInlineError('directory-error', err.message || 'Could not open folder');
        }}
      }}

      function openDirectoryBrowser(targetId) {{
        const input = document.getElementById(targetId);
        if (!input) return;
        runSetupState.active_directory_target = targetId;
        setDirectoryModal(true);
        loadDirectoryBrowser(input.value || (runSetupState.defaults || {{}}).output_dir || '');
      }}

      function useCurrentDirectory() {{
        const targetId = runSetupState.active_directory_target;
        const data = runSetupState.directory_browser_state || {{}};
        const input = targetId ? document.getElementById(targetId) : null;
        if (!input || !data.current_path) return;
        input.value = data.current_path;
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        closeDirectoryModal();
      }}

      function showInlineError(sectionId, message) {{
        const el = document.getElementById(sectionId);
        if (!el) return;
        if (message) {{
          el.textContent = message;
          el.style.display = 'block';
        }} else {{
          el.textContent = '';
          el.style.display = 'none';
        }}
      }}

      function numberFieldValue(id, fallback) {{
        const el = document.getElementById(id);
        const raw = el ? el.value : '';
        const n = Number.parseFloat(raw);
        return Number.isFinite(n) ? n : fallback;
      }}

      function integerFieldValue(id, fallback) {{
        const el = document.getElementById(id);
        const raw = el ? el.value : '';
        const n = Number.parseInt(raw, 10);
        return Number.isFinite(n) ? n : fallback;
      }}

      function normalizeTargetValues(value) {{
        const raw = Array.isArray(value) ? value : [value];
        const values = raw.map(item => String(item || '').trim()).filter(Boolean);
        if (!values.length || values.includes('All Communities')) return ['All Communities'];
        return [...new Set(values)];
      }}

      let targetCommunitySearchText = '';

      function getTargetCommunities() {{
        const el = document.getElementById('target-community');
        if (!el) return [];
        return normalizeTargetValues(Array.from(el.selectedOptions || []).map(option => option.value));
      }}

      function setTargetDropdownOpen(open) {{
        const field = document.querySelector('.target-community-field');
        const trigger = document.getElementById('target-community-trigger');
        const search = document.getElementById('target-community-search');
        if (!field || !trigger) return;
        field.classList.toggle('is-open', !!open);
        trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open && search) {{
          window.setTimeout(() => {{
            search.focus();
            search.select();
          }}, 0);
        }}
      }}

      function toggleTargetDropdown() {{
        const field = document.querySelector('.target-community-field');
        setTargetDropdownOpen(!field?.classList.contains('is-open'));
      }}

      function setTargetSelectValues(values, emit = true) {{
        const tc = document.getElementById('target-community');
        if (!tc) return;
        const normalized = normalizeTargetValues(values);
        const selectedValues = new Set(normalized);
        Array.from(tc.options || []).forEach(option => {{
          option.selected = selectedValues.has(option.value);
        }});
        if (!Array.from(tc.selectedOptions || []).length && tc.options.length) {{
          tc.options[0].selected = true;
        }}
        renderTargetPicker();
        if (emit) schedulePreflightRefresh();
      }}

      function updateTargetCommunitySummary() {{
        const tc = document.getElementById('target-community');
        const summary = document.getElementById('target-community-summary');
        const triggerText = document.getElementById('target-community-trigger-text');
        const countBadge = document.getElementById('target-community-count');
        if (!tc) return;
        const choices = Array.from(tc.options || []).map(option => option.value);
        const values = getTargetCommunities();
        const updateVisibleText = (mainText, badgeText, summaryText) => {{
          if (triggerText) triggerText.textContent = mainText;
          if (countBadge) countBadge.textContent = badgeText;
          if (summary) summary.textContent = summaryText;
        }};
        if (!choices.length) {{
          updateVisibleText('No communities loaded', '0', 'No communities loaded yet.');
          return;
        }}
        if (!values.length || values.includes('All Communities')) {{
          updateVisibleText('All communities', 'All', 'Run across all communities.');
          return;
        }}
        const visibleNames = values.slice(0, 2).join(', ');
        const triggerRest = values.length > 2 ? ` +${{values.length - 2}}` : '';
        const summaryNames = values.slice(0, 3).join(', ');
        const summaryRest = values.length > 3 ? ` +${{values.length - 3}} more` : '';
        updateVisibleText(`${{visibleNames}}${{triggerRest}}`, `${{values.length}} selected`, `${{values.length}} selected: ${{summaryNames}}${{summaryRest}}`);
      }}

      function renderTargetPicker() {{
        const tc = document.getElementById('target-community');
        const list = document.getElementById('target-community-list');
        if (!tc || !list) return;
        const selectedValues = new Set(Array.from(tc.selectedOptions || []).map(option => option.value));
        const query = (targetCommunitySearchText || '').toLowerCase();
        const options = Array.from(tc.options || []).map(option => option.value);
        const filtered = options.filter(value => !query || value.toLowerCase().includes(query));
        list.innerHTML = '';
        if (!filtered.length) {{
          const empty = document.createElement('div');
          empty.className = 'field-hint';
          empty.textContent = 'No matching communities.';
          list.appendChild(empty);
          updateTargetCommunitySummary();
          return;
        }}
        filtered.forEach(value => {{
          const row = document.createElement('label');
          row.className = `target-community-option ${{selectedValues.has(value) ? 'is-selected' : ''}}`;
          row.title = value;
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.value = value;
          checkbox.checked = selectedValues.has(value);
          checkbox.addEventListener('change', () => {{
            const current = new Set(Array.from(tc.selectedOptions || []).map(option => option.value));
            if (value === 'All Communities') {{
              setTargetSelectValues(checkbox.checked ? ['All Communities'] : [], true);
              return;
            }}
            current.delete('All Communities');
            if (checkbox.checked) current.add(value); else current.delete(value);
            setTargetSelectValues([...current], true);
          }});
          const labelText = document.createElement('span');
          labelText.textContent = value === 'All Communities' ? 'All communities' : value;
          row.appendChild(checkbox);
          row.appendChild(labelText);
          list.appendChild(row);
        }});
        updateTargetCommunitySummary();
      }}

      function renderTargetOptions(targetPayload) {{
        const tc = document.getElementById('target-community');
        if (!tc || !targetPayload) return;
        const selectedValues = new Set(normalizeTargetValues(targetPayload.value));
        tc.innerHTML = (targetPayload.choices || []).map(opt => `<option value="${{opt}}" ${{selectedValues.has(opt)?'selected':''}}>${{opt}}</option>`).join('');
        if (!Array.from(tc.selectedOptions || []).length && tc.options.length) tc.options[0].selected = true;
        renderTargetPicker();
      }}

      async function loadDefaults() {{
        try {{
          const res = await fetch('/api/run/defaults');
          if (!res.ok) throw new Error(`defaults request failed: ${{res.status}}`);
          const data = await res.json();
          runSetupState.defaults = data.defaults || {{}};
          renderDefaults(runSetupState.defaults);
        }} catch (err) {{
          console.error('Failed to load defaults, using embedded fallback.', err);
          runSetupState.defaults = {{ ...EMBEDDED_RUN_DEFAULTS }};
          renderDefaults(runSetupState.defaults);
        }}
      }}

      function renderDefaults(d) {{
        const setVal = (id, v) => {{
          const el = document.getElementById(id);
          if (el) el.value = v ?? '';
        }};
        const setPlaceholder = (id, v) => {{
          const el = document.getElementById(id);
          if (el) el.placeholder = v ?? '';
        }};
        setVal('model-name', d.model_name);
        setVal('rounds', d.rounds);
        setVal('agreement-mode', d.agreement_mode);
        setVal('fixed-ratio', d.agreement_fixed_ratio ?? 1.0);
        setVal('extension-cap', d.max_extension_ratio);
        setVal('subsidy-cap', d.cash_subsidy_cap);
        setVal('min-profit', d.developer_min_profit_rate);
        setVal('planner-soft-policy-text', d.planner_soft_policy_text || '');
        setVal('output-dir', d.output_dir);
        setVal('community-path', d.community_file || '');
        setVal('boundary-path', d.boundary_path || '');
        setVal('api-key', d.api_key || '');
        setVal('api-base-url', d.api_base_url || '');
        setVal('repeat-count', d.repeat_count || 1);
        if (d.api_key_loaded) {{
          setPlaceholder('api-key', `Loaded from ${{d.api_key_source || 'local config'}} (${{d.api_key_masked || 'masked'}})`);
        }} else {{
          setPlaceholder('api-key', 'Required');
        }}
        setVal('residents-per-household', d.residents_per_household);
        setVal('vacancy-ratio', d.vacancy_ratio);
        setVal('representatives', d.representatives_per_community);
        setVal('hardship-quantile', d.hardship_quantile);
        setPlaceholder('residents-per-household', d.residents_per_household);
        setPlaceholder('vacancy-ratio', d.vacancy_ratio);
        setPlaceholder('representatives', d.representatives_per_community);
        setPlaceholder('hardship-quantile', d.hardship_quantile);

        renderTargetOptions(d.target_community);

        const tmpl = document.getElementById('template-link');
        if (tmpl && d.template_url) {{
          tmpl.href = d.template_url;
        }}

        const req = document.getElementById('required-columns-html');
        if (req && d.required_columns_html) {{
          req.innerHTML = d.required_columns_html;
          req.style.display = 'block';
        }}

        runSetupState.selected_utility_categories = d.selected_utility_categories || [...DEFAULT_SELECTED_UTILITY_CATEGORIES];
        runSetupState.planner_components = d.planner_components || [];
        runSetupState.developer_components = d.developer_components || [];
        runSetupState.resident_components = d.resident_components || [];
        runSetupState.planner_options = d.planner_utility_options || d.planner_components || [];
        runSetupState.developer_options = d.developer_utility_options || d.developer_components || [];
        runSetupState.resident_options = d.resident_utility_options || d.resident_components || [];
        runSetupState.agreement_rules_table = d.agreement_rules_table || [];
        runSetupState.configured_utility_fields = d.configured_utility_fields || [];
        runSetupState.community_csv_columns = d.community_csv_columns || [];

        renderPreflight(d.preflight_html || '');
        runSetupState.preview_ok = false;
        runSetupState.generated_ok = false;
        setPathInputMeta('output-dir');
        setPathInputMeta('save-bundle-dir');
        if (!runSetupState.community_file_path && d.community_file) {{
          setPathSummary('community-file-summary', d.community_file, 'Default file ready');
          setPathDisplay('community-status', d.community_file, 'Using default: ');
        }}
        if (!runSetupState.boundary_path && d.boundary_path) {{
          setPathSummary('boundary-file-summary', d.boundary_path, 'Default boundary ready');
          setPathDisplay('boundary-status-text', d.boundary_path, 'Using default: ');
          runSetupState.boundary_path = d.boundary_path;
        }}
        renderAgreementTable();
        applyUtilityCategories(true);
        renderValidationState(null);
        updateGenerateButton();
        setLaunchEnabledState();
        updateStepProgressState();
        const saveDir = document.getElementById('save-bundle-dir');
        if (saveDir) {{
          saveDir.value = d.agents_output_dir || 'data/agents_by_community';
          setPathInputMeta('save-bundle-dir');
        }}
        if (!runSetupState.auto_preview_triggered && d.community_file) {{
          runSetupState.auto_preview_triggered = true;
          runPreview();
        }}
      }}

      function renderPreflight(html) {{
        const el = document.getElementById('preflight-html');
        if (el) el.innerHTML = html || '<div class=\"launch-summary\"><div class=\"launch-summary-grid\"><div class=\"launch-summary-item\"><span class=\"launch-summary-key\">Summary:</span><span class=\"launch-summary-value\">Waiting for validation</span></div></div></div>';
      }}

      function setHTML(id, html) {{
        const el = document.getElementById(id);
        if (el) el.innerHTML = html || '';
      }}

      function renderAgreementTable() {{
        const body = document.getElementById('agreement-rules-body');
        if (!body) return;
        const rows = runSetupState.agreement_rules_table || [];
        body.innerHTML = rows.map((row, idx) => `
          <tr>
            <td><input type=\"number\" step=\"1\" data-idx=\"${{idx}}\" data-field=\"max_age\" value=\"${{row.max_age ?? ''}}\"></td>
            <td><input type=\"number\" step=\"0.01\" data-idx=\"${{idx}}\" data-field=\"ratio\" value=\"${{row.ratio ?? ''}}\"></td>
          </tr>
        `).join('');
        body.querySelectorAll('input').forEach(inp => {{
          inp.addEventListener('input', (e) => {{
            const idx = Number(e.target.dataset.idx);
            const field = e.target.dataset.field;
            if (!runSetupState.agreement_rules_table[idx]) runSetupState.agreement_rules_table[idx] = {{}};
            runSetupState.agreement_rules_table[idx][field] = parseFloat(e.target.value);
          }});
        }});
      }}

      function normalizeSelectedUtilityCategories(value) {{
        const requested = Array.isArray(value) ? value : DEFAULT_SELECTED_UTILITY_CATEGORIES;
        return DEFAULT_SELECTED_UTILITY_CATEGORIES.filter(cat => requested.includes(cat) && UTILITY_CATEGORY_DEFS[cat]);
      }}

      function slugifyUtilityKey(value) {{
        const slug = String(value || '').toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
        return slug || `custom_field_${{Math.random().toString(36).slice(2, 8)}}`;
      }}

      function cloneFieldConfig(field) {{
        return JSON.parse(JSON.stringify(field));
      }}

      function defaultFieldDefByKey(key) {{
        return (UTILITY_FIELD_DEFS || []).find(field => field.key === key) || null;
      }}

      function defaultConfiguredFieldsForCategories(selectedCategories) {{
        const categories = new Set(normalizeSelectedUtilityCategories(selectedCategories));
        return (UTILITY_FIELD_DEFS || []).filter(field => categories.has(field.category)).map(field => {{
          const cloned = cloneFieldConfig(field);
          cloned.is_overridden = false;
          return cloned;
        }});
      }}

      function normalizeConfiguredUtilityFields(selectedCategories, configuredFields = null) {{
        const categories = new Set(normalizeSelectedUtilityCategories(selectedCategories));
        const builtinDefaults = defaultConfiguredFieldsForCategories([...categories]);
        const incoming = Array.isArray(configuredFields) ? configuredFields : [];
        const incomingByKey = new Map(incoming.map(field => [field.key, field]));
        const fields = builtinDefaults.map(field => {{
          const existing = incomingByKey.get(field.key) || {{}};
          return {{
            ...field,
            enabled: existing.enabled ?? field.enabled ?? true,
            is_overridden: existing.is_overridden ?? false,
            value_mode: (existing.is_overridden ? (existing.value_mode || field.value_mode || 'fixed') : (field.value_mode || 'fixed')),
            fixed_value: (existing.is_overridden ? (existing.fixed_value ?? field.fixed_value ?? 0) : (field.fixed_value ?? 0)),
            community_field: (existing.is_overridden ? (existing.community_field ?? field.community_field ?? null) : (field.community_field ?? null)),
            description: (existing.is_overridden ? (existing.description ?? field.description ?? null) : (field.description ?? null)),
          }};
        }});
        incoming.forEach(field => {{
          if (!field || field.builtin) return;
          const category = field.category || 'custom';
          if (category !== 'custom' && !categories.has(category)) return;
          const key = slugifyUtilityKey(field.custom_key || field.key || field.label);
          if (fields.some(item => item.key === key)) return;
          fields.push({{
            ...cloneFieldConfig(field),
            key,
            custom_key: key,
            custom_label: field.custom_label || field.label,
            builtin: false,
            enabled: field.enabled ?? true,
            is_overridden: field.is_overridden ?? true,
            value_mode: field.value_mode || 'fixed',
          }});
        }});
        return fields;
      }}

      function computeConfiguredUtilityState(selectedCategories, configuredFields = null) {{
        const fields = normalizeConfiguredUtilityFields(selectedCategories, configuredFields);
        return {{
          selected_utility_categories: normalizeSelectedUtilityCategories(selectedCategories),
          configured_utility_fields: fields,
          planner_options: fields.filter(field => field.agent === 'planner').map(field => field.key),
          developer_options: fields.filter(field => field.agent === 'developer').map(field => field.key),
          resident_options: fields.filter(field => field.agent === 'resident').map(field => field.key),
          planner_components: fields.filter(field => field.enabled && field.agent === 'planner').map(field => field.key),
          developer_components: fields.filter(field => field.enabled && field.agent === 'developer').map(field => field.key),
          resident_components: fields.filter(field => field.enabled && field.agent === 'resident').map(field => field.key),
        }};
      }}

      function utilityFieldInvalidMessage(field) {{
        if (!field || !field.enabled) return '';
        if (field.builtin && !field.is_overridden) return '';
        if ((field.value_mode || 'fixed') === 'fixed') {{
          return (field.fixed_value === null || field.fixed_value === undefined || field.fixed_value === '' || Number.isNaN(Number(field.fixed_value)))
            ? 'Fixed value is required.'
            : '';
        }}
        if (!field.community_field) return 'Community CSV field is required.';
        if (!(runSetupState.community_csv_columns || []).includes(field.community_field)) return `Field "${{field.community_field}}" is not available in the active community CSV.`;
        return '';
      }}

      function renderValueFlowModelFromState() {{
        const container = document.getElementById('value-flow-html');
        if (!container) return;
        const activeFields = (runSetupState.configured_utility_fields || []).filter(field => field.enabled);
        const categories = normalizeSelectedUtilityCategories(runSetupState.selected_utility_categories);
        const rows = categories.map(cat => {{
          const categoryFields = activeFields.filter(field => (field.category || 'custom') === cat);
          if (!categoryFields.length) return '';
          const categoryLabel = cat === 'custom' ? 'Custom' : (UTILITY_CATEGORY_DEFS[cat]?.label || cat);
          const categoryDef = UTILITY_CATEGORY_DEFS[cat] || {{}};
          const aggregateDirection = (actor) => {{
            const dirs = Array.from(new Set(categoryFields.filter(field => field.agent === actor).map(field => field.direction || 'neutral')));
            if (!dirs.length) return 'neutral';
            const nonNeutral = dirs.filter(dir => dir !== 'neutral');
            if (!nonNeutral.length) return 'neutral';
            if (Array.from(new Set(nonNeutral)).length === 1) return nonNeutral[0];
            return 'transfer';
          }};
          const cells = ['planner', 'developer', 'resident'].map(actor => {{
            const fallback = categoryDef.impacts?.[actor] || 'neutral';
            const spec = UTILITY_IMPACT_SPECS[aggregateDirection(actor) || fallback] || UTILITY_IMPACT_SPECS[fallback] || UTILITY_IMPACT_SPECS.neutral;
            return `<td><span class="flow-pill ${{spec[2]}}"><span class="flow-pill-symbol">${{spec[0]}}</span><span>${{spec[1]}}</span></span></td>`;
          }}).join('');
          const customizedCount = categoryFields.filter(field => !field.builtin || field.is_overridden).length;
          const sourceSummary = customizedCount ? `${{customizedCount}} customized field${{customizedCount > 1 ? 's' : ''}}` : 'Default';
          return `
            <tr>
              <td class="flow-factor-cell">
                <span class="flow-factor-dot neutral"></span>
                <span>${{categoryLabel}}</span>
                <div class="value-flow-subtitle" style="font-size:11px;">${{sourceSummary}}</div>
              </td>
              ${{cells}}
            </tr>
          `;
        }}).join('');
        container.innerHTML = `
          <div class="value-flow-card">
            <div class="value-flow-head">
              <div class="value-flow-title-row">
                <div class="value-flow-title">Utility Setting</div>
                <div class="value-flow-subtitle">Configured from utility categories and field sources</div>
              </div>
              <div class="value-flow-meta">${{activeFields.length}} active fields · ${{(runSetupState.community_csv_columns || []).length}} community columns</div>
            </div>
            <div class="value-flow-table-shell">
              <table class="value-flow-table">
                <thead>
                  <tr>
                    <th>Factor</th>
                    <th>Planner</th>
                    <th>Developer</th>
                    <th>Resident</th>
                  </tr>
                </thead>
                <tbody>
                  ${{rows || '<tr><td class="flow-empty-cell" colspan="4">No utility fields configured.</td></tr>'}}
                </tbody>
              </table>
            </div>
          </div>
        `;
      }}

      function renderOverrides() {{
        const activeKey = runSetupState.active_utility_editor_key || null;
        const activeCategory = runSetupState.active_utility_category_editor || null;
        const panel = document.getElementById('utility-category-editor-panel');
        const titleEl = document.getElementById('utility-category-editor-title');
        const copyEl = document.getElementById('utility-category-editor-copy');
        const bodyEl = document.getElementById('utility-category-editor-body');
        if (!panel || !titleEl || !bodyEl) return;
        if (!activeCategory) {{
          panel.style.display = 'none';
          bodyEl.innerHTML = '';
          return;
        }}
        const categoryLabel = UTILITY_CATEGORY_DEFS[activeCategory]?.label || activeCategory;
        titleEl.textContent = `${{categoryLabel}} configuration`;
        if (copyEl) copyEl.textContent = `Only ${{categoryLabel.toLowerCase()}} utility fields are shown here.`;
        panel.style.display = 'grid';
        const renderGroup = (agent) => {{
          const fields = (runSetupState.configured_utility_fields || []).filter(field => field.agent === agent && (field.category || 'custom') === activeCategory);
          if (!fields.length) return '';
          return `
            <div class="utility-agent-section">
              <div class="utility-agent-section-title">${{agent}}</div>
              <div class="utility-field-list">
                ${{fields.map(field => {{
            const invalid = utilityFieldInvalidMessage(field);
            const isExpanded = activeKey === field.key;
            const communityOptions = (runSetupState.community_csv_columns || []).map(col => `<option value="${{col}}" ${{field.community_field===col?'selected':''}}>${{col}}</option>`).join('');
            const sourceSummary = field.builtin && !field.is_overridden
              ? 'Default'
              : ((field.value_mode || 'fixed') === 'community_field' ? 'Community field' : 'Fixed value');
            const valueSummary = field.builtin && !field.is_overridden
              ? (((field.value_mode || 'fixed') === 'community_field')
                ? `Builtin field: ${{field.community_field || 'not set'}}`
                : `Builtin value: ${{field.fixed_value ?? 'configured in model'}}`)
              : (((field.value_mode || 'fixed') === 'community_field')
                ? `Reads from: ${{field.community_field || 'No field selected'}}`
                : `Value: ${{field.fixed_value ?? 'Not set'}}`);
            return `
              <div class="utility-field-card">
                <div class="utility-field-head">
                  <div>
                    <div class="utility-field-title">${{field.label}}</div>
                    <div class="utility-field-meta">${{field.category}} · ${{field.direction}}${{field.builtin ? '' : ' · custom'}}</div>
                  </div>
                  <div class="utility-field-actions">
                    <label><input type="checkbox" data-field-key="${{field.key}}" data-action="enabled" ${{field.enabled ? 'checked' : ''}}> Enabled</label>
                    <button class="button ghost" type="button" data-field-key="${{field.key}}" data-action="toggle_expand">${{isExpanded ? 'Close' : (field.builtin && !field.is_overridden ? 'Modify' : 'Edit')}}</button>
                    ${{field.builtin ? '' : `<button class="button ghost" type="button" data-field-key="${{field.key}}" data-action="remove">Remove</button>`}}
                  </div>
                </div>
                <div class="utility-field-summary">
                  <div class="utility-field-summary-row">
                    <span class="utility-field-summary-label">Source</span>
                    <span class="utility-field-summary-value">${{sourceSummary}}</span>
                  </div>
                  <div class="utility-field-summary-row">
                    <span class="utility-field-summary-label">Current value</span>
                    <span class="utility-field-summary-value" title="${{valueSummary}}">${{valueSummary}}</span>
                  </div>
                </div>
                ${{isExpanded ? `
                  <div class="utility-field-editor">
                    <div class="utility-field-grid">
                      <div class="run-field">
                        <label>Source mode</label>
                        <select data-field-key="${{field.key}}" data-action="value_mode">
                          <option value="fixed" ${{(field.value_mode||'fixed')==='fixed'?'selected':''}}>Fixed value</option>
                          <option value="community_field" ${{field.value_mode==='community_field'?'selected':''}}>Community CSV field</option>
                        </select>
                      </div>
                      <div class="run-field">
                        <label>${{(field.value_mode || 'fixed') === 'community_field' ? 'Community CSV field' : 'Fixed value'}}</label>
                        ${{(field.value_mode || 'fixed') === 'community_field'
                          ? `<select data-field-key="${{field.key}}" data-action="community_field">
                              <option value="">Select field</option>
                              ${{communityOptions}}
                            </select>`
                          : `<input data-field-key="${{field.key}}" data-action="fixed_value" type="number" step="0.01" value="${{field.fixed_value ?? ''}}" />`
                        }}
                      </div>
                    </div>
                    ${{field.description ? `<div class="field-hint">${{field.description}}</div>` : ''}}
                  </div>
                  <div class="toolbar">
                    <div class="toolbar-actions">
                      ${{field.builtin ? `<button class="button ghost" type="button" data-field-key="${{field.key}}" data-action="reset_default">Reset to default</button>` : ''}}
                      <button class="button secondary" type="button" data-field-key="${{field.key}}" data-action="done">Done</button>
                    </div>
                  </div>
                ` : ''}}
                ${{invalid ? `<div class="utility-field-inline-note">${{invalid}}</div>` : ''}}
              </div>
            `;
                }}).join('')}}
              </div>
            </div>
          `;
        }};
        bodyEl.innerHTML = ['planner', 'developer', 'resident'].map(renderGroup).filter(Boolean).join('') || '<div class="run-inline-note">No utility fields are enabled for this category.</div>';
        bodyEl.querySelectorAll('[data-field-key][data-action]').forEach(node => {{
          if (node.tagName === 'BUTTON') node.addEventListener('click', handleUtilityFieldAction);
          else node.addEventListener('change', handleUtilityFieldChange);
        }});
      }}

      function renderUtilityCategories() {{
        const container = document.getElementById('utility-category-options');
        if (!container) return;
        const cats = normalizeSelectedUtilityCategories(runSetupState.selected_utility_categories);
        const activeCategory = runSetupState.active_utility_category_editor || null;
        container.innerHTML = Object.entries(UTILITY_CATEGORY_DEFS).map(([key, def]) => `
          <div class="utility-category-row ${{activeCategory === key ? 'is-active' : ''}}">
            <div class="utility-category-row-main">
              <label><input type="checkbox" data-cat="${{key}}" ${{cats.includes(key)?'checked':''}}> <span class="utility-category-label">${{def.label}}</span></label>
            </div>
            <button class="button ghost" type="button" data-category-editor="${{key}}">${{activeCategory === key ? 'Close' : 'Modify'}}</button>
          </div>
        `).join('');
        container.querySelectorAll('input[type=\"checkbox\"]').forEach(cb => {{
          cb.addEventListener('change', (e) => {{
            const cat = e.target.dataset.cat;
            const selected = new Set(normalizeSelectedUtilityCategories(runSetupState.selected_utility_categories));
            if (e.target.checked) selected.add(cat); else selected.delete(cat);
            runSetupState.selected_utility_categories = DEFAULT_SELECTED_UTILITY_CATEGORIES.filter(value => selected.has(value));
            if (!runSetupState.selected_utility_categories.includes(runSetupState.active_utility_category_editor)) {{
              runSetupState.active_utility_category_editor = null;
              runSetupState.active_utility_editor_key = null;
            }}
            applyUtilityCategories(false);
          }});
        }});
        container.querySelectorAll('[data-category-editor]').forEach(btn => {{
          btn.addEventListener('click', (e) => {{
            const key = e.currentTarget.dataset.categoryEditor;
            if (runSetupState.active_utility_category_editor === key) {{
              runSetupState.active_utility_category_editor = null;
              runSetupState.active_utility_editor_key = null;
            }} else {{
              runSetupState.active_utility_category_editor = key;
              runSetupState.active_utility_editor_key = null;
            }}
            renderUtilityCategories();
            renderOverrides();
          }});
        }});
      }}

      function applyUtilityCategories(preserveCurrent = false) {{
        const next = computeConfiguredUtilityState(
          runSetupState.selected_utility_categories,
          preserveCurrent ? (runSetupState.configured_utility_fields || []) : []
        );
        runSetupState.selected_utility_categories = next.selected_utility_categories;
        runSetupState.configured_utility_fields = next.configured_utility_fields;
        runSetupState.planner_options = next.planner_options;
        runSetupState.developer_options = next.developer_options;
        runSetupState.resident_options = next.resident_options;
        runSetupState.planner_components = next.planner_components;
        runSetupState.developer_components = next.developer_components;
        runSetupState.resident_components = next.resident_components;
        if (runSetupState.active_utility_category_editor && !runSetupState.selected_utility_categories.includes(runSetupState.active_utility_category_editor)) {{
          runSetupState.active_utility_category_editor = null;
          runSetupState.active_utility_editor_key = null;
        }}
        renderValueFlowModelFromState();
        renderOverrides();
        renderUtilityCategories();
        renderCustomFieldBuilderOptions();
      }}

      function renderCustomFieldBuilderOptions() {{
        const select = document.getElementById('custom-field-community-field');
        if (!select) return;
        const current = select.value;
        select.innerHTML = `<option value="">Select field</option>${{(runSetupState.community_csv_columns || []).map(col => `<option value="${{col}}">${{col}}</option>`).join('')}}`;
        if ((runSetupState.community_csv_columns || []).includes(current)) select.value = current;
        const shell = document.getElementById('custom-field-builder-shell');
        const btn = document.getElementById('toggle-custom-field-builder-btn');
        if (shell) shell.style.display = runSetupState.show_custom_field_builder ? 'grid' : 'none';
        if (btn) btn.textContent = runSetupState.show_custom_field_builder ? 'Hide custom field form' : 'Add custom utility field';
      }}

      function toggleCustomFieldBuilder(forceValue = null) {{
        runSetupState.show_custom_field_builder = typeof forceValue === 'boolean'
          ? forceValue
          : !runSetupState.show_custom_field_builder;
        renderCustomFieldBuilderOptions();
      }}

      function handleUtilityFieldChange(event) {{
        const key = event.target.dataset.fieldKey;
        const action = event.target.dataset.action;
        const field = (runSetupState.configured_utility_fields || []).find(item => item.key === key);
        if (!field) return;
        if (action === 'enabled') field.enabled = !!event.target.checked;
        if (action === 'value_mode') {{ field.value_mode = event.target.value; field.is_overridden = true; }}
        if (action === 'fixed_value') {{ field.fixed_value = event.target.value === '' ? null : Number(event.target.value); field.is_overridden = true; }}
        if (action === 'community_field') {{ field.community_field = event.target.value || null; field.is_overridden = true; }}
        if (action === 'description') {{ field.description = event.target.value || null; field.is_overridden = true; }}
        applyUtilityCategories(true);
      }}

      function handleUtilityFieldAction(event) {{
        const key = event.target.dataset.fieldKey;
        const action = event.target.dataset.action;
        if (!key) return;
        if (action === 'remove') {{
          runSetupState.configured_utility_fields = (runSetupState.configured_utility_fields || []).filter(field => field.key !== key);
          if (runSetupState.active_utility_editor_key === key) runSetupState.active_utility_editor_key = null;
          applyUtilityCategories(true);
          return;
        }}
        if (action === 'toggle_expand') {{
          const field = (runSetupState.configured_utility_fields || []).find(item => item.key === key);
          if (!field) return;
          if (runSetupState.active_utility_editor_key === key) {{
            runSetupState.active_utility_editor_key = null;
          }} else {{
            runSetupState.active_utility_editor_key = key;
            if (field.builtin && !field.is_overridden) field.is_overridden = true;
          }}
          applyUtilityCategories(true);
          return;
        }}
        if (action === 'done') {{
          runSetupState.active_utility_editor_key = null;
          applyUtilityCategories(true);
          return;
        }}
        if (action === 'reset_default') {{
          const field = (runSetupState.configured_utility_fields || []).find(item => item.key === key);
          const builtinDefault = defaultFieldDefByKey(key);
          if (!field || !builtinDefault) return;
          field.is_overridden = false;
          field.value_mode = builtinDefault.value_mode || 'fixed';
          field.fixed_value = builtinDefault.fixed_value ?? null;
          field.community_field = builtinDefault.community_field ?? null;
          field.description = builtinDefault.description ?? null;
          if (runSetupState.active_utility_editor_key === key) runSetupState.active_utility_editor_key = null;
          applyUtilityCategories(true);
        }}
      }}

      function addCustomUtilityField() {{
        showInlineError('custom-field-error', '');
        const label = document.getElementById('custom-field-label')?.value?.trim() || '';
        if (!label) {{
          showInlineError('custom-field-error', 'Custom field label is required.');
          return;
        }}
        const key = slugifyUtilityKey(label);
        if ((runSetupState.configured_utility_fields || []).some(field => field.key === key)) {{
          showInlineError('custom-field-error', `Custom field key "${{key}}" already exists.`);
          return;
        }}
        const valueMode = document.getElementById('custom-field-value-mode')?.value || 'fixed';
        runSetupState.configured_utility_fields = [
          ...(runSetupState.configured_utility_fields || []),
          {{
            key,
            custom_key: key,
            label,
            custom_label: label,
            agent: document.getElementById('custom-field-agent')?.value || 'resident',
            category: document.getElementById('custom-field-category')?.value || 'custom',
            direction: document.getElementById('custom-field-direction')?.value || 'neutral',
            builtin: false,
            enabled: !!document.getElementById('custom-field-enabled')?.checked,
            is_overridden: true,
            value_mode: valueMode,
            fixed_value: valueMode === 'fixed' ? (document.getElementById('custom-field-fixed-value')?.value === '' ? null : Number(document.getElementById('custom-field-fixed-value')?.value)) : null,
            community_field: valueMode === 'community_field' ? (document.getElementById('custom-field-community-field')?.value || null) : null,
            description: document.getElementById('custom-field-impact-description')?.value?.trim() || null,
            impact_description: document.getElementById('custom-field-impact-description')?.value?.trim() || null,
          }}
        ];
        if (runSetupState.active_utility_editor_key === key) runSetupState.active_utility_editor_key = null;
        runSetupState.show_custom_field_builder = false;
        applyUtilityCategories(true);
        ['custom-field-label','custom-field-fixed-value','custom-field-impact-description'].forEach(id => {{
          const el = document.getElementById(id);
          if (el) el.value = '';
        }});
      }}

      function formatCount(value) {{
        const n = Number(value || 0);
        return Number.isFinite(n) ? n.toLocaleString() : '0';
      }}

      function shortPath(path) {{
        return compactPathDisplay(path || '') || '—';
      }}

      function setPromptStatus(message, level = 'neutral') {{
        runSetupState.prompt_status_message = message || '';
        runSetupState.prompt_ready = level === 'ready';
        ['prompt-fields-status', 'prompt-fields-status-load'].forEach(id => {{
          const el = document.getElementById(id);
          if (!el) return;
          el.textContent = message || 'Prompt fields checked automatically';
          el.classList.remove('is-ready', 'is-warning', 'is-error');
          if (level === 'ready') el.classList.add('is-ready');
          else if (level === 'warning') el.classList.add('is-warning');
          else if (level === 'error') el.classList.add('is-error');
        }});
        updateCsvPrepUi();
      }}

      function setCsvMode(mode) {{
        runSetupState.csv_prep_mode = mode === 'load' ? 'load' : 'generate';
        const isLoad = runSetupState.csv_prep_mode === 'load';
        const genBtn = document.getElementById('csv-mode-generate');
        const loadBtn = document.getElementById('csv-mode-load');
        const genPanel = document.getElementById('csv-generate-panel');
        const loadPanel = document.getElementById('csv-load-panel');
        if (genBtn) {{
          genBtn.classList.toggle('is-active', !isLoad);
          genBtn.setAttribute('aria-selected', !isLoad ? 'true' : 'false');
        }}
        if (loadBtn) {{
          loadBtn.classList.toggle('is-active', isLoad);
          loadBtn.setAttribute('aria-selected', isLoad ? 'true' : 'false');
        }}
        if (genPanel) genPanel.classList.toggle('is-active', !isLoad && !runSetupState.generated_ok);
        if (loadPanel) loadPanel.classList.toggle('is-active', isLoad && !runSetupState.generated_ok);
        if (!runSetupState.generated_ok) {{
          setPromptStatus(isLoad ? 'Will be checked automatically after loading' : 'Will be checked automatically after generation', 'neutral');
        }} else {{
          updateCsvPrepUi();
        }}
      }}

      function markCsvPrepDirty(message = '') {{
        runSetupState.generated_ok = false;
        runSetupState.generated_bundle_state = {{}};
        runSetupState.prompt_ready = false;
        runSetupState.csvs_saved_dir = '';
        if (message) setPromptStatus(message, 'neutral');
        updateCsvPrepUi();
        updateGenerateButton();
        setLaunchEnabledState();
        updateStepProgressState();
      }}

      function updateCsvPrepUi() {{
        const state = runSetupState.generated_bundle_state || {{}};
        const validation = state ? null : null;
        const bundleReady = !!(state.all_agents_csv_path && state.representative_csv_path && runSetupState.generated_ok);
        const genPanel = document.getElementById('csv-generate-panel');
        const loadPanel = document.getElementById('csv-load-panel');
        const isLoad = runSetupState.csv_prep_mode === 'load';
        if (genPanel) genPanel.classList.toggle('is-active', !isLoad && !bundleReady);
        if (loadPanel) loadPanel.classList.toggle('is-active', isLoad && !bundleReady);
        const resultCard = document.getElementById('csv-result-card');
        if (resultCard) resultCard.classList.toggle('is-visible', bundleReady);
        const residentsSummary = document.getElementById('residents-csv-summary');
        if (residentsSummary) residentsSummary.innerHTML = state.all_agents_csv_path ? `<strong>${{shortPath(state.all_agents_csv_path)}}</strong>` : 'Will be generated automatically';
        const repsSummary = document.getElementById('representatives-csv-summary');
        if (repsSummary) repsSummary.innerHTML = state.representative_csv_path ? `<strong>${{shortPath(state.representative_csv_path)}}</strong>` : 'Will be selected automatically from generated residents';
        const residentsCount = state.residents_count ?? state.estimated_residents ?? 0;
        const representativesCount = state.representatives_count ?? state.estimated_representatives ?? 0;
        const resEl = document.getElementById('csv-result-residents');
        if (resEl) resEl.textContent = formatCount(residentsCount);
        const repEl = document.getElementById('csv-result-representatives');
        if (repEl) repEl.textContent = formatCount(representativesCount);
        const promptEl = document.getElementById('csv-result-prompts');
        if (promptEl) promptEl.textContent = runSetupState.prompt_ready ? 'Ready' : (runSetupState.prompt_status_message || 'Not checked');
        const savedEl = document.getElementById('csv-result-saved-to');
        if (savedEl) savedEl.textContent = runSetupState.csvs_saved_dir || shortPath(state.staging_dir || state.all_agents_csv_path || '');
        const secondary = document.getElementById('csv-secondary-action-btn');
        if (secondary) secondary.textContent = isLoad ? 'Reload' : 'Regenerate';
      }}

      function updateGenerateButton() {{
        const enable = runSetupState.preview_ok && !!getCommunityPath();
        const mainGenerateBtn = document.getElementById('generate-csvs-btn');
        if (mainGenerateBtn) {{
          mainGenerateBtn.classList.toggle('is-disabled', !enable);
          mainGenerateBtn.setAttribute('aria-disabled', !enable);
        }}
        const btn = document.getElementById('generate-btn');
        const selectBtn = document.getElementById('select-reps-btn');
        if (btn) {{
          btn.classList.toggle('is-disabled', !enable);
          btn.setAttribute('aria-disabled', !enable);
        }}
        const selectEnable = !!(runSetupState.generated_bundle_state || {{}}).all_agents_csv_path;
        if (selectBtn) {{
          selectBtn.classList.toggle('is-disabled', !selectEnable);
          selectBtn.setAttribute('aria-disabled', !selectEnable);
        }}
        updateCsvPrepUi();
      }}

      function setLaunchEnabledState() {{
        const btn = document.getElementById('launch-btn');
        const note = document.getElementById('launch-note');
        const badge = document.getElementById('launch-status-badge');
        const enable = runSetupState.generated_ok && runSetupState.preview_ok && !!getCommunityPath();
        const hasCommunity = !!getCommunityPath();
        const hasPreview = !!runSetupState.preview_ok;
        let statusText = 'Blocked';
        let statusTone = 'error';
        let noteText = 'Blocked: CSVs are not prepared';
        if (enable) {{
          statusText = 'Ready';
          statusTone = 'success';
          noteText = 'Ready to launch';
        }} else if (hasCommunity && hasPreview) {{
          statusText = 'Pending';
          statusTone = 'warning';
          noteText = 'Resident and representative CSVs missing';
        }} else if (!hasCommunity) {{
          noteText = 'Community file missing';
        }} else if (!hasPreview) {{
          noteText = 'Validation incomplete';
        }}
        if (btn) {{
          btn.classList.toggle('is-disabled', !enable);
          btn.setAttribute('aria-disabled', !enable);
        }}
        if (note) {{
          note.textContent = noteText;
        }}
        if (badge) {{
          badge.className = `status-pill launch-status-badge ${{statusTone}}`;
          badge.textContent = statusText;
        }}
      }}

      async function uploadCommunityFile(file) {{
        if (!file) return;
        showInlineError('community-error', '');
        setBusyState('panel-step1', true);
        const form = new FormData();
        form.append('community_file', file);
        try {{
          const res = await fetch('/api/run/upload', {{ method: 'POST', body: form }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (data.status !== 'ok') throw new Error(data.message || 'Upload failed');
          runSetupState.community_file_token = data.community_file_token;
          runSetupState.community_file_path = data.community_file_path;
          const communityPathInput = document.getElementById('community-path');
          if (communityPathInput) {{
            communityPathInput.value = data.community_file_path;
            setPathInputMeta('community-path');
          }}
          setPathSummary('community-file-summary', data.display_name || data.community_file_path, 'Uploaded file ready');
          setPathDisplay('community-status', data.display_name || data.community_file_path, 'Uploaded: ');
          runPreview();
        }} catch (err) {{
          showInlineError('community-error', err.message || 'Upload failed');
        }} finally {{
          setBusyState('panel-step1', false);
        }}
      }}

      async function uploadBoundaryFiles(fileList) {{
        if (!fileList || !fileList.length) return;
        showInlineError('boundary-error', '');
        setBusyState('panel-step1', true);
        const form = new FormData();
        Array.from(fileList).forEach(f => form.append('boundary_files', f));
        try {{
          const res = await fetch('/api/run/upload', {{ method: 'POST', body: form }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (data.status !== 'ok') throw new Error(data.message || 'Upload failed');
          runSetupState.boundary_bundle_token = data.boundary_bundle_token;
          runSetupState.boundary_path = data.boundary_path;
          const boundaryPathInput = document.getElementById('boundary-path');
          if (boundaryPathInput) {{
            boundaryPathInput.value = data.boundary_path;
            setPathInputMeta('boundary-path');
          }}
          setPathSummary('boundary-file-summary', data.display_name || data.boundary_path, 'Boundary file ready');
          setPathDisplay('boundary-status-text', data.display_name || data.boundary_path, 'Uploaded: ');
          runPreview();
        }} catch (err) {{
          showInlineError('boundary-error', err.message || 'Upload failed');
        }} finally {{
          setBusyState('panel-step1', false);
        }}
      }}

      async function runPreview() {{
        const defaults = runSetupState.defaults || {{}};
        const communityPath = getCommunityPath();
        const boundaryPath = getBoundaryPath();
        if (!communityPath) {{
          showInlineError('community-error', 'Please upload community file first.');
          return;
        }}
        setBusyState('panel-step2', true);
        try {{
          const body = {{
            community_file: communityPath,
            shp_files: boundaryPath ? [boundaryPath] : null,
            residents_per_household: numberFieldValue('residents-per-household', defaults.residents_per_household ?? {DEFAULT_RESIDENTS_PER_HOUSEHOLD}),
            vacancy_ratio: numberFieldValue('vacancy-ratio', defaults.vacancy_ratio ?? {DEFAULT_VACANCY_RATIO}),
            representatives_per_community: integerFieldValue('representatives', defaults.representatives_per_community ?? {DEFAULT_REPRESENTATIVES_PER_COMMUNITY}),
            hardship_quantile: numberFieldValue('hardship-quantile', defaults.hardship_quantile ?? {DEFAULT_HARDSHIP_QUANTILE}),
            target_community: getTargetCommunities(),
            model_name: document.getElementById('model-name').value || defaults.model_name || "{_default_model_name()}",
            rounds: integerFieldValue('rounds', defaults.rounds ?? 8),
            agreement_mode: document.getElementById('agreement-mode').value || defaults.agreement_mode || "by_build_year",
            agreement_fixed_ratio: numberFieldValue('fixed-ratio', defaults.agreement_fixed_ratio ?? 1.0),
            max_extension_ratio: numberFieldValue('extension-cap', defaults.max_extension_ratio ?? 0.3),
            cash_subsidy_cap: numberFieldValue('subsidy-cap', defaults.cash_subsidy_cap ?? 0.1),
            developer_min_profit_rate: numberFieldValue('min-profit', defaults.developer_min_profit_rate ?? {DEFAULT_DEVELOPER_MIN_PROFIT_RATE}),
            planner_soft_policy_text: document.getElementById('planner-soft-policy-text').value || "",
            output_dir: document.getElementById('output-dir').value || defaults.output_dir || "{_default_output_dir_ui()}",
            generated_bundle_state: runSetupState.generated_bundle_state || {{}},
            agreement_rules_table: runSetupState.agreement_rules_table || defaults.agreement_rules_table || [],
            selected_utility_categories: runSetupState.selected_utility_categories || defaults.selected_utility_categories || [...DEFAULT_SELECTED_UTILITY_CATEGORIES],
            configured_utility_fields: runSetupState.configured_utility_fields || defaults.configured_utility_fields || [],
            planner_utility_components: runSetupState.planner_components || [],
            developer_utility_components: runSetupState.developer_components || [],
            resident_utility_components: runSetupState.resident_components || [],
          }};
          const res = await fetch('/api/run/preview', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(body),
          }});
          if (!res.ok) {{
            const txt = await res.text();
            throw new Error(txt || 'Preview failed');
          }}
          const data = await res.json();
          renderPreview(data);
        }} catch (err) {{
          showInlineError('community-error', err.message || 'Preview failed');
        }} finally {{
          setBusyState('panel-step2', false);
        }}
      }}

      function renderPreview(payload) {{
        if (!payload) return;
        renderValidationState(payload);
        if (payload.preflight_html) setHTML('preflight-html', payload.preflight_html);
        renderTargetOptions(payload.target_community);
        if (payload.selected_utility_categories) runSetupState.selected_utility_categories = payload.selected_utility_categories;
        if (payload.generated_bundle_state) runSetupState.generated_bundle_state = payload.generated_bundle_state;
        if (payload.planner_components) runSetupState.planner_components = payload.planner_components;
        if (payload.developer_components) runSetupState.developer_components = payload.developer_components;
        if (payload.resident_components) runSetupState.resident_components = payload.resident_components;
        if (payload.planner_options) runSetupState.planner_options = payload.planner_options;
        if (payload.developer_options) runSetupState.developer_options = payload.developer_options;
        if (payload.resident_options) runSetupState.resident_options = payload.resident_options;
        if (payload.configured_utility_fields) runSetupState.configured_utility_fields = payload.configured_utility_fields;
        if (payload.community_csv_columns) runSetupState.community_csv_columns = payload.community_csv_columns;
        if (payload.agreement_rules_table) {{
          runSetupState.agreement_rules_table = payload.agreement_rules_table;
          renderAgreementTable();
        }}
        applyUtilityCategories(true);
        runSetupState.preview_ok = true;
        runSetupState.generated_ok = !!payload.validation_state?.bundle_ready;
        renderValidationState(payload);
        updateGenerateButton();
        setLaunchEnabledState();
        updateSaveButtonState();
        updateStepProgressState();
      }}

      function buildGenerateRequestBody() {{
        const defaults = runSetupState.defaults || {{}};
        const communityPath = getCommunityPath();
        const boundaryPath = getBoundaryPath();
        return {{
          community_file: communityPath,
          shp_files: boundaryPath ? [boundaryPath] : null,
          residents_per_household: numberFieldValue('residents-per-household', defaults.residents_per_household),
          vacancy_ratio: numberFieldValue('vacancy-ratio', defaults.vacancy_ratio),
          representatives_per_community: integerFieldValue('representatives', defaults.representatives_per_community),
          hardship_quantile: numberFieldValue('hardship-quantile', defaults.hardship_quantile),
          target_community: getTargetCommunities(),
          model_name: document.getElementById('model-name').value || defaults.model_name,
          rounds: integerFieldValue('rounds', defaults.rounds),
          agreement_mode: document.getElementById('agreement-mode').value || defaults.agreement_mode,
          max_extension_ratio: numberFieldValue('extension-cap', defaults.max_extension_ratio),
          cash_subsidy_cap: numberFieldValue('subsidy-cap', defaults.cash_subsidy_cap),
          developer_min_profit_rate: numberFieldValue('min-profit', defaults.developer_min_profit_rate),
          output_dir: document.getElementById('output-dir').value || defaults.output_dir,
          agreement_rules_table: runSetupState.agreement_rules_table || defaults.agreement_rules_table || [],
          selected_utility_categories: runSetupState.selected_utility_categories || defaults.selected_utility_categories || [...DEFAULT_SELECTED_UTILITY_CATEGORIES],
          configured_utility_fields: runSetupState.configured_utility_fields || defaults.configured_utility_fields || [],
          planner_utility_components: runSetupState.planner_components || defaults.planner_components || [],
          developer_utility_components: runSetupState.developer_components || defaults.developer_components || [],
          resident_utility_components: runSetupState.resident_components || defaults.resident_components || [],
        }};
      }}

      async function runGenerateAgents(options = {{}}) {{
        showInlineError('generate-error', '');
        const communityPath = getCommunityPath();
        if (!runSetupState.preview_ok || !communityPath) {{
          showInlineError('generate-error', 'Upload and preview a valid community file first.');
          return null;
        }}
        const btn = document.getElementById(options.main ? 'generate-csvs-btn' : 'generate-btn');
        if (btn && !options.ignoreDisabled && btn.classList.contains('is-disabled')) return null;
        if (btn) btn.classList.add('is-disabled');
        if (!options.noBusy) setBusyState('panel-step2', true);
        try {{
          const res = await fetch('/api/run/generate_residents', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(buildGenerateRequestBody()),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          renderGenerateAgents(data);
          return data;
        }} catch (err) {{
          runSetupState.last_generate_error = err.message || 'Generate residents and representatives failed';
          showInlineError('generate-error', runSetupState.last_generate_error);
          return null;
        }} finally {{
          if (!options.noBusy) setBusyState('panel-step2', false);
          if (btn && !options.keepDisabled) btn.classList.remove('is-disabled');
        }}
      }}

      function renderGenerateAgents(payload) {{
        renderPreview(payload);
        if (payload.preflight_html) renderPreflight(payload.preflight_html);
        if (payload.generated_bundle_state) runSetupState.generated_bundle_state = payload.generated_bundle_state;
        runSetupState.preview_ok = true;
        runSetupState.generated_ok = !!payload.validation_state?.bundle_ready;
        if (payload.selected_utility_categories) runSetupState.selected_utility_categories = payload.selected_utility_categories;
        runSetupState.planner_components = payload.planner_components || runSetupState.planner_components;
        runSetupState.developer_components = payload.developer_components || runSetupState.developer_components;
        runSetupState.resident_components = payload.resident_components || runSetupState.resident_components;
        if (payload.planner_options) runSetupState.planner_options = payload.planner_options;
        if (payload.developer_options) runSetupState.developer_options = payload.developer_options;
        if (payload.resident_options) runSetupState.resident_options = payload.resident_options;
        if (payload.configured_utility_fields) runSetupState.configured_utility_fields = payload.configured_utility_fields;
        if (payload.community_csv_columns) runSetupState.community_csv_columns = payload.community_csv_columns;
        if (payload.agreement_rules_table) {{
          runSetupState.agreement_rules_table = payload.agreement_rules_table;
          renderAgreementTable();
        }}
        applyUtilityCategories(true);
        renderValidationState(payload);
        updateGenerateButton();
        setLaunchEnabledState();
        updateSaveButtonState();
        updateStepProgressState();
      }}

      async function autoEnsurePromptFields() {{
        const state = runSetupState.generated_bundle_state || {{}};
        if (!state.all_agents_csv_path) {{
          setPromptStatus('Prompt fields: residents CSV missing', 'error');
          return false;
        }}
        setPromptStatus('Checking prompt fields...', 'warning');
        try {{
          const checkRes = await fetch('/api/run/check_prompt_fields', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ generated_bundle_state: state }}),
          }});
          if (!checkRes.ok) throw new Error(await checkRes.text());
          const checkData = await checkRes.json();
          if (checkData.prompt_ready) {{
            setPromptStatus('Ready', 'ready');
            return true;
          }}
          if (checkData.can_generate_prompts === false) {{
            const missing = (checkData.missing_prompt_source_fields || []).join(', ');
            setPromptStatus(missing ? `Missing fields: ${{missing}}` : (checkData.status_message || 'Prompt fields are not ready'), 'error');
            return false;
          }}
          const missingCount = Number(checkData.prompt_missing_count || 0);
          setPromptStatus(missingCount ? `Generating missing prompt fields for ${{missingCount.toLocaleString()}} residents...` : 'Generating missing prompt fields...', 'warning');
          const genRes = await fetch('/api/run/generate_prompt_fields', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ generated_bundle_state: runSetupState.generated_bundle_state || {{}} }}),
          }});
          if (!genRes.ok) throw new Error(await genRes.text());
          const genData = await genRes.json();
          if (genData.generated_bundle_state) runSetupState.generated_bundle_state = genData.generated_bundle_state;
          setPromptStatus(genData.prompt_ready === false ? (genData.status_message || 'Prompt fields are not ready') : 'Ready', genData.prompt_ready === false ? 'error' : 'ready');
          updateCsvPrepUi();
          return genData.prompt_ready !== false;
        }} catch (err) {{
          setPromptStatus(err.message || 'Prompt field check failed', 'error');
          return false;
        }}
      }}

      async function savePreparedCsvs() {{
        const dirInput = document.getElementById('save-bundle-dir');
        const target_dir = (dirInput ? dirInput.value.trim() : '') || (runSetupState.defaults?.agents_output_dir || 'data/agents_by_community');
        if (dirInput && !dirInput.value.trim()) {{
          dirInput.value = target_dir;
          setPathInputMeta('save-bundle-dir');
        }}
        const res = await fetch('/api/run/save_bundle', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            target_dir,
            generated_bundle_state: runSetupState.generated_bundle_state || {{}},
          }}),
        }});
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        if (data.residents_csv || data.representatives_csv) {{
          runSetupState.generated_bundle_state = {{
            ...(runSetupState.generated_bundle_state || {{}}),
            all_agents_csv_path: data.residents_csv || (runSetupState.generated_bundle_state || {{}}).all_agents_csv_path,
            representative_csv_path: data.representatives_csv || (runSetupState.generated_bundle_state || {{}}).representative_csv_path,
            staging_dir: target_dir,
          }};
        }}
        runSetupState.csvs_saved_dir = target_dir;
        return data;
      }}

      async function runGenerateAndSaveCsvs() {{
        const btn = document.getElementById('generate-csvs-btn');
        if (btn && btn.classList.contains('is-disabled')) return;
        showInlineError('generate-error', '');
        const status = document.getElementById('save-bundle-status');
        if (status) status.textContent = 'Generating residents and representatives...';
        setBusyState('panel-step2', true);
        if (btn) btn.classList.add('is-disabled');
        try {{
          const data = await runGenerateAgents({{ main: true, noBusy: true, ignoreDisabled: true, keepDisabled: true }});
          if (!data) throw new Error(runSetupState.last_generate_error || 'Generate residents and representatives failed.');
          if (status) status.textContent = 'Checking prompt fields...';
          const promptOk = await autoEnsurePromptFields();
          if (!promptOk) throw new Error(runSetupState.prompt_status_message || 'Prompt fields are not ready.');
          if (status) status.textContent = 'Saving CSVs...';
          await savePreparedCsvs();
          runSetupState.generated_ok = true;
          updateCsvPrepUi();
          renderValidationState(data);
          updateGenerateButton();
          setLaunchEnabledState();
          updateStepProgressState();
          if (status) status.textContent = 'Generated successfully.';
        }} catch (err) {{
          runSetupState.generated_ok = false;
          showInlineError('generate-error', err.message || 'Generate residents and representatives failed');
          if (status) status.textContent = '';
          updateCsvPrepUi();
          setLaunchEnabledState();
          updateStepProgressState();
        }} finally {{
          if (btn) btn.classList.remove('is-disabled');
          setBusyState('panel-step2', false);
        }}
      }}

      async function runSelectRepresentatives() {{
        showInlineError('generate-error', '');
        const btn = document.getElementById('select-reps-btn');
        if (btn && btn.classList.contains('is-disabled')) return;
        if (btn) btn.classList.add('is-disabled');
        setBusyState('panel-step2', true);
        const defaults = runSetupState.defaults || {{}};
        try {{
          const res = await fetch('/api/run/select_representatives', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              community_file: getCommunityPath(),
              shp_files: getBoundaryPath() ? [getBoundaryPath()] : null,
              representatives_per_community: integerFieldValue('representatives', defaults.representatives_per_community),
              hardship_quantile: numberFieldValue('hardship-quantile', defaults.hardship_quantile),
              generated_bundle_state: runSetupState.generated_bundle_state || {{}},
            }}),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (data.generated_bundle_state) runSetupState.generated_bundle_state = data.generated_bundle_state;
          runSetupState.generated_ok = !!data.validation_state?.bundle_ready;
          renderValidationState(data);
          if (data.status_message) document.getElementById('save-bundle-status').textContent = data.status_message;
          updateGenerateButton();
          setLaunchEnabledState();
          updateSaveButtonState();
          updateStepProgressState();
        }} catch (err) {{
          showInlineError('generate-error', err.message || 'Select representatives failed');
        }} finally {{
          setBusyState('panel-step2', false);
          updateGenerateButton();
        }}
      }}

      async function runLoadExistingBundle(options = {{}}) {{
        showInlineError('generate-error', '');
        const defaults = runSetupState.defaults || {{}};
        const status = document.getElementById('save-bundle-status');
        const btn = document.getElementById('load-existing-bundle-btn');
        if (btn && !options.auto) btn.classList.add('is-disabled');
        if (status && !options.auto) status.textContent = 'Loading CSVs...';
        setBusyState('panel-step2', true);
        try {{
          const residentsPath = document.getElementById('existing-residents-csv')?.value || '';
          const repsPath = document.getElementById('existing-representatives-csv')?.value || '';
          const res = await fetch('/api/run/load_existing_bundle', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              community_file: getCommunityPath(),
              shp_files: getBoundaryPath() ? [getBoundaryPath()] : null,
              residents_csv_path: residentsPath,
              representatives_csv_path: repsPath,
              representatives_per_community: integerFieldValue('representatives', defaults.representatives_per_community),
            }}),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (data.generated_bundle_state) runSetupState.generated_bundle_state = data.generated_bundle_state;
          runSetupState.preview_ok = true;
          runSetupState.generated_ok = !!data.validation_state?.bundle_ready;
          runSetupState.csvs_saved_dir = compactPathDisplay((runSetupState.generated_bundle_state || {{}}).staging_dir || '');
          renderValidationState(data);
          if (status) status.textContent = 'Checking prompt fields...';
          const promptOk = await autoEnsurePromptFields();
          if (!promptOk) throw new Error(runSetupState.prompt_status_message || 'Prompt fields are not ready.');
          if (status) status.textContent = 'Loaded successfully.';
          updateGenerateButton();
          setLaunchEnabledState();
          updateSaveButtonState();
          updateStepProgressState();
          updateCsvPrepUi();
          return data;
        }} catch (err) {{
          runSetupState.generated_ok = false;
          showInlineError('generate-error', err.message || 'Load CSVs failed');
          if (status && !options.auto) status.textContent = '';
          setPromptStatus(err.message || 'Prompt field check failed', 'error');
          updateCsvPrepUi();
          setLaunchEnabledState();
          updateStepProgressState();
          return null;
        }} finally {{
          setBusyState('panel-step2', false);
          if (btn) btn.classList.remove('is-disabled');
        }}
      }}

      async function runCheckPromptFields() {{
        const status = document.getElementById('prompt-fields-status');
        if (status) status.textContent = 'Checking...';
        try {{
          const res = await fetch('/api/run/check_prompt_fields', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ generated_bundle_state: runSetupState.generated_bundle_state || {{}} }}),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (status) status.textContent = data.status_message || 'Prompt fields checked.';
        }} catch (err) {{
          if (status) status.textContent = err.message || 'Prompt field check failed';
        }}
      }}

      async function runGeneratePromptFields() {{
        const status = document.getElementById('prompt-fields-status');
        const btn = document.getElementById('generate-prompt-fields-btn');
        if (btn) btn.disabled = true;
        if (status) status.textContent = 'Checking prompt fields...';
        try {{
          const checkRes = await fetch('/api/run/check_prompt_fields', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ generated_bundle_state: runSetupState.generated_bundle_state || {{}} }}),
          }});
          if (!checkRes.ok) throw new Error(await checkRes.text());
          const checkData = await checkRes.json();
          if (checkData.prompt_ready) {{
            if (status) status.textContent = checkData.status_message ? `${{checkData.status_message}}. No generation needed.` : 'role_prompt already exists. No generation needed.';
            return;
          }}
          const missingText = Number.isFinite(Number(checkData.prompt_missing_count))
            ? `Generating missing role_prompt for ${{Number(checkData.prompt_missing_count).toLocaleString()}} residents...`
            : 'Generating missing role_prompt...';
          if (status) status.textContent = checkData.status_message ? `${{checkData.status_message}}. ${{missingText}}` : missingText;

          const res = await fetch('/api/run/generate_prompt_fields', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ generated_bundle_state: runSetupState.generated_bundle_state || {{}} }}),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          if (data.generated_bundle_state) runSetupState.generated_bundle_state = data.generated_bundle_state;
          if (status) status.textContent = data.status_message || 'Prompt fields generated.';
        }} catch (err) {{
          if (status) status.textContent = err.message || 'Prompt field generation failed';
        }} finally {{
          if (btn) btn.disabled = false;
        }}
      }}

      function updateProgressPanel(job) {{
        const panel = document.getElementById('run-progress-panel');
        const label = document.getElementById('run-progress-label');
        const percent = document.getElementById('run-progress-percent');
        const fill = document.getElementById('run-progress-fill');
        const log = document.getElementById('run-progress-log');
        if (panel) panel.style.display = 'grid';
        const progress = Math.max(0, Math.min(1, Number(job?.progress || 0)));
        if (label) label.textContent = job?.message || job?.status || 'Running';
        if (percent) percent.textContent = `${{Math.round(progress * 100)}}%`;
        if (fill) fill.style.width = `${{Math.round(progress * 100)}}%`;
        if (log) {{
          log.textContent = job?.log || '';
          log.scrollTop = log.scrollHeight;
        }}
      }}

      function setRunActive(active) {{
        const launchBtn = document.getElementById('launch-btn');
        const cancelBtn = document.getElementById('cancel-run-btn');
        if (launchBtn) {{
          launchBtn.classList.toggle('is-disabled', active);
          launchBtn.setAttribute('aria-disabled', active);
        }}
        if (cancelBtn) {{
          cancelBtn.classList.toggle('is-disabled', !active);
          cancelBtn.setAttribute('aria-disabled', !active);
        }}
      }}

      async function pollRunJob(jobId) {{
        runSetupState.active_run_job_id = jobId;
        setRunActive(true);
        while (runSetupState.active_run_job_id === jobId) {{
          const res = await fetch(`/api/run/job/${{jobId}}`);
          if (!res.ok) throw new Error(await res.text());
          const job = await res.json();
          updateProgressPanel(job);
          if (job.status === 'completed') {{
            runSetupState.active_run_job_id = null;
            setRunActive(false);
            renderLaunch(job.result || {{}});
            return;
          }}
          if (job.status === 'cancelled') {{
            runSetupState.active_run_job_id = null;
            setRunActive(false);
            showInlineError('launch-error', 'Run cancelled.');
            return;
          }}
          if (job.status === 'failed') {{
            runSetupState.active_run_job_id = null;
            setRunActive(false);
            throw new Error(job.error || 'Run failed');
          }}
          await new Promise(resolve => setTimeout(resolve, 1000));
        }}
      }}

      async function cancelRun() {{
        const jobId = runSetupState.active_run_job_id;
        if (!jobId) return;
        const btn = document.getElementById('cancel-run-btn');
        if (btn) btn.classList.add('is-disabled');
        await fetch(`/api/run/job/${{jobId}}/cancel`, {{ method: 'POST' }});
      }}

      async function runLaunch() {{
        showInlineError('launch-error', '');
        const btnCheck = document.getElementById('launch-btn');
        if (btnCheck && btnCheck.classList.contains('is-disabled')) return;
        const communityPath = getCommunityPath();
        const boundaryPath = getBoundaryPath();
        if (!runSetupState.generated_ok || !communityPath) {{
          showInlineError('launch-error', 'Prepare resident and representative CSVs before launching a run.');
          return;
        }}
        const defaults = runSetupState.defaults || {{}};
        const btn = document.getElementById('launch-btn');
        if (btn) btn.classList.add('is-disabled');
        setBusyState('panel-step4', true);
        try {{
          const body = {{
            community_file: communityPath,
            shp_files: boundaryPath ? [boundaryPath] : null,
            generated_bundle_state: runSetupState.generated_bundle_state || {{}},
            target_community: getTargetCommunities(),
            model_name: document.getElementById('model-name').value || defaults.model_name,
            rounds_num: integerFieldValue('rounds', defaults.rounds ?? 8),
            agreement_mode: document.getElementById('agreement-mode').value || defaults.agreement_mode,
            agreement_fixed_ratio: numberFieldValue('fixed-ratio', defaults.agreement_fixed_ratio ?? 1.0),
            agreement_current_year: defaults.agreement_current_year || {_system_current_year()},
            max_extension_ratio: numberFieldValue('extension-cap', defaults.max_extension_ratio ?? 0.3),
            cash_subsidy_cap: numberFieldValue('subsidy-cap', defaults.cash_subsidy_cap ?? 0.1),
            developer_min_profit_rate: numberFieldValue('min-profit', defaults.developer_min_profit_rate ?? {DEFAULT_DEVELOPER_MIN_PROFIT_RATE}),
            planner_soft_policy_text: document.getElementById('planner-soft-policy-text').value || "",
            residents_per_household: numberFieldValue('residents-per-household', defaults.residents_per_household ?? {DEFAULT_RESIDENTS_PER_HOUSEHOLD}),
            vacancy_ratio: numberFieldValue('vacancy-ratio', defaults.vacancy_ratio ?? {DEFAULT_VACANCY_RATIO}),
            representatives_per_community: integerFieldValue('representatives', defaults.representatives_per_community ?? {DEFAULT_REPRESENTATIVES_PER_COMMUNITY}),
            hardship_quantile: numberFieldValue('hardship-quantile', defaults.hardship_quantile ?? {DEFAULT_HARDSHIP_QUANTILE}),
            output_dir: document.getElementById('output-dir').value || defaults.output_dir || "{_default_output_dir_ui()}",
            planner_utility_components: runSetupState.planner_components,
            developer_utility_components: runSetupState.developer_components,
            resident_utility_components: runSetupState.resident_components,
            selected_utility_categories: runSetupState.selected_utility_categories || defaults.selected_utility_categories || [...DEFAULT_SELECTED_UTILITY_CATEGORIES],
            configured_utility_fields: runSetupState.configured_utility_fields || defaults.configured_utility_fields || [],
            agreement_rules_table: runSetupState.agreement_rules_table || defaults.agreement_rules_table || [],
            api_key: document.getElementById('api-key').value || defaults.api_key || "",
            api_base_url: document.getElementById('api-base-url').value || defaults.api_base_url || "",
            repeat_count: integerFieldValue('repeat-count', defaults.repeat_count ?? 1),
          }};
          const progressPanel = document.getElementById('run-progress-panel');
          if (progressPanel) progressPanel.style.display = 'grid';
          updateProgressPanel({{ status: 'queued', progress: 0, message: 'Queued', log: '' }});
          const res = await fetch('/api/run/launch_job', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(body),
          }});
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          await pollRunJob(data.job_id);
        }} catch (err) {{
          showInlineError('launch-error', err.message || 'Launch failed');
        }} finally {{
          setBusyState('panel-step4', false);
          if (!runSetupState.active_run_job_id && btn) btn.classList.remove('is-disabled');
        }}
      }}

      function renderLaunch(payload) {{
        if (!payload) return;
        renderPreflight(payload.preflight_html || payload.preflight || '');
        const label = document.getElementById('run-progress-label');
        if (label) label.textContent = 'Run completed. Open Experiment Results Analysis or Policy Comparison from the page navigation.';
        setLaunchEnabledState();
      }}

      function resetRunSetupState() {{
        closeAdvancedModal();
        runSetupState.community_file_token = null;
        runSetupState.boundary_bundle_token = null;
        runSetupState.community_file_path = null;
        runSetupState.boundary_path = null;
        runSetupState.generated_bundle_state = {{}};
        runSetupState.preview_ok = false;
        runSetupState.generated_ok = false;
        runSetupState.planner_components = [];
        runSetupState.developer_components = [];
        runSetupState.resident_components = [];
        runSetupState.agreement_rules_table = [];
        runSetupState.planner_options = [];
        runSetupState.developer_options = [];
        runSetupState.resident_options = [];
        runSetupState.configured_utility_fields = [];
        runSetupState.community_csv_columns = [];
        runSetupState.active_utility_category_editor = null;
        runSetupState.active_utility_editor_key = null;
        runSetupState.show_custom_field_builder = false;
        runSetupState.selected_utility_categories = [...DEFAULT_SELECTED_UTILITY_CATEGORIES];
        runSetupState.auto_preview_triggered = false;
        runSetupState.active_run_job_id = null;
      }}

      async function runReset() {{
        setBusyState('panel-step4', true);
        try {{
          const res = await fetch('/api/run/reset');
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          renderReset(data);
        }} catch (err) {{
          showInlineError('launch-error', err.message || 'Reset failed');
        }} finally {{
          setBusyState('panel-step4', false);
        }}
      }}

      function renderReset(payload) {{
        resetRunSetupState();
        const defaults = payload.defaults || {{}};
        runSetupState.defaults = defaults;
        renderDefaults(defaults);
        if (!(defaults.community_file)) {{
          document.getElementById('community-status').textContent = 'No file selected.';
        }}
        if (!(defaults.boundary_path)) {{
          document.getElementById('boundary-status-text').textContent = 'No boundary uploaded.';
        }}
        showInlineError('community-error', '');
        showInlineError('boundary-error', '');
        showInlineError('generate-error', '');
        showInlineError('launch-error', '');
        if (payload.cleared_state) {{
          runSetupState.generated_bundle_state = payload.cleared_state.generated_bundle_state || {{}};
          runSetupState.planner_components = payload.cleared_state.planner_components || [];
          runSetupState.developer_components = payload.cleared_state.developer_components || [];
          runSetupState.resident_components = payload.cleared_state.resident_components || [];
          runSetupState.selected_utility_categories = payload.cleared_state.selected_utility_categories || defaults.selected_utility_categories || [...DEFAULT_SELECTED_UTILITY_CATEGORIES];
          runSetupState.planner_options = payload.cleared_state.planner_options || defaults.planner_utility_options || [];
          runSetupState.developer_options = payload.cleared_state.developer_options || defaults.developer_utility_options || [];
          runSetupState.resident_options = payload.cleared_state.resident_options || defaults.resident_utility_options || [];
          runSetupState.configured_utility_fields = payload.cleared_state.configured_utility_fields || defaults.configured_utility_fields || [];
          runSetupState.community_csv_columns = payload.cleared_state.community_csv_columns || defaults.community_csv_columns || [];
          runSetupState.agreement_rules_table = payload.cleared_state.agreement_rules_table || runSetupState.agreement_rules_table || [];
          renderPreflight(payload.cleared_state.preflight_html || defaults.preflight_html || '');
          renderAgreementTable();
          applyUtilityCategories(true);
        }}
        renderValidationState(payload.cleared_state || null);
        updateGenerateButton();
        setLaunchEnabledState();
        updateSaveButtonState();
        updateStepProgressState();
      }}

      let preflightTimer = null;
      function schedulePreflightRefresh() {{
        if (preflightTimer) clearTimeout(preflightTimer);
        preflightTimer = setTimeout(runPreflight, 300);
      }}

      function toggleFixedRatioVisibility() {{
        const mode = document.getElementById('agreement-mode').value;
        const field = document.getElementById('fixed-ratio-field');
        if (field) field.style.display = mode === 'fixed' ? 'block' : 'none';
      }}

      function updateSaveButtonState() {{
        const btn = document.getElementById('save-bundle-btn');
        const helper = document.getElementById('save-bundle-helper');
        const enable = runSetupState.generated_ok && !!(runSetupState.generated_bundle_state || {{}}).representative_csv_path;
        if (btn) {{
          btn.classList.toggle('is-disabled', !enable);
          btn.setAttribute('aria-disabled', !enable);
        }}
        if (helper) {{
          helper.textContent = enable
            ? 'Ready to save'
            : 'Available after generation';
        }}
      }}

      async function saveGeneratedBundle() {{
        const btn = document.getElementById('save-bundle-btn');
        const status = document.getElementById('save-bundle-status');
        if (!btn || btn.classList.contains('is-disabled')) return;
        if (status) status.textContent = 'Saving...';
        try {{
          const data = await savePreparedCsvs();
          if (status) status.textContent = `Saved: ${{shortPath(data.residents_csv)}} and ${{shortPath(data.representatives_csv)}}`;
          updateCsvPrepUi();
        }} catch (err) {{
          if (status) status.textContent = err.message || 'Save failed';
        }}
      }}

      async function runPreflight() {{
        const defaults = runSetupState.defaults || {{}};
        const body = {{
          target_community: getTargetCommunities(),
          model_name: document.getElementById('model-name').value || defaults.model_name,
          rounds_num: integerFieldValue('rounds', defaults.rounds ?? 8),
          agreement_mode: document.getElementById('agreement-mode').value || defaults.agreement_mode,
          agreement_fixed_ratio: numberFieldValue('fixed-ratio', defaults.agreement_fixed_ratio ?? 1.0),
          max_extension_ratio: numberFieldValue('extension-cap', defaults.max_extension_ratio ?? 0.3),
          cash_subsidy_cap: numberFieldValue('subsidy-cap', defaults.cash_subsidy_cap ?? 0.1),
          developer_min_profit_rate: numberFieldValue('min-profit', defaults.developer_min_profit_rate ?? {DEFAULT_DEVELOPER_MIN_PROFIT_RATE}),
          output_dir: document.getElementById('output-dir').value || defaults.output_dir || "{_default_output_dir_ui()}",
          generated_bundle_state: runSetupState.generated_bundle_state || {{}},
          configured_utility_fields: runSetupState.configured_utility_fields || defaults.configured_utility_fields || [],
        }};
        try {{
          const res = await fetch('/api/run/preflight', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(body),
          }});
          if (!res.ok) return;
          const data = await res.json();
          renderPreflight(data.preflight_html || '');
        }} catch (err) {{
          console.error('preflight failed', err);
        }}
      }}

      document.addEventListener('DOMContentLoaded', () => {{
        loadDefaults();
        const cf = document.getElementById('community-file');
        if (cf) {{
          cf.addEventListener('change', (e) => {{
            const file = e.target.files?.[0];
            setFilePickerCaption('community-file-picker-caption', file ? file.name : 'No upload selected');
            uploadCommunityFile(file);
          }});
        }}
        const communityPath = document.getElementById('community-path');
        if (communityPath) {{
          communityPath.addEventListener('input', () => {{
            setPathInputMeta('community-path');
            runSetupState.preview_ok = false;
            runSetupState.generated_ok = false;
            runSetupState.generated_bundle_state = {{}};
            setPromptStatus('Prompt fields will be checked after CSVs are prepared', 'neutral');
            setPathSummary('community-file-summary', communityPath.value, 'No file selected');
            setPathDisplay('community-status', communityPath.value, 'Using path: ');
            renderValidationState(null);
            updateGenerateButton();
            setLaunchEnabledState();
            updateStepProgressState();
          }});
          communityPath.addEventListener('change', runPreview);
        }}
        const bf = document.getElementById('boundary-files');
        if (bf) {{
          bf.addEventListener('change', (e) => {{
            const files = Array.from(e.target.files || []);
            setFilePickerCaption('boundary-file-picker-caption', files.length ? `${{files.length}} file${{files.length > 1 ? 's' : ''}} selected` : 'No upload selected');
            uploadBoundaryFiles(e.target.files);
          }});
        }}
        const boundaryPath = document.getElementById('boundary-path');
        if (boundaryPath) {{
          boundaryPath.addEventListener('input', () => {{
            setPathInputMeta('boundary-path');
            runSetupState.preview_ok = false;
            runSetupState.generated_ok = false;
            setPromptStatus('Prompt fields will be checked after CSVs are prepared', 'neutral');
            setPathSummary('boundary-file-summary', boundaryPath.value, 'No boundary file selected');
            setPathDisplay('boundary-status-text', boundaryPath.value, 'Using path: ');
            renderValidationState(null);
            updateGenerateButton();
            setLaunchEnabledState();
            updateStepProgressState();
          }});
          boundaryPath.addEventListener('change', runPreview);
        }}
        const detailsToggle = document.getElementById('validation-details-toggle');
        if (detailsToggle) detailsToggle.addEventListener('click', () => {{
          const panel = document.getElementById('validation-details-panel');
          const open = !(panel?.classList.contains('is-open'));
          if (panel) {{
            panel.classList.toggle('is-open', open);
            panel.setAttribute('aria-hidden', open ? 'false' : 'true');
          }}
          detailsToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
          detailsToggle.textContent = open ? 'Hide details' : 'View details';
        }});
        const modeGenerateBtn = document.getElementById('csv-mode-generate');
        if (modeGenerateBtn) modeGenerateBtn.addEventListener('click', () => setCsvMode('generate'));
        const modeLoadBtn = document.getElementById('csv-mode-load');
        if (modeLoadBtn) modeLoadBtn.addEventListener('click', () => setCsvMode('load'));
        const generateCsvsBtn = document.getElementById('generate-csvs-btn');
        if (generateCsvsBtn) generateCsvsBtn.addEventListener('click', runGenerateAndSaveCsvs);
        const genBtn = document.getElementById('generate-btn');
        if (genBtn) genBtn.addEventListener('click', runGenerateAgents);
        const selectRepsBtn = document.getElementById('select-reps-btn');
        if (selectRepsBtn) selectRepsBtn.addEventListener('click', runSelectRepresentatives);
        const loadExistingBtn = document.getElementById('load-existing-bundle-btn');
        if (loadExistingBtn) loadExistingBtn.addEventListener('click', () => runLoadExistingBundle());
        ['existing-residents-csv', 'existing-representatives-csv'].forEach(id => {{
          const el = document.getElementById(id);
          if (!el) return;
          el.addEventListener('input', () => {{
            setPathInputMeta(id);
            runSetupState.generated_ok = false;
            setPromptStatus('Will be checked automatically after loading', 'neutral');
            updateCsvPrepUi();
          }});
          el.addEventListener('change', () => {{
            const residentsPath = document.getElementById('existing-residents-csv')?.value.trim();
            const repsPath = document.getElementById('existing-representatives-csv')?.value.trim();
            if (runSetupState.csv_prep_mode === 'load' && residentsPath && repsPath) runLoadExistingBundle({{ auto: true }});
          }});
        }});
        const saveBtn = document.getElementById('save-bundle-btn');
        if (saveBtn) saveBtn.addEventListener('click', saveGeneratedBundle);
        const continueBtn = document.getElementById('csv-continue-btn');
        if (continueBtn) continueBtn.addEventListener('click', () => {{
          const step3 = document.getElementById('panel-step3');
          if (step3) step3.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }});
        const csvSecondaryBtn = document.getElementById('csv-secondary-action-btn');
        if (csvSecondaryBtn) csvSecondaryBtn.addEventListener('click', () => {{
          if (runSetupState.csv_prep_mode === 'load') runLoadExistingBundle();
          else runGenerateAndSaveCsvs();
        }});
        const step2AdvancedTrigger = document.getElementById('step2-advanced-trigger');
        if (step2AdvancedTrigger) {{
          step2AdvancedTrigger.addEventListener('click', () => {{
            setAdvancedModal(runSetupState.active_advanced_modal === 'step2' ? null : 'step2');
          }});
        }}
        const step3AdvancedTrigger = document.getElementById('step3-advanced-trigger');
        if (step3AdvancedTrigger) {{
          step3AdvancedTrigger.addEventListener('click', () => {{
            setAdvancedModal(runSetupState.active_advanced_modal === 'step3' ? null : 'step3');
          }});
        }}
        const advancedModal = document.getElementById('advanced-settings-modal');
        const advancedModalClose = document.getElementById('advanced-modal-close');
        if (advancedModalClose) advancedModalClose.addEventListener('click', closeAdvancedModal);
        if (advancedModal) {{
          advancedModal.addEventListener('click', (event) => {{
            if (event.target === advancedModal) closeAdvancedModal();
          }});
        }}
        document.querySelectorAll('[data-directory-target]').forEach((btn) => {{
          btn.addEventListener('click', () => openDirectoryBrowser(btn.dataset.directoryTarget));
        }});
        const directoryModal = document.getElementById('directory-modal');
        const directoryClose = document.getElementById('directory-modal-close');
        const directoryCancel = document.getElementById('directory-cancel-btn');
        const directorySelect = document.getElementById('directory-select-btn');
        const directoryProject = document.getElementById('directory-project-btn');
        const directoryHome = document.getElementById('directory-home-btn');
        const directoryParent = document.getElementById('directory-parent-btn');
        if (directoryClose) directoryClose.addEventListener('click', closeDirectoryModal);
        if (directoryCancel) directoryCancel.addEventListener('click', closeDirectoryModal);
        if (directorySelect) directorySelect.addEventListener('click', useCurrentDirectory);
        [directoryProject, directoryHome, directoryParent].forEach((btn) => {{
          if (!btn) return;
          btn.addEventListener('click', () => loadDirectoryBrowser(btn.dataset.path || ''));
        }});
        if (directoryModal) {{
          directoryModal.addEventListener('click', (event) => {{
            if (event.target === directoryModal) closeDirectoryModal();
          }});
        }}
        document.addEventListener('keydown', (event) => {{
          if (event.key !== 'Escape') return;
          if (document.getElementById('directory-modal')?.classList.contains('is-open')) {{
            closeDirectoryModal();
            return;
          }}
          if (runSetupState.active_advanced_modal) {{
            closeAdvancedModal();
          }}
        }});
        const closeCategoryBtn = document.getElementById('close-utility-category-editor-btn');
        if (closeCategoryBtn) {{
          closeCategoryBtn.addEventListener('click', () => {{
            runSetupState.active_utility_category_editor = null;
            runSetupState.active_utility_editor_key = null;
            renderUtilityCategories();
            renderOverrides();
          }});
        }}
        const addCustomBtn = document.getElementById('add-custom-field-btn');
        if (addCustomBtn) addCustomBtn.addEventListener('click', addCustomUtilityField);
        const toggleCustomBtn = document.getElementById('toggle-custom-field-builder-btn');
        if (toggleCustomBtn) toggleCustomBtn.addEventListener('click', () => toggleCustomFieldBuilder());
        const cancelCustomBtn = document.getElementById('cancel-custom-field-btn');
        if (cancelCustomBtn) cancelCustomBtn.addEventListener('click', () => toggleCustomFieldBuilder(false));
        ['model-name','rounds','agreement-mode','fixed-ratio','extension-cap','subsidy-cap','min-profit','output-dir','api-base-url','repeat-count'].forEach(id => {{
          const el = document.getElementById(id);
          if (el) el.addEventListener('input', schedulePreflightRefresh);
        }});
        const targetTrigger = document.getElementById('target-community-trigger');
        if (targetTrigger) targetTrigger.addEventListener('click', toggleTargetDropdown);
        const targetField = document.querySelector('.target-community-field');
        document.addEventListener('click', (event) => {{
          if (targetField && !targetField.contains(event.target)) setTargetDropdownOpen(false);
        }});
        document.addEventListener('keydown', (event) => {{
          if (event.key === 'Escape') setTargetDropdownOpen(false);
        }});
        const targetSearch = document.getElementById('target-community-search');
        if (targetSearch) targetSearch.addEventListener('input', (event) => {{
          targetCommunitySearchText = event.target.value || '';
          renderTargetPicker();
        }});
        const targetSelectAllBtn = document.getElementById('target-select-all-btn');
        if (targetSelectAllBtn) targetSelectAllBtn.addEventListener('click', () => {{
          const tc = document.getElementById('target-community');
          const values = Array.from(tc?.options || []).map(option => option.value).filter(value => value && value !== 'All Communities');
          setTargetSelectValues(values, true);
        }});
        const targetClearBtn = document.getElementById('target-clear-btn');
        if (targetClearBtn) targetClearBtn.addEventListener('click', () => setTargetSelectValues(['All Communities'], true));
        ['output-dir', 'save-bundle-dir'].forEach(id => {{
          const el = document.getElementById(id);
          if (el) el.addEventListener('input', () => {{
            setPathInputMeta(id);
            updateCsvPrepUi();
          }});
        }});
        ['residents-per-household', 'vacancy-ratio', 'representatives', 'hardship-quantile'].forEach(id => {{
          const el = document.getElementById(id);
          if (el) el.addEventListener('change', () => markCsvPrepDirty('Prompt fields will be checked after CSVs are prepared'));
        }});
        const am = document.getElementById('agreement-mode');
        if (am) am.addEventListener('change', () => {{ toggleFixedRatioVisibility(); schedulePreflightRefresh(); }});
        toggleFixedRatioVisibility();
        const launchBtn = document.getElementById('launch-btn');
        if (launchBtn) launchBtn.addEventListener('click', runLaunch);
        const cancelBtn = document.getElementById('cancel-run-btn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelRun);
        const resetBtn = document.getElementById('reset-btn');
        if (resetBtn) resetBtn.addEventListener('click', runReset);
      }});
    </script>
    """
    return _html_shell("Upload & Run", body, embedded=embedded)
