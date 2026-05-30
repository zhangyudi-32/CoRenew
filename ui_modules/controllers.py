
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def _phase2_detail_outputs(
    phase2_root: str,
    rule_id: str,
    community_name: str | None,
    seed: str | None = None,
):
    if not community_name:
        empty_df = pd.DataFrame()
        return (
            "### Community Detail\n\nSelect a community from the map or dropdown first.",
            gr.update(choices=[], value=None),
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )

    log_index = _index_phase2_logs(phase2_root, rule_id)
    candidates = log_index.get(community_name, [])
    if not candidates:
        empty_df = pd.DataFrame()
        return (
            f"### {community_name}\n\nNo raw negotiation log was found for this community under `{rule_id}`.",
            gr.update(choices=[], value=None),
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )

    seed_choices = [str(item["seed"]) for item in candidates]
    selected_seed = str(seed) if seed and str(seed) in seed_choices else seed_choices[0]
    selected_log = next(item for item in candidates if str(item["seed"]) == selected_seed)
    log_data = _load_json(selected_log["log_path"])
    seed_result_df = _load_phase2_seed_results(phase2_root, rule_id, selected_seed)
    seed_result_row = seed_result_df.loc[seed_result_df["community_name"] == community_name] if "community_name" in seed_result_df.columns else pd.DataFrame()
    seed_result_path = seed_result_row.iloc[0]["community_result_path"] if not seed_result_row.empty and "community_result_path" in seed_result_row.columns else selected_log.get("community_result_path")
    round_df = _build_round_dataframe(log_data)
    round_choices = round_df["轮次"].astype(int).astype(str).tolist() if not round_df.empty else []
    selected_round = round_choices[-1] if round_choices else None
    resident_df = _build_resident_round_dataframe(log_data, _safe_int(selected_round, 0))

    raw_rows = _load_phase2_community_results(phase2_root)
    if raw_rows.empty or "community_name" not in raw_rows.columns:
        community_rows = pd.DataFrame()
    else:
        annotated_rows = _annotate_phase2_policy_groups(raw_rows)
        filter_col = "policy_rule_id" if "policy_rule_id" in annotated_rows.columns else "rule_id"
        if filter_col in annotated_rows.columns:
            community_rows = annotated_rows[
                (annotated_rows[filter_col].astype(str) == str(rule_id))
                & (annotated_rows["community_name"].astype(str).str.strip() == community_name)
            ]
        else:
            community_rows = pd.DataFrame()
        if not community_rows.empty and "seed" in community_rows.columns:
            community_rows = community_rows.sort_values("seed")

    detail_md = _build_log_summary_markdown(
        log_data,
        extra_lines=[
            f"- rule_id: `{rule_id}`",
            f"- seed: `{selected_seed}`",
            f"- log_path: `{selected_log['log_path']}`",
            f"- community_result_path: `{seed_result_path}`" if seed_result_path else "- community_result_path: `N/A`",
            f"- sample count in this community: `{len(community_rows)}`",
        ],
    )

    return (
        detail_md,
        gr.update(choices=seed_choices, value=selected_seed),
        _build_round_plot(log_data),
        round_df,
        gr.update(choices=round_choices, value=selected_round),
        resident_df,
        log_data,
    )


def refresh_phase2_dashboard(
    phase2_root: str,
    phase2_shp_upload: Any,
    selected_rule: str | None,
    metric: str,
    selected_community: str | None,
    selected_seed: str | None,
):
    root_path = Path(_strip_str(phase2_root) or DEFAULT_PHASE2_ROOT)
    if not root_path.exists():
        placeholder = _placeholder_figure("Result directory not found", str(root_path))
        empty_df = pd.DataFrame()
        return (
            f"### Result directory not found\n\n`{root_path}`",
            placeholder,
            {},
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            empty_df,
            empty_df,
            "### Community Detail\n\nProvide a valid phase2 result directory first.",
            gr.update(choices=[], value=None),
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )

    global_df = _load_phase2_global_results(str(root_path))
    if global_df.empty or "rule_id" not in global_df.columns:
        placeholder = _placeholder_figure("Policy comparison data not found", str(root_path))
        empty_df = pd.DataFrame()
        return (
            f"### Policy comparison data not found\n\n`{root_path}`\n\nThis optional dataset is separate from `/run/setup` launch results.",
            placeholder,
            {},
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            empty_df,
            empty_df,
            "### Community Detail\n\nNo phase2 data loaded.",
            gr.update(choices=[], value=None),
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )
    rule_choices = _phase2_rule_choices(global_df)
    selected_rule = selected_rule if selected_rule in set(global_df["rule_id"].tolist()) else str(global_df.iloc[0]["rule_id"])
    seed_choices = list(_available_phase2_seeds(str(root_path), selected_rule))
    if selected_seed not in seed_choices:
        selected_seed = "43" if "43" in seed_choices else (seed_choices[0] if seed_choices else None)

    summary_df = _summarize_phase2_rule(str(root_path), selected_rule)
    display_df = (
        _load_phase2_seed_results(str(root_path), selected_rule, selected_seed)
        if selected_seed
        else pd.DataFrame()
    )
    community_choices = summary_df["community_name"].astype(str).tolist()
    selected_community = selected_community if selected_community in community_choices else (
        community_choices[0] if community_choices else None
    )

    boundary_path = _resolve_shape_path(phase2_shp_upload)
    map_title = f"Experiment Results Analysis | {selected_rule}" if selected_seed else f"Experiment Results Analysis | {selected_rule}"
    map_path, map_state = _render_metric_map(
        display_df if not display_df.empty else summary_df,
        boundary_path,
        metric,
        map_title,
        selected_community,
    )
    detail_outputs = list(_phase2_detail_outputs(str(root_path), selected_rule, selected_community, selected_seed))
    detail_outputs[1] = gr.update(choices=seed_choices, value=selected_seed)

    return (
        _phase2_overview_markdown(str(root_path), global_df, selected_rule, summary_df),
        map_path,
        map_state,
        gr.update(choices=rule_choices, value=selected_rule),
        gr.update(choices=community_choices, value=selected_community),
        _phase2_rule_table(global_df),
        _community_summary_table(summary_df),
        *detail_outputs,
    )


def select_phase2_from_map(
    phase2_root: str,
    phase2_shp_upload: Any,
    selected_rule: str | None,
    metric: str,
    selected_seed: str | None,
    map_state: dict[str, Any],
    evt: gr.SelectData,
):
    selected_community = _pick_community_from_click(evt, map_state)
    return refresh_phase2_dashboard(
        phase2_root,
        phase2_shp_upload,
        selected_rule,
        metric,
        selected_community,
        selected_seed,
    )


def update_phase2_round_table(log_json: dict[str, Any], round_number: str | None):
    return _build_resident_round_dataframe(log_json or {}, _safe_int(round_number, 0))


def refresh_phase2_main(
    phase2_root: str,
    phase2_shp_upload: Any,
    selected_rule: str | None,
    metric: str,
    selected_community: str | None,
    selected_seed: str | None,
):
    outputs = refresh_phase2_dashboard(
        phase2_root,
        phase2_shp_upload,
        selected_rule,
        metric,
        selected_community,
        selected_seed,
    )
    overview, _map_path, map_state, rule_update, community_update = outputs[:5]
    seed_update = outputs[8]
    boundary_path = map_state.get("boundary_path")
    selected_rule_value = rule_update.get("value") if isinstance(rule_update, dict) else selected_rule
    selected_community_value = community_update.get("value") if isinstance(community_update, dict) else selected_community
    selected_seed_value = seed_update.get("value") if isinstance(seed_update, dict) else selected_seed
    global_url = _make_phase2_global_url(
        _strip_str(phase2_root) or str(DEFAULT_PHASE2_ROOT),
        boundary_path,
        selected_rule_value,
        metric,
        selected_seed_value,
    )
    embedded_global_url = _make_phase2_global_url(
        _strip_str(phase2_root) or str(DEFAULT_PHASE2_ROOT),
        boundary_path,
        selected_rule_value,
        metric,
        selected_seed_value,
        embedded=True,
    )
    links_html = _links_html(
        global_url,
        _make_phase2_community_url(
            _strip_str(phase2_root) or str(DEFAULT_PHASE2_ROOT),
            boundary_path,
            selected_rule_value,
            selected_community_value,
            selected_seed_value,
        ),
        selected_community_value,
    )
    return (
        overview,
        links_html,
        _iframe_html(embedded_global_url, "Waiting for the experiment analysis page...", height=860, frameless=True),
        {**map_state, "global_url": global_url},
        rule_update,
        community_update,
        seed_update,
    )


def select_phase2_from_map_main(
    phase2_root: str,
    phase2_shp_upload: Any,
    selected_rule: str | None,
    metric: str,
    selected_seed: str | None,
    map_state: dict[str, Any],
    evt: gr.SelectData,
):
    selected_community = _pick_community_from_click(evt, map_state)
    return refresh_phase2_main(
        phase2_root,
        phase2_shp_upload,
        selected_rule,
        metric,
        selected_community,
        selected_seed,
    )


