
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

DEFAULT_GITHUB_PAGES_EXPORT_DIR = ROOT / "docs"

def _static_seed_key(seed: str | None) -> str:
    value = _strip_str(seed)
    return f"seed-{value}" if value else "seed-default"


def _static_slug(value: Any, prefix: str = "item") -> str:
    text = _strip_str(value)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10] if text else "empty"
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if ascii_slug:
        return f"{prefix}-{ascii_slug[:32]}-{digest}"
    return f"{prefix}-{digest}"


def _phase2_global_static_relpath(rule_id: str, metric: str, seed: str | None) -> PurePosixPath:
    return PurePosixPath("phase2") / "global" / f"{rule_id}__{_static_seed_key(seed)}__{metric}.html"


def _phase2_community_static_relpath(
    rule_id: str,
    community_name: str | None,
    seed: str | None,
) -> PurePosixPath:
    return (
        PurePosixPath("phase2")
        / "community"
        / f"{rule_id}__{_static_seed_key(seed)}__{_static_slug(community_name, prefix='community')}.html"
    )


def _phase2_compare_static_relpath() -> PurePosixPath:
    return PurePosixPath("phase2") / "compare" / "index.html"


def _site_index_static_relpath() -> PurePosixPath:
    return PurePosixPath("index.html")


def _static_href(from_relpath: PurePosixPath, to_relpath: PurePosixPath) -> str:
    from_dir = str(from_relpath.parent)
    if from_dir in {"", "."}:
        from_dir = "."
    return posixpath.relpath(str(to_relpath), from_dir)


def _write_static_page(target_root: Path, relpath: PurePosixPath, content: str) -> Path:
    target_path = target_root.joinpath(*relpath.parts)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return target_path


def _replace_many(text: str, replacements: dict[str, str]) -> str:
    updated = text
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if old:
            updated = updated.replace(old, new)
    return updated


def _preferred_phase2_seed(phase2_root: str, rule_id: str) -> str | None:
    seed_choices = list(_available_phase2_seeds(phase2_root, rule_id))
    if "43" in seed_choices:
        return "43"
    return seed_choices[0] if seed_choices else None


def _sanitize_static_export_html(
    html_text: str,
    phase2_root: str,
    boundary_path: str | None,
) -> str:
    sanitized = html_text
    if phase2_root:
        sanitized = sanitized.replace(phase2_root, "Bundled phase2 dataset")
        try:
            sanitized = sanitized.replace(str(Path(phase2_root).resolve()), "Bundled phase2 dataset")
        except Exception:
            pass
    if boundary_path:
        sanitized = sanitized.replace(boundary_path, "")
        try:
            sanitized = sanitized.replace(str(Path(boundary_path).resolve()), "")
        except Exception:
            pass
    return sanitized


