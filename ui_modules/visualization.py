
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def _env_banner() -> str:
    runtime_python = _runtime_python()
    current_env = os.environ.get("CONDA_DEFAULT_ENV", "unknown")
    return (
        f"Current UI Python: `{sys.executable}`\n\n"
        f"Simulation subprocess Python: `{runtime_python}`\n\n"
        f"Current CONDA environment: `{current_env}`\n\n"
        f"Recommended launch command: `conda run -n thesis python ui_app.py`"
    )


def _placeholder_figure(title: str, message: str) -> str:
    fig = plt.figure(figsize=(10, 6), dpi=120)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#f8fafc")
    ax.axis("off")
    fig.text(0.05, 0.92, title, fontsize=18, weight="bold", color="#0f172a", **_font_kwargs())
    fig.text(0.05, 0.80, message, fontsize=13, color="#475569", **_font_kwargs())
    output_path = _temp_png("placeholder")
    fig.savefig(output_path, facecolor="#f8fafc")
    plt.close(fig)
    return output_path


def _prepare_plot_geodf(
    boundary_path: str,
    summary_df: pd.DataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, tuple[float, float], tuple[float, float]]:
    boundary_gdf = _read_boundary(boundary_path).copy()
    summary = summary_df.copy()
    summary["community_name"] = summary["community_name"].astype(str).str.strip()

    focus_gdf = boundary_gdf.merge(summary, on="community_name", how="left")
    matched = focus_gdf[focus_gdf["community_name"].isin(summary["community_name"])]
    bounds_source = matched if not matched.empty else boundary_gdf

    minx, miny, maxx, maxy = bounds_source.total_bounds
    x_span = max(maxx - minx, 1e-6)
    y_span = max(maxy - miny, 1e-6)
    x_pad = x_span * 0.08
    y_pad = y_span * 0.08
    xlim = (minx - x_pad, maxx + x_pad)
    ylim = (miny - y_pad, maxy + y_pad)

    if focus_gdf.crs is not None and getattr(focus_gdf.crs, "is_geographic", False):
        projected = focus_gdf.to_crs(focus_gdf.estimate_utm_crs() or "EPSG:3857")
        centroids = gpd.GeoSeries(projected.geometry.centroid, crs=projected.crs).to_crs(focus_gdf.crs)
    else:
        centroids = focus_gdf.geometry.centroid
    focus_gdf["centroid_pt"] = centroids.values
    return boundary_gdf, focus_gdf, xlim, ylim


def _render_metric_map(
    summary_df: pd.DataFrame,
    boundary_path: str | None,
    metric: str,
    title: str,
    selected_community: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if boundary_path is None:
        return _placeholder_figure("Map unavailable", "Boundary file not found."), {}
    if summary_df.empty:
        return _placeholder_figure("Map unavailable", "No community results are available for display."), {}

    boundary_gdf, plot_gdf, xlim, ylim = _prepare_plot_geodf(boundary_path, summary_df)
    metric_df = plot_gdf.dropna(subset=[metric]).copy() if metric in plot_gdf.columns else plot_gdf.iloc[0:0].copy()
    value_series = _map_value_series(metric_df, metric)
    valid_values = value_series.dropna()

    width_px = 1180
    height_px = 820
    dpi = 120
    fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    ax = fig.add_axes([0.00, 0.02, 1.00, 0.90])
    ax.set_facecolor("#f8fafc")
    ax.axis("off")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    boundary_gdf.plot(ax=ax, color="#F8F9FA", edgecolor="#DEE2E6", linewidth=0.55, zorder=1)

    cmap = plt.get_cmap("YlGnBu")
    if valid_values.empty:
        color_values = None
        scatter_colors = "#268CA0"
        size_values = np.full(len(metric_df), 230.0)
        norm = None
    else:
        vmin = float(valid_values.min())
        vmax = float(valid_values.max())
        if abs(vmax - vmin) < 1e-9:
            vmax = vmin + 1.0
        norm = Normalize(vmin=vmin, vmax=vmax)
        color_values = pd.to_numeric(metric_df[metric], errors="coerce")
        size_base = color_values.fillna(color_values.mean() if not color_values.dropna().empty else 1.0)
        if size_base.max() > 0:
            size_values = 180.0 + (size_base / size_base.max()) * 560.0
        else:
            size_values = np.full(len(metric_df), 230.0)
        scatter_colors = color_values

    scatter = None
    if not metric_df.empty:
        scatter = ax.scatter(
            metric_df["centroid_pt"].x,
            metric_df["centroid_pt"].y,
            c=scatter_colors,
            cmap=cmap if color_values is not None else None,
            norm=norm,
            s=size_values,
            edgecolor="white",
            linewidth=0.9,
            alpha=0.88,
            zorder=3,
        )

    if selected_community:
        highlight = metric_df[metric_df["community_name"] == selected_community]
        if not highlight.empty:
            highlight_sizes = pd.Series(size_values, index=metric_df.index).loc[highlight.index].to_numpy()
            ax.scatter(
                highlight["centroid_pt"].x,
                highlight["centroid_pt"].y,
                s=highlight_sizes * 1.35 if len(highlight_sizes) else 520,
                facecolors="none",
                edgecolors="#F97316",
                linewidths=2.8,
                zorder=4,
            )

    texts = []
    for row in metric_df.itertuples():
        centroid = getattr(row, "centroid_pt", None)
        if centroid is None:
            continue
        label = f"{row.community_name}\n({getattr(row, metric):.2f})"
        text_obj = ax.text(
            centroid.x,
            centroid.y,
            label,
            ha="center",
            va="center",
            fontsize=13,
            color="#0F172A",
            zorder=5,
            **_font_kwargs(),
        )
        texts.append(text_obj)

    if HAS_ADJUST_TEXT and texts:
        adjust_text(
            texts,
            ax=ax,
            expand_points=(1.35, 1.35),
            expand_text=(1.15, 1.15),
            arrowprops=dict(arrowstyle="->", color="#94A3B8", lw=0.5, alpha=0.6),
        )

    fig.text(0.03, 0.965, title, fontsize=18, weight="bold", color="#0f172a", **_font_kwargs())
    fig.text(0.03, 0.935, f"Highlighted metric: {MAP_METRICS.get(metric, metric)}", fontsize=11, color="#475569", **_font_kwargs())

    if scatter is not None and norm is not None and not valid_values.empty:
        cax = fig.add_axes([0.80, 0.16, 0.018, 0.24])
        cbar = fig.colorbar(scatter, cax=cax, orientation="vertical")
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(labelsize=10, colors="#334155")

    output_path = _temp_png("map")
    fig.savefig(output_path, facecolor="#f8fafc")
    plt.close(fig)

    map_state = {
        "boundary_path": boundary_path,
        "summary_records": summary_df.to_dict(orient="records"),
        "metric": metric,
        "xlim": xlim,
        "ylim": ylim,
        "width_px": width_px,
        "height_px": height_px,
    }
    return output_path, map_state


def _export_metric_map_png(
    summary_df: pd.DataFrame,
    boundary_path: str | None,
    metric: str,
    title: str,
    subtitle: str | None = None,
) -> str:
    output_path = _temp_png("community_result_map_export")
    fig = plt.figure(figsize=(9.7, 8.5), dpi=180)
    fig.patch.set_facecolor("#ffffff")
    ratio_metric = metric in {"final_agree_ratio", "avg_extension_ratio", "avg_subsidy_ratio"}

    if boundary_path is None or not Path(boundary_path).exists():
        ax = fig.add_axes([0.04, 0.08, 0.92, 0.84])
        ax.axis("off")
        fig.text(0.05, 0.945, title, fontsize=23, weight="bold", color="#111827", **_font_kwargs())
        fig.text(0.05, 0.895, "Boundary file not available.", fontsize=14.5, color="#6b7280", **_font_kwargs())
        fig.savefig(output_path, facecolor="#ffffff")
        plt.close(fig)
        return output_path

    boundary_gdf, plot_gdf, xlim, ylim = _prepare_plot_geodf(boundary_path, summary_df)
    metric_gdf = plot_gdf.copy()
    metric_values = _map_value_series(metric_gdf, metric)
    valid_mask = metric_values.notna()
    valid_values = metric_values[valid_mask]
    cmap = plt.get_cmap("YlGnBu")
    norm = None

    grid = fig.add_gridspec(
        2,
        2,
        left=0.05,
        right=0.95,
        top=0.89,
        bottom=0.08,
        width_ratios=[4.1, 1.25],
        height_ratios=[0.44, 0.56],
        wspace=0.05,
        hspace=0.30,
    )

    ax_map = fig.add_subplot(grid[:, 0])
    ax_map.set_facecolor("#ffffff")
    ax_map.axis("off")
    ax_map.set_xlim(*xlim)
    ax_map.set_ylim(*ylim)
    ax_map.set_aspect("equal", adjustable="box")

    boundary_gdf.plot(ax=ax_map, color="#f5f5f5", edgecolor="#d4d4d8", linewidth=0.6, zorder=1)

    empty_gdf = metric_gdf.loc[~valid_mask].copy()
    if not empty_gdf.empty:
        empty_gdf.plot(ax=ax_map, color="#d4d4d8", edgecolor="#cbd5e1", linewidth=0.8, zorder=2)

    if not valid_values.empty:
        vmin = float(valid_values.min())
        vmax = float(valid_values.max())
        if abs(vmax - vmin) < 1e-9:
            if ratio_metric:
                pad = 0.05 if vmin > 0.05 else 0.02
                vmin = max(0.0, vmin - pad)
                vmax = min(1.0, vmax + pad) if vmax <= 1.0 else vmax + pad
                if abs(vmax - vmin) < 1e-9:
                    vmax = vmin + 0.01
            else:
                pad = max(abs(vmin) * 0.05, 1.0)
                vmin -= pad
                vmax += pad
        norm = Normalize(vmin=vmin, vmax=vmax)
        metric_gdf.loc[valid_mask].plot(
            ax=ax_map,
            column=metric,
            cmap=cmap,
            linewidth=0.9,
            edgecolor="#ffffff",
            vmin=vmin,
            vmax=vmax,
            zorder=3,
        )

    fig.text(0.05, 0.948, title, fontsize=23, weight="bold", color="#111827", **_font_kwargs())
    fig.text(
        0.05,
        0.904,
        subtitle or f"Highlighted metric: {MAP_METRICS.get(metric, metric)}",
        fontsize=14,
        color="#6b7280",
        **_font_kwargs(),
    )

    legend_ax = fig.add_subplot(grid[0, 1])
    legend_ax.set_facecolor("#ffffff")
    legend_ax.axis("off")
    legend_ax.set_xlim(0, 1)
    legend_ax.set_ylim(0, 1)
    legend_ax.text(0.00, 0.98, "Map Legend", fontsize=16, weight="bold", color="#111827", va="top", **_font_kwargs())
    legend_ax.text(0.00, 0.84, MAP_METRICS.get(metric, metric), fontsize=13, color="#6b7280", va="top", **_font_kwargs())
    legend_ax.scatter([0.06], [0.62], s=125, color="#d1d5db", edgecolors="#cbd5e1")
    legend_ax.text(0.15, 0.62, "No result available", va="center", fontsize=12, color="#111827", **_font_kwargs())

    if norm is not None:
        cax = legend_ax.inset_axes([0.00, 0.27, 0.84, 0.09])
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
        cbar.outline.set_visible(False)
        ticks = np.linspace(norm.vmin, norm.vmax, 4)
        cbar.set_ticks(ticks)
        cbar.ax.tick_params(labelsize=11, colors="#6b7280", pad=3, length=0)
        cbar.ax.set_xticklabels(
            [
                _format_ratio(tick) if ratio_metric else f"{tick:.3f}"
                for tick in ticks
            ]
        )

    hist_ax = fig.add_subplot(grid[1, 1])
    hist_ax.set_facecolor("#ffffff")
    hist_ax.text(
        0.0,
        1.20,
        "Metric Distribution",
        transform=hist_ax.transAxes,
        fontsize=16,
        fontweight="bold",
        color="#111827",
        va="top",
        clip_on=False,
        **_font_kwargs(),
    )
    hist_ax.text(
        0.0,
        1.10,
        f"{int(valid_values.shape[0])} communities with results",
        transform=hist_ax.transAxes,
        fontsize=12.5,
        color="#6b7280",
        va="bottom",
        clip_on=False,
        **_font_kwargs(),
    )
    if not valid_values.empty:
        hist_ax.hist(valid_values, bins=min(max(len(valid_values), 4), 10), color="#111827", edgecolor="#ffffff", alpha=0.96)
    else:
        hist_ax.text(0.5, 0.5, "No values available", ha="center", va="center", fontsize=12, color="#6b7280", **_font_kwargs())
        hist_ax.set_xticks([])
        hist_ax.set_yticks([])
    if ratio_metric:
        hist_ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(xmax=1.0))
    hist_ax.spines["top"].set_visible(False)
    hist_ax.spines["right"].set_visible(False)
    hist_ax.spines["left"].set_color("#d4d4d8")
    hist_ax.spines["bottom"].set_color("#d4d4d8")
    hist_ax.tick_params(colors="#6b7280", labelsize=10.5)
    hist_ax.grid(axis="y", color="#f3f4f6", linewidth=0.8)

    fig.savefig(output_path, facecolor="#ffffff")
    plt.close(fig)
    return output_path