def preview_run_inputs(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    generated_bundle_state: dict[str, Any] | None = None,
):
    community_path = community_file or _default_community_csv()
    shape_path = _resolve_shape_path(shp_files)

    community_df = _read_table(community_path)
    community_missing = _validate_columns(community_df, COMMUNITY_AGENT_GENERATION_COLUMNS)
    population_missing = _validate_columns(community_df, COMMUNITY_POPULATION_COLUMNS)
    simulation_missing = _validate_columns(community_df, COMMUNITY_REQUIRED_COLUMNS)
    communities = _community_list_from_data(community_df, None)
    choice_values = ["All Communities"] + communities
    default_target = communities[0] if communities else "All Communities"
    missing_groups = []
    if population_missing:
        missing_groups.append(f"population synthesis fields missing: {', '.join(population_missing)}")
    if simulation_missing:
        missing_groups.append(f"simulation fields missing: {', '.join(simulation_missing)}")

    status_ok = not missing_groups
    households, estimated_residents, estimated_representatives = _estimate_generation_summary(
        community_df,
        residents_per_household,
        representatives_per_community,
    )
    generated_ready = bool(generated_bundle_state and generated_bundle_state.get("representative_csv_path"))
    generated_summary = (
        generated_bundle_state.get("summary_text")
        if generated_ready
        else f"Pending generation · est. ~{estimated_representatives:,} reps from ~{estimated_residents:,} residents"
    )

    default_count = 0
    file_rows = [
        ("Community File", community_file is not None, community_missing, _display_path(community_path), "file"),
        ("Generated agents + representatives", generated_ready, community_missing if not generated_ready else [], generated_summary, "generated"),
        ("Boundary shapefile", shp_files is not None, [], _display_path(shape_path), "file"),
    ]
    for label, uploaded, missing, display_path, row_type in file_rows:
        if missing:
            icon_class = "status-dot warn"
            badge = "Need fields"
            detail = ", ".join(missing)
            badge_tone = "warn"
        elif row_type == "generated":
            icon_class = "status-dot ok"
            badge = "Ready" if generated_ready else "Pending"
            detail = display_path
            badge_tone = "ok" if generated_ready else "neutral"
        else:
            icon_class = "status-dot ok" if uploaded or label == "Boundary shapefile" else "status-dot neutral"
            badge = "Uploaded" if uploaded else "Using default"
            detail = display_path
            badge_tone = "ok" if uploaded else "neutral"
            if not uploaded:
                default_count += 1

    blocking = bool(population_missing or simulation_missing)
    refresh_state = "Ready to run" if status_ok and generated_ready else ("Ready to generate" if status_ok else "Blocking issues")
    refresh_detail = f"{len(communities)} communities available · ~{estimated_representatives:,} representatives will be elected" if communities else "Please check input files"
    population_status = "Population fields ready" if not population_missing else f"Population fields missing: {', '.join(population_missing)}"
    simulation_status = "Simulation fields ready" if not simulation_missing else f"Simulation fields missing: {', '.join(simulation_missing)}"
    generation_status = "Generated bundle ready" if generated_ready else "Generated bundle pending"
    status_tone = "block" if blocking else ("warn" if not generated_ready else "ok")

    community_meta = f"""
    <div class="upload-meta-card upload-meta-inline {'warn' if community_missing else 'ok'}">
      <span class="upload-meta-badge {'warn' if community_missing else ('ok' if community_file is not None else 'neutral')}">{'Uploaded' if community_file is not None else 'Using default'}</span>
      <div class="upload-meta-path" title="{html.escape(_display_path(community_path))}">{html.escape(_display_path(community_path))}</div>
      <div class="upload-meta-note upload-meta-note-inline {'warn' if population_missing else 'ok'}">{html.escape(f"{len(COMMUNITY_POPULATION_COLUMNS) - len(population_missing)}/{len(COMMUNITY_POPULATION_COLUMNS)} fields ready" if not population_missing else 'Missing: ' + ', '.join(population_missing))}</div>
    </div>
    """
    generation_meta = f"""
    <div class="generation-estimate-row">
      <span class="upload-meta-badge {'ok' if generated_ready else 'neutral'}">{'Ready' if generated_ready else 'Pending'}</span>
      <span class="generation-estimate-copy" title="{html.escape(generated_summary)}">{html.escape(generated_summary if generated_ready else f'Est. ~{estimated_representatives:,} reps')}</span>
    </div>
    """
    shp_meta = f"""
    <div class="upload-meta-card upload-meta-inline {'ok' if shp_files is not None else 'neutral'}">
      <span class="upload-meta-badge {'ok' if shp_files is not None else 'neutral'}">{'Uploaded' if shp_files is not None else 'Using default'}</span>
      <div class="upload-meta-path" title="{html.escape(_display_path(shape_path))}">{html.escape(_display_path(shape_path))}</div>
    </div>
    """

    status_html = f"""
    <div class="summary-card summary-card-compact validation-console-card">
      <div class="validation-pill-row">
        <span class="validation-pill {status_tone}">{refresh_state}</span>
        <span class="validation-pill">{len(communities)} communities detected</span>
        <span class="validation-pill">~{estimated_residents:,} generated residents</span>
        <span class="validation-pill">{default_count} default sources</span>
      </div>
      <div class="validation-short-list">
        <div class="validation-short-row">
          <span class="validation-short-label">Population fields</span>
          <span class="validation-mini-badge {'ok' if not population_missing else 'block'}">{'Ready' if not population_missing else f'{len(COMMUNITY_POPULATION_COLUMNS) - len(population_missing)}/{len(COMMUNITY_POPULATION_COLUMNS)} ready'}</span>
        </div>
        <div class="validation-short-row">
          <span class="validation-short-label">Simulation fields</span>
          <span class="validation-mini-badge {'ok' if not simulation_missing else 'block'}">{'Ready' if not simulation_missing else f'{len(COMMUNITY_REQUIRED_COLUMNS) - len(simulation_missing)}/{len(COMMUNITY_REQUIRED_COLUMNS)} ready'}</span>
        </div>
        <div class="validation-short-row">
          <span class="validation-short-label">Boundary</span>
          <span class="validation-mini-badge {'ok' if shp_files is not None else 'neutral'}">{'Uploaded' if shp_files is not None else 'Default'}</span>
        </div>
        <div class="validation-short-row">
          <span class="validation-short-label">Bundle</span>
          <span class="validation-mini-badge {'ok' if generated_ready else 'warn'}">{'Ready' if generated_ready else 'Pending'}</span>
        </div>
      </div>
    </div>
    """

    return (
        status_html,
        gr.update(choices=choice_values, value=default_target),
        community_meta,
        generation_meta,
        shp_meta,
    )


def preview_run_main(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
):
    community_path = community_file or _default_community_csv()
    community_df = _read_table(community_path)
    value_flow_html, planner_value_update, developer_value_update, resident_value_update = _derive_value_flow_model(community_df)
    status_text, target_update, community_meta, generation_meta, shp_meta = preview_run_inputs(
        community_file,
        shp_files,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        {},
    )
    target_value = target_update.get("value") if isinstance(target_update, dict) else target_community
    _, _, agreement_rules_box_update = _agreement_visibility_updates(agreement_mode)
    return (
        status_text,
        target_update,
        "",
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        community_meta,
        generation_meta,
        shp_meta,
        _run_preflight_markup(
            target_value,
            model_name,
            rounds_num,
            agreement_mode,
            max_extension_ratio,
            cash_subsidy_cap,
            developer_min_profit_rate,
            output_dir,
            {},
        ),
        {},
        agreement_rules_box_update,
        value_flow_html,
        gr.update(value=planner_value_update),
        gr.update(value=developer_value_update),
        gr.update(value=resident_value_update),
    )


def reset_run_page():
    api_defaults = load_local_api_defaults()
    community_df = _read_table(_default_community_csv())
    value_flow_html, planner_value_update, developer_value_update, resident_value_update = _derive_value_flow_model(community_df)
    status_text, target_update, community_meta, generation_meta, shp_meta = preview_run_inputs(
        None,
        None,
        DEFAULT_RESIDENTS_PER_HOUSEHOLD,
        DEFAULT_VACANCY_RATIO,
        DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
        DEFAULT_HARDSHIP_QUANTILE,
        {},
    )
    target_value = target_update.get("value") if isinstance(target_update, dict) else None
    return (
        gr.update(value=None),
        gr.update(value=None),
        target_update,
        gr.update(value=api_defaults.get("model") or _default_model_name()),
        gr.update(value=8),
        gr.update(value="by_build_year"),
        gr.update(value=1.0, visible=False),
        gr.update(value=2026, visible=True),
        gr.update(value=DEFAULT_AGREEMENT_RULE_ROWS.copy()),
        gr.update(value=DEFAULT_RESIDENTS_PER_HOUSEHOLD),
        gr.update(value=DEFAULT_VACANCY_RATIO),
        gr.update(value=DEFAULT_REPRESENTATIVES_PER_COMMUNITY),
        gr.update(value=DEFAULT_HARDSHIP_QUANTILE),
        gr.update(value=0.3),
        gr.update(value=0.1),
        gr.update(value=DEFAULT_DEVELOPER_MIN_PROFIT_RATE),
        gr.update(value=[value for _, value in PLANNER_COST_BENEFIT_OPTIONS]),
        gr.update(value=[value for _, value in DEVELOPER_COST_BENEFIT_OPTIONS]),
        gr.update(value=[value for _, value in RESIDENT_COST_BENEFIT_OPTIONS]),
        gr.update(value=api_defaults.get("api_key") or ""),
        gr.update(value=api_defaults.get("base_url") or _default_llm_base_url()),
        gr.update(value=_default_output_dir_ui()),
        status_text,
        "",
        "### No run executed yet.",
        "",
        {},
        gr.update(choices=[], value=None),
        pd.DataFrame(),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        community_meta,
        generation_meta,
        shp_meta,
        _run_preflight_markup(
            target_value,
            _default_model_name(),
            8,
            "by_build_year",
            0.3,
            0.1,
            DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
            _default_output_dir_ui(),
            {},
            "",
        ),
        {},
        gr.update(visible=True),
        value_flow_html,
        gr.update(value=planner_value_update),
        gr.update(value=developer_value_update),
        gr.update(value=resident_value_update),
    )