def _build_phase2_global_static_page(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    metric: str,
    seed: str | None,
    current_relpath: PurePosixPath,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    selected_rule = rule_id if rule_id in set(global_df["rule_id"].astype(str).tolist()) else str(global_df.iloc[0]["rule_id"])
    selected_seed = seed if seed in set(_available_phase2_seeds(phase2_root, selected_rule)) else _preferred_phase2_seed(phase2_root, selected_rule)
    page_html = _build_phase2_global_page(
        phase2_root=phase2_root,
        boundary_path=boundary_path,
        rule_id=selected_rule,
        metric=metric,
        seed=selected_seed,
        embedded=False,
    )
    summary_df = _summarize_phase2_rule(phase2_root, selected_rule)
    communities = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    replacements: dict[str, str] = {}
    dynamic_metric_switch = _metric_switch_html(
        "/phase2/global",
        {
            "phase2_root": phase2_root,
            "boundary_path": boundary_path or "",
            "rule_id": selected_rule,
            "seed": selected_seed or "",
        },
        metric,
    )
    static_metric_switch = '<div class="seg-group">' + "".join(
        f'<a class="seg-button{" active" if metric_key == metric else ""}" '
        f'href="{_static_href(current_relpath, _phase2_global_static_relpath(selected_rule, metric_key, selected_seed))}">'
        f"{html.escape(metric_label)}</a>"
        for metric_key, metric_label in MAP_METRICS.items()
    ) + "</div>"
    replacements[dynamic_metric_switch] = static_metric_switch

    for metric_key in MAP_METRICS:
        dynamic_url = _make_phase2_global_url(
            phase2_root=phase2_root,
            boundary_path=boundary_path,
            rule_id=selected_rule,
            metric=metric_key,
            seed=selected_seed,
            embedded=False,
        )
        replacements[dynamic_url] = _static_href(
            current_relpath,
            _phase2_global_static_relpath(selected_rule, metric_key, selected_seed),
        )

    compare_dynamic_url = "/phase2/compare?" + urlencode(
        {
            "phase2_root": phase2_root,
            "mode": "aggregate_policy",
            "rule_ids": [selected_rule],
        },
        doseq=True,
    )
    replacements[compare_dynamic_url] = _static_href(current_relpath, _phase2_compare_static_relpath())
    replacements['href="/app"'] = f'href="{_static_href(current_relpath, _site_index_static_relpath())}"'

    export_dynamic = _make_phase2_global_export_url(
        phase2_root=phase2_root,
        boundary_path=boundary_path,
        rule_id=selected_rule,
        metric=metric,
        seed=selected_seed,
    )
    replacements[
        f'<a class="button secondary" href="{export_dynamic}">Save Map Image</a>'
    ] = '<span class="button secondary disabled" aria-disabled="true">PNG Export Unavailable</span>'
    replacements['action="/phase2/global"'] = 'action="#"'
    replacements['openLink.setAttribute("href", "/phase2/community?" + params.toString());'] = 'openLink.setAttribute("href", "#");'

    for community_name in communities:
        dynamic_url = _make_phase2_community_url(
            phase2_root=phase2_root,
            boundary_path=boundary_path,
            rule_id=selected_rule,
            community_name=community_name,
            seed=selected_seed,
        )
        if dynamic_url:
            replacements[dynamic_url] = _static_href(
                current_relpath,
                _phase2_community_static_relpath(selected_rule, community_name, selected_seed),
            )

    page_html = _replace_many(page_html, replacements)
    page_html = _sanitize_static_export_html(page_html, phase2_root, boundary_path)

    rule_target_map = {
        str(rule_value): _static_href(
            current_relpath,
            _phase2_global_static_relpath(
                str(rule_value),
                metric,
                _preferred_phase2_seed(phase2_root, str(rule_value)),
            ),
        )
        for rule_value in global_df["rule_id"].astype(str).tolist()
    }
    community_target_map = {
        community_name: _static_href(
            current_relpath,
            _phase2_community_static_relpath(selected_rule, community_name, selected_seed),
        )
        for community_name in communities
    }
    current_target = _static_href(
        current_relpath,
        _phase2_global_static_relpath(selected_rule, metric, selected_seed),
    )
    script = f"""
    <script>
      (function() {{
        const ruleMap = {json.dumps(rule_target_map, ensure_ascii=False)};
        const communityMap = {json.dumps(community_target_map, ensure_ascii=False)};
        const form = document.querySelector(".analysis-sidebar-form");
        const ruleSelect = form ? form.querySelector('select[name="rule_id"]') : null;
        const sourceInput = form ? form.querySelector('input[name="phase2_root"]') : null;
        const openLink = document.getElementById("phase2-open-community");
        const communitySelect = document.getElementById("phase2-community-picker");

        if (sourceInput) {{
          sourceInput.value = "Bundled phase2 dataset";
          sourceInput.readOnly = true;
          sourceInput.title = "Bundled phase2 dataset";
        }}

        function updateCommunityLink() {{
          if (!openLink || !communitySelect) return;
          const target = communityMap[communitySelect.value || ""] || "#";
          openLink.setAttribute("href", target);
          openLink.classList.toggle("disabled", target === "#");
        }}

        form?.addEventListener("submit", (event) => {{
          event.preventDefault();
          const target = ruleMap[ruleSelect?.value || ""] || {json.dumps(current_target, ensure_ascii=False)};
          if (target) window.location.href = target;
        }});

        communitySelect?.addEventListener("change", updateCommunityLink);
        updateCommunityLink();
      }})();
    </script>
    """
    return page_html.replace("</body>", f"{script}\n</body>")


def _build_phase2_community_static_page(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    community_name: str | None,
    seed: str | None,
    current_relpath: PurePosixPath,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    selected_rule = rule_id if rule_id in set(global_df["rule_id"].astype(str).tolist()) else str(global_df.iloc[0]["rule_id"])
    summary_df = _summarize_phase2_rule(phase2_root, selected_rule)
    communities = summary_df["community_name"].astype(str).tolist() if not summary_df.empty else []
    selected_community = community_name if community_name in communities else (communities[0] if communities else None)
    log_index = _index_phase2_logs(phase2_root, selected_rule)
    seed_choices = [item["seed"] for item in log_index.get(selected_community or "", [])]
    selected_seed = seed if seed in seed_choices else (seed_choices[0] if seed_choices else _preferred_phase2_seed(phase2_root, selected_rule))
    page_html = _build_phase2_community_page(
        phase2_root=phase2_root,
        boundary_path=boundary_path,
        rule_id=selected_rule,
        community_name=selected_community,
        seed=selected_seed,
        round_number=None,
    )
    back_dynamic = "/phase2/global?" + urlencode(
        {
            "phase2_root": phase2_root,
            "boundary_path": boundary_path or "",
            "rule_id": selected_rule,
            "metric": "final_agree_ratio",
            "seed": selected_seed or "",
        }
    )
    replacements: dict[str, str] = {
        back_dynamic: _static_href(
            current_relpath,
            _phase2_global_static_relpath(selected_rule, "final_agree_ratio", selected_seed),
        ),
        'action="/phase2/community"': 'action="#"',
    }
    page_html = _replace_many(page_html, replacements)
    page_html = _sanitize_static_export_html(page_html, phase2_root, boundary_path)

    route_map: dict[str, str] = {}
    for target_community in communities:
        target_seed_choices = [item["seed"] for item in log_index.get(target_community, [])]
        for target_seed in target_seed_choices:
            route_map[f"{target_community}::{target_seed}"] = _static_href(
                current_relpath,
                _phase2_community_static_relpath(selected_rule, target_community, target_seed),
            )

    current_target = _static_href(
        current_relpath,
        _phase2_community_static_relpath(selected_rule, selected_community, selected_seed),
    )
    script = f"""
    <script>
      (function() {{
        const routeMap = {json.dumps(route_map, ensure_ascii=False)};
        const form = document.querySelector(".detail-inline-form");
        const communitySelect = form ? form.querySelector('select[name="community_name"]') : null;
        const seedSelect = form ? form.querySelector('select[name="seed"]') : null;

        function resolveTarget() {{
          const communityValue = communitySelect?.value || "";
          const seedValue = seedSelect?.value || "";
          return routeMap[`${{communityValue}}::${{seedValue}}`] || {json.dumps(current_target, ensure_ascii=False)};
        }}

        form?.addEventListener("submit", (event) => {{
          event.preventDefault();
          const target = resolveTarget();
          if (target) window.location.href = target;
        }});
      }})();
    </script>
    """
    return page_html.replace("</body>", f"{script}\n</body>")


def _build_phase2_compare_static_page(
    phase2_root: str,
    current_relpath: PurePosixPath,
) -> str:
    global_df = _load_phase2_global_results(phase2_root)
    selected_rule_ids = global_df["rule_id"].astype(str).tolist()
    pair_df = _load_phase2_policy_community_pairs(phase2_root)
    selected_communities = sorted(pair_df["community_name"].astype(str).unique().tolist()) if not pair_df.empty else []
    comparison_df = _phase2_comparison_dataset(
        phase2_root=phase2_root,
        selected_rule_ids=selected_rule_ids,
        selected_communities=selected_communities,
        mode="aggregate_policy",
    )
    if not comparison_df.empty:
        comparison_df = comparison_df.copy()
        comparison_df["pareto_status"] = _pareto_status(comparison_df, list(COMPARISON_METRICS.keys()))
        comparison_df["weighted_score"] = _weighted_scores(
            comparison_df,
            {metric_key: 1.0 for metric_key in COMPARISON_METRICS},
        )
        comparison_df["frontier_label"] = comparison_df.apply(
            lambda row: (
                f"[{_safe_float(row.get('extension_cap')) * 100:.0f},{_safe_float(row.get('subsidy_cap')) * 100:.0f}]"
                if not pd.isna(row.get("extension_cap")) and not pd.isna(row.get("subsidy_cap"))
                else str(row.get("rule_id") or "N/A")
            ),
            axis=1,
        )
        comparison_df["explore_url"] = comparison_df["rule_id"].map(
            lambda rule_value: _static_href(
                current_relpath,
                _phase2_global_static_relpath(
                    str(rule_value),
                    "final_agree_ratio",
                    _preferred_phase2_seed(phase2_root, str(rule_value)),
                ),
            )
        )
    top_weighted_row = (
        comparison_df.sort_values("weighted_score", ascending=False, na_position="last").iloc[0]
        if not comparison_df.empty and comparison_df["weighted_score"].notna().any()
        else None
    )
    kpi_cards = [
        {
            "label": "Policies",
            "value": str(len(selected_rule_ids)),
            "hint": "Rules bundled into this static export",
        },
        {
            "label": "Communities",
            "value": str(len(selected_communities)),
            "hint": "Communities covered by the comparison set",
        },
        {
            "label": "Champion Rule",
            "value": str(global_df.iloc[0]["rule_id"]) if not global_df.empty else "N/A",
            "hint": "Highest-ranked rule in phase2_global_rule_results.csv",
        },
        {
            "label": "Top Composite Rule",
            "value": str(top_weighted_row["rule_id"]) if top_weighted_row is not None else "N/A",
            "hint": "Equal-weight composite score across all objectives",
        },
    ]
    rows_payload = _json_ready(
        comparison_df[
            [
                "rule_id",
                "rule_content",
                "community_count",
                "final_agree_ratio",
                "developer_profit",
                "resident_mean_utility",
                "utility_gini",
                "subsidy_total_cost",
                "extension_ratio_final",
                "weighted_score",
                "pareto_status",
                "frontier_label",
                "explore_url",
            ]
        ]
        if not comparison_df.empty
        else comparison_df
    )
    stats_html = _stats_cards_html(kpi_cards)
    home_href = _static_href(current_relpath, _site_index_static_relpath())
    default_global_href = _static_href(
        current_relpath,
        _phase2_global_static_relpath(
            str(global_df.iloc[0]["rule_id"]) if not global_df.empty else "rule_0000",
            "final_agree_ratio",
            _preferred_phase2_seed(phase2_root, str(global_df.iloc[0]["rule_id"])) if not global_df.empty else None,
        ),
    )
    body = f"""
    <style>
      .compare-static-toolbar {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        align-items: end;
      }}
      .compare-static-toolbar label {{
        display: grid;
        gap: 6px;
        font-size: 13px;
        font-weight: 700;
        color: var(--text);
      }}
      .compare-static-toolbar input,
      .compare-static-toolbar select {{
        min-height: 44px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--surface);
      }}
      .compare-static-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: flex-end;
      }}
      .compare-static-grid {{
        display: grid;
        grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.85fr);
        gap: 24px;
        align-items: start;
      }}
      .compare-static-plot {{
        min-height: 520px;
      }}
      .compare-static-sideplot {{
        min-height: 420px;
      }}
      @media (max-width: 1040px) {{
        .compare-static-toolbar,
        .compare-static-grid {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
    <div class="panel">
      <div class="section-head">
        <div class="section-title">Policy Trade-off Analysis</div>
        <div class="section-copy">This GitHub Pages export keeps the comparison workspace static and browser-only. Search narrows both the chart and the table.</div>
      </div>
      {stats_html}
    </div>
    <div class="panel">
      <div class="compare-static-toolbar">
        <label>Objective 1
          <select id="compare-objective-1">{_option_html([(cfg["label"], key) for key, cfg in COMPARISON_METRICS.items()], "final_agree_ratio")}</select>
        </label>
        <label>Objective 2
          <select id="compare-objective-2">{_option_html([(cfg["label"], key) for key, cfg in COMPARISON_METRICS.items()], "developer_profit")}</select>
        </label>
        <label>Search
          <input id="compare-search" type="search" placeholder="Search rule id or policy content" />
        </label>
        <div class="compare-static-actions">
          <button id="compare-frontier-toggle" class="plot-action-button" type="button">Compute Pareto Frontier</button>
          <a class="button secondary" href="{default_global_href}">Open Analysis</a>
          <a class="button ghost" href="{home_href}">Back Home</a>
        </div>
      </div>
    </div>
    <div class="compare-static-grid">
      <div class="panel">
        <div class="section-head compact">
          <div class="section-title">Pareto Trade-off Scatter</div>
          <div class="section-copy">Click a point to open its rule page.</div>
        </div>
        <div id="compare-scatter" class="compare-static-plot"></div>
      </div>
      <div class="panel">
        <div class="section-head compact">
          <div class="section-title">Composite Ranking</div>
          <div class="section-copy">Equal-weight composite score across all objectives.</div>
        </div>
        <div id="compare-ranking" class="compare-static-sideplot"></div>
      </div>
    </div>
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Comparison Table</div>
        <div class="section-copy">Search and sort to inspect trade-offs across all bundled policies.</div>
      </div>
      <div id="compare-table"></div>
    </div>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
      (function() {{
        const allRows = {json.dumps(rows_payload, ensure_ascii=False)};
        const metricConfig = {{
          ...{json.dumps(COMPARISON_METRICS, ensure_ascii=False)},
          weighted_score: {{ label: "Weighted Score", format: "score" }},
        }};
        const tableColumns = [
          {{ key: "rule_id", label: "Rule ID" }},
          {{ key: "rule_content", label: "Policy Content" }},
          {{ key: "community_count", label: "Communities" }},
          {{ key: "final_agree_ratio", label: "Agreement Rate" }},
          {{ key: "developer_profit", label: "Developer Profit" }},
          {{ key: "resident_mean_utility", label: "Resident Mean Utility" }},
          {{ key: "utility_gini", label: "Utility Gini" }},
          {{ key: "subsidy_total_cost", label: "Subsidy Cost" }},
          {{ key: "extension_ratio_final", label: "Extension Ratio" }},
          {{ key: "weighted_score", label: "Weighted Score" }},
          {{ key: "pareto_status", label: "Pareto Status" }},
          {{ key: "explore_url", label: "Open" }},
        ];
        const searchInput = document.getElementById("compare-search");
        const frontierToggle = document.getElementById("compare-frontier-toggle");
        const objective1Select = document.getElementById("compare-objective-1");
        const objective2Select = document.getElementById("compare-objective-2");
        const sortState = {{ key: "weighted_score", dir: "desc" }};
        let showFrontier = false;
        let xMetric = objective1Select.value;
        let yMetric = objective2Select.value;

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

        function filteredRows() {{
          const query = (searchInput.value || "").trim().toLowerCase();
          if (!query) return [...allRows];
          return allRows.filter((row) =>
            Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(query))
          );
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

        function sortedRows() {{
          const rows = filteredRows();
          rows.sort((left, right) => compareValues(left[sortState.key], right[sortState.key], sortState.key, sortState.dir));
          return rows;
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

        function frontierRows(rows) {{
          const candidates = rows.filter((row) => typeof row[xMetric] === "number" && typeof row[yMetric] === "number");
          return candidates.filter((candidate, index) =>
            !candidates.some((other, otherIndex) => otherIndex !== index && pointDominates(other, candidate, [xMetric, yMetric]))
          ).sort((left, right) => (left[xMetric] ?? 0) - (right[xMetric] ?? 0));
        }}

        function renderScatter() {{
          const rows = filteredRows();
          if (!rows.length) {{
            document.getElementById("compare-scatter").innerHTML = '<div class="chart-empty">No rows match the current search.</div>';
            return;
          }}
          const categories = [
            {{ status: "Dominated", color: "#94a3b8", size: 12 }},
            {{ status: "Pareto-optimal", color: "#111827", size: 15 }},
            {{ status: "Incomplete", color: "#e5e7eb", size: 11 }},
          ];
          const traces = categories.map((category) => {{
            const subset = rows.filter((row) => row.pareto_status === category.status && typeof row[xMetric] === "number" && typeof row[yMetric] === "number");
            return {{
              x: subset.map((row) => row[xMetric]),
              y: subset.map((row) => row[yMetric]),
              text: subset.map((row) => row.rule_id),
              customdata: subset.map((row) => [row.explore_url]),
              type: "scatter",
              mode: "markers",
              name: category.status,
              marker: {{
                size: category.size,
                color: category.color,
                line: {{ color: "#ffffff", width: category.status === "Pareto-optimal" ? 2.2 : 1.2 }},
                opacity: category.status === "Incomplete" ? 0.45 : 0.9,
              }},
              hovertemplate:
                "<b>%{{text}}</b><br>" +
                `${{metricConfig[xMetric]?.label || xMetric}}: %{{x}}<br>` +
                `${{metricConfig[yMetric]?.label || yMetric}}: %{{y}}<br>` +
                "Pareto Status: " + category.status + "<extra></extra>",
            }};
          }}).filter((trace) => trace.x.length);

          if (showFrontier) {{
            const frontier = frontierRows(rows);
            if (frontier.length) {{
              traces.push({{
                x: frontier.map((row) => row[xMetric]),
                y: frontier.map((row) => row[yMetric]),
                text: frontier.map((row) => row.frontier_label || row.rule_id),
                customdata: frontier.map((row) => [row.explore_url]),
                type: "scatter",
                mode: "lines+markers+text",
                name: "2D Frontier",
                textposition: "top center",
                textfont: {{ size: 12, color: "#991b1b", family: "Microsoft YaHei, PingFang SC, sans-serif" }},
                line: {{ color: "#c2410c", width: 2.4 }},
                marker: {{ size: 12, color: "#b91c1c", line: {{ color: "#ffffff", width: 1.8 }} }},
                hovertemplate:
                  "<b>%{{text}}</b><br>" +
                  `${{metricConfig[xMetric]?.label || xMetric}}: %{{x}}<br>` +
                  `${{metricConfig[yMetric]?.label || yMetric}}: %{{y}}<br>` +
                  "2D Pareto frontier<extra></extra>",
              }});
            }}
          }}

          Plotly.react("compare-scatter", traces, {{
            margin: {{ l: 56, r: 20, t: 20, b: 50 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: metricConfig[xMetric]?.label || xMetric, gridcolor: "#f1f5f9", zeroline: false }},
            yaxis: {{ title: metricConfig[yMetric]?.label || yMetric, gridcolor: "#f1f5f9", zeroline: false }},
            hovermode: "closest",
            legend: {{ orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "left", x: 0 }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 13, color: "#4b5563" }},
          }}, {{ displayModeBar: false, responsive: true }});

          const chart = document.getElementById("compare-scatter");
          if (chart && chart.on && chart.dataset.boundCompareClick !== "true") {{
            chart.on("plotly_click", (event) => {{
              const target = event.points && event.points.length ? event.points[0].customdata?.[0] : null;
              if (target) window.location.href = target;
            }});
            chart.dataset.boundCompareClick = "true";
          }}
        }}

        function renderRanking() {{
          const rows = filteredRows()
            .filter((row) => typeof row.weighted_score === "number" && !Number.isNaN(row.weighted_score))
            .sort((left, right) => right.weighted_score - left.weighted_score)
            .slice(0, 10)
            .reverse();
          if (!rows.length) {{
            document.getElementById("compare-ranking").innerHTML = '<div class="chart-empty">No rows match the current search.</div>';
            return;
          }}
          Plotly.react("compare-ranking", [{{
            type: "bar",
            orientation: "h",
            x: rows.map((row) => row.weighted_score * 100),
            y: rows.map((row) => row.rule_id),
            customdata: rows.map((row) => [row.explore_url]),
            marker: {{
              color: rows.map((row) => row.pareto_status === "Pareto-optimal" ? "#111827" : "#94a3b8"),
              line: {{ color: "#ffffff", width: 1.2 }},
            }},
            hovertemplate: "<b>%{{y}}</b><br>Composite Score: %{{x:.1f}}/100<extra></extra>",
          }}], {{
            margin: {{ l: 96, r: 18, t: 10, b: 40 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: "Composite Score", range: [0, 100], gridcolor: "#f1f5f9", zeroline: false }},
            yaxis: {{ title: "", automargin: true }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 13, color: "#4b5563" }},
            showlegend: false,
          }}, {{ displayModeBar: false, responsive: true }});

          const chart = document.getElementById("compare-ranking");
          if (chart && chart.on && chart.dataset.boundRankingClick !== "true") {{
            chart.on("plotly_click", (event) => {{
              const target = event.points && event.points.length ? event.points[0].customdata?.[0] : null;
              if (target) window.location.href = target;
            }});
            chart.dataset.boundRankingClick = "true";
          }}
        }}

        function renderTable() {{
          const container = document.getElementById("compare-table");
          const rows = sortedRows();
          const headerHtml = tableColumns.map((column) => {{
            const active = sortState.key === column.key ? ` is-sorted sort-${{sortState.dir}}` : "";
            return `<th class="table-header${{active}}" data-key="${{column.key}}">${{column.label}}</th>`;
          }}).join("");
          const bodyHtml = rows.map((row) => {{
            const rowClass = row.pareto_status === "Pareto-optimal" ? "table-row is-active" : "table-row";
            const cells = tableColumns.map((column) => {{
              if (column.key === "explore_url") {{
                return row.explore_url
                  ? `<td class="table-cell"><a class="inline-table-link" href="${{row.explore_url}}">Open</a></td>`
                  : `<td class="table-cell">N/A</td>`;
              }}
              const alignClass = metricConfig[column.key] || column.key === "community_count" ? " align-right" : "";
              const displayValue = metricConfig[column.key] ? formatValue(column.key, row[column.key]) : String(row[column.key] ?? "N/A");
              return `<td class="table-cell${{alignClass}}">${{displayValue}}</td>`;
            }}).join("");
            return `<tr class="${{rowClass}}">${{cells}}</tr>`;
          }}).join("") || `<tr><td class="table-empty" colspan="${{tableColumns.length}}">No rows match the current search.</td></tr>`;
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

        function renderAll() {{
          renderScatter();
          renderRanking();
          renderTable();
        }}

        frontierToggle?.addEventListener("click", () => {{
          showFrontier = !showFrontier;
          frontierToggle.textContent = showFrontier ? "Hide Pareto Frontier" : "Compute Pareto Frontier";
          frontierToggle.classList.toggle("is-active", showFrontier);
          renderScatter();
        }});
        searchInput?.addEventListener("input", renderAll);
        objective1Select?.addEventListener("change", () => {{
          xMetric = objective1Select.value;
          if (xMetric === yMetric) {{
            const fallback = Object.keys(metricConfig).find((key) => key !== "weighted_score" && key !== xMetric);
            if (fallback) {{
              yMetric = fallback;
              objective2Select.value = fallback;
            }}
          }}
          renderScatter();
        }});
        objective2Select?.addEventListener("change", () => {{
          yMetric = objective2Select.value;
          if (xMetric === yMetric) {{
            const fallback = Object.keys(metricConfig).find((key) => key !== "weighted_score" && key !== yMetric);
            if (fallback) {{
              xMetric = fallback;
              objective1Select.value = fallback;
            }}
          }}
          renderScatter();
        }});

        renderAll();
      }})();
    </script>
    """
    return _html_shell("Policy Trade-off Analysis", body, embedded=False)


def _build_github_pages_index(
    phase2_root: str,
    total_rules: int,
    total_communities: int,
    analysis_href: str,
    compare_href: str,
) -> str:
    stats_html = _stats_cards_html(
        [
            {"label": "Policies", "value": str(total_rules), "hint": "Bundled phase2 rules"},
            {"label": "Communities", "value": str(total_communities), "hint": "Communities covered in the export"},
            {"label": "Data Source", "value": "Bundled phase2 dataset", "hint": "No server runtime required"},
        ]
    )
    body = f"""
    <div class="panel">
      <div class="section-head">
        <div class="section-title">Urban Renewal Result Explorer</div>
        <div class="section-copy">This export is ready for GitHub Pages. It keeps the phase2 analysis and browsing workflow static, and leaves Upload & Run on the local Python app.</div>
      </div>
      {stats_html}
      <div class="linkline">
        <a class="button primary" href="{analysis_href}">Open Analysis</a>
        <a class="button secondary" href="{compare_href}">Open Comparison</a>
      </div>
    </div>
    <div class="panel">
      <div class="section-head compact">
        <div class="section-title">Scope</div>
      </div>
      <ul>
        <li>Experiment result map browsing and community detail playback are included.</li>
        <li>Policy comparison is included as a browser-side static page.</li>
        <li>Upload, validation, resident generation, and simulation launch remain local-only because GitHub Pages cannot run Python or FastAPI.</li>
      </ul>
    </div>
    """
    return _html_shell("Urban Renewal Result Explorer", body, embedded=False)


def export_github_pages_site(
    target_dir: str | Path = DEFAULT_GITHUB_PAGES_EXPORT_DIR,
    phase2_root: str | Path = DEFAULT_PHASE2_ROOT,
    boundary_path: str | None = None,
) -> dict[str, Any]:
    export_root = Path(target_dir).resolve()
    export_root.mkdir(parents=True, exist_ok=True)
    resolved_phase2_root = str(Path(phase2_root).resolve())
    resolved_boundary_path = boundary_path or _resolve_shape_path(None)

    global_df = _load_phase2_global_results(resolved_phase2_root)
    rule_ids = global_df["rule_id"].astype(str).tolist()
    community_pairs = _load_phase2_policy_community_pairs(resolved_phase2_root)
    total_communities = int(community_pairs["community_name"].nunique()) if not community_pairs.empty else 0

    global_page_count = 0
    community_page_count = 0

    for rule_id in rule_ids:
        seeds = list(_available_phase2_seeds(resolved_phase2_root, rule_id))
        seeds = seeds or [None]
        for seed in seeds:
            for metric_key in MAP_METRICS:
                relpath = _phase2_global_static_relpath(rule_id, metric_key, seed)
                page_html = _build_phase2_global_static_page(
                    phase2_root=resolved_phase2_root,
                    boundary_path=resolved_boundary_path,
                    rule_id=rule_id,
                    metric=metric_key,
                    seed=seed,
                    current_relpath=relpath,
                )
                _write_static_page(export_root, relpath, page_html)
                global_page_count += 1
                plt.close("all")

        log_index = _index_phase2_logs(resolved_phase2_root, rule_id)
        for community_name, entries in log_index.items():
            for entry in entries:
                relpath = _phase2_community_static_relpath(rule_id, community_name, entry["seed"])
                page_html = _build_phase2_community_static_page(
                    phase2_root=resolved_phase2_root,
                    boundary_path=resolved_boundary_path,
                    rule_id=rule_id,
                    community_name=community_name,
                    seed=entry["seed"],
                    current_relpath=relpath,
                )
                _write_static_page(export_root, relpath, page_html)
                community_page_count += 1
                plt.close("all")

    compare_relpath = _phase2_compare_static_relpath()
    compare_html = _build_phase2_compare_static_page(resolved_phase2_root, compare_relpath)
    _write_static_page(export_root, compare_relpath, compare_html)
    plt.close("all")

    default_rule = str(global_df.iloc[0]["rule_id"]) if not global_df.empty else "rule_0000"
    default_seed = _preferred_phase2_seed(resolved_phase2_root, default_rule)
    default_analysis_relpath = _phase2_global_static_relpath(default_rule, "final_agree_ratio", default_seed)
    index_html = _build_github_pages_index(
        phase2_root=resolved_phase2_root,
        total_rules=len(rule_ids),
        total_communities=total_communities,
        analysis_href=_static_href(_site_index_static_relpath(), default_analysis_relpath),
        compare_href=_static_href(_site_index_static_relpath(), compare_relpath),
    )
    _write_static_page(export_root, _site_index_static_relpath(), index_html)
    (export_root / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "export_dir": str(export_root),
        "index_page": str((export_root / "index.html").resolve()),
        "global_pages": global_page_count,
        "community_pages": community_page_count,
        "compare_page": str(export_root.joinpath(*compare_relpath.parts).resolve()),
    }