def _pick_community_from_click(evt: gr.SelectData | None, map_state: dict[str, Any]) -> str | None:
    if evt is None or not map_state:
        return None

    index = getattr(evt, "index", None)
    if not isinstance(index, (list, tuple)) or len(index) < 2:
        return None

    boundary_path = map_state.get("boundary_path")
    summary_records = map_state.get("summary_records") or []
    if not boundary_path or not summary_records:
        return None

    summary_df = pd.DataFrame(summary_records)
    _, plot_gdf, xlim, ylim = _prepare_plot_geodf(boundary_path, summary_df)
    metric = map_state.get("metric", "final_agree_ratio")
    metric_df = plot_gdf.dropna(subset=[metric]).copy() if metric in plot_gdf.columns else plot_gdf.iloc[0:0].copy()
    target_gdf = metric_df if not metric_df.empty else plot_gdf
    width_px = max(int(map_state.get("width_px", 1)), 1)
    height_px = max(int(map_state.get("height_px", 1)), 1)

    candidates: list[tuple[float, str]] = []
    for px, py in [(index[0], index[1]), (index[1], index[0])]:
        try:
            px = float(px)
            py = float(py)
        except Exception:
            continue

        x = xlim[0] + px / max(width_px - 1, 1) * (xlim[1] - xlim[0])
        y = ylim[1] - py / max(height_px - 1, 1) * (ylim[1] - ylim[0])
        point = Point(x, y)

        contains = target_gdf[target_gdf.geometry.contains(point)]
        if not contains.empty:
            return str(contains.iloc[0]["community_name"])

        distances = target_gdf["centroid_pt"].distance(point)
        if len(distances) > 0:
            idx = distances.idxmin()
            candidates.append((float(distances.loc[idx]), str(target_gdf.loc[idx, "community_name"])))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _build_round_dataframe(log_data: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for round_info in log_data.get("negotiation_history", []):
        residents = round_info.get("residents", [])
        total = len(residents)
        agree_count = sum(1 for item in residents if item.get("agree"))
        expected_base_prices = [_safe_float(item.get("expected_base_price"), np.nan) for item in residents]
        expected_extension_prices = [_safe_float(item.get("expected_extension_price"), np.nan) for item in residents]
        quoted_base_prices = [_safe_float(item.get("quoted_base_price"), np.nan) for item in residents]
        quoted_extension_prices = [_safe_float(item.get("quoted_extension_price"), np.nan) for item in residents]
        expected_extension_area = [_safe_float(item.get("expected_extension_area"), np.nan) for item in residents]
        rows.append(
            {
                "轮次": round_info.get("round"),
                "同意户数": agree_count,
                "总户数": total,
                "同意率": agree_count / total if total else np.nan,
                "规划扩面比例": _safe_float(round_info.get("planner", {}).get("extension_ratio"), np.nan),
                "规划补贴比例": _safe_float(round_info.get("planner", {}).get("cash_subsidy_ratio"), np.nan),
                "开发商原面积报价": _safe_float(round_info.get("developer", {}).get("base_price"), np.nan),
                "开发商扩面报价": _safe_float(round_info.get("developer", {}).get("extension_price"), np.nan),
                "开发商停车费": _safe_float(round_info.get("developer", {}).get("parking_fee"), np.nan),
                "平均意向扩面面积": _mean_or_nan(expected_extension_area),
                "平均心理原面积价格": _mean_or_nan(expected_base_prices),
                "平均心理扩面价格": _mean_or_nan(expected_extension_prices),
                "平均报出原面积价格": _mean_or_nan(quoted_base_prices),
                "平均报出扩面价格": _mean_or_nan(quoted_extension_prices),
            }
        )
    return pd.DataFrame(rows)


def _build_resident_round_dataframe(log_data: dict[str, Any], round_number: int | None) -> pd.DataFrame:
    if round_number is None:
        return pd.DataFrame()

    for round_info in log_data.get("negotiation_history", []):
        if _safe_int(round_info.get("round"), -1) != _safe_int(round_number, -1):
            continue
        df = pd.DataFrame(round_info.get("residents", []))
        if df.empty:
            return df
        rename_map = {
            "agent_id": "住户ID",
            "agree": "是否同意",
            "chosen_extension_area": "本轮选择扩面面积",
            "want_parking": "是否要车位",
            "expected_base_price": "心理原面积价格",
            "expected_extension_price": "心理扩面价格",
            "quoted_base_price": "报出原面积价格",
            "quoted_extension_price": "报出扩面价格",
            "expected_extension_area": "期望扩面面积",
        }
        df = df.rename(columns=rename_map)
        for column in ["是否同意", "是否要车位"]:
            if column in df.columns:
                df[column] = df[column].map({True: "Yes", False: "No"})
        return df

    return pd.DataFrame()


def _build_round_plot(log_data: dict[str, Any]):
    round_df = _build_round_dataframe(log_data)
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.patch.set_facecolor("#f8fafc")

    if round_df.empty:
        for ax in axes:
            ax.axis("off")
        fig.text(0.08, 0.85, "No round history available", fontsize=15, color="#475569", **_font_kwargs())
        return fig

    x = round_df["轮次"]

    axes[0].plot(x, round_df["同意率"], marker="o", color="#36AABF", linewidth=2.2)
    axes[0].set_ylabel("Agreement Rate", **_font_kwargs())
    axes[0].set_ylim(0, 1.05)
    axes[0].grid(alpha=0.25)

    axes[1].plot(x, round_df["规划扩面比例"], marker="o", color="#36AABF", label="Extension Ratio", linewidth=2.0)
    axes[1].plot(x, round_df["规划补贴比例"], marker="s", color="#ea580c", label="Subsidy Ratio", linewidth=2.0)
    axes[1].set_ylabel("Planner Policy", **_font_kwargs())
    axes[1].legend(frameon=False, prop=FONT_PROP)
    axes[1].grid(alpha=0.25)

    axes[2].plot(x, round_df["开发商原面积报价"], marker="o", color="#7c3aed", label="Base Price", linewidth=2.0)
    axes[2].plot(x, round_df["开发商扩面报价"], marker="s", color="#dc2626", label="Extension Price", linewidth=2.0)
    axes[2].set_ylabel("Price", **_font_kwargs())
    axes[2].set_xlabel("Round", **_font_kwargs())
    axes[2].legend(frameon=False, prop=FONT_PROP)
    axes[2].grid(alpha=0.25)

    for ax in axes:
        ax.set_facecolor("#ffffff")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("Discussion Playback", fontsize=16, y=0.98, color="#0f172a", **_font_kwargs())
    fig.tight_layout()
    return fig


def _save_figure(fig, prefix: str) -> str:
    output_path = _temp_png(prefix)
    fig.savefig(output_path, facecolor="#f8fafc", bbox_inches="tight")
    plt.close(fig)
    return output_path


def _df_to_html(df: pd.DataFrame, title: str | None = None) -> str:
    if df is None or df.empty:
        return f"<section><h3>{title or 'Table'}</h3><p>No data available.</p></section>"
    heading = f"<h3>{title}</h3>" if title else ""
    return (
        f"<section>{heading}"
        f"{df.to_html(index=False, classes='data-table', border=0, escape=False)}"
        "</section>"
    )


def _simple_markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    html_lines: list[str] = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{stripped[4:]}</h2>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{stripped}</p>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def _stats_cards_html(cards: list[dict[str, str]]) -> str:
    chunks = []
    for card in cards:
        value_class = "stat-value"
        if card.get("value_class"):
            value_class += f" {card['value_class']}"
        hint_class = "stat-hint"
        if card.get("hint_class"):
            hint_class += f" {card['hint_class']}"
        chunks.append(
            f"""
            <div class="stat-card">
              <div class="stat-label">{card.get('label', '')}</div>
              <div class="{value_class}">{card.get('value', 'N/A')}</div>
              <div class="{hint_class}">{card.get('hint', '')}</div>
            </div>
            """
        )
    return f'<div class="stats-grid">{"".join(chunks)}</div>'


def _display_panel_value(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na", "--"}:
        return "N/A"
    return html.escape(text)


def _key_value_panel_html(title: str, items: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in items:
        rows.append(
            f"""
            <div class="kv-item">
              <div class="kv-label">{html.escape(str(label))}</div>
              <div class="kv-value">{_display_panel_value(value)}</div>
            </div>
            """
        )
    return (
        f'<div class="section-head compact"><div class="section-title">{html.escape(str(title))}</div></div>'
        f'<div class="kv-grid">{"".join(rows)}</div>'
    )


def _metric_switch_html(base_path: str, params: dict[str, Any], current_metric: str) -> str:
    chips = []
    for metric_key, metric_label in MAP_METRICS.items():
        query = params | {"metric": metric_key}
        is_active = metric_key == current_metric
        chips.append(
            f'<a class="seg-button{" active" if is_active else ""}" href="{base_path}?{urlencode(query)}">{metric_label}</a>'
        )
    return f'<div class="seg-group metric-switch-list">{"".join(chips)}</div>'


def _coverage_summary(boundary_path: str | None, summary_df: pd.DataFrame) -> tuple[int, int]:
    if not boundary_path:
        total = int(summary_df["community_name"].nunique()) if not summary_df.empty and "community_name" in summary_df.columns else 0
        return total, total
    boundary_df = _read_boundary(boundary_path)
    total = int(boundary_df["community_name"].nunique()) if "community_name" in boundary_df.columns else len(boundary_df)
    if summary_df.empty or "community_name" not in summary_df.columns:
        return total, 0
    matched = boundary_df.merge(summary_df[["community_name"]].drop_duplicates(), on="community_name", how="inner")
    return total, int(matched["community_name"].nunique()) if "community_name" in matched.columns else len(matched)


def _detail_payload(
    log_data: dict[str, Any],
    round_df: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    round_records = _json_ready(round_df.rename(columns=ROUND_UI_RENAME))
    resident_by_round: dict[str, list[dict[str, Any]]] = {}
    for round_info in log_data.get("negotiation_history", []):
        round_number = str(_safe_int(round_info.get("round"), 0))
        resident_df = _build_resident_round_dataframe(log_data, _safe_int(round_number, 0))
        resident_by_round[round_number] = _json_ready(resident_df.rename(columns=RESIDENT_UI_RENAME))
    return round_records, resident_by_round


def _build_interactive_detail_page(
    page_title: str,
    page_description: str,
    header_chips: list[str],
    back_url: str,
    back_label: str,
    controls_html: str,
    summary_cards_html: str,
    current_result_html: str,
    round_records: list[dict[str, Any]],
    resident_by_round: dict[str, list[dict[str, Any]]],
    initial_round: int | None,
) -> str:
    round_json = json.dumps(_json_ready(round_records), ensure_ascii=False)
    resident_json = json.dumps(_json_ready(resident_by_round), ensure_ascii=False)
    initial_round_value = initial_round if initial_round is not None else 0
    return f"""
    <div class="panel detail-topbar-panel">
      <div class="detail-topbar-row">
        <div class="detail-title-block">
          <div class="detail-overline">Community Detail</div>
          <h1>{page_title}</h1>
          <div class="meta">{page_description}</div>
        </div>
        <div class="detail-controlbar">
          <div class="detail-control-panel">
            {controls_html}
          </div>
        </div>
      </div>
    </div>
    <div class="detail-main-stack">
      <div class="detail-summary-grid">
        <div class="panel detail-summary-panel">
          <div class="section-head compact">
            <div class="section-title">Result Summary</div>
          </div>
          {summary_cards_html}
        </div>
        <div class="panel detail-current-panel">
          {_key_value_panel_html("Current Community Result", []) if not current_result_html else current_result_html}
        </div>
      </div>
      <div class="panel detail-playback-panel">
        <div class="playback-topbar">
          <div class="section-head compact playback-head">
            <div class="section-title">Discussion Playback</div>
            <div class="section-copy">Replay the negotiation round by round. Charts and tables update together.</div>
          </div>
          <div class="timeline-shell">
            <button class="timeline-play" id="timeline-play-button" type="button">Play</button>
            <input class="timeline-slider" id="timeline-slider" type="range" min="0" max="0" value="0" step="1" />
            <div class="timeline-badge" id="timeline-badge">Round -</div>
          </div>
        </div>
        <div class="timeline-pills" id="timeline-pills"></div>
        <div class="chart-grid detail-chart-grid">
          <div class="chart-card">
            <div class="chart-head">
              <div class="chart-title">Agreement Rate by Round</div>
              <div id="agreement-legend" class="chart-legend"></div>
            </div>
            <div id="agreement-chart" class="plot-frame"></div>
          </div>
          <div class="chart-card">
            <div class="chart-head">
              <div class="chart-title">Planner Policy by Round</div>
              <div id="policy-legend" class="chart-legend"></div>
            </div>
            <div id="policy-chart" class="plot-frame"></div>
          </div>
          <div class="chart-card chart-card-rich">
            <div class="chart-head">
              <div class="chart-title">Developer Offers vs Resident Expectations</div>
              <div id="pricing-legend" class="chart-legend"></div>
            </div>
            <div id="pricing-chart" class="plot-frame"></div>
          </div>
        </div>
      </div>
      <div class="detail-lower-grid">
        <div class="panel detail-table-panel">
          <div class="section-head compact">
            <div class="section-title">Round Metrics</div>
            <div class="section-copy">Rows accumulate to the active round.</div>
          </div>
          <div id="round-table"></div>
        </div>
        <div class="panel detail-table-panel detail-resident-panel">
          <div class="section-head compact">
            <div class="section-title">Resident Decisions</div>
            <div class="section-copy">Search and inspect the active round's resident-level decisions.</div>
          </div>
          <div class="table-toolbar detail-table-toolbar">
            <input id="resident-search" class="table-search" type="search" placeholder="Search resident ID, decision, or pricing field" />
          </div>
          <div id="resident-table"></div>
        </div>
      </div>
    </div>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <script>
      (function() {{
        const roundRecords = {round_json};
        const residentByRound = {resident_json};
        const roundValues = [...new Set(
          roundRecords.map((row) => Number(row["Round"])).filter((value) => !Number.isNaN(value))
        )].sort((left, right) => left - right);
        let currentRound = {initial_round_value} || (roundValues.length ? roundValues[roundValues.length - 1] : 0);
        let playing = false;
        let timerId = null;
        const roundState = {{ sortKey: "Round", sortDir: "asc" }};
        const residentState = {{ sortKey: "Resident ID", sortDir: "asc", search: "" }};

        const percentColumns = new Set(["Agreement Rate", "Planner Extension Ratio", "Planner Subsidy Ratio"]);
        const currencyColumns = new Set([
          "Developer Base Price",
          "Developer Extension Price",
          "Developer Parking Fee",
          "Avg Expected Base Price",
          "Avg Expected Extension Price",
          "Avg Quoted Base Price",
          "Avg Quoted Extension Price",
          "Expected Base Price",
          "Expected Extension Price",
          "Quoted Base Price",
          "Quoted Extension Price"
        ]);
        const integerColumns = new Set(["Round", "Agreeing Households", "Total Households"]);
        const numberColumns = new Set(["Avg Expected Extension Area", "Selected Extension Area", "Expected Extension Area"]);

        const slider = document.getElementById("timeline-slider");
        const badge = document.getElementById("timeline-badge");
        const playButton = document.getElementById("timeline-play-button");
        const roundPills = document.getElementById("timeline-pills");
        const residentSearch = document.getElementById("resident-search");

        function formatNumber(value, digits = 2) {{
          if (value === null || value === undefined || value === "") return "N/A";
          if (typeof value !== "number" || Number.isNaN(value)) return String(value);
          return new Intl.NumberFormat("en-US", {{ maximumFractionDigits: digits, minimumFractionDigits: digits }}).format(value);
        }}

        function formatCurrency(value) {{
          if (value === null || value === undefined || value === "") return "N/A";
          if (typeof value !== "number" || Number.isNaN(value)) return String(value);
          return "¥" + new Intl.NumberFormat("en-US", {{ maximumFractionDigits: 0 }}).format(value);
        }}

        function formatPercent(value) {{
          if (value === null || value === undefined || value === "") return "N/A";
          if (typeof value !== "number" || Number.isNaN(value)) return String(value);
          return (value * 100).toFixed(1) + "%";
        }}

        function formatValue(column, value) {{
          if (value === null || value === undefined || value === "") return "N/A";
          if (percentColumns.has(column)) return formatPercent(value);
          if (currencyColumns.has(column)) return formatCurrency(value);
          if (integerColumns.has(column)) return typeof value === "number" ? String(Math.round(value)) : String(value);
          if (numberColumns.has(column)) return formatNumber(value, 2);
          if (typeof value === "number") return formatNumber(value, 3);
          return String(value);
        }}

        function compareValues(a, b, direction) {{
          const factor = direction === "desc" ? -1 : 1;
          const left = a === null || a === undefined ? "" : a;
          const right = b === null || b === undefined ? "" : b;
          if (typeof left === "number" && typeof right === "number") return (left - right) * factor;
          return String(left).localeCompare(String(right), undefined, {{ numeric: true, sensitivity: "base" }}) * factor;
        }}

        function sortRows(rows, state) {{
          const cloned = [...rows];
          cloned.sort((left, right) => compareValues(left[state.sortKey], right[state.sortKey], state.sortDir));
          return cloned;
        }}

        function renderTable(containerId, rows, state, options = {{}}) {{
          const container = document.getElementById(containerId);
          const columns = options.columns || (rows.length ? Object.keys(rows[0]) : []);
          const highlightedRound = options.highlightRound;
          const searchable = options.searchable ? residentState.search.trim().toLowerCase() : "";
          let filteredRows = [...rows];
          if (searchable) {{
            filteredRows = filteredRows.filter((row) =>
              columns.some((column) => String(row[column] ?? "").toLowerCase().includes(searchable))
            );
          }}
          const sortedRows = sortRows(filteredRows, state);
          const headerHtml = columns.map((column) => {{
            const active = state.sortKey === column ? ` is-sorted sort-${{state.sortDir}}` : "";
            return `<th class="table-header${{active}}" data-column="${{column}}">${{column}}</th>`;
          }}).join("");
          const bodyHtml = sortedRows.map((row) => {{
            const rowClass = highlightedRound && Number(row["Round"]) === Number(highlightedRound) ? "table-row is-active" : "table-row";
            const cells = columns.map((column) => {{
              const alignClass = (percentColumns.has(column) || currencyColumns.has(column) || numberColumns.has(column) || integerColumns.has(column)) ? " align-right" : "";
              return `<td class="table-cell${{alignClass}}">${{formatValue(column, row[column])}}</td>`;
            }}).join("");
            return `<tr class="${{rowClass}}" data-round="${{row["Round"] ?? ""}}">${{cells}}</tr>`;
          }}).join("") || `<tr><td class="table-empty" colspan="${{Math.max(columns.length, 1)}}">No data available.</td></tr>`;
          container.innerHTML = `<div class="table-wrap"><table class="interactive-table"><thead><tr>${{headerHtml}}</tr></thead><tbody>${{bodyHtml}}</tbody></table></div>`;
          container.querySelectorAll("th[data-column]").forEach((header) => {{
            header.addEventListener("click", () => {{
              const column = header.dataset.column;
              if (state.sortKey === column) {{
                state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
              }} else {{
                state.sortKey = column;
                state.sortDir = "asc";
              }}
              if (containerId === "round-table") {{
                renderRoundTable();
              }} else {{
                renderResidentTable();
              }}
            }});
          }});
          if (containerId === "round-table") {{
            container.querySelectorAll("tbody tr[data-round]").forEach((row) => {{
              row.addEventListener("click", () => {{
                const round = Number(row.dataset.round);
                if (!Number.isNaN(round)) setCurrentRound(round);
              }});
            }});
          }}
        }}

        function roundRecord(round) {{
          return roundRecords.find((row) => Number(row["Round"]) === Number(round)) || null;
        }}

        function residentRows(round) {{
          return residentByRound[String(round)] || [];
        }}

        function visibleRoundRecords() {{
          return roundRecords
            .filter((row) => Number(row["Round"]) <= Number(currentRound))
            .sort((left, right) => Number(left["Round"]) - Number(right["Round"]));
        }}

        function currentRoundRecord() {{
          const rows = visibleRoundRecords();
          return rows.length ? rows[rows.length - 1] : null;
        }}

        function activeTrace(rows, column, name, color, hovertemplate, options = {{}}) {{
          return {{
            x: rows.map((row) => row["Round"]),
            y: rows.map((row) => row[column]),
            type: "scatter",
            mode: "lines+markers",
            line: {{ color, width: options.width || 3, dash: options.dash || "solid" }},
            marker: {{
              size: options.markerSize || 8,
              color,
              line: {{ color: "#ffffff", width: 1.6 }}
            }},
            name,
            hovertemplate
          }};
        }}

        function currentMarkerTrace(row, column, color, hovertemplate, options = {{}}) {{
          if (!row) return null;
          const value = row[column];
          if (value === null || value === undefined || value === "" || Number.isNaN(value)) return null;
          return {{
            x: [row["Round"]],
            y: [value],
            type: "scatter",
            mode: "markers",
            marker: {{
              size: options.size || 12,
              color,
              line: {{ color: "#ffffff", width: 2.5 }}
            }},
            hoverinfo: "skip",
            showlegend: false
          }};
        }}

        function renderExternalLegend(containerId, items) {{
          const container = document.getElementById(containerId);
          if (!container) return;
          const html = (items || []).map((item) => `
            <div class="chart-legend-item">
              <span class="chart-legend-dot" style="background:${{item.color}};"></span>
              <span class="chart-legend-label">${{item.label}}</span>
            </div>
          `).join("");
          container.innerHTML = html;
        }}

        function baseLayout(title, yaxisTitle, options = {{}}) {{
          const minRound = roundValues.length ? Math.min(...roundValues) : 0;
          const maxRound = roundValues.length ? Math.max(...roundValues) : 0;
          return {{
            margin: {{ l: 54, r: 14, t: 12, b: 36 }},
            height: options.height || 240,
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            hovermode: "x unified",
            xaxis: {{
              title: {{ text: "Round", standoff: 10 }},
              gridcolor: "#f1f5f9",
              zeroline: false,
              automargin: true,
              tickmode: "array",
              tickvals: roundValues,
              range: [minRound - 0.2, maxRound + 0.2]
            }},
            yaxis: {{
              title: {{ text: yaxisTitle, standoff: 12 }},
              gridcolor: "#f1f5f9",
              zeroline: false,
              automargin: true,
              rangemode: options.rangemode || "normal"
            }},
            font: {{ family: "Microsoft YaHei, PingFang SC, sans-serif", size: 13, color: "#4b5563" }},
            showlegend: false,
          }};
        }}

        function bindChartNavigation(chartId) {{
          const chart = document.getElementById(chartId);
          if (!chart || !chart.on || chart.dataset.roundBinding === "true") return;
          chart.on("plotly_click", (event) => {{
            if (event.points && event.points.length) {{
              const round = Number(event.points[0].x);
              if (!Number.isNaN(round)) {{
                stopPlayback();
                setCurrentRound(round);
              }}
            }}
          }});
          chart.dataset.roundBinding = "true";
        }}

        function renderCharts() {{
          if (!roundRecords.length) return;
          const visibleRounds = visibleRoundRecords();
          const currentRow = currentRoundRecord();
          const agreementTraces = [
            activeTrace(
              visibleRounds,
              "Agreement Rate",
              "Agreement Rate",
              "#36AABF",
              "Round %{{x}}<br>Agreement Rate: %{{y:.1%}}<extra></extra>"
            ),
            currentMarkerTrace(
              currentRow,
              "Agreement Rate",
              "#15803d",
              "Current Round %{{x}}<br>Agreement Rate: %{{y:.1%}}<extra></extra>"
            )
          ].filter(Boolean);
          renderExternalLegend("agreement-legend", [
            {{ label: "Agreement Rate", color: "#36AABF" }}
          ]);
          Plotly.react("agreement-chart", agreementTraces, baseLayout("Agreement Rate", "Agreement Rate", {{ rangemode: "tozero", height: 198 }}), {{ displayModeBar: false, responsive: true }});

          const policyTraces = [
            activeTrace(
              visibleRounds,
              "Planner Extension Ratio",
              "Extension Ratio",
              "#55B6C8",
              "Round %{{x}}<br>Extension Ratio: %{{y:.1%}}<extra></extra>"
            ),
            activeTrace(
              visibleRounds,
              "Planner Subsidy Ratio",
              "Subsidy Ratio",
              "#f97316",
              "Round %{{x}}<br>Subsidy Ratio: %{{y:.1%}}<extra></extra>"
            ),
            currentMarkerTrace(
              currentRow,
              "Planner Extension Ratio",
              "#36AABF",
              "Current Round %{{x}}<br>Extension Ratio: %{{y:.1%}}<extra></extra>"
            ),
            currentMarkerTrace(
              currentRow,
              "Planner Subsidy Ratio",
              "#ea580c",
              "Current Round %{{x}}<br>Subsidy Ratio: %{{y:.1%}}<extra></extra>"
            )
          ].filter(Boolean);
          renderExternalLegend("policy-legend", [
            {{ label: "Extension Ratio", color: "#55B6C8" }},
            {{ label: "Subsidy Ratio", color: "#f97316" }}
          ]);
          Plotly.react("policy-chart", policyTraces, baseLayout("Planner Policy", "Ratio", {{ rangemode: "tozero", height: 198 }}), {{ displayModeBar: false, responsive: true }});

          const pricingTraces = [
            activeTrace(
              visibleRounds,
              "Developer Base Price",
              "Developer Base Price",
              "#111827",
              "Round %{{x}}<br>Developer Base Price: ¥%{{y:,.0f}}<extra></extra>"
            ),
            activeTrace(
              visibleRounds,
              "Developer Extension Price",
              "Developer Extension Price",
              "#7c3aed",
              "Round %{{x}}<br>Developer Extension Price: ¥%{{y:,.0f}}<extra></extra>"
            ),
            activeTrace(
              visibleRounds,
              "Avg Expected Base Price",
              "Resident Expected Base Price",
              "#36AABF",
              "Round %{{x}}<br>Resident Expected Base Price: ¥%{{y:,.0f}}<extra></extra>",
              {{ width: 2.5, markerSize: 6, dash: "dot" }}
            ),
            activeTrace(
              visibleRounds,
              "Avg Expected Extension Price",
              "Resident Expected Extension Price",
              "#ef4444",
              "Round %{{x}}<br>Resident Expected Extension Price: ¥%{{y:,.0f}}<extra></extra>",
              {{ width: 2.5, markerSize: 6, dash: "dot" }}
            ),
            currentMarkerTrace(
              currentRow,
              "Developer Base Price",
              "#111827",
              "Current Round %{{x}}<br>Developer Base Price: ¥%{{y:,.0f}}<extra></extra>"
            ),
            currentMarkerTrace(
              currentRow,
              "Developer Extension Price",
              "#7c3aed",
              "Current Round %{{x}}<br>Developer Extension Price: ¥%{{y:,.0f}}<extra></extra>"
            ),
            currentMarkerTrace(
              currentRow,
              "Avg Expected Base Price",
              "#268CA0",
              "Current Round %{{x}}<br>Resident Expected Base Price: ¥%{{y:,.0f}}<extra></extra>",
              {{ size: 10 }}
            ),
            currentMarkerTrace(
              currentRow,
              "Avg Expected Extension Price",
              "#dc2626",
              "Current Round %{{x}}<br>Resident Expected Extension Price: ¥%{{y:,.0f}}<extra></extra>",
              {{ size: 10 }}
            )
          ].filter(Boolean);
          renderExternalLegend("pricing-legend", [
            {{ label: "Developer Base Price", color: "#111827" }},
            {{ label: "Developer Extension Price", color: "#7c3aed" }},
            {{ label: "Resident Expected Base Price", color: "#36AABF" }},
            {{ label: "Resident Expected Extension Price", color: "#ef4444" }}
          ]);
          Plotly.react("pricing-chart", pricingTraces, baseLayout("Offers vs Expectations", "Price", {{ height: 198 }}), {{ displayModeBar: false, responsive: true }});

          ["agreement-chart", "policy-chart", "pricing-chart"].forEach(bindChartNavigation);
        }}

        function renderRoundPills() {{
          roundPills.innerHTML = roundValues.map((round) => `
            <button type="button" class="round-pill${{Number(round) === Number(currentRound) ? " active" : ""}}" data-round="${{round}}">Round ${{round}}</button>
          `).join("");
          roundPills.querySelectorAll("button[data-round]").forEach((button) => {{
            button.addEventListener("click", () => {{
              stopPlayback();
              setCurrentRound(Number(button.dataset.round));
            }});
          }});
        }}

        function renderRoundTable() {{
          const visibleRows = visibleRoundRecords();
          renderTable("round-table", visibleRows, roundState, {{
            columns: roundRecords.length ? Object.keys(roundRecords[0]) : [],
            highlightRound: currentRound
          }});
        }}

        function renderResidentTable() {{
          renderTable("resident-table", residentRows(currentRound), residentState, {{
            columns: residentRows(currentRound).length ? Object.keys(residentRows(currentRound)[0]) : [],
            searchable: true
          }});
        }}

        function syncTimelineUi() {{
          badge.textContent = currentRound ? `Round ${{currentRound}}` : "Round -";
          const sliderIndex = Math.max(roundValues.indexOf(Number(currentRound)), 0);
          slider.value = sliderIndex;
          renderRoundPills();
        }}

        function setCurrentRound(round) {{
          if (!roundValues.length) return;
          const nextRound = Number(round);
          if (!roundValues.includes(nextRound)) return;
          currentRound = nextRound;
          syncTimelineUi();
          renderCharts();
          renderRoundTable();
          renderResidentTable();
        }}

        function stopPlayback() {{
          playing = false;
          playButton.textContent = "Play";
          if (timerId) {{
            window.clearInterval(timerId);
            timerId = null;
          }}
        }}

        function startPlayback() {{
          if (!roundValues.length) return;
          playing = true;
          playButton.textContent = "Pause";
          timerId = window.setInterval(() => {{
            const currentIndex = roundValues.indexOf(Number(currentRound));
            if (currentIndex >= roundValues.length - 1) {{
              stopPlayback();
              return;
            }}
            setCurrentRound(roundValues[currentIndex + 1]);
          }}, 1100);
        }}

        playButton.addEventListener("click", () => {{
          if (playing) {{
            stopPlayback();
          }} else {{
            startPlayback();
          }}
        }});

        slider.addEventListener("input", () => {{
          const nextRound = roundValues[Number(slider.value)];
          stopPlayback();
          if (nextRound !== undefined) setCurrentRound(nextRound);
        }});

        residentSearch.addEventListener("input", (event) => {{
          residentState.search = event.target.value || "";
          renderResidentTable();
        }});

        if (roundValues.length) {{
          slider.max = String(Math.max(roundValues.length - 1, 0));
          const initialExistingRound = roundValues.includes(Number(currentRound)) ? Number(currentRound) : roundValues[roundValues.length - 1];
          setCurrentRound(initialExistingRound);
        }} else {{
          badge.textContent = "No rounds";
          document.getElementById("agreement-chart").innerHTML = '<div class="chart-empty">No round history available.</div>';
          document.getElementById("policy-chart").innerHTML = '<div class="chart-empty">No round history available.</div>';
          document.getElementById("pricing-chart").innerHTML = '<div class="chart-empty">No round history available.</div>';
          renderRoundTable();
          renderResidentTable();
        }}
      }})();
    </script>
    """


def _phase2_result_pairs(row: pd.Series | None, log_data: dict[str, Any], seed: str | None, sample_count: int, phase2_root: str | None = None) -> list[tuple[str, str]]:
    final_metrics = log_data.get("final_metrics", {}) or {}
    community_info = log_data.get("community_info", {}) or {}
    computed_objectives: dict[str, Any] = {}
    try:
        root_obj = Path(_resolve_app_path(str(phase2_root or DEFAULT_PHASE2_ROOT)))
        log_path_value = row.get("log_path") if row is not None and "log_path" in row else ""
        log_path_obj = Path(str(log_path_value)) if log_path_value else None
        if log_path_obj is not None and not log_path_obj.is_absolute():
            candidate = root_obj / log_path_obj
            log_path_obj = candidate if candidate.exists() else log_path_obj
        if log_path_obj is None or not log_path_obj.exists():
            # The detail page already has the parsed raw log. Compute objectives anyway;
            # log_path is only needed for locating config/agent metadata, not for the
            # final-round resident decisions stored in the log itself.
            log_path_obj = root_obj
            run_cfg = {}
        else:
            run_cfg = _config_for_log_path(log_path_obj, root_obj)
        computed_objectives = _phase2_compute_objectives_from_log(log_data, log_path_obj, root_obj, run_cfg)
    except Exception:
        computed_objectives = {}

    def row_value(column: str, fallback: Any = np.nan) -> Any:
        if row is not None and column in row:
            value = row.get(column)
            try:
                if not pd.isna(value):
                    return value
            except Exception:
                if value not in (None, ""):
                    return value
        if column in computed_objectives:
            computed_value = computed_objectives.get(column)
            try:
                if not pd.isna(computed_value):
                    return computed_value
            except Exception:
                if computed_value not in (None, ""):
                    return computed_value
        return fallback

    threshold = row_value("threshold", community_info.get("required_agree_ratio"))
    is_success = row_value("is_success", np.nan)
    if pd.isna(_safe_float(is_success, np.nan)):
        final_agree_ratio = _safe_float(final_metrics.get("final_agree_ratio"), np.nan)
        threshold_float = _safe_float(threshold, np.nan)
        is_success = 1.0 if not pd.isna(final_agree_ratio) and not pd.isna(threshold_float) and final_agree_ratio >= threshold_float else (0.0 if not pd.isna(final_agree_ratio) and not pd.isna(threshold_float) else np.nan)

    developer_profit = row_value("developer_profit", final_metrics.get("final_profit"))
    developer_profit_rate = row_value("developer_profit_rate", final_metrics.get("final_profit_rate"))
    utility_gini = _safe_float(row_value("utility_gini", np.nan), np.nan)

    items = [
        ("Seed", seed or "Auto"),
        ("Required Threshold", _format_ratio(threshold)),
        ("Success", "Yes" if _safe_float(is_success, 0.0) >= 0.5 else "No"),
        ("Developer Profit", _format_currency(developer_profit)),
        ("Developer Profit Rate", _format_ratio(developer_profit_rate)),
        ("Resident Mean Utility", _format_currency(row_value("resident_mean_utility", np.nan))),
        ("Utility Gini", f"{utility_gini:.3f}" if not pd.isna(utility_gini) else "0.000"),
        ("Subsidy Total Cost", _format_currency(row_value("subsidy_total_cost", np.nan))),
        ("Samples In This Community", _format_number(sample_count)),
    ]
    return items


def _run_result_pairs(row: pd.Series | None, log_data: dict[str, Any]) -> list[tuple[str, str]]:
    final_metrics = log_data.get("final_metrics", {})
    return [
        ("Outcome", _humanize_identifier(log_data.get("outcome"))),
        ("Termination Reason", _humanize_identifier(log_data.get("termination_reason"))),
        ("Developer Profit", _format_currency(final_metrics.get("final_profit"))),
        ("Developer Profit Rate", _format_ratio(final_metrics.get("final_profit_rate"))),
        ("Generated Log", _display_path(row.get("log_path")) if row is not None and "log_path" in row else "N/A"),
    ]


def _build_log_summary_markdown(
    log_data: dict[str, Any],
    extra_lines: list[str] | None = None,
) -> str:
    community_name = _strip_str(log_data.get("community_info", {}).get("name"))
    final_metrics = log_data.get("final_metrics", {})
    planner = log_data.get("final_policy", {}).get("planner", {})
    developer = log_data.get("final_policy", {}).get("developer", {})

    lines = [
        f"### {community_name or 'Unnamed Community'}",
        "",
        f"- outcome: `{log_data.get('outcome', 'unknown')}`",
        f"- termination_reason: `{log_data.get('termination_reason', 'unknown')}`",
        f"- rounds: `{log_data.get('rounds', 0)}`",
        f"- final_agree_ratio: `{_format_ratio(final_metrics.get('final_agree_ratio'))}`",
        f"- planner.extension_ratio: `{_format_ratio(planner.get('extension_ratio'))}`",
        f"- planner.cash_subsidy_ratio: `{_format_ratio(planner.get('cash_subsidy_ratio'))}`",
        f"- developer.base_price: `{_format_currency(developer.get('base_price'))}`",
        f"- developer.extension_price: `{_format_currency(developer.get('extension_price'))}`",
        f"- developer.parking_fee: `{_format_currency(developer.get('parking_fee'))}`",
        f"- developer.profit: `{_format_currency(final_metrics.get('final_profit'))}`",
        f"- developer.profit_rate: `{_format_ratio(final_metrics.get('final_profit_rate'))}`",
    ]
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def _phase2_rule_choices(global_df: pd.DataFrame) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for rank, row in global_df.reset_index(drop=True).iterrows():
        community_count = _safe_int(row.get("community_count"), 0)
        run_count = _safe_int(row.get("run_count"), 0)
        sample_text = f" | {community_count} communities"
        if run_count > 0:
            sample_text += f" | {run_count} runs averaged"
        label = (
            f"#{rank + 1} {_phase2_rule_content_text(row)} | "
            f"success={_safe_float(row.get('success_rate'), np.nan):.1%}{sample_text}"
        )
        choices.append((label, str(row["rule_id"])))
    return choices


def _phase2_policy_text_short_name(policy_text: Any) -> str:
    text = _strip_str(policy_text).replace("\n", " ").strip()
    if not text:
        return ""
    parts = re.findall(r"[A-Za-z0-9_\-]+|[\u4e00-\u9fff]", text)
    return parts[0] if parts else text.split()[0]


def _phase2_rule_content_text(row: pd.Series | None) -> str:
    if row is None:
        return "N/A"
    base = _policy_rule_content(row.get("extension_cap"), row.get("subsidy_cap"))
    natural_short = _phase2_policy_text_short_name(row.get("planner_soft_policy_text")) if "planner_soft_policy_text" in row else ""
    if natural_short:
        return f"{base} · NL policy: {natural_short}"

    content = _strip_str(row.get("rule_content")) if "rule_content" in row else ""
    if content:
        match = re.search(r"(.*?\bNL policy:\s*)(.+)$", content, flags=re.IGNORECASE)
        if match:
            short = _phase2_policy_text_short_name(match.group(2))
            if short:
                return f"{match.group(1)}{short}"
        return content
    return base


def _phase2_rule_display_text(row: pd.Series | None) -> str:
    if row is None:
        return "N/A"
    return _phase2_rule_content_text(row)


def _phase2_rule_hint_text(row: pd.Series | None) -> str:
    if row is None:
        return "Policy search rule currently in view"
    return f"Success rate {row['success_rate']:.1%}"


def _format_comparison_value(metric: str, value: Any) -> str:
    if metric == "weighted_score":
        return "N/A" if value is None or pd.isna(value) else f"{float(value) * 100:.1f}/100"
    config = COMPARISON_METRICS.get(metric, {})
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    if config.get("format") == "ratio":
        return f"{value:.1%}"
    if config.get("format") == "currency":
        return f"¥{value:,.0f}"
    if config.get("format") == "float":
        return f"{value:.3f}"
    return f"{value:,.3f}"


def _multi_option_html(options: list[tuple[str, str]], selected_values: list[str] | tuple[str, ...]) -> str:
    selected = {str(value) for value in selected_values}
    chunks = []
    for label, value in options:
        is_selected = " selected" if str(value) in selected else ""
        chunks.append(f'<option value="{html.escape(str(value))}"{is_selected}>{html.escape(str(label))}</option>')
    return "\n".join(chunks)


def _multi_checklist_html(
    group_id: str,
    field_name: str,
    options: list[tuple[str, str]],
    selected_values: list[str] | tuple[str, ...],
    search_placeholder: str,
) -> str:
    selected = {str(value) for value in selected_values}
    items = []
    for label, value in options:
        checked = " checked" if str(value) in selected else ""
        label_text = str(label)
        value_text = str(value)
        items.append(
            f"""
            <label class="multi-check-item" data-filter="{html.escape((label_text + ' ' + value_text).lower())}">
              <input type="checkbox" name="{html.escape(field_name)}" value="{html.escape(value_text)}"{checked} />
              <span class="multi-check-copy">{html.escape(label_text)}</span>
            </label>
            """
        )
    return f"""
    <div class="multi-check-card" id="{html.escape(group_id)}">
      <div class="multi-check-toolbar">
        <input class="multi-check-search" type="search" placeholder="{html.escape(search_placeholder)}" />
        <div class="multi-check-actions">
          <button type="button" class="mini-button" data-action="all">Select all</button>
          <button type="button" class="mini-button" data-action="clear">Clear</button>
        </div>
      </div>
      <div class="multi-check-summary"><span class="multi-check-count">0</span> selected</div>
      <div class="multi-check-list">
        {''.join(items)}
      </div>
    </div>
    """


def _segmented_links_html(
    base_path: str,
    param_name: str,
    options: list[tuple[str, str]],
    current_value: str,
    params: dict[str, Any],
) -> str:
    chips = []
    for label, value in options:
        next_params = dict(params)
        next_params[param_name] = value
        chips.append(
            f'<a class="seg-button{" active" if value == current_value else ""}" '
            f'href="{base_path}?{urlencode(next_params, doseq=True)}">{html.escape(label)}</a>'
        )
    return f'<div class="seg-group metric-switch-list">{"".join(chips)}</div>'


@lru_cache(maxsize=16)
def _load_phase2_policy_community_pairs(phase2_root: str) -> pd.DataFrame:
    raw = _load_phase2_community_results(phase2_root).copy()
    required = {"rule_id", "community_name"}
    if raw.empty or not required.issubset(raw.columns):
        return pd.DataFrame()
    if "seed" not in raw.columns:
        raw["seed"] = np.nan
    for column in [
        "rule_content",
        "planner_soft_policy_text",
        "threshold",
        "is_success",
        "final_agree_ratio",
        "developer_profit",
        "resident_mean_utility",
        "utility_gini",
        "subsidy_total_cost",
        "extension_ratio_final",
        "cash_subsidy_ratio_final",
    ]:
        if column not in raw.columns:
            raw[column] = "" if column in {"rule_content", "planner_soft_policy_text"} else np.nan
    grouped = (
        raw.groupby(["rule_id", "community_name"], as_index=False)
        .agg(
            sample_count=("seed", "count"),
            rule_content=("rule_content", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            planner_soft_policy_text=("planner_soft_policy_text", lambda values: next((_strip_str(v) for v in values if _strip_str(v)), "")),
            threshold=("threshold", "mean"),
            success_rate=("is_success", "mean"),
            final_agree_ratio=("final_agree_ratio", "mean"),
            developer_profit=("developer_profit", "mean"),
            resident_mean_utility=("resident_mean_utility", "mean"),
            utility_gini=("utility_gini", "mean"),
            subsidy_total_cost=("subsidy_total_cost", "mean"),
            extension_ratio_final=("extension_ratio_final", "mean"),
            cash_subsidy_ratio_final=("cash_subsidy_ratio_final", "mean"),
        )
        .sort_values(["rule_id", "community_name"])
        .reset_index(drop=True)
    )
    global_df = _load_phase2_global_results(phase2_root)
    if not global_df.empty and "rule_id" in global_df.columns:
        global_cols = [
            column
            for column in ["rule_id", "success_rate", "community_count", "run_count", "extension_cap", "subsidy_cap", "rule_content", "planner_soft_policy_text"]
            if column in global_df.columns
        ]
        grouped = grouped.merge(
            global_df[global_cols],
            on="rule_id",
            how="left",
            suffixes=("", "_global"),
        )
    grouped = _apply_phase2_rule_caps(grouped, phase2_root)
    computed_rule_content = grouped.apply(lambda row: _policy_rule_content(row.get("extension_cap"), row.get("subsidy_cap")), axis=1)
    if "rule_content_global" in grouped.columns:
        local_content = grouped.get("rule_content", pd.Series([""] * len(grouped), index=grouped.index)).map(_strip_str)
        global_content = grouped["rule_content_global"].map(_strip_str)
        grouped["rule_content"] = local_content.where(local_content.astype(bool), global_content)
    if "rule_content" in grouped.columns:
        existing_rule_content = grouped["rule_content"].map(_strip_str)
        grouped["rule_content"] = existing_rule_content.where(existing_rule_content.astype(bool), computed_rule_content)
    else:
        grouped["rule_content"] = computed_rule_content
    grouped["rule_display"] = grouped.apply(_phase2_rule_content_text, axis=1)
    grouped["rule_content"] = grouped["rule_display"]
    return grouped


def _pareto_status(series_df: pd.DataFrame, metric_keys: list[str]) -> pd.Series:
    if series_df.empty:
        return pd.Series(dtype=object)
    values = series_df[metric_keys].apply(pd.to_numeric, errors="coerce")
    complete_mask = values.notna().all(axis=1).to_numpy()
    statuses = np.full(len(series_df), "Incomplete", dtype=object)
    if not complete_mask.any():
        return pd.Series(statuses, index=series_df.index)

    complete_indices = np.where(complete_mask)[0]
    matrix = values.to_numpy(dtype=float)
    pareto_mask = np.ones(len(series_df), dtype=bool)
    epsilon = 1e-12

    for i in complete_indices:
        for j in complete_indices:
            if i == j:
                continue
            better_or_equal = True
            strictly_better = False
            for metric in metric_keys:
                goal = COMPARISON_METRICS[metric]["goal"]
                left = matrix[i, values.columns.get_loc(metric)]
                right = matrix[j, values.columns.get_loc(metric)]
                if goal == "max":
                    if right + epsilon < left:
                        better_or_equal = False
                        break
                    if right > left + epsilon:
                        strictly_better = True
                else:
                    if right > left + epsilon:
                        better_or_equal = False
                        break
                    if right + epsilon < left:
                        strictly_better = True
            if better_or_equal and strictly_better:
                pareto_mask[i] = False
                break

    statuses[complete_mask] = np.where(pareto_mask[complete_mask], "Pareto-optimal", "Dominated")
    return pd.Series(statuses, index=series_df.index)


def _weighted_scores(series_df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    if series_df.empty:
        return pd.Series(dtype=float)

    metric_keys = [metric for metric in COMPARISON_METRICS if metric in series_df.columns]
    if not metric_keys:
        return pd.Series(np.nan, index=series_df.index, dtype=float)

    raw_weights = {metric: max(_safe_float(weights.get(metric), 1.0), 0.0) for metric in metric_keys}
    if sum(raw_weights.values()) <= 0:
        raw_weights = {metric: 1.0 for metric in metric_keys}

    values = series_df[metric_keys].apply(pd.to_numeric, errors="coerce")
    normalized = pd.DataFrame(index=values.index)
    epsilon = 1e-12

    for metric in metric_keys:
        series = values[metric]
        valid = series.dropna()
        if valid.empty:
            normalized[metric] = np.nan
            continue
        lower = float(valid.min())
        upper = float(valid.max())
        span = upper - lower
        if span <= epsilon:
            normalized[metric] = series.map(lambda value: 1.0 if pd.notna(value) else np.nan)
            continue

        if COMPARISON_METRICS[metric]["goal"] == "max":
            normalized[metric] = (series - lower) / span
        else:
            normalized[metric] = (upper - series) / span

    normalized = normalized.clip(lower=0.0, upper=1.0)
    weight_series = pd.Series(raw_weights, dtype=float)
    valid_rows = normalized.notna().all(axis=1)
    scores = pd.Series(np.nan, index=series_df.index, dtype=float)
    if valid_rows.any():
        scores.loc[valid_rows] = (
            normalized.loc[valid_rows, metric_keys].mul(weight_series, axis=1).sum(axis=1) / float(weight_series.sum())
        )
    return scores


def _phase2_comparison_dataset(
    phase2_root: str,
    selected_rule_ids: list[str],
    selected_communities: list[str],
    mode: str,
) -> pd.DataFrame:
    pair_df = _load_phase2_policy_community_pairs(phase2_root).copy()
    if selected_rule_ids:
        pair_df = pair_df[pair_df["rule_id"].isin(selected_rule_ids)]
    if selected_communities:
        pair_df = pair_df[pair_df["community_name"].isin(selected_communities)]
    if pair_df.empty:
        return pair_df

    metric_columns = list(COMPARISON_METRICS.keys())
    if mode == "aggregate_policy":
        aggregated = (
            pair_df.groupby(["rule_id", "rule_content", "rule_display", "extension_cap", "subsidy_cap"], as_index=False, dropna=False)
            .agg(
                community_count=("community_name", "nunique"),
                selected_success_rate=("success_rate", "mean"),
                **{metric: (metric, "mean") for metric in metric_columns},
            )
            .sort_values(["rule_id"])
            .reset_index(drop=True)
        )
        return aggregated

    pair_df = pair_df.sort_values(["rule_id", "community_name"]).reset_index(drop=True)
    return pair_df


def _summarize_phase2_rule(phase2_root: str, rule_id: str) -> pd.DataFrame:
    raw = _annotate_phase2_policy_groups(_load_phase2_community_results(phase2_root))
    if raw.empty:
        return pd.DataFrame()
    filter_col = "policy_rule_id" if "policy_rule_id" in raw.columns else "rule_id"
    raw = raw.loc[raw[filter_col].astype(str) == str(rule_id)].copy()
    if raw.empty:
        return pd.DataFrame()
    for column in ["final_agree_ratio", "extension_ratio_final", "cash_subsidy_ratio_final", "resident_mean_utility", "utility_gini", "seed"]:
        if column not in raw.columns:
            raw[column] = np.nan
    summary = (
        raw.groupby("community_name", as_index=False)
        .agg(
            final_agree_ratio=("final_agree_ratio", "mean"),
            avg_extension_ratio=("extension_ratio_final", "mean"),
            avg_subsidy_ratio=("cash_subsidy_ratio_final", "mean"),
            resident_mean_utility=("resident_mean_utility", "mean"),
            utility_gini=("utility_gini", "mean"),
            run_count=("seed", "count"),
        )
        .sort_values("community_name")
        .reset_index(drop=True)
    )
    return summary


def _phase2_overview_markdown(
    phase2_root: str,
    global_df: pd.DataFrame,
    rule_id: str,
    summary_df: pd.DataFrame,
) -> str:
    selected_rule = global_df.loc[global_df["rule_id"] == rule_id].iloc[0]
    champion_rule = global_df.iloc[0]
    lines = [
        "### Experiment Overview",
        "",
        f"- result directory: `{_display_path(phase2_root)}`",
        f"- current rule: `{rule_id}`",
        f"- champion rule: `{champion_rule['rule_id']}`",
        f"- current rule success rate: `{selected_rule['success_rate']:.1%}`",
        f"- current rule extension cap: `{selected_rule['extension_cap']:.0%}`",
        f"- current rule subsidy cap: `{selected_rule['subsidy_cap']:.0%}`",
        f"- average final agreement rate: `{_format_ratio(summary_df['final_agree_ratio'].mean() if 'final_agree_ratio' in summary_df.columns and not summary_df.empty else np.nan)}`",
        f"- average final Extension Policy: `{_format_ratio(summary_df['avg_extension_ratio'].mean() if 'avg_extension_ratio' in summary_df.columns and not summary_df.empty else np.nan)}`",
        f"- average final Subsidy Policy: `{_format_ratio(summary_df['avg_subsidy_ratio'].mean() if 'avg_subsidy_ratio' in summary_df.columns and not summary_df.empty else np.nan)}`",
        f"- average fairness gini: `{selected_rule['avg_utility_gini']:.3f}`",
        f"- communities covered by the current map: `{len(summary_df)}`",
    ]
    return "\n".join(lines)


def _phase2_rule_table(global_df: pd.DataFrame) -> pd.DataFrame:
    table = global_df.copy()
    table["success_rate"] = table["success_rate"].map(lambda v: f"{v:.1%}")
    table["extension_cap"] = table["extension_cap"].map(lambda v: f"{v:.0%}")
    table["subsidy_cap"] = table["subsidy_cap"].map(lambda v: f"{v:.0%}")
    table["avg_utility_gini"] = table["avg_utility_gini"].map(lambda v: f"{v:.3f}")
    table["total_subsidy_cost"] = table["total_subsidy_cost"].map(lambda v: f"{v:,.0f}")
    return table


def _community_summary_table(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()
    table = summary_df.copy()
    rename_map = {
        "community_name": "Community",
        "final_agree_ratio": "Final Agreement Rate",
        "avg_extension_ratio": "Final Extension Policy",
        "avg_subsidy_ratio": "Final Subsidy Policy",
        "resident_mean_utility": "Resident Mean Utility",
        "utility_gini": "Utility Gini",
        "run_count": "Sample Count",
    }
    table = table.rename(columns=rename_map)
    for column in ["Final Agreement Rate", "Final Extension Policy", "Final Subsidy Policy"]:
        if column in table.columns:
            table[column] = table[column].map(_format_ratio)
    for column in ["Resident Mean Utility"]:
        if column in table.columns:
            table[column] = table[column].map(_format_currency)
    if "Utility Gini" in table.columns:
        table["Utility Gini"] = table["Utility Gini"].map(lambda v: f"{v:.3f}")
    return table


def _phase2_seed_table(seed_df: pd.DataFrame) -> pd.DataFrame:
    if seed_df.empty:
        return pd.DataFrame()
    table = seed_df.copy()
    rename_map = {
        "community_name": "Community",
        "seed": "Seed",
        "threshold": "Threshold",
        "is_success": "Success",
        "final_agree_ratio": "Final Agreement Rate",
        "avg_extension_ratio": "Final Extension Policy",
        "avg_subsidy_ratio": "Final Subsidy Policy",
        "developer_profit": "Developer Profit",
        "developer_profit_rate": "Developer Profit Rate",
        "resident_mean_utility": "Resident Mean Utility",
        "low_income_mean_utility": "Low-income Resident Mean Utility",
        "utility_std": "Utility Std Dev",
        "utility_gini": "Utility Gini",
        "subsidy_total_cost": "Total Subsidy Cost",
        "community_result_path": "community_result.json",
        "log_path": "negotiation_log",
    }
    table = table.rename(columns=rename_map)
    for column in ["Threshold", "Final Agreement Rate", "Final Extension Policy", "Final Subsidy Policy", "Developer Profit Rate"]:
        if column in table.columns:
            table[column] = table[column].map(_format_ratio)
    if "Success" in table.columns:
        table["Success"] = table["Success"].map(lambda v: "Yes" if _safe_float(v, 0.0) >= 0.5 else "No")
    for column in ["Developer Profit", "Resident Mean Utility", "Low-income Resident Mean Utility", "Total Subsidy Cost"]:
        if column in table.columns:
            table[column] = table[column].map(_format_currency)
    for column in ["Utility Std Dev", "Utility Gini"]:
        if column in table.columns:
            table[column] = table[column].map(lambda v: f"{_safe_float(v, np.nan):.3f}" if not pd.isna(v) else "N/A")
    return table


def _make_phase2_global_url(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    metric: str,
    seed: str | None = None,
    embedded: bool = False,
) -> str:
    query = {
        "phase2_root": phase2_root,
        "rule_id": rule_id,
        "metric": metric,
    }
    if boundary_path:
        query["boundary_path"] = boundary_path
    if seed:
        query["seed"] = seed
    if embedded:
        query["embedded"] = "1"
    return f"/phase2/global?{urlencode(query)}"


def _make_phase2_global_export_url(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    metric: str,
    seed: str | None = None,
) -> str:
    query = {
        "phase2_root": phase2_root,
        "rule_id": rule_id,
        "metric": metric,
    }
    if boundary_path:
        query["boundary_path"] = boundary_path
    if seed:
        query["seed"] = seed
    return f"/phase2/global/export?{urlencode(query)}"


def _make_phase2_community_url(
    phase2_root: str,
    boundary_path: str | None,
    rule_id: str,
    community_name: str | None,
    seed: str | None,
) -> str | None:
    if not community_name:
        return None
    query = {
        "phase2_root": phase2_root,
        "rule_id": rule_id,
        "community_name": community_name,
    }
    if boundary_path:
        query["boundary_path"] = boundary_path
    if seed:
        query["seed"] = seed
    return f"/phase2/community?{urlencode(query)}"


def _save_run_metadata(payload: dict[str, Any]) -> str:
    run_id = f"run_{_timestamp()}_{os.getpid()}"
    target = RUN_METADATA_DIR / f"{run_id}.json"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return run_id


def _load_run_metadata(run_id: str) -> dict[str, Any]:
    target = RUN_METADATA_DIR / f"{run_id}.json"
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_run_global_url(run_id: str, metric: str = "final_agree_ratio") -> str:
    return f"/run/global?{urlencode({'run_id': run_id, 'metric': metric})}"


def _make_run_global_export_url(run_id: str, metric: str = "final_agree_ratio") -> str:
    return f"/run/global/export?{urlencode({'run_id': run_id, 'metric': metric})}"


def _make_run_community_url(run_id: str, community_name: str | None) -> str | None:
    if not community_name:
        return None
    return f"/run/community?{urlencode({'run_id': run_id, 'community_name': community_name})}"


def _make_preview_global_url(
    community_csv_path: str,
    boundary_path: str | None,
) -> str:
    query = {"community_csv_path": community_csv_path}
    if boundary_path:
        query["boundary_path"] = boundary_path
    return f"/preview/global?{urlencode(query)}"


def _make_run_setup_url(embedded: bool = False) -> str:
    query = {}
    if embedded:
        query["embedded"] = "1"
    return f"/run/setup?{urlencode(query)}" if query else "/run/setup"


def _ensure_upload_cache_dir() -> Path:
    UPLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_CACHE_DIR


def _save_uploaded_run_file(file: UploadFile, bundle_dir: Path | None = None) -> Path:
    target_dir = bundle_dir or _ensure_upload_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file.filename
    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return target_path.resolve()


def _save_uploaded_shapefile_bundle(files: list[UploadFile]) -> Path:
    bundle_dir = _ensure_upload_cache_dir() / f"shp_bundle_{_timestamp()}_{os.getpid()}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        _save_uploaded_run_file(f, bundle_dir=bundle_dir)
    return bundle_dir.resolve()


def _links_html(global_url: str | None, community_url: str | None, community_name: str | None) -> str:
    global_link = (
        f'<a class="nav-link" href="{global_url}" target="_blank">Open Global Results</a>'
        if global_url
        else '<span class="nav-link disabled">Global results unavailable</span>'
    )
    community_link = (
        f'<a class="nav-link" href="{community_url}" target="_blank">Open {community_name} Detail</a>'
        if community_url and community_name
        else '<span class="nav-link disabled">Select a community first</span>'
    )
    return (
        '<div class="link-bar">'
        f"{global_link}{community_link}"
        "</div>"
    )


def _iframe_html(url: str | None, empty_text: str, height: int = 760, frameless: bool = False) -> str:
    if not url:
        return (
            '<div class="iframe-empty">'
            f"<div>{empty_text}</div>"
            "</div>"
        )
    return (
        f'<div class="iframe-wrap{" frameless" if frameless else ""}">'
        f'<iframe src="{url}" title="interactive-map" '
        f'style="width:100%;height:{height}px;border:0;border-radius:18px;background:#fff;"></iframe>'
        "</div>"
    )


def _leaflet_tooltip_html(row: pd.Series) -> str:
    extra_lines: list[str] = [
        f"Rule: {row.get('rule_label', 'N/A') or 'N/A'}",
        f"Metric Value: {row.get('metric_display', 'N/A') or 'N/A'}",
    ]
    if not row.get("has_data"):
        extra_lines.append("Status: No result available")
    else:
        extra_lines.extend(
            [
                f"Final Agreement Rate: {_format_ratio(row.get('final_agree_ratio'))}",
                f"Final Extension Policy: {_format_ratio(row.get('avg_extension_ratio'))}",
                f"Final Subsidy Policy: {_format_ratio(row.get('avg_subsidy_ratio'))}",
            ]
        )
        if row.get("threshold") is not None and not pd.isna(row.get("threshold")):
            extra_lines.append(f"Threshold: {_format_ratio(row.get('threshold'))}")
        if row.get("rounds") is not None and not pd.isna(row.get("rounds")):
            extra_lines.append(f"Discussion Rounds: {int(row.get('rounds'))}")
        if row.get("run_count") is not None and not pd.isna(row.get("run_count")):
            extra_lines.append(f"Samples: {int(row.get('run_count'))}")
    body = "<br/>".join(extra_lines)
    return (
        "<div style='font-size:13px;line-height:1.45;'>"
        f"<strong>{row['community_name']}</strong><br/>{body}"
        "</div>"
    )


def _leaflet_feature_collection(
    boundary_path: str | None,
    summary_df: pd.DataFrame,
    metric: str,
    detail_url_builder,
):
    if not boundary_path:
        return {}, [23.125, 113.265], 11, {
            "metric": metric,
            "metric_label": MAP_METRICS.get(metric, metric),
            "is_ratio": "ratio" in metric,
            "vmin": None,
            "vmax": None,
            "valid_count": 0,
            "gradient_colors": [],
        }

    boundary_gdf = _read_boundary(boundary_path).copy()
    if boundary_gdf.crs is None:
        boundary_gdf = boundary_gdf.set_crs("EPSG:4326")
    if not getattr(boundary_gdf.crs, "is_geographic", False):
        boundary_gdf = boundary_gdf.to_crs("EPSG:4326")

    merged = boundary_gdf.merge(summary_df, on="community_name", how="left")
    if metric in merged.columns:
        numeric = pd.to_numeric(merged[metric], errors="coerce")
    else:
        numeric = pd.Series(np.nan, index=merged.index, dtype=float)
    valid = numeric.dropna()
    cmap = plt.get_cmap("YlGnBu")
    norm = None
    if not valid.empty:
        vmin = float(valid.min())
        vmax = float(valid.max())
        if abs(vmax - vmin) < 1e-9:
            vmax = vmin + 1.0
        norm = Normalize(vmin=vmin, vmax=vmax)

    merged["fill_color"] = "#D1D5DB"
    if norm is not None:
        merged.loc[numeric.notna(), "fill_color"] = [
            to_hex(cmap(norm(float(value)))) for value in numeric[numeric.notna()]
        ]

    merged["has_data"] = numeric.notna()
    merged["metric_value_raw"] = numeric
    merged["metric_display"] = numeric.map(lambda value: _format_metric_value(metric, value))
    if "rule_label" in merged.columns:
        available_rules = merged["rule_label"].dropna().astype(str)
        default_rule = available_rules.iloc[0] if not available_rules.empty else ""
        if default_rule:
            merged["rule_label"] = merged["rule_label"].fillna(default_rule)
    merged["tooltip_html"] = merged.apply(_leaflet_tooltip_html, axis=1)
    merged["detail_url"] = merged.apply(
        lambda row: detail_url_builder(row["community_name"]) if row.get("has_data") else None,
        axis=1,
    )
    for optional_column in [
        "final_agree_ratio",
        "avg_extension_ratio",
        "avg_subsidy_ratio",
        "rounds",
        "run_count",
        "rule_label",
        "seed",
        "threshold",
    ]:
        if optional_column not in merged.columns:
            merged[optional_column] = np.nan
    feature_collection = json.loads(
        merged[
            [
                "community_name",
                "fill_color",
                "has_data",
                "tooltip_html",
                "detail_url",
                "metric_value_raw",
                "metric_display",
                "final_agree_ratio",
                "avg_extension_ratio",
                "avg_subsidy_ratio",
                "rule_label",
                "seed",
                "threshold",
                "rounds",
                "run_count",
                "geometry",
            ]
        ].to_json()
    )

    minx, miny, maxx, maxy = merged.total_bounds
    center = [(miny + maxy) / 2, (minx + maxx) / 2]
    overlay_meta = {
        "metric": metric,
        "metric_label": MAP_METRICS.get(metric, metric),
        "is_ratio": "ratio" in metric,
        "vmin": float(valid.min()) if not valid.empty else None,
        "vmax": float(valid.max()) if not valid.empty else None,
        "valid_count": int(valid.shape[0]),
        "gradient_colors": [to_hex(cmap(step)) for step in np.linspace(0.18, 0.95, 6)],
    }
    return feature_collection, center, 13, overlay_meta


def _leaflet_map_block(
    map_id: str,
    feature_collection: dict[str, Any],
    center: list[float],
    zoom: int,
    height: int = 760,
    overlay_meta: dict[str, Any] | None = None,
) -> str:
    geojson = json.dumps(feature_collection, ensure_ascii=False)
    overlay_spec = json.dumps(overlay_meta or {}, ensure_ascii=False)
    overlay_html = ""
    if overlay_meta:
        overlay_html = f"""
        <div class="map-overlay-card map-distribution-card">
          <div class="map-overlay-head">
            <div class="map-overlay-title">Metric Distribution</div>
            <div class="map-overlay-copy" id="{map_id}-distribution-copy"></div>
          </div>
          <div id="{map_id}-distribution" class="map-distribution-plot"></div>
        </div>
        <div class="map-overlay-card map-legend-card" id="{map_id}-legend"></div>
        """
    return f"""
    <div class="map-shell" style="height:{height}px;">
      <div id="{map_id}" class="map-canvas" style="width:100%;height:{height}px;border-radius:18px;overflow:hidden;border:1px solid #e2e8f0;background:linear-gradient(180deg,#f8fafc 0%,#eef2f7 100%);"></div>
      {overlay_html}
    </div>
    <link
      rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-sA+e2atf0z7Q6D0wPp1nHrvJp6k9bLrjR04xyKx0i0k="
      crossorigin=""
    />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    {'<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>' if overlay_meta else ''}
    <script>
      (function() {{
        const mapRoot = document.getElementById("{map_id}");
        const overlayMeta = {overlay_spec};
        const map = L.map("{map_id}", {{
          zoomControl: true,
          attributionControl: false,
          dragging: false,
          scrollWheelZoom: false,
          doubleClickZoom: false,
          boxZoom: false,
          keyboard: false,
          touchZoom: false,
          tap: false
        }});
        map.setView([{center[0]}, {center[1]}], {zoom});
        const geojson = {geojson};
        const tooltipId = "{map_id}-tooltip";
        let tooltip = document.getElementById(tooltipId);
        if (!tooltip) {{
          tooltip = document.createElement("div");
          tooltip.id = tooltipId;
          tooltip.style.position = "fixed";
          tooltip.style.zIndex = "9999";
          tooltip.style.pointerEvents = "none";
          tooltip.style.opacity = "0";
          tooltip.style.transform = "translateY(6px)";
          tooltip.style.transition = "opacity 120ms ease, transform 120ms ease";
          tooltip.style.maxWidth = "280px";
          tooltip.style.padding = "10px 12px";
          tooltip.style.borderRadius = "14px";
          tooltip.style.border = "1px solid rgba(148, 163, 184, 0.35)";
          tooltip.style.background = "rgba(255, 255, 255, 0.98)";
          tooltip.style.boxShadow = "0 18px 48px rgba(15, 23, 42, 0.18)";
          tooltip.style.color = "#0f172a";
          document.body.appendChild(tooltip);
        }}

        function positionTooltip(event) {{
          if (!event || !event.originalEvent) return;
          const offsetX = 18;
          const offsetY = 18;
          const tooltipWidth = tooltip.offsetWidth || 220;
          const tooltipHeight = tooltip.offsetHeight || 120;
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;
          const left = Math.min(
            Math.max(12, event.originalEvent.clientX + offsetX),
            Math.max(12, viewportWidth - tooltipWidth - 12)
          );
          const top = Math.min(
            Math.max(12, event.originalEvent.clientY + offsetY),
            Math.max(12, viewportHeight - tooltipHeight - 12)
          );
          tooltip.style.left = left + "px";
          tooltip.style.top = top + "px";
        }}

        function showTooltip(feature, event) {{
          if (!feature || !feature.properties || !feature.properties.tooltip_html) return;
          tooltip.innerHTML = feature.properties.tooltip_html;
          tooltip.style.opacity = "1";
          tooltip.style.transform = "translateY(0)";
          positionTooltip(event);
        }}

        function hideTooltip() {{
          tooltip.style.opacity = "0";
          tooltip.style.transform = "translateY(6px)";
        }}

        function formatOverlayValue(value) {{
          if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
          if (overlayMeta.is_ratio) return (Number(value) * 100).toFixed(1) + "%";
          return Number(value).toFixed(3);
        }}

        function renderMapOverlays() {{
          if (!overlayMeta || !Object.keys(overlayMeta).length) return;
          const legendRoot = document.getElementById("{map_id}-legend");
          const distributionRoot = document.getElementById("{map_id}-distribution");
          const distributionCopy = document.getElementById("{map_id}-distribution-copy");
          const values = (geojson.features || [])
            .map((feature) => feature?.properties?.metric_value_raw)
            .filter((value) => typeof value === "number" && !Number.isNaN(value));

          if (legendRoot) {{
            const stops = Array.isArray(overlayMeta.gradient_colors) ? overlayMeta.gradient_colors : [];
            const gradient = stops.length ? `linear-gradient(90deg, ${{stops.join(", ")}})` : "#d1d5db";
            legendRoot.innerHTML = `
              <div class="map-overlay-head">
                <div class="map-overlay-title">Map Legend</div>
                <div class="map-overlay-copy">${{overlayMeta.metric_label || "Selected Metric"}}</div>
              </div>
              <div class="map-legend-stack">
                <div class="map-legend-row">
                  <span class="map-swatch is-empty"></span>
                  <span>No result available</span>
                </div>
                <div class="map-legend-row is-gradient">
                  <span class="map-gradient-bar" style="background:${{gradient}};"></span>
                  <div class="map-gradient-labels">
                    <span>${{formatOverlayValue(overlayMeta.vmin)}}</span>
                    <span>${{formatOverlayValue(overlayMeta.vmax)}}</span>
                  </div>
                </div>
              </div>
            `;
          }}

          if (distributionCopy) {{
            distributionCopy.textContent = `${{values.length}} communities with results`;
          }}

          if (!distributionRoot) return;
          if (!values.length || !window.Plotly) {{
            distributionRoot.innerHTML = '<div class="map-mini-empty">No result values available.</div>';
            return;
          }}

          const tickFormat = overlayMeta.is_ratio ? ".0%" : null;
          Plotly.react(
            distributionRoot,
            [{{
              type: "histogram",
              x: values,
              nbinsx: Math.min(Math.max(values.length, 4), 10),
              marker: {{
                color: "#0f172a",
                line: {{ color: "#ffffff", width: 1.2 }},
              }},
              opacity: 0.92,
              hovertemplate: overlayMeta.is_ratio
                ? "Range: %{{x:.1%}}<br>Count: %{{y}}<extra></extra>"
                : "Range: %{{x:.3f}}<br>Count: %{{y}}<extra></extra>",
            }}],
            {{
              margin: {{ l: 34, r: 12, t: 8, b: 32 }},
              paper_bgcolor: "rgba(255,255,255,0)",
              plot_bgcolor: "#ffffff",
              bargap: 0.08,
              xaxis: {{
                title: "",
                gridcolor: "#f1f5f9",
                zeroline: false,
                tickformat: tickFormat,
                automargin: true,
              }},
              yaxis: {{
                title: "",
                gridcolor: "#f8fafc",
                zeroline: false,
                automargin: true,
              }},
              font: {{
                family: "Microsoft YaHei, PingFang SC, sans-serif",
                size: 11,
                color: "#475569",
              }},
              showlegend: false,
            }},
            {{ displayModeBar: false, responsive: true }}
          );
        }}

        function navigateToDetail(url) {{
          if (!url) return;
          try {{
            if (window.top && window.top !== window.self) {{
              window.top.location.href = url;
              return;
            }}
          }} catch (error) {{}}
          window.location.href = url;
        }}

        function styleFeature(feature) {{
          const hasData = feature.properties.has_data;
          return {{
            color: hasData ? "#64748b" : "#cbd5e1",
            weight: hasData ? 1.35 : 0.9,
            fillColor: feature.properties.fill_color || "#D1D5DB",
            fillOpacity: hasData ? 0.76 : 0.22
          }};
        }}

        function attachPathHandlers(layer, feature) {{
          const element = layer.getElement && layer.getElement();
          const clickable = Boolean(feature.properties.detail_url);
          if (!element || element.dataset.boundMapHandlers === "true") return;
          element.dataset.boundMapHandlers = "true";
          element.style.pointerEvents = "auto";
          element.style.cursor = clickable ? "pointer" : "default";
          if (clickable) {{
            element.addEventListener("click", (event) => {{
              event.preventDefault();
              event.stopPropagation();
              navigateToDetail(feature.properties.detail_url);
            }});
          }}
        }}

        function onEachFeature(feature, layer) {{
          const clickable = Boolean(feature.properties.detail_url);
          layer.on("add", function() {{
            attachPathHandlers(layer, feature);
          }});
          layer.on({{
            mouseover: function(e) {{
              e.target.setStyle({{
                weight: feature.properties.has_data ? 2.8 : 1.8,
                color: clickable ? "#0f172a" : "#94a3b8",
                fillOpacity: feature.properties.has_data ? 0.92 : 0.32
              }});
              if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
                e.target.bringToFront();
              }}
              mapRoot.style.cursor = clickable ? "pointer" : "default";
              showTooltip(feature, e);
            }},
            mousemove: function(e) {{
              mapRoot.style.cursor = clickable ? "pointer" : "default";
              positionTooltip(e);
            }},
            mouseout: function(e) {{
              geoLayer.resetStyle(e.target);
              mapRoot.style.cursor = "";
              hideTooltip();
            }},
            click: function(e) {{
              if (feature.properties.detail_url) {{
                L.DomEvent.stopPropagation(e);
                navigateToDetail(feature.properties.detail_url);
              }}
            }}
          }});
        }}
        const geoLayer = L.geoJSON(geojson, {{
          style: styleFeature,
          onEachFeature: onEachFeature
        }}).addTo(map);
        window.requestAnimationFrame(() => {{
          geoLayer.eachLayer((layer) => {{
            if (layer && layer.feature) attachPathHandlers(layer, layer.feature);
          }});
        }});
        mapRoot.addEventListener("mouseleave", hideTooltip);
        try {{
          let resultBounds = null;
          geoLayer.eachLayer((layer) => {{
            if (!layer || !layer.feature || !layer.feature.properties || !layer.feature.properties.has_data) return;
            const layerBounds = layer.getBounds ? layer.getBounds() : null;
            if (!layerBounds || !layerBounds.isValid || !layerBounds.isValid()) return;
            if (resultBounds) {{
              resultBounds.extend(layerBounds);
            }} else {{
              resultBounds = L.latLngBounds(layerBounds.getSouthWest(), layerBounds.getNorthEast());
            }}
          }});
          const targetBounds = resultBounds && resultBounds.isValid && resultBounds.isValid()
            ? resultBounds
            : geoLayer.getBounds();
          map.fitBounds(targetBounds, {{padding: [24, 24]}});
        }} catch (e) {{}}
        renderMapOverlays();
      }})();
    </script>
    """