def _run_summary_table(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()
    table = summary_df.copy()
    rename_map = {
        "community_name": "Community",
        "final_agree_ratio": "Final Agreement Rate",
        "avg_extension_ratio": "Final Extension Policy",
        "avg_subsidy_ratio": "Final Subsidy Policy",
        "outcome": "Outcome",
        "rounds": "Rounds",
        "log_path": "Log Path",
    }
    table = table.rename(columns=rename_map)
    for column in ["Final Agreement Rate", "Final Extension Policy", "Final Subsidy Policy"]:
        if column in table.columns:
            table[column] = table[column].map(_format_ratio)
    return table


def _run_summary_table_html(summary_df: Any) -> str:
    if not hasattr(summary_df, "to_html"):
        return ""
    if getattr(summary_df, "empty", True):
        return pd.DataFrame().to_html(index=False, escape=False)
    display_columns = {
        "Final Agreement Rate",
        "Final Extension Policy",
        "Final Subsidy Policy",
    }
    table = summary_df if display_columns.intersection(set(summary_df.columns)) else _run_summary_table(summary_df)
    return table.to_html(index=False, escape=False)


def _collect_latest_run_results(output_dir: str) -> pd.DataFrame:
    root = Path(_resolve_app_path(output_dir))
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return pd.DataFrame()

    for sim_dir in sorted(root.glob("sim_*")):
        logs = sorted(sim_dir.glob("negotiation_log_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            continue
        log_path = logs[0]
        log_data = _load_json(str(log_path.resolve()))
        final_metrics = log_data.get("final_metrics", {})
        final_policy = log_data.get("final_policy", {})
        planner = final_policy.get("planner", {})
        rows.append(
            {
                "community_name": _normalize_community_name(
                    _strip_str(log_data.get("community_info", {}).get("name")) or sim_dir.name.replace("sim_", "")
                ),
                "outcome": _strip_str(log_data.get("outcome")) or "unknown",
                "final_agree_ratio": _safe_float(final_metrics.get("final_agree_ratio"), np.nan),
                "avg_extension_ratio": _safe_float(planner.get("extension_ratio"), np.nan),
                "avg_subsidy_ratio": _safe_float(planner.get("cash_subsidy_ratio"), np.nan),
                "rounds": _safe_int(log_data.get("rounds"), 0),
                "log_path": str(log_path.resolve()),
            }
        )

    return pd.DataFrame(rows).sort_values("community_name").reset_index(drop=True) if rows else pd.DataFrame()


def _run_overview_markdown(
    output_dir: str,
    summary_df: pd.DataFrame,
    community_csv_path: str,
    representative_csv_path: str,
    all_agents_csv_path: str,
    shape_path: str | None,
) -> str:
    if summary_df.empty:
        return (
            "### Run completed, but no logs were found\n\n"
            f"- output_dir: `{_display_path(output_dir)}`\n"
            "- Check the uploaded data or execution logs."
        )

    return "\n".join(
        [
            "### Current Run Results",
            "",
            f"- output_dir: `{_display_path(output_dir)}`",
            f"- community data: `{_display_path(community_csv_path)}`",
            f"- elected representatives: `{_display_path(representative_csv_path)}`",
            f"- generated resident profiles: `{_display_path(all_agents_csv_path)}`",
            f"- boundary file: `{_display_path(shape_path)}`",
            f"- communities with generated logs: `{len(summary_df)}`",
            f"- average final agreement rate: `{_format_ratio(summary_df['final_agree_ratio'].mean() if 'final_agree_ratio' in summary_df.columns else np.nan)}`",
            f"- average final Extension Policy: `{_format_ratio(summary_df['avg_extension_ratio'].mean() if 'avg_extension_ratio' in summary_df.columns else np.nan)}`",
            f"- average final Subsidy Policy: `{_format_ratio(summary_df['avg_subsidy_ratio'].mean() if 'avg_subsidy_ratio' in summary_df.columns else np.nan)}`",
            f"- template config: `{_display_path(DEFAULT_TEMPLATE_CONFIG)}`",
        ]
    )


def _run_detail_outputs(summary_df: pd.DataFrame, selected_community: str | None):
    if summary_df.empty or not selected_community:
        empty_df = pd.DataFrame()
        return (
            "### Community Detail\n\nWaiting for run results.",
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )

    row = summary_df.loc[summary_df["community_name"] == selected_community]
    if row.empty:
        empty_df = pd.DataFrame()
        return (
            "### Community Detail\n\nCommunity not found.",
            _build_round_plot({}),
            empty_df,
            gr.update(choices=[], value=None),
            empty_df,
            {},
        )

    log_path = row.iloc[0]["log_path"]
    log_data = _load_json(str(log_path))
    round_df = _build_round_dataframe(log_data)
    round_choices = round_df["轮次"].astype(int).astype(str).tolist() if not round_df.empty else []
    selected_round = round_choices[-1] if round_choices else None
    resident_df = _build_resident_round_dataframe(log_data, _safe_int(selected_round, 0))

    detail_md = _build_log_summary_markdown(
        log_data,
        extra_lines=[f"- log_path: `{log_path}`"],
    )
    return (
        detail_md,
        _build_round_plot(log_data),
        round_df,
        gr.update(choices=round_choices, value=selected_round),
        resident_df,
        log_data,
    )

def _as_dict_from_update(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _value_from_update(obj: Any):
    d = _as_dict_from_update(obj)
    return d.get("value", obj)


def _choices_from_update(obj: Any):
    d = _as_dict_from_update(obj)
    return d.get("choices")


def _visible_from_update(obj: Any) -> bool:
    d = _as_dict_from_update(obj)
    return bool(d.get("visible", True))


def _normalize_target_communities(target_community: Any) -> list[str]:
    if target_community is None:
        return []
    if isinstance(target_community, str):
        raw_values = [target_community]
    elif isinstance(target_community, (list, tuple, set)):
        raw_values = list(target_community)
    else:
        raw_values = [str(target_community)]
    values = [_strip_str(value) for value in raw_values if _strip_str(value)]
    if not values or any(value == "All Communities" or value.lower() == "none" for value in values):
        return ["none"]
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _target_community_display(target_community: Any) -> str:
    values = _normalize_target_communities(target_community)
    if not values or values == ["none"]:
        return "All Communities"
    return ", ".join(values)


def _run_preview_payload(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    selected_utility_categories: Any = None,
    planner_utility_components: Any = None,
    developer_utility_components: Any = None,
    resident_utility_components: Any = None,
    configured_utility_fields: Any = None,
) -> dict[str, Any]:
    payload = {}
    community_df = _read_table(community_file or _default_community_csv())
    population_missing = _validate_columns(community_df, COMMUNITY_POPULATION_COLUMNS)
    simulation_missing = _validate_columns(community_df, COMMUNITY_REQUIRED_COLUMNS)
    communities = _community_list_from_data(community_df, None)
    _households, estimated_residents, estimated_representatives = _estimate_generation_summary(
        community_df,
        residents_per_household,
        representatives_per_community,
    )
    shape_path = _resolve_shape_path(shp_files)
    generated_ready = bool((generated_bundle_state or {}).get("representative_csv_path"))
    normalized_fields, community_columns = _validate_configured_utility_fields(
        configured_utility_fields,
        community_df,
        selected_utility_categories,
    )
    (
        status_text,
        target_update,
        links_html,
        overview_vis,
        log_vis,
        result_vis,
        community_meta,
        generation_meta,
        shp_meta,
        preflight_html,
        generated_state,
        agreement_rules_box_update,
        value_flow_html,
        planner_update,
        developer_update,
        resident_update,
    ) = preview_run_main(
        community_file,
        shp_files,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        output_dir,
        generated_bundle_state,
    )
    utility_state = _compute_value_flow_state(
        selected_categories=selected_utility_categories,
        configured_utility_fields=normalized_fields,
        community_columns=community_columns,
        planner_components=planner_utility_components,
        developer_components=developer_utility_components,
        resident_components=resident_utility_components,
    )
    payload["input_status_html"] = status_text
    payload["target_community"] = {"choices": _choices_from_update(target_update), "value": _value_from_update(target_update)}
    payload["links_html"] = links_html
    payload["overview_visible"] = _visible_from_update(overview_vis)
    payload["log_visible"] = _visible_from_update(log_vis)
    payload["result_visible"] = _visible_from_update(result_vis)
    payload["community_meta_html"] = community_meta
    payload["generation_meta_html"] = generation_meta
    payload["shp_meta_html"] = shp_meta
    payload["preflight_html"] = preflight_html
    payload["generated_bundle_state"] = generated_state
    payload["agreement_rules"] = {
        "fixed_visible": False,
        "current_year_value": None,
        "rules_box_visible": _visible_from_update(agreement_rules_box_update),
    }
    payload["value_flow_model_html"] = utility_state["value_flow_model_html"]
    payload["planner_components"] = utility_state["planner_components"]
    payload["developer_components"] = utility_state["developer_components"]
    payload["resident_components"] = utility_state["resident_components"]
    payload["planner_options"] = utility_state["planner_options"]
    payload["developer_options"] = utility_state["developer_options"]
    payload["resident_options"] = utility_state["resident_options"]
    payload["selected_utility_categories"] = utility_state["selected_utility_categories"]
    payload["configured_utility_fields"] = utility_state["configured_utility_fields"]
    payload["community_csv_columns"] = utility_state["community_csv_columns"]
    payload["agreement_rules_table"] = DEFAULT_AGREEMENT_RULE_ROWS.to_dict(orient="records")
    payload["validation_state"] = {
        "community_ready": bool(community_file or _default_community_csv()),
        "boundary_ready": bool(shape_path),
        "population_ready": not population_missing,
        "simulation_ready": not simulation_missing,
        "bundle_ready": generated_ready,
        "population_message": (
            "Population fields are ready."
            if not population_missing
            else f"Missing fields: {', '.join(population_missing)}"
        ),
        "simulation_message": (
            "Simulation fields are ready."
            if not simulation_missing
            else f"Missing fields: {', '.join(simulation_missing)}"
        ),
        "communities_detected": len(communities),
        "estimated_residents": int(estimated_residents),
        "estimated_representatives": int(estimated_representatives),
        "next_action": "generate" if not generated_ready else "generated",
    }
    return payload


def _run_generate_agents_payload(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    selected_utility_categories: Any = None,
    planner_utility_components: Any = None,
    developer_utility_components: Any = None,
    resident_utility_components: Any = None,
    configured_utility_fields: Any = None,
) -> dict[str, Any]:
    community_df = _read_table(community_file or _default_community_csv())
    population_missing = _validate_columns(community_df, COMMUNITY_POPULATION_COLUMNS)
    simulation_missing = _validate_columns(community_df, COMMUNITY_REQUIRED_COLUMNS)
    communities = _community_list_from_data(community_df, None)
    _households, estimated_residents, estimated_representatives = _estimate_generation_summary(
        community_df,
        residents_per_household,
        representatives_per_community,
    )
    shape_path = _resolve_shape_path(shp_files)
    normalized_fields, community_columns = _validate_configured_utility_fields(
        configured_utility_fields,
        community_df,
        selected_utility_categories,
    )
    (
        status_text,
        target_update,
        community_meta,
        generation_meta,
        shp_meta,
        preflight_html,
        generated_state,
        agreement_rules_box_update,
        value_flow_html,
        planner_update,
        developer_update,
        resident_update,
    ) = generate_run_agents_main(
        community_file,
        shp_files,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        output_dir,
    )
    utility_state = _compute_value_flow_state(
        selected_categories=selected_utility_categories,
        configured_utility_fields=normalized_fields,
        community_columns=community_columns,
        planner_components=planner_utility_components,
        developer_components=developer_utility_components,
        resident_components=resident_utility_components,
    )
    return {
        "input_status_html": status_text,
        "target_community": {"choices": _choices_from_update(target_update), "value": _value_from_update(target_update)},
        "community_meta_html": community_meta,
        "generation_meta_html": generation_meta,
        "shp_meta_html": shp_meta,
        "preflight_html": preflight_html,
        "generated_bundle_state": generated_state,
        "agreement_rules_box_visible": _visible_from_update(agreement_rules_box_update),
        "value_flow_model_html": utility_state["value_flow_model_html"],
        "planner_components": utility_state["planner_components"],
        "developer_components": utility_state["developer_components"],
        "resident_components": utility_state["resident_components"],
        "planner_options": utility_state["planner_options"],
        "developer_options": utility_state["developer_options"],
        "resident_options": utility_state["resident_options"],
        "selected_utility_categories": utility_state["selected_utility_categories"],
        "configured_utility_fields": utility_state["configured_utility_fields"],
        "community_csv_columns": utility_state["community_csv_columns"],
        "agreement_rules_table": DEFAULT_AGREEMENT_RULE_ROWS.to_dict(orient="records"),
        "validation_state": {
            "community_ready": bool(community_file or _default_community_csv()),
            "boundary_ready": bool(shape_path),
            "population_ready": not population_missing,
            "simulation_ready": not simulation_missing,
            "bundle_ready": True,
            "population_message": (
                "Population fields are ready."
                if not population_missing
                else f"Missing fields: {', '.join(population_missing)}"
            ),
            "simulation_message": (
                "Simulation fields are ready."
                if not simulation_missing
                else f"Missing fields: {', '.join(simulation_missing)}"
            ),
            "communities_detected": len(communities),
            "estimated_residents": int(estimated_residents),
            "estimated_representatives": int(estimated_representatives),
            "next_action": "generated",
        },
    }


def _bundle_validation_payload(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    representatives_per_community: int,
    generated_state: dict[str, Any],
) -> dict[str, Any]:
    community_df = _read_table(community_file or generated_state.get("community_csv_path") or _default_community_csv())
    population_missing = _validate_columns(community_df, COMMUNITY_POPULATION_COLUMNS)
    simulation_missing = _validate_columns(community_df, COMMUNITY_REQUIRED_COLUMNS)
    communities = _community_list_from_data(community_df, None)
    _households, estimated_residents, estimated_representatives = _estimate_generation_summary(
        community_df,
        residents_per_household,
        representatives_per_community,
    )
    shape_path = _resolve_shape_path(shp_files)
    return {
        "community_ready": bool(community_file or generated_state.get("community_csv_path") or _default_community_csv()),
        "boundary_ready": bool(shape_path),
        "population_ready": not population_missing,
        "simulation_ready": not simulation_missing,
        "residents_ready": bool(generated_state.get("all_agents_csv_path")),
        "representatives_ready": bool(generated_state.get("representative_csv_path")),
        "bundle_ready": bool(generated_state.get("all_agents_csv_path") and generated_state.get("representative_csv_path")),
        "population_message": (
            "Population fields are ready."
            if not population_missing
            else f"Missing fields: {', '.join(population_missing)}"
        ),
        "simulation_message": (
            "Simulation fields are ready."
            if not simulation_missing
            else f"Missing fields: {', '.join(simulation_missing)}"
        ),
        "communities_detected": len(communities),
        "estimated_residents": int(estimated_residents),
        "estimated_representatives": int(estimated_representatives),
        "next_action": "generated" if generated_state.get("representative_csv_path") else "select_representatives",
    }


def _run_generate_residents_payload(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
) -> dict[str, Any]:
    outputs = generate_run_agents_main(
        community_file,
        shp_files,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        output_dir,
    )
    (
        status_text,
        target_update,
        community_meta,
        generation_meta,
        shp_meta,
        preflight_html,
        generated_state,
        agreement_rules_box_update,
        value_flow_html,
        planner_update,
        developer_update,
        resident_update,
    ) = outputs
    all_agents_path = generated_state.get("all_agents_csv_path")
    representative_path = generated_state.get("representative_csv_path")
    all_agents_df = _read_table(all_agents_path, normalize_aliases=False) if all_agents_path else pd.DataFrame()
    representatives_df = _read_table(representative_path, normalize_aliases=False) if representative_path else pd.DataFrame()
    generated_state = {
        **generated_state,
        "residents_count": int(len(all_agents_df)),
        "representatives_count": int(len(representatives_df)),
        "summary_text": f"Generated {len(all_agents_df):,} residents and {len(representatives_df):,} representatives.",
    }
    return {
        "input_status_html": status_text,
        "target_community": {"choices": _choices_from_update(target_update), "value": _value_from_update(target_update)},
        "community_meta_html": community_meta,
        "generation_meta_html": generation_meta,
        "shp_meta_html": shp_meta,
        "preflight_html": preflight_html,
        "generated_bundle_state": generated_state,
        "agreement_rules_box_visible": _visible_from_update(agreement_rules_box_update),
        "value_flow_model_html": value_flow_html,
        "planner_components": _value_from_update(planner_update),
        "developer_components": _value_from_update(developer_update),
        "resident_components": _value_from_update(resident_update),
        "validation_state": _bundle_validation_payload(
            community_file,
            shp_files,
            residents_per_household,
            representatives_per_community,
            generated_state,
        ),
        "status_message": generated_state["summary_text"],
    }


def _run_select_representatives_payload(
    community_file: str | None,
    shp_files: Any,
    representatives_per_community: int,
    hardship_quantile: float,
    generated_bundle_state: dict[str, Any] | None,
) -> dict[str, Any]:
    state = dict(generated_bundle_state or {})
    all_agents_path = state.get("all_agents_csv_path")
    if not all_agents_path:
        raise ValueError("Generate residents or load an existing residents CSV first.")
    all_agents_df = _read_table(all_agents_path, normalize_aliases=False)
    missing = _validate_columns(all_agents_df, ALL_AGENT_REQUIRED_COLUMNS)
    if missing:
        raise ValueError(f"Residents CSV missing columns: {', '.join(missing)}")
    staging_dir = Path(state.get("staging_dir") or (TMP_UI_DIR / f"generated_bundle_{_timestamp()}_{os.getpid()}"))
    staging_dir.mkdir(parents=True, exist_ok=True)
    representative_csv_path = _select_representatives_from_all_agents(
        all_agents_df,
        staging_dir,
        representatives_per_community,
        hardship_quantile,
    )
    reps_df = _read_table(representative_csv_path, normalize_aliases=False)
    state["staging_dir"] = str(staging_dir)
    state["representative_csv_path"] = representative_csv_path
    state["residents_count"] = int(len(all_agents_df))
    state["representatives_count"] = int(len(reps_df))
    state["summary_text"] = f"{len(reps_df):,} representatives selected from {len(all_agents_df):,} residents"
    return {
        "generated_bundle_state": state,
        "validation_state": _bundle_validation_payload(
            community_file,
            shp_files,
            DEFAULT_RESIDENTS_PER_HOUSEHOLD,
            representatives_per_community,
            state,
        ),
        "status_message": state["summary_text"],
    }


def _run_load_existing_bundle_payload(
    community_file: str | None,
    shp_files: Any,
    residents_csv_path: str | None,
    representatives_csv_path: str | None,
    representatives_per_community: int,
) -> dict[str, Any]:
    if not _strip_str(residents_csv_path):
        raise ValueError("Residents CSV path is required.")
    if not _strip_str(representatives_csv_path):
        raise ValueError("Representatives CSV path is required.")
    all_agents_path = str(Path(_resolve_app_path(residents_csv_path)).resolve())
    if not Path(all_agents_path).exists():
        raise ValueError(f"Residents CSV not found: {all_agents_path}")
    all_agents_df = _read_table(all_agents_path, normalize_aliases=False)
    missing = _validate_columns(all_agents_df, ALL_AGENT_REQUIRED_COLUMNS)
    if missing:
        raise ValueError(f"Residents CSV missing columns: {', '.join(missing)}")

    representative_path = str(Path(_resolve_app_path(representatives_csv_path)).resolve())
    if not Path(representative_path).exists():
        raise ValueError(f"Representatives CSV not found: {representative_path}")
    reps_df = _read_table(representative_path, normalize_aliases=False)
    rep_missing = _validate_columns(reps_df, AGENT_REQUIRED_COLUMNS)
    if rep_missing:
        raise ValueError(f"Representatives CSV missing columns: {', '.join(rep_missing)}")

    state = {
        "staging_dir": str(Path(all_agents_path).parent),
        "community_csv_path": str(Path(_resolve_app_path(community_file or _default_community_csv())).resolve()),
        "all_agents_csv_path": all_agents_path,
        "representative_csv_path": representative_path,
        "residents_count": int(len(all_agents_df)),
        "representatives_count": int(len(reps_df)),
        "summary_text": f"Loaded {len(all_agents_df):,} residents and {len(reps_df):,} representatives",
    }
    return {
        "generated_bundle_state": state,
        "validation_state": _bundle_validation_payload(
            community_file,
            shp_files,
            DEFAULT_RESIDENTS_PER_HOUSEHOLD,
            representatives_per_community,
            state,
        ),
        "status_message": state["summary_text"],
    }

PROMPT_SOURCE_COLUMNS = {"age", "annual_income_rmb", "unit_size_sqm"}


def _missing_prompt_source_fields(all_agents_df: pd.DataFrame) -> list[str]:
    return sorted([col for col in PROMPT_SOURCE_COLUMNS if col not in all_agents_df.columns])


def _run_check_prompt_fields_payload(generated_bundle_state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(generated_bundle_state or {})
    all_agents_path = state.get("all_agents_csv_path")
    if not all_agents_path:
        raise ValueError("Generate residents or load an existing residents CSV first.")
    all_agents_df = _read_table(all_agents_path, normalize_aliases=False)
    has_column = "role_prompt" in all_agents_df.columns
    total = len(all_agents_df)
    filled = int(all_agents_df["role_prompt"].fillna("").astype(str).str.strip().ne("").sum()) if has_column else 0
    missing = max(total - filled, 0)
    source_missing = _missing_prompt_source_fields(all_agents_df) if missing else []
    can_generate = not source_missing and total > 0
    if has_column and missing == 0 and total > 0:
        status_message = "Prompt fields: Ready"
    elif source_missing:
        status_message = f"Prompt fields: Missing fields: {', '.join(source_missing)}"
    elif not has_column:
        status_message = f"Prompt fields: role_prompt is missing for {total:,} residents"
    else:
        status_message = f"Prompt fields: role_prompt missing for {missing:,} of {total:,} residents"
    return {
        "status_message": status_message,
        "prompt_ready": has_column and filled == total and total > 0,
        "has_prompt_column": has_column,
        "prompt_filled_count": filled,
        "prompt_missing_count": missing,
        "prompt_total_count": total,
        "missing_prompt_source_fields": source_missing,
        "can_generate_prompts": can_generate,
    }

def _run_generate_prompt_fields_payload(generated_bundle_state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(generated_bundle_state or {})
    all_agents_path = state.get("all_agents_csv_path")
    if not all_agents_path:
        raise ValueError("Generate residents or load an existing residents CSV first.")
    all_agents_df = _read_table(all_agents_path, normalize_aliases=False)
    total = len(all_agents_df)
    source_missing = _missing_prompt_source_fields(all_agents_df)
    if source_missing:
        return {
            "generated_bundle_state": state,
            "status_message": f"Prompt fields: Missing fields: {', '.join(source_missing)}",
            "prompt_ready": False,
            "generated_count": 0,
            "missing_prompt_source_fields": source_missing,
            "can_generate_prompts": False,
        }
    if total == 0:
        state["all_agents_csv_path"] = all_agents_path
        return {
            "generated_bundle_state": state,
            "status_message": "No residents found, so no role_prompt fields were generated.",
            "prompt_ready": False,
            "generated_count": 0,
        }

    if "role_prompt" not in all_agents_df.columns:
        all_agents_df["role_prompt"] = ""

    prompt_values = all_agents_df["role_prompt"].fillna("").astype(str).str.strip()
    missing_mask = prompt_values.eq("")
    missing_count = int(missing_mask.sum())
    existing_count = total - missing_count

    if missing_count == 0:
        state["all_agents_csv_path"] = all_agents_path
        return {
            "generated_bundle_state": state,
            "status_message": f"Prompt fields: Ready. role_prompt already exists for all {total:,} residents.",
            "prompt_ready": True,
            "generated_count": 0,
        }

    all_agents_df.loc[missing_mask, "role_prompt"] = all_agents_df.loc[missing_mask].apply(
        lambda row: _build_role_prompt(row.to_dict()), axis=1
    )
    all_agents_df.to_csv(all_agents_path, index=False, encoding="utf-8-sig")
    state["all_agents_csv_path"] = all_agents_path
    return {
        "generated_bundle_state": state,
        "status_message": (
            f"Prompt fields: Ready. Generated missing role_prompt for {missing_count:,} residents"
            + (f"; kept {existing_count:,} existing prompts." if existing_count else ".")
        ),
        "prompt_ready": True,
        "generated_count": missing_count,
    }


def _run_preflight_payload(
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    planner_soft_policy_text: str | None = None,
) -> dict[str, Any]:
    preflight_html = refresh_run_preflight_main(
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        output_dir,
        generated_bundle_state,
        planner_soft_policy_text,
    )
    return {"preflight_html": preflight_html}


def _run_launch_payload(
    community_file: str | None,
    shp_files: Any,
    target_community: str | None,
    model_name: str,
    rounds_num: int,
    agreement_mode: str,
    agreement_fixed_ratio: float,
    agreement_current_year: int,
    agreement_rules_table: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    max_extension_ratio: float,
    cash_subsidy_cap: float,
    developer_min_profit_rate: float,
    planner_utility_components: list[str] | None,
    developer_utility_components: list[str] | None,
    resident_utility_components: list[str] | None,
    api_key: str,
    api_base_url: str | None,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    selected_utility_categories: Any = None,
    configured_utility_fields: Any = None,
    planner_soft_policy_text: str | None = None,
    repeat_count: int = 1,
    job_id: str | None = None,
) -> dict[str, Any]:
    community_df = _read_table(community_file or _default_community_csv())
    normalized_fields, _community_columns = _validate_configured_utility_fields(
        configured_utility_fields,
        community_df,
        selected_utility_categories,
    )
    (
        overview,
        run_log,
        links_html,
        run_result_state,
        community_update,
        summary_table,
        overview_vis,
        log_vis,
        result_vis,
    ) = run_uploaded_simulation_main(
        community_file,
        shp_files,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        agreement_fixed_ratio,
        agreement_current_year,
        agreement_rules_table,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        planner_utility_components,
        developer_utility_components,
        resident_utility_components,
        api_key,
        api_base_url,
        output_dir,
        generated_bundle_state,
        normalized_fields,
        planner_soft_policy_text,
        repeat_count,
        job_id,
    )
    selected_community = _value_from_update(community_update)
    return {
        "overview_html": overview,
        "run_log": run_log,
        "links_html": links_html,
        "run_result_state": run_result_state,
        "community_selector": {"choices": _choices_from_update(community_update), "value": selected_community},
        "summary_table_html": _run_summary_table_html(summary_table),
        "overview_visible": _visible_from_update(overview_vis),
        "log_visible": _visible_from_update(log_vis),
        "result_visible": _visible_from_update(result_vis),
        "run_id": run_result_state.get("run_id"),
        "global_url": run_result_state.get("global_url"),
        "community_url": _make_run_community_url(run_result_state.get("run_id"), selected_community),
        "selected_utility_categories": _normalize_selected_utility_categories(selected_utility_categories),
        "configured_utility_fields": _json_ready(normalized_fields),
        "preflight_html": _run_preflight_payload(
            target_community,
            model_name,
            rounds_num,
            agreement_mode,
            max_extension_ratio,
            cash_subsidy_cap,
            developer_min_profit_rate,
            output_dir,
            generated_bundle_state,
            planner_soft_policy_text,
        )["preflight_html"],
    }


def _run_launch_payload_from_data(data: dict[str, Any], job_id: str | None = None) -> dict[str, Any]:
    return _run_launch_payload(
        data.get("community_file") or _default_community_csv(),
        data.get("shp_files") or ([data.get("boundary_path")] if data.get("boundary_path") else ([_display_path(DEFAULT_BOUNDARY_SHP)] if DEFAULT_BOUNDARY_SHP.exists() else None)),
        data.get("target_community"),
        data.get("model_name") or _default_model_name(),
        int(data.get("rounds_num", data.get("rounds", 8))),
        data.get("agreement_mode", "by_build_year"),
        float(data.get("agreement_fixed_ratio", 1.0)),
        int(data.get("agreement_current_year", _system_current_year())),
        data.get("agreement_rules_table"),
        float(data.get("residents_per_household", DEFAULT_RESIDENTS_PER_HOUSEHOLD)),
        float(data.get("vacancy_ratio", DEFAULT_VACANCY_RATIO)),
        int(data.get("representatives_per_community", DEFAULT_REPRESENTATIVES_PER_COMMUNITY)),
        float(data.get("hardship_quantile", DEFAULT_HARDSHIP_QUANTILE)),
        float(data.get("max_extension_ratio", 0.3)),
        float(data.get("cash_subsidy_cap", 0.1)),
        float(data.get("developer_min_profit_rate", DEFAULT_DEVELOPER_MIN_PROFIT_RATE)),
        data.get("planner_utility_components"),
        data.get("developer_utility_components"),
        data.get("resident_utility_components"),
        data.get("api_key") or "",
        data.get("api_base_url") or data.get("llm_base_url") or "",
        data.get("output_dir") or _default_output_dir_ui(),
        data.get("generated_bundle_state"),
        data.get("selected_utility_categories"),
        data.get("configured_utility_fields"),
        data.get("planner_soft_policy_text") or "",
        int(data.get("repeat_count", data.get("experiment_repeats", 1)) or 1),
        job_id,
    )


def _run_launch_job_worker(job_id: str, data: dict[str, Any]):
    try:
        result = _run_launch_payload_from_data(data, job_id=job_id)
        _update_run_job(
            job_id,
            status="completed",
            progress=1.0,
            message="Completed",
            result=_json_ready(result),
            process=None,
        )
    except Exception as exc:
        current = _public_run_job(job_id)
        status = "cancelled" if current.get("cancel_requested") else "failed"
        safe_error = _redact_sensitive_text(str(exc), [data.get("api_key", "")])
        _update_run_job(
            job_id,
            status=status,
            message="Cancelled" if status == "cancelled" else "Failed",
            error=safe_error,
            process=None,
        )
        _append_run_job_log(job_id, f"\n{safe_error}\n")


def _run_reset_payload() -> dict[str, Any]:
    reset_outputs = reset_run_page()
    (
        community_file_update,
        shp_update,
        target_update,
        model_update,
        rounds_update,
        agreement_mode_update,
        fixed_ratio_update,
        current_year_update,
        agreement_rules_table_update,
        residents_per_household_update,
        vacancy_ratio_update,
        representatives_update,
        hardship_update,
        max_extension_update,
        subsidy_cap_update,
        developer_profit_update,
        planner_components_update,
        developer_components_update,
        resident_components_update,
        api_key_update,
        api_base_url_update,
        output_dir_update,
        status_text,
        links_html,
        overview_md,
        log_text,
        run_result_state,
        community_selector_update,
        summary_table_df,
        overview_vis,
        log_vis,
        result_vis,
        community_meta,
        generation_meta,
        shp_meta,
        preflight_html,
        generated_state,
        agreement_rules_box_update,
        value_flow_html,
        planner_value_update,
        developer_value_update,
        resident_value_update,
    ) = reset_outputs
    utility_state = _compute_value_flow_state(
        configured_utility_fields=_default_configured_utility_fields(),
        community_columns=_community_csv_columns_for_path(_default_community_csv()),
    )
    return {
        "defaults": {
          "community_file": _value_from_update(community_file_update),
          "boundary_files": _value_from_update(shp_update),
          "target_community": {"choices": _choices_from_update(target_update), "value": _value_from_update(target_update)},
          "model_name": _value_from_update(model_update),
          "rounds": _value_from_update(rounds_update),
          "agreement_mode": _value_from_update(agreement_mode_update),
          "agreement_fixed_ratio": _value_from_update(fixed_ratio_update),
          "agreement_current_year": _value_from_update(current_year_update),
          "agreement_rules_table": _json_ready(_value_from_update(agreement_rules_table_update)),
          "residents_per_household": _value_from_update(residents_per_household_update),
          "vacancy_ratio": _value_from_update(vacancy_ratio_update),
          "representatives_per_community": _value_from_update(representatives_update),
          "hardship_quantile": _value_from_update(hardship_update),
          "max_extension_ratio": _value_from_update(max_extension_update),
          "cash_subsidy_cap": _value_from_update(subsidy_cap_update),
          "developer_min_profit_rate": _value_from_update(developer_profit_update),
          "planner_components": utility_state["planner_components"],
          "developer_components": utility_state["developer_components"],
          "resident_components": utility_state["resident_components"],
          "planner_utility_options": utility_state["planner_options"],
          "developer_utility_options": utility_state["developer_options"],
          "resident_utility_options": utility_state["resident_options"],
          "selected_utility_categories": utility_state["selected_utility_categories"],
          "configured_utility_fields": utility_state["configured_utility_fields"],
          "community_csv_columns": utility_state["community_csv_columns"],
          "api_key": _value_from_update(api_key_update),
          "api_base_url": _value_from_update(api_base_url_update),
          "output_dir": _value_from_update(output_dir_update),
          "agents_output_dir": _default_agents_output_dir_ui(),
        },
        "cleared_state": {
          "input_status_html": status_text,
          "links_html": links_html,
          "overview_markdown": overview_md,
          "run_log": log_text,
          "run_result_state": run_result_state,
          "community_selector": {"choices": _choices_from_update(community_selector_update), "value": _value_from_update(community_selector_update)},
          "summary_table_html": _run_summary_table_html(summary_table_df),
          "overview_visible": _visible_from_update(overview_vis),
          "log_visible": _visible_from_update(log_vis),
          "result_visible": _visible_from_update(result_vis),
          "community_meta_html": community_meta,
          "generation_meta_html": generation_meta,
          "shp_meta_html": shp_meta,
          "preflight_html": preflight_html,
          "generated_bundle_state": _json_ready(generated_state),
          "agreement_rules_box_visible": _visible_from_update(agreement_rules_box_update),
          "value_flow_model_html": utility_state["value_flow_model_html"],
          "planner_components": utility_state["planner_components"],
          "developer_components": utility_state["developer_components"],
          "resident_components": utility_state["resident_components"],
          "planner_options": utility_state["planner_options"],
          "developer_options": utility_state["developer_options"],
          "resident_options": utility_state["resident_options"],
          "selected_utility_categories": utility_state["selected_utility_categories"],
          "configured_utility_fields": utility_state["configured_utility_fields"],
          "community_csv_columns": utility_state["community_csv_columns"],
        },
    }
    return (
        detail_md,
        _build_round_plot(log_data),
        round_df,
        gr.update(choices=round_choices, value=selected_round),
        resident_df,
        log_data,
    )


def _prepare_run_datasets(
    community_file: str | None,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    generated_bundle_state: dict[str, Any] | None = None,
):
    if generated_bundle_state and generated_bundle_state.get("representative_csv_path") and generated_bundle_state.get("all_agents_csv_path"):
        staging_dir = Path(generated_bundle_state["staging_dir"])
        community_csv_path = str(generated_bundle_state["community_csv_path"])
        agent_csv_path = str(generated_bundle_state["representative_csv_path"])
        all_agents_csv_path = str(generated_bundle_state["all_agents_csv_path"])
    else:
        raise gr.Error("Please click 'Generate Residents' before running the simulation.")

    agent_df = _read_table(agent_csv_path, normalize_aliases=False)
    all_agents_df = _read_table(all_agents_csv_path, normalize_aliases=False)
    agent_missing = _validate_columns(agent_df, AGENT_REQUIRED_COLUMNS)
    all_agents_missing = _validate_columns(all_agents_df, ALL_AGENT_REQUIRED_COLUMNS)
    if agent_missing or all_agents_missing:
        generated_errors = []
        if agent_missing:
            generated_errors.append(f"generated representatives missing columns: {', '.join(agent_missing)}")
        if all_agents_missing:
            generated_errors.append(f"generated resident profiles missing columns: {', '.join(all_agents_missing)}")
        raise gr.Error("Generated data validation failed:\n\n" + "\n".join(generated_errors))

    return staging_dir, community_csv_path, agent_csv_path, all_agents_csv_path


def _save_generated_bundle_to_dir(generated_bundle_state: dict[str, Any], target_dir: str) -> dict[str, str]:
    if not generated_bundle_state:
        raise ValueError("No generated bundle to save.")
    rep_path = generated_bundle_state.get("representative_csv_path")
    all_path = generated_bundle_state.get("all_agents_csv_path")
    if not rep_path or not all_path:
        raise ValueError("Generated bundle missing CSV paths.")
    dest_dir = Path(_resolve_app_path(target_dir))
    dest_dir.mkdir(parents=True, exist_ok=True)
    rep_dest = dest_dir / Path(rep_path).name
    all_dest = dest_dir / Path(all_path).name
    shutil.copy(rep_path, rep_dest)
    shutil.copy(all_path, all_dest)
    return {"representatives_csv": str(rep_dest), "residents_csv": str(all_dest)}


def generate_run_agents_main(
    community_file: str | None,
    shp_files: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
):
    community_src = community_file or _default_community_csv()
    staging_dir = TMP_UI_DIR / f"generated_bundle_{_timestamp()}_{os.getpid()}"
    community_csv_path = _copy_or_convert_table(community_src, staging_dir, "community")
    community_df = _read_table(community_csv_path)
    value_flow_html, planner_value_update, developer_value_update, resident_value_update = _derive_value_flow_model(community_df)
    community_missing = _validate_columns(community_df, COMMUNITY_AGENT_GENERATION_COLUMNS)
    if community_missing:
        raise gr.Error("Community file is missing required generation fields:\n\n" + "\n".join(community_missing))

    representative_csv_path, all_agents_csv_path = _generate_agent_bundle(
        community_df,
        staging_dir,
        residents_per_household=float(residents_per_household),
        vacancy_ratio=float(vacancy_ratio),
        representatives_per_community=int(representatives_per_community),
        hardship_quantile=float(hardship_quantile),
    )
    reps_df = _read_table(representative_csv_path, normalize_aliases=False)
    all_agents_df = _read_table(all_agents_csv_path, normalize_aliases=False)
    communities = _community_list_from_data(community_df=community_df)
    generated_state = {
        "staging_dir": str(staging_dir),
        "community_csv_path": community_csv_path,
        "representative_csv_path": representative_csv_path,
        "all_agents_csv_path": all_agents_csv_path,
        "summary_text": f"{len(reps_df):,} representatives from {len(all_agents_df):,} generated residents across {len(communities)} communities",
    }
    status_text, target_update, community_meta, generation_meta, shp_meta = preview_run_inputs(
        community_file,
        shp_files,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        generated_state,
    )
    target_value = target_update.get("value") if isinstance(target_update, dict) else target_community
    _, _, agreement_rules_box_update = _agreement_visibility_updates(agreement_mode)
    return (
        status_text,
        target_update,
        community_meta,
        generation_meta,
        shp_meta,
        _run_preflight_markup(
            target_value,
            model_name,
            rounds_num,
            agreement_mode,
            max_extension_ratio,
            cash_subsidy_cap,
            developer_min_profit_rate,
            output_dir,
            generated_state,
        ),
        generated_state,
        agreement_rules_box_update,
        value_flow_html,
        gr.update(value=planner_value_update),
        gr.update(value=developer_value_update),
        gr.update(value=resident_value_update),
    )


def refresh_run_preflight_main(
    target_community: str | None,
    model_name: str | None,
    rounds_num: Any,
    agreement_mode: str | None,
    max_extension_ratio: Any,
    cash_subsidy_cap: Any,
    developer_min_profit_rate: Any,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    planner_soft_policy_text: str | None = None,
):
    return _run_preflight_markup(
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        output_dir,
        generated_bundle_state,
        planner_soft_policy_text,
    )


def build_launch_config_from_ui_payload(
    community_file: str | None,
    shp_files: Any,
    target_community: str | None,
    model_name: str,
    rounds_num: int,
    agreement_mode: str,
    agreement_fixed_ratio: float,
    agreement_current_year: int,
    agreement_rules_table: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    max_extension_ratio: float,
    cash_subsidy_cap: float,
    developer_min_profit_rate: float,
    planner_utility_components: list[str] | None,
    developer_utility_components: list[str] | None,
    resident_utility_components: list[str] | None,
    api_key: str,
    api_base_url: str | None,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    configured_utility_fields: list[dict[str, Any]] | None = None,
    planner_soft_policy_text: str | None = None,
    repeat_count: int = 1,
    job_id: str | None = None,
) -> dict[str, Any]:
    if not _strip_str(api_key):
        raise gr.Error("The current template uses LLM-based resident agents. An API key is required.")

    staging_dir, community_csv_path, agent_csv_path, all_agents_csv_path = _prepare_run_datasets(
        community_file,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        generated_bundle_state,
    )
    shape_path = _resolve_shape_path(shp_files)

    cfg = _load_template_config()
    run_output_dir = _resolve_app_path(output_dir or _default_output_dir_ui())

    cfg["community_csv"] = community_csv_path
    cfg["resident_csv"] = agent_csv_path
    cfg["all_agents_path"] = all_agents_csv_path
    cfg["official_csv"] = str(DEFAULT_OFFICIAL_CSV.resolve())
    cfg["llm_name"] = _strip_str(model_name) or _default_model_name()
    cfg["llm_base_url"] = _strip_str(api_base_url)
    cfg["llm_parallel_residents"] = True
    cfg["resident_llm_concurrency"] = int(cfg.get("resident_llm_concurrency", 8) or 8)
    cfg["serialize_llm_calls"] = False
    cfg["llm_generate_role_prompt"] = False
    cfg["rounds_num"] = int(rounds_num)
    cfg["max_extension_ratio"] = float(max_extension_ratio)
    cfg["cash_subsidy_cap"] = float(cash_subsidy_cap)
    planner_rule = cfg.get("planner_rule", {}) if isinstance(cfg.get("planner_rule", {}), dict) else {}
    planner_rule["policy"] = "baseline"
    cfg["planner_rule"] = planner_rule
    developer_rule = cfg.get("developer_rule", {}) if isinstance(cfg.get("developer_rule", {}), dict) else {}
    developer_rule["policy"] = "baseline"
    developer_rule["min_profit_rate"] = float(developer_min_profit_rate)
    cfg["developer_rule"] = developer_rule
    agreement_rule = cfg.get("agreement_rule", {}) if isinstance(cfg.get("agreement_rule", {}), dict) else {}
    agreement_rule["mode"] = _strip_str(agreement_mode) or "by_build_year"
    agreement_rule["fixed_ratio"] = float(agreement_fixed_ratio)
    by_build_year = agreement_rule.get("by_build_year", {}) if isinstance(agreement_rule.get("by_build_year", {}), dict) else {}
    by_build_year["current_year"] = int(_safe_int(agreement_current_year, 2026))
    by_build_year["rules"] = _normalize_agreement_rule_rows(agreement_rules_table)
    agreement_rule["by_build_year"] = by_build_year
    cfg["agreement_rule"] = agreement_rule
    cfg["cost_benefit_modules"] = {
        "planner": list(planner_utility_components or []),
        "developer": list(developer_utility_components or []),
        "resident": list(resident_utility_components or []),
    }
    if configured_utility_fields is not None:
        cfg["configured_utility_fields"] = _json_ready(configured_utility_fields)
    cfg["planner_soft_policy_text"] = _strip_str(planner_soft_policy_text)
    cfg["repeat_count"] = max(1, int(_safe_int(repeat_count, 1)))
    target_communities = _normalize_target_communities(target_community)
    cfg["target_community"] = target_communities[0] if target_communities else "none"
    cfg["output_dir"] = run_output_dir
    cfg["base_log_dir"] = str((Path(run_output_dir) / "logs").resolve())
    cfg["run_timestamp"] = f"ui_run_{_timestamp()}"
    cfg["resume_from_checkpoint"] = False
    cfg["api_key"] = ""
    cfg["api_key_source"] = "[runtime only]"
    cfg["api_key_masked"] = mask_api_key(api_key) if api_key else ""

    config_path = staging_dir / "ui_run.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    cmd = [
        _runtime_python(),
        "-u",
        str(ROOT / "main.py"),
        "--config",
        str(config_path),
        "--target_community",
        str(cfg["target_community"]),
        "--run_timestamp",
        str(cfg["run_timestamp"]),
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["LLM_API_KEY"] = _strip_str(api_key)
    env["OPENAI_API_KEY"] = _strip_str(api_key)
    if _strip_str(api_base_url):
        env["LLM_BASE_URL"] = _strip_str(api_base_url)
        env["OPENAI_BASE_URL"] = _strip_str(api_base_url)

    return {
        "cmd": cmd,
        "env": env,
        "config_path": str(config_path),
        "sanitized_config": cfg,
        "run_output_dir": run_output_dir,
        "shape_path": shape_path,
        "community_csv_path": community_csv_path,
        "agent_csv_path": agent_csv_path,
        "all_agents_csv_path": all_agents_csv_path,
        "target_community": target_community,
        "target_communities": target_communities,
        "api_key": _strip_str(api_key),
        "api_base_url": _strip_str(api_base_url),
        "repeat_count": max(1, int(_safe_int(repeat_count, 1))),
        "job_id": job_id,
    }


def _write_launch_artifacts(launch_config: dict[str, Any], run_log: str, summary_df: pd.DataFrame) -> None:
    output_dir = Path(launch_config["run_output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    config_copy = output_dir / "ui_run.yaml"
    with open(config_copy, "w", encoding="utf-8") as f:
        yaml.safe_dump(launch_config["sanitized_config"], f, allow_unicode=True, sort_keys=False)
    (output_dir / "run_log.txt").write_text(
        _redact_sensitive_text(run_log, [launch_config.get("api_key", "")]),
        encoding="utf-8",
    )
    summary_records = _json_ready(summary_df.to_dict(orient="records")) if not summary_df.empty else []
    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump({"results": summary_records}, f, ensure_ascii=False, indent=2)
    if not summary_df.empty:
        summary_df.to_csv(output_dir / "summary.csv", index=False, encoding="utf-8-sig")


def _clear_result_data_caches() -> None:
    for name in [
        "_load_phase2_global_results",
        "_load_phase2_community_results",
        "_load_phase2_seed_results",
        "_index_phase2_logs",
        "_available_phase2_seeds",
        "_load_phase2_policy_community_pairs",
        "_summarize_phase2_rule",
        "_load_json",
    ]:
        fn = globals().get(name)
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()


def launch_run_from_config(config: dict[str, Any]) -> dict[str, Any]:
    cmd = config["cmd"]
    env = config["env"]
    job_id = config.get("job_id")
    api_key = config.get("api_key", "")
    repeat_count = max(1, int(_safe_int(config.get("repeat_count"), 1)))
    run_log = "Simulation launched from the local web app.\n"
    run_logs: list[str] = []

    target_communities = config.get("target_communities") or [_normalize_target_communities(config.get("target_community"))[0]]
    target_communities = [target for target in target_communities if _strip_str(target)] or ["none"]

    def _repeat_cmd(index: int, target: str) -> list[str]:
        run_cmd = list(cmd)
        if "--target_community" in run_cmd:
            run_cmd[run_cmd.index("--target_community") + 1] = target
        if repeat_count <= 1 and len(target_communities) <= 1:
            return run_cmd
        repeat_timestamp = f"ui_run_{_timestamp()}_r{index + 1:03d}_{_sanitize_filename(target)}"
        if "--run_timestamp" in run_cmd:
            run_cmd[run_cmd.index("--run_timestamp") + 1] = repeat_timestamp
        return run_cmd

    if job_id:
        total_runs = repeat_count * len(target_communities)
        _update_run_job(job_id, status="running", progress=0.02, message=f"Starting simulation 1/{total_runs}")
        _append_run_job_log(job_id, run_log)
        run_idx = 0
        for repeat_idx in range(repeat_count):
            for target in target_communities:
                run_idx += 1
                _update_run_job(
                    job_id,
                    status="running",
                    progress=max(0.02, (run_idx - 1) / max(total_runs, 1)),
                    message=f"Running simulation {run_idx}/{total_runs}: {_target_community_display(target)}",
                )
                _append_run_job_log(job_id, f"\n--- Simulation {run_idx}/{total_runs}: {_target_community_display(target)} ---\n")
                process = subprocess.Popen(
                    _repeat_cmd(repeat_idx, target),
                    cwd=str(ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                )
                _update_run_job(job_id, process=process)
                stdout_parts: list[str] = []
                assert process.stdout is not None
                for line in process.stdout:
                    stdout_parts.append(line)
                    _append_run_job_log(job_id, line)
                    _parse_progress_line(job_id, line)
                    if _public_run_job(job_id).get("cancel_requested"):
                        try:
                            process.terminate()
                        except Exception:
                            pass
                        break
                return_code = process.wait()
                stdout_text = "".join(stdout_parts).strip()
                run_logs.append(f"--- Simulation {run_idx}/{total_runs}: {_target_community_display(target)} ---\n{stdout_text}".strip())
                if _public_run_job(job_id).get("cancel_requested"):
                    _update_run_job(job_id, status="cancelled", progress=0.0, message="Cancelled")
                    raise gr.Error("Simulation run cancelled.")
                if return_code != 0:
                    combined_log = "\n\n".join([run_log.strip(), *run_logs]).strip()
                    raise gr.Error(f"Simulation run failed.\n\n{_redact_sensitive_text(combined_log, [api_key])}")
        run_log = "\n\n".join([run_log.strip(), *run_logs]).strip()
    else:
        total_runs = repeat_count * len(target_communities)
        run_idx = 0
        for repeat_idx in range(repeat_count):
            for target in target_communities:
                run_idx += 1
                completed = subprocess.run(
                    _repeat_cmd(repeat_idx, target),
                    cwd=str(ROOT),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )

                log_sections = [f"Simulation {run_idx}/{total_runs}: {_target_community_display(target)}"]
                if completed.stdout.strip():
                    log_sections.extend(["", "STDOUT:", completed.stdout.strip()])
                if completed.stderr.strip():
                    log_sections.extend(["", "STDERR:", completed.stderr.strip()])
                run_logs.append("\n".join(log_sections).strip())
                run_log = _redact_sensitive_text("\n\n".join(["Simulation launched from the local web app.", *run_logs]).strip(), [api_key])

                if completed.returncode != 0:
                    raise gr.Error(f"Simulation run failed.\n\n{run_log}")

    summary_df = _collect_latest_run_results(config["run_output_dir"])
    _write_launch_artifacts(config, run_log, summary_df)
    _clear_result_data_caches()
    return {
        "run_log": run_log,
        "summary_df": summary_df,
        "output_dir": config["run_output_dir"],
    }


def run_uploaded_simulation(
    community_file: str | None,
    shp_files: Any,
    target_community: str | None,
    model_name: str,
    rounds_num: int,
    agreement_mode: str,
    agreement_fixed_ratio: float,
    agreement_current_year: int,
    agreement_rules_table: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    max_extension_ratio: float,
    cash_subsidy_cap: float,
    developer_min_profit_rate: float,
    planner_utility_components: list[str] | None,
    developer_utility_components: list[str] | None,
    resident_utility_components: list[str] | None,
    api_key: str,
    api_base_url: str | None,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    configured_utility_fields: list[dict[str, Any]] | None = None,
    planner_soft_policy_text: str | None = None,
    repeat_count: int = 1,
    job_id: str | None = None,
):
    launch_config = build_launch_config_from_ui_payload(
        community_file,
        shp_files,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        agreement_fixed_ratio,
        agreement_current_year,
        agreement_rules_table,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        planner_utility_components,
        developer_utility_components,
        resident_utility_components,
        api_key,
        api_base_url,
        output_dir,
        generated_bundle_state,
        configured_utility_fields,
        planner_soft_policy_text,
        repeat_count,
        job_id,
    )
    launch_result = launch_run_from_config(launch_config)
    run_output_dir = launch_result["output_dir"]
    shape_path = launch_config["shape_path"]
    community_csv_path = launch_config["community_csv_path"]
    agent_csv_path = launch_config["agent_csv_path"]
    all_agents_csv_path = launch_config["all_agents_csv_path"]
    run_log = launch_result["run_log"]
    summary_df = launch_result["summary_df"]
    community_choices = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    target_values = _normalize_target_communities(target_community)
    preferred_target = target_values[0] if target_values and target_values != ["none"] else None
    selected_community = (
        community_choices[0]
        if not community_choices
        else (
            preferred_target if preferred_target in community_choices else community_choices[0]
        )
    )

    map_path, map_state = _render_metric_map(
        summary_df,
        shape_path,
        "final_agree_ratio",
        "Run Result Map",
        selected_community,
    )

    run_id = _save_run_metadata(
        {
            "output_dir": run_output_dir,
            "boundary_path": shape_path,
            "community_csv_path": community_csv_path,
            "agent_csv_path": agent_csv_path,
            "selected_community": selected_community,
        }
    )

    return (
        _run_overview_markdown(run_output_dir, summary_df, community_csv_path, agent_csv_path, all_agents_csv_path, shape_path),
        run_log,
        map_path,
        {
            **map_state,
            "output_dir": run_output_dir,
            "run_id": run_id,
        },
        gr.update(choices=community_choices, value=selected_community),
        _run_summary_table(summary_df),
        *_run_detail_outputs(summary_df, selected_community),
    )


def select_run_from_map(run_map_state: dict[str, Any], evt: gr.SelectData):
    selected_community = _pick_community_from_click(evt, run_map_state)
    summary_df = pd.DataFrame(run_map_state.get("summary_records") or [])
    if summary_df.empty and run_map_state.get("output_dir"):
        summary_df = _collect_latest_run_results(run_map_state["output_dir"])

    map_path, map_state = _render_metric_map(
        summary_df,
        run_map_state.get("boundary_path"),
        run_map_state.get("metric", "final_agree_ratio"),
        "Run Result Map",
        selected_community,
    )

    return (
        map_path,
        {
            **map_state,
            "output_dir": run_map_state.get("output_dir"),
        },
        gr.update(
            choices=summary_df["community_name"].astype(str).tolist() if not summary_df.empty else [],
            value=selected_community,
        ),
        *_run_detail_outputs(summary_df, selected_community),
    )


def refresh_run_detail(run_map_state: dict[str, Any], selected_community: str | None):
    summary_df = pd.DataFrame(run_map_state.get("summary_records") or [])
    if summary_df.empty and run_map_state.get("output_dir"):
        summary_df = _collect_latest_run_results(run_map_state["output_dir"])

    map_path, map_state = _render_metric_map(
        summary_df,
        run_map_state.get("boundary_path"),
        run_map_state.get("metric", "final_agree_ratio"),
        "Run Result Map",
        selected_community,
    )

    return (
        map_path,
        {
            **map_state,
            "output_dir": run_map_state.get("output_dir"),
        },
        *_run_detail_outputs(summary_df, selected_community),
    )


def update_run_round_table(run_log_json: dict[str, Any], round_number: str | None):
    return _build_resident_round_dataframe(run_log_json or {}, _safe_int(round_number, 0))


def run_uploaded_simulation_main(
    community_file: str | None,
    shp_files: Any,
    target_community: str | None,
    model_name: str,
    rounds_num: int,
    agreement_mode: str,
    agreement_fixed_ratio: float,
    agreement_current_year: int,
    agreement_rules_table: Any,
    residents_per_household: float,
    vacancy_ratio: float,
    representatives_per_community: int,
    hardship_quantile: float,
    max_extension_ratio: float,
    cash_subsidy_cap: float,
    developer_min_profit_rate: float,
    planner_utility_components: list[str] | None,
    developer_utility_components: list[str] | None,
    resident_utility_components: list[str] | None,
    api_key: str,
    api_base_url: str | None,
    output_dir: str | None,
    generated_bundle_state: dict[str, Any] | None,
    configured_utility_fields: list[dict[str, Any]] | None = None,
    planner_soft_policy_text: str | None = None,
    repeat_count: int = 1,
    job_id: str | None = None,
):
    outputs = run_uploaded_simulation(
        community_file,
        shp_files,
        target_community,
        model_name,
        rounds_num,
        agreement_mode,
        agreement_fixed_ratio,
        agreement_current_year,
        agreement_rules_table,
        residents_per_household,
        vacancy_ratio,
        representatives_per_community,
        hardship_quantile,
        max_extension_ratio,
        cash_subsidy_cap,
        developer_min_profit_rate,
        planner_utility_components,
        developer_utility_components,
        resident_utility_components,
        api_key,
        api_base_url,
        output_dir,
        generated_bundle_state,
        configured_utility_fields,
        planner_soft_policy_text,
        repeat_count,
        job_id,
    )
    overview, run_log, _map_path, map_state, community_update, summary_table = outputs[:6]
    run_id = map_state.get("run_id")
    selected_community = community_update.get("value") if isinstance(community_update, dict) else None
    global_url = _make_run_global_url(run_id) if run_id else None
    links_html = _links_html(
        global_url,
        _make_run_community_url(run_id, selected_community) if run_id else None,
        selected_community,
    )
    return (
        overview,
        run_log,
        links_html,
        {**map_state, "global_url": global_url},
        community_update,
        summary_table,
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=True),
    )


def select_run_from_map_main(run_map_state: dict[str, Any], evt: gr.SelectData):
    outputs = select_run_from_map(run_map_state, evt)
    map_path, map_state, community_update = outputs[:3]
    selected_community = community_update.get("value") if isinstance(community_update, dict) else None
    links_html = _links_html(
        _make_run_global_url(map_state.get("run_id")) if map_state.get("run_id") else None,
        _make_run_community_url(map_state.get("run_id"), selected_community) if map_state.get("run_id") else None,
        selected_community,
    )
    return map_path, map_state, community_update, links_html


def refresh_run_links(run_map_state: dict[str, Any], selected_community: str | None):
    global_url = run_map_state.get("global_url") or (
        _make_run_global_url(run_map_state.get("run_id")) if run_map_state.get("run_id") else None
    )
    links_html = _links_html(
        global_url,
        _make_run_community_url(run_map_state.get("run_id"), selected_community) if run_map_state.get("run_id") else None,
        selected_community,
    )
    return links_html
