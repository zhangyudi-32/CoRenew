
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def create_app(home_path: str = "/app") -> FastAPI:
    fastapi_app = FastAPI()

    @fastapi_app.get("/", include_in_schema=False)
    def home_redirect():
        return RedirectResponse(url=home_path)

    @fastapi_app.get("/run/setup", response_class=HTMLResponse)
    def run_setup_page(embedded: bool = False):
        return HTMLResponse(_build_run_setup_page(embedded))

    @fastapi_app.get("/local-file")
    def local_file(path: str = Query(...)):
        target = Path(path)
        if not target.exists():
            return HTMLResponse("file not found", status_code=404)
        return FileResponse(target)

    @fastapi_app.get("/api/local/directories", response_class=JSONResponse)
    def api_local_directories(path: str = ""):
        try:
            raw_path = str(path or "").strip()
            if raw_path:
                target = Path(raw_path).expanduser()
                if not target.is_absolute():
                    target = (ROOT / target).resolve()
                else:
                    target = target.resolve()
            else:
                target = ROOT.resolve()
            if target.is_file():
                target = target.parent
            if not target.exists():
                raise ValueError(f"Folder does not exist: {raw_path}")
            if not target.is_dir():
                raise ValueError(f"Not a folder: {raw_path}")
            directories = []
            for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
                try:
                    if child.is_dir() and not child.name.startswith("."):
                        directories.append({"name": child.name, "path": _display_path(str(child))})
                except OSError:
                    continue
            parent = target.parent if target.parent != target else target
            return JSONResponse(_json_ready({
                "status": "ok",
                "current_path": _display_path(str(target)),
                "absolute_path": str(target),
                "parent_path": _display_path(str(parent)),
                "project_path": _display_path(str(ROOT.resolve())),
                "home_path": _display_path(str(Path.home().resolve())),
                "directories": directories,
            }))
        except Exception as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)

    @fastapi_app.get("/api/run/defaults", response_class=JSONResponse)
    def api_run_defaults():
        api_defaults = load_local_api_defaults()
        reset_payload = _run_reset_payload()
        defaults = reset_payload["defaults"]
        cleared = reset_payload["cleared_state"]

        defaults["community_file"] = _display_path(DEFAULT_COMMUNITY_CSV if DEFAULT_COMMUNITY_CSV.exists() else _default_community_csv())
        defaults["boundary_path"] = _display_path(DEFAULT_BOUNDARY_SHP if DEFAULT_BOUNDARY_SHP.exists() else _resolve_shape_path(None))
        defaults["output_dir"] = defaults.get("output_dir") or _default_output_dir_ui()
        defaults["agents_output_dir"] = defaults.get("agents_output_dir") or _default_agents_output_dir_ui()
        defaults["model_name"] = api_defaults.get("model") or defaults.get("model_name") or _default_model_name()
        defaults["rounds"] = defaults.get("rounds") or 8
        defaults["agreement_mode"] = defaults.get("agreement_mode") or "by_build_year"
        defaults["agreement_fixed_ratio"] = defaults.get("agreement_fixed_ratio") or 1.0
        defaults["agreement_current_year"] = defaults.get("agreement_current_year") or _system_current_year()
        defaults["max_extension_ratio"] = defaults.get("max_extension_ratio") or 0.3
        defaults["cash_subsidy_cap"] = defaults.get("cash_subsidy_cap") or 0.1
        defaults["developer_min_profit_rate"] = defaults.get("developer_min_profit_rate") or DEFAULT_DEVELOPER_MIN_PROFIT_RATE
        defaults["planner_soft_policy_text"] = defaults.get("planner_soft_policy_text") or ""
        defaults["residents_per_household"] = defaults.get("residents_per_household") or DEFAULT_RESIDENTS_PER_HOUSEHOLD
        defaults["vacancy_ratio"] = defaults.get("vacancy_ratio") or DEFAULT_VACANCY_RATIO
        defaults["representatives_per_community"] = defaults.get("representatives_per_community") or DEFAULT_REPRESENTATIVES_PER_COMMUNITY
        defaults["hardship_quantile"] = defaults.get("hardship_quantile") or DEFAULT_HARDSHIP_QUANTILE
        defaults["api_key"] = api_defaults.get("api_key") or defaults.get("api_key") or ""
        defaults["api_key_masked"] = api_defaults.get("api_key_masked", "")
        defaults["api_key_source"] = api_defaults.get("api_key_source", "manual")
        defaults["api_key_loaded"] = bool(api_defaults.get("api_key"))
        defaults["api_base_url"] = api_defaults.get("base_url") or defaults.get("api_base_url") or _default_llm_base_url()
        defaults["repeat_count"] = defaults.get("repeat_count") or 1
        defaults["agreement_rules_table"] = defaults.get("agreement_rules_table") or DEFAULT_AGREEMENT_RULE_ROWS.to_dict(orient="records")
        utility_state = _compute_value_flow_state(
            defaults.get("selected_utility_categories"),
            defaults.get("configured_utility_fields") or _default_configured_utility_fields(defaults.get("selected_utility_categories")),
            _community_csv_columns_for_path(defaults["community_file"]),
        )
        defaults["selected_utility_categories"] = utility_state["selected_utility_categories"]
        defaults["configured_utility_fields"] = utility_state["configured_utility_fields"]
        defaults["community_csv_columns"] = utility_state["community_csv_columns"]
        defaults["planner_components"] = utility_state["planner_components"]
        defaults["developer_components"] = utility_state["developer_components"]
        defaults["resident_components"] = utility_state["resident_components"]
        defaults["planner_utility_components"] = utility_state["planner_components"]
        defaults["developer_utility_components"] = utility_state["developer_components"]
        defaults["resident_utility_components"] = utility_state["resident_components"]
        defaults["planner_utility_options"] = utility_state["planner_options"]
        defaults["developer_utility_options"] = utility_state["developer_options"]
        defaults["resident_utility_options"] = utility_state["resident_options"]
        preflight_html = _run_preflight_payload(
            defaults["target_community"]["value"],
            defaults["model_name"],
            defaults["rounds"],
            defaults["agreement_mode"],
            defaults["max_extension_ratio"],
            defaults["cash_subsidy_cap"],
            defaults["developer_min_profit_rate"],
            defaults["output_dir"],
            {},
            defaults["planner_soft_policy_text"],
        )["preflight_html"]
        defaults["preflight_html"] = preflight_html
        defaults["value_flow_model_html"] = utility_state["value_flow_model_html"]
        defaults["template_url"] = _file_url(str(_ensure_run_template_excel()))
        defaults["required_columns_html"] = _required_upload_data_markup()
        return JSONResponse(_json_ready({"defaults": defaults}))

    @fastapi_app.post("/api/run/preview", response_class=JSONResponse)
    async def api_run_preview(payload: dict = Body(...)):
        data = payload or {}
        community_path = data.get("community_file") or data.get("community_file_path") or _default_community_csv()
        if not community_path:
            return JSONResponse({"status": "error", "message": "community_file is required"}, status_code=400)
        shp_files = data.get("shp_files") or data.get("boundary_path") or (_display_path(DEFAULT_BOUNDARY_SHP) if DEFAULT_BOUNDARY_SHP.exists() else _resolve_shape_path(None))
        if isinstance(shp_files, str):
            shp_files = [str(p) for p in Path(shp_files).glob("*")] if Path(shp_files).is_dir() else [shp_files]
        try:
            result = _run_preview_payload(
                community_path,
                shp_files,
                data.get("residents_per_household") if data.get("residents_per_household") is not None else DEFAULT_RESIDENTS_PER_HOUSEHOLD,
                data.get("vacancy_ratio") if data.get("vacancy_ratio") is not None else DEFAULT_VACANCY_RATIO,
                data.get("representatives_per_community") if data.get("representatives_per_community") is not None else DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
                data.get("hardship_quantile") if data.get("hardship_quantile") is not None else DEFAULT_HARDSHIP_QUANTILE,
                data.get("target_community"),
                data.get("model_name") or _default_model_name(),
                data.get("rounds") if data.get("rounds") is not None else 8,
                data.get("agreement_mode") or "by_build_year",
                data.get("max_extension_ratio") if data.get("max_extension_ratio") is not None else 0.3,
                data.get("cash_subsidy_cap") if data.get("cash_subsidy_cap") is not None else 0.1,
                data.get("developer_min_profit_rate") if data.get("developer_min_profit_rate") is not None else DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
                data.get("output_dir") or _default_output_dir_ui(),
                data.get("generated_bundle_state") or {},
                data.get("selected_utility_categories"),
                data.get("planner_utility_components"),
                data.get("developer_utility_components"),
                data.get("resident_utility_components"),
                data.get("configured_utility_fields"),
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/generate_agents", response_class=JSONResponse)
    async def api_run_generate_agents(payload: dict = Body(...)):
        data = payload or {}
        community_path = data.get("community_file") or data.get("community_file_path") or _default_community_csv()
        if not community_path:
            return JSONResponse({"status": "error", "message": "community_file is required"}, status_code=400)
        shp_files = data.get("shp_files") or data.get("boundary_path") or (_display_path(DEFAULT_BOUNDARY_SHP) if DEFAULT_BOUNDARY_SHP.exists() else _resolve_shape_path(None))
        if isinstance(shp_files, str):
            shp_files = [str(p) for p in Path(shp_files).glob("*")] if Path(shp_files).is_dir() else [shp_files]
        try:
            result = _run_generate_agents_payload(
                community_path,
                shp_files,
                data.get("residents_per_household") if data.get("residents_per_household") is not None else DEFAULT_RESIDENTS_PER_HOUSEHOLD,
                data.get("vacancy_ratio") if data.get("vacancy_ratio") is not None else DEFAULT_VACANCY_RATIO,
                data.get("representatives_per_community") if data.get("representatives_per_community") is not None else DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
                data.get("hardship_quantile") if data.get("hardship_quantile") is not None else DEFAULT_HARDSHIP_QUANTILE,
                data.get("target_community"),
                data.get("model_name") or _default_model_name(),
                data.get("rounds") if data.get("rounds") is not None else 8,
                data.get("agreement_mode") or "by_build_year",
                data.get("max_extension_ratio") if data.get("max_extension_ratio") is not None else 0.3,
                data.get("cash_subsidy_cap") if data.get("cash_subsidy_cap") is not None else 0.1,
                data.get("developer_min_profit_rate") if data.get("developer_min_profit_rate") is not None else DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
                data.get("output_dir") or _default_output_dir_ui(),
                data.get("selected_utility_categories"),
                data.get("planner_utility_components"),
                data.get("developer_utility_components"),
                data.get("resident_utility_components"),
                data.get("configured_utility_fields"),
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/generate_residents", response_class=JSONResponse)
    async def api_run_generate_residents(payload: dict = Body(...)):
        data = payload or {}
        community_path = data.get("community_file") or data.get("community_file_path") or _default_community_csv()
        if not community_path:
            return JSONResponse({"status": "error", "message": "community_file is required"}, status_code=400)
        shp_files = data.get("shp_files") or data.get("boundary_path") or (_display_path(DEFAULT_BOUNDARY_SHP) if DEFAULT_BOUNDARY_SHP.exists() else _resolve_shape_path(None))
        if isinstance(shp_files, str):
            shp_files = [str(p) for p in Path(shp_files).glob("*")] if Path(shp_files).is_dir() else [shp_files]
        try:
            result = _run_generate_residents_payload(
                community_path,
                shp_files,
                data.get("residents_per_household") if data.get("residents_per_household") is not None else DEFAULT_RESIDENTS_PER_HOUSEHOLD,
                data.get("vacancy_ratio") if data.get("vacancy_ratio") is not None else DEFAULT_VACANCY_RATIO,
                data.get("representatives_per_community") if data.get("representatives_per_community") is not None else DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
                data.get("hardship_quantile") if data.get("hardship_quantile") is not None else DEFAULT_HARDSHIP_QUANTILE,
                data.get("target_community"),
                data.get("model_name") or _default_model_name(),
                data.get("rounds") if data.get("rounds") is not None else 8,
                data.get("agreement_mode") or "by_build_year",
                data.get("max_extension_ratio") if data.get("max_extension_ratio") is not None else 0.3,
                data.get("cash_subsidy_cap") if data.get("cash_subsidy_cap") is not None else 0.1,
                data.get("developer_min_profit_rate") if data.get("developer_min_profit_rate") is not None else DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
                data.get("output_dir") or _default_output_dir_ui(),
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/select_representatives", response_class=JSONResponse)
    async def api_run_select_representatives(payload: dict = Body(...)):
        data = payload or {}
        try:
            result = _run_select_representatives_payload(
                data.get("community_file") or _default_community_csv(),
                data.get("shp_files") or data.get("boundary_path"),
                data.get("representatives_per_community") if data.get("representatives_per_community") is not None else DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
                data.get("hardship_quantile") if data.get("hardship_quantile") is not None else DEFAULT_HARDSHIP_QUANTILE,
                data.get("generated_bundle_state") or {},
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/load_existing_bundle", response_class=JSONResponse)
    async def api_run_load_existing_bundle(payload: dict = Body(...)):
        data = payload or {}
        try:
            result = _run_load_existing_bundle_payload(
                data.get("community_file") or _default_community_csv(),
                data.get("shp_files") or data.get("boundary_path"),
                data.get("residents_csv_path"),
                data.get("representatives_csv_path"),
                data.get("representatives_per_community") if data.get("representatives_per_community") is not None else DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/check_prompt_fields", response_class=JSONResponse)
    async def api_run_check_prompt_fields(payload: dict = Body(...)):
        try:
            result = _run_check_prompt_fields_payload((payload or {}).get("generated_bundle_state") or {})
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/generate_prompt_fields", response_class=JSONResponse)
    async def api_run_generate_prompt_fields(payload: dict = Body(...)):
        try:
            result = _run_generate_prompt_fields_payload((payload or {}).get("generated_bundle_state") or {})
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/preflight", response_class=JSONResponse)
    async def api_run_preflight(payload: dict = Body(...)):
        data = payload or {}
        try:
            community_path = data.get("community_file") or data.get("community_file_path") or _default_community_csv()
            community_df = _read_table(community_path) if community_path else None
            if community_df is not None:
                _validate_configured_utility_fields(
                    data.get("configured_utility_fields"),
                    community_df,
                    data.get("selected_utility_categories"),
                )
            result = _run_preflight_payload(
                data.get("target_community"),
                data.get("model_name") or _default_model_name(),
                data.get("rounds_num", data.get("rounds", 8)),
                data.get("agreement_mode", "by_build_year"),
                data.get("max_extension_ratio", 0.3),
                data.get("cash_subsidy_cap", 0.1),
                data.get("developer_min_profit_rate", DEFAULT_DEVELOPER_MIN_PROFIT_RATE),
                data.get("output_dir") or _default_output_dir_ui(),
                data.get("generated_bundle_state") or {},
                data.get("planner_soft_policy_text") or "",
            )
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/launch", response_class=JSONResponse)
    async def api_run_launch(payload: dict = Body(...)):
        data = payload or {}
        try:
            result = _run_launch_payload_from_data(data)
        except ValueError as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)
        return JSONResponse(_json_ready(result))

    @fastapi_app.post("/api/run/launch_job", response_class=JSONResponse)
    async def api_run_launch_job(payload: dict = Body(...)):
        data = payload or {}
        job_id = _new_run_job()
        thread = threading.Thread(target=_run_launch_job_worker, args=(job_id, data), daemon=True)
        _update_run_job(job_id, status="queued", message="Queued")
        thread.start()
        return JSONResponse(_json_ready({"status": "ok", "job_id": job_id, **_public_run_job(job_id)}))

    @fastapi_app.get("/api/run/job/{job_id}", response_class=JSONResponse)
    async def api_run_job_status(job_id: str):
        job = _public_run_job(job_id)
        if not job:
            return JSONResponse({"status": "error", "message": "job not found"}, status_code=404)
        return JSONResponse(_json_ready(job))

    @fastapi_app.post("/api/run/job/{job_id}/cancel", response_class=JSONResponse)
    async def api_run_job_cancel(job_id: str):
        job = _public_run_job(job_id)
        if not job:
            return JSONResponse({"status": "error", "message": "job not found"}, status_code=404)
        _update_run_job(job_id, cancel_requested=True, message="Cancelling")
        process = None
        with RUN_JOBS_LOCK:
            process = (RUN_JOBS.get(job_id) or {}).get("process")
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        return JSONResponse(_json_ready(_public_run_job(job_id)))

    @fastapi_app.post("/api/run/save_bundle", response_class=JSONResponse)
    async def api_run_save_bundle(payload: dict = Body(...)):
        data = payload or {}
        target_dir = data.get("target_dir") or _default_agents_output_dir_ui()
        generated_bundle_state = data.get("generated_bundle_state") or {}
        try:
            saved = _save_generated_bundle_to_dir(generated_bundle_state, target_dir)
        except Exception as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
        return JSONResponse(_json_ready({"status": "ok", **saved}))

    @fastapi_app.get("/api/run/reset", response_class=JSONResponse)
    def api_run_reset():
        return JSONResponse(_json_ready(_run_reset_payload()))

    @fastapi_app.post("/api/run/upload", response_class=JSONResponse)
    async def api_run_upload(community_file: UploadFile | None = File(None), boundary_files: list[UploadFile] | None = File(None)):
        try:
            bundle_dir = _ensure_upload_cache_dir()
            if community_file is None and not boundary_files:
                return JSONResponse({"status": "error", "message": "No file provided."}, status_code=400)

            if community_file is not None:
                community_path = _save_uploaded_run_file(community_file, bundle_dir=bundle_dir)
                return JSONResponse(
                    {
                        "status": "ok",
                        "kind": "community",
                        "community_file_token": str(community_path),
                        "community_file_path": str(community_path),
                        "display_name": community_file.filename,
                        "message": "Community file uploaded.",
                    }
                )

            if boundary_files:
                if len(boundary_files) == 0:
                    return JSONResponse({"status": "error", "message": "Boundary files missing."}, status_code=400)
                bundle_path = _save_uploaded_shapefile_bundle(boundary_files)
                return JSONResponse(
                    {
                        "status": "ok",
                        "kind": "boundary",
                        "boundary_bundle_token": str(bundle_path),
                        "boundary_path": str(bundle_path),
                        "display_name": bundle_path.name,
                        "message": "Boundary bundle uploaded.",
                    }
                )
        except Exception as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

    @fastapi_app.get("/phase2/global", response_class=HTMLResponse)
    def phase2_global_page(
        phase2_root: str = _default_output_dir_ui(),
        boundary_path: str | None = None,
        rule_id: str | None = None,
        metric: str = "final_agree_ratio",
        seed: str | None = None,
        embedded: bool = False,
    ):
        resolved_boundary = boundary_path or _resolve_shape_path(None)
        return HTMLResponse(_build_phase2_global_page(phase2_root, resolved_boundary, rule_id, metric, seed, embedded))

    @fastapi_app.get("/phase2/global/export")
    def phase2_global_export(
        phase2_root: str = _default_output_dir_ui(),
        boundary_path: str | None = None,
        rule_id: str | None = None,
        metric: str = "final_agree_ratio",
        seed: str | None = None,
    ):
        resolved_boundary = boundary_path or _resolve_shape_path(None)
        global_df = _load_phase2_global_results(phase2_root)
        if global_df.empty or "rule_id" not in global_df.columns:
            return HTMLResponse("phase2 policy-search dataset not found", status_code=404)
        selected_rule = rule_id if rule_id in set(global_df["rule_id"].tolist()) else str(global_df.iloc[0]["rule_id"])

        map_df = _summarize_phase2_rule(phase2_root, selected_rule).copy()
        export_path = _export_metric_map_png(
            map_df,
            resolved_boundary,
            metric,
            f"Community Mean Result Map · {selected_rule}",
            f"Selected metric: {MAP_METRICS.get(metric, metric)} · mean by rule + community",
        )
        return FileResponse(export_path, media_type="image/png", filename=f"{selected_rule}_{metric}_community_result_map.png")

    @fastapi_app.get("/phase2/community", response_class=HTMLResponse)
    def phase2_community_page(
        phase2_root: str = _default_output_dir_ui(),
        boundary_path: str | None = None,
        rule_id: str = "rule_0015",
        community_name: str | None = None,
        seed: str | None = None,
        round_number: str | None = None,
    ):
        resolved_boundary = boundary_path or _resolve_shape_path(None)
        return HTMLResponse(
            _build_phase2_community_page(
                phase2_root,
                resolved_boundary,
                rule_id,
                community_name,
                seed,
                round_number,
            )
        )

    @fastapi_app.get("/phase2/compare", response_class=HTMLResponse)
    def phase2_compare_page(
        phase2_root: str = _default_output_dir_ui(),
        mode: str = "aggregate_policy",
        rule_ids: list[str] | None = Query(None),
        community_names: list[str] | None = Query(None),
        x_metric: str = "final_agree_ratio",
        y_metric: str = "developer_profit",
        evaluation: str = "pareto",
        weight_final_agree_ratio: float = 1.0,
        weight_developer_profit: float = 1.0,
        weight_resident_mean_utility: float = 1.0,
        weight_utility_gini: float = 1.0,
        weight_subsidy_total_cost: float = 1.0,
        weight_extension_ratio_final: float = 1.0,
        embedded: bool = False,
    ):
        return HTMLResponse(
            _build_phase2_compare_page(
                phase2_root,
                mode,
                rule_ids,
                community_names,
                x_metric,
                y_metric,
                evaluation,
                {
                    "final_agree_ratio": weight_final_agree_ratio,
                    "developer_profit": weight_developer_profit,
                    "resident_mean_utility": weight_resident_mean_utility,
                    "utility_gini": weight_utility_gini,
                    "subsidy_total_cost": weight_subsidy_total_cost,
                    "extension_ratio_final": weight_extension_ratio_final,
                },
                embedded,
            )
        )

    @fastapi_app.get("/run/global", response_class=HTMLResponse)
    def run_global_page(run_id: str, metric: str = "final_agree_ratio"):
        return HTMLResponse(_build_run_global_page(run_id, metric))

    @fastapi_app.get("/run/global/export")
    def run_global_export(run_id: str, metric: str = "final_agree_ratio"):
        metadata = _load_run_metadata(run_id)
        output_dir = metadata.get("output_dir", "")
        boundary_path = metadata.get("boundary_path")
        summary_df = _collect_latest_run_results(output_dir)
        export_path = _export_metric_map_png(
            summary_df,
            boundary_path,
            metric,
            f"Community Result Map · {run_id}",
            f"Selected metric: {MAP_METRICS.get(metric, metric)}",
        )
        return FileResponse(export_path, media_type="image/png", filename=f"{run_id}_{metric}_community_result_map.png")

    @fastapi_app.get("/preview/global", response_class=HTMLResponse)
    def preview_global_page(
        community_csv_path: str = _default_community_csv(),
        boundary_path: str | None = None,
    ):
        resolved_boundary = boundary_path or _resolve_shape_path(None)
        return HTMLResponse(_build_preview_global_page(community_csv_path, resolved_boundary))

    @fastapi_app.get("/run/community", response_class=HTMLResponse)
    def run_community_page(
        run_id: str,
        community_name: str | None = None,
        round_number: str | None = None,
    ):
        return HTMLResponse(_build_run_community_page(run_id, community_name, round_number))

    demo = build_ui()
    return gr.mount_gradio_app(
        fastapi_app,
        demo,
        path="/app",
        app_kwargs={"docs_url": None, "redoc_url": None},
        theme=gr.themes.Default(
            primary_hue="blue",
            secondary_hue="amber",
            neutral_hue="slate",
        ).set(
            body_background_fill="#FFFFFF",
            body_background_fill_dark="#FFFFFF",
            background_fill_primary="#FFFFFF",
            background_fill_primary_dark="#FFFFFF",
            background_fill_secondary="#FFFFFF",
            background_fill_secondary_dark="#FFFFFF",
            block_background_fill="#FFFFFF",
            block_background_fill_dark="#FFFFFF",
            panel_background_fill="#FFFFFF",
            panel_background_fill_dark="#FFFFFF",
            color_accent_soft="#FFFFFF",
            color_accent_soft_dark="#FFFFFF",
            input_background_fill="#FFFFFF",
            input_background_fill_dark="#FFFFFF",
            input_background_fill_hover="#FFFFFF",
            input_background_fill_hover_dark="#FFFFFF",
            input_background_fill_focus="#FFFFFF",
            input_background_fill_focus_dark="#FFFFFF",
            button_secondary_background_fill="#FFFFFF",
            button_secondary_background_fill_dark="#FFFFFF",
            button_secondary_background_fill_hover="#FFFFFF",
            button_secondary_background_fill_hover_dark="#FFFFFF",
            stat_background_fill="#FFFFFF",
            stat_background_fill_dark="#FFFFFF",
            code_background_fill="#FFFFFF",
            code_background_fill_dark="#FFFFFF",
            block_border_color="#E4E4E7",
            panel_border_color="#E4E4E7",
            input_border_color="#E4E4E7",
            button_secondary_border_color="#E4E4E7",
            table_even_background_fill="#FFFFFF",
            table_even_background_fill_dark="#FFFFFF",
            table_odd_background_fill="#FFFFFF",
            table_odd_background_fill_dark="#FFFFFF",
        ),
        css="""
        :root {
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
          --app-bg: #f5f5f5;
          --surface: #ffffff;
          --surface-soft: #fafafa;
          --border: #e4e4e7;
          --border-strong: #d4d4d8;
          --text: #09090b;
          --muted: #71717a;
          --muted-soft: #a1a1aa;
          --accent: #18181b;
          --accent-soft: #ffffff;
          --shadow-soft: 0 1px 2px rgba(15, 23, 42, 0.04);
          --shadow-card: 0 2px 10px rgba(0, 0, 0, 0.06);
          --radius-xl: 28px;
          --radius-lg: 22px;
          --radius-md: 16px;
          --radius-sm: 12px;
        }
        body, .gradio-container {
          background: var(--app-bg);
          color: var(--text);
        }
        .gradio-container {
          --background-fill-primary: 255, 255, 255;
          --background-fill-secondary: 255, 255, 255;
          --body-background-fill: 255, 255, 255;
          --body-background-fill-subdued: 255, 255, 255;
          --block-background-fill: 255, 255, 255;
          --block-background-fill-dark: 255, 255, 255;
          --panel-background-fill: 255, 255, 255;
          --panel-background-fill-dark: 255, 255, 255;
          --block-border-color: 228, 228, 231;
          --block-border-width: 1px;
          --body-text-color: var(--text);
          --body-text-color-subdued: var(--muted);
          --input-background-fill: 255, 255, 255;
          --input-border-color: 228, 228, 231;
          --button-primary-background-fill: 24, 24, 27;
          --button-primary-border-color: 24, 24, 27;
          --button-primary-text-color: #ffffff;
          --button-secondary-background-fill: 255, 255, 255;
          --button-secondary-border-color: 228, 228, 231;
          --button-secondary-text-color: var(--text);
          max-width: 1500px !important;
          padding: 0 var(--container-desktop) var(--space-8) var(--container-desktop) !important;
        }
        .gradio-container,
        .gradio-container button,
        .gradio-container input,
        .gradio-container textarea,
        .gradio-container select {
          font-family: "Microsoft YaHei", "PingFang SC", sans-serif !important;
        }
        .topbar-shell {
          margin: calc(-1 * var(--space-1)) calc(-1 * var(--container-desktop)) var(--space-4) calc(-1 * var(--container-desktop));
          padding: var(--space-4) var(--container-desktop);
          background: #ffffff;
          border-bottom: 1px solid var(--border);
          box-shadow: 0 1px 0 rgba(15, 23, 42, 0.02);
        }
        .topbar-inner {
          max-width: 1380px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
        }
        .brand-lockup {
          display: flex;
          align-items: center;
          gap: 18px;
          min-width: 0;
          flex: 1 1 auto;
        }
        .brand-badge {
          width: 64px;
          height: 64px;
          border-radius: 16px;
          background: linear-gradient(145deg, #111827 0%, #1f2937 100%);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          font-weight: 800;
          flex: 0 0 auto;
        }
        .brand-copy {
          min-width: 0;
        }
        .app-title {
          margin: 0 0 6px 0;
          font-size: 28px;
          line-height: 1.05;
          color: var(--text);
          font-weight: 800;
        }
        .app-subtitle {
          color: var(--muted);
          font-size: 15px;
          line-height: 1.35;
        }
        .topbar-aside {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 0 0 auto;
        }
        .topbar-viz {
          width: min(360px, 30vw);
          min-width: 260px;
          border: 1px solid var(--border);
          border-radius: 22px;
          background: #ffffff;
          padding: 8px 10px;
          box-shadow: var(--shadow-soft);
        }
        .negotiation-svg {
          width: 100%;
          height: 78px;
          display: block;
        }
        .viz-node {
          fill: #ffffff;
          stroke: #d4d4d8;
          stroke-width: 1.2;
        }
        .viz-node-owners {
          fill: #fcfcfd;
        }
        .viz-node-planner {
          fill: #f8fafc;
        }
        .viz-node-developer {
          fill: #fafaf9;
        }
        .viz-overline {
          fill: #71717a;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        .viz-value {
          fill: #111827;
          font-size: 14px;
          font-weight: 800;
        }
        .viz-route {
          stroke: #cbd5e1;
          stroke-width: 2.2;
          stroke-linecap: round;
          stroke-dasharray: 6 8;
          animation: route-flow 14s linear infinite;
        }
        .viz-route-soft {
          stroke: #dbe4ef;
          stroke-width: 1.8;
          animation-duration: 18s;
        }
        .viz-anchor {
          fill: #94a3b8;
          animation: pulse-anchor 2.8s ease-in-out infinite;
        }
        .mini-person {
          transform-box: fill-box;
          transform-origin: center;
        }
        .person-amber {
          color: #c2410c;
        }
        .person-teal {
          color: #36AABF;
        }
        .person-slate {
          color: #334155;
        }
        .mode-pill {
          flex: 0 0 auto;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px;
          padding: 0 16px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--text);
          font-size: 14px;
          font-weight: 600;
        }
        @keyframes route-flow {
          to {
            stroke-dashoffset: -140;
          }
        }
        @keyframes pulse-anchor {
          0%, 100% {
            opacity: 0.55;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.18);
          }
        }
        .section-head {
          margin: 0 0 var(--space-4) 0;
        }
        .section-head.compact {
          margin: 0 0 var(--space-3) 0;
        }
        .section-title {
          font-size: 26px;
          line-height: 1.18;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 6px;
        }
        .section-copy {
          color: var(--muted);
          font-size: 14px;
          line-height: 1.55;
        }
        .section-inline-label {
          margin: 2px 0 10px 0;
          font-size: 14px;
          font-weight: 700;
          color: var(--text);
        }
        .block {
          border-radius: inherit !important;
          border: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        .surface-card {
          border: 1px solid var(--border) !important;
          background: var(--surface) !important;
          border-radius: var(--radius-xl) !important;
          box-shadow: var(--shadow-card) !important;
          padding: var(--space-5) !important;
        }
        .surface-card-lg {
          padding: var(--space-5) !important;
        }
        .surface-card-xl {
          padding: var(--space-6) !important;
        }
        .surface-card .block {
          border: 0 !important;
          box-shadow: none !important;
          background: transparent !important;
        }
        .surface-card > div,
        .surface-card > div > div,
        .surface-card > div > div > div {
          background: transparent !important;
        }
        .block > div {
          padding-left: 0;
          padding-right: 0;
        }
        h1, h2, h3, p, div, span, label {letter-spacing: 0 !important;}
        .environment-card {
          margin-top: 16px;
          margin-bottom: 14px;
        }
        .environment-card > .block {
          padding: 0 !important;
        }
        .environment-card .label-wrap,
        .environment-card .accordion-header {
          min-height: 58px !important;
        }
        .app-tabs-shell,
        .tabs {
          margin-top: 0;
        }
        .tabitem {
          border-radius: 0 !important;
          border: 0 !important;
          background: transparent !important;
          padding: 8px 0 0 0 !important;
          box-shadow: none !important;
        }
        .tab-nav {
          background: transparent !important;
          padding: 0 var(--space-1) 10px var(--space-1) !important;
          gap: var(--space-3) !important;
          border-bottom: 1px solid rgba(235, 230, 219, 0.8) !important;
        }
        .tab-nav button {
          border-radius: 16px !important;
          padding: 11px 24px !important;
          margin-right: 0 !important;
          font-weight: 700 !important;
          border: 1px solid var(--border) !important;
          background: var(--surface) !important;
          color: var(--text) !important;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
          min-height: 50px;
          font-size: 16px !important;
        }
        .tab-nav button.selected {
          background: var(--accent) !important;
          color: #ffffff !important;
          border-color: var(--accent) !important;
        }
        .link-bar {
          display:flex;
          gap:12px;
          flex-wrap:wrap;
          margin: 2px 0 0 0;
          align-items: center;
        }
        .nav-link {
          display:inline-flex;
          align-items:center;
          justify-content:center;
          min-height: 52px;
          padding: 0 18px;
          border-radius: var(--radius-sm);
          background: var(--accent);
          color: white;
          text-decoration:none;
          font-weight:700;
          white-space:nowrap;
          border: 1px solid var(--accent);
          box-shadow: none;
        }
        .nav-link.disabled {
          background: var(--accent-soft);
          color: var(--muted);
          border-color: var(--border);
        }
        .summary-card {
          padding: 4px 2px;
        }
        .summary-card-compact {
          padding: 0;
        }
        .summary-title {
          font-size: 20px;
          line-height: 1.2;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 6px;
        }
        .summary-subtitle {
          color: var(--muted);
          font-size: 13px;
          line-height: 1.55;
          margin-bottom: 12px;
        }
        .validation-pill-row {
          display: flex;
          gap: var(--space-2);
          flex-wrap: wrap;
          margin-bottom: var(--space-3);
        }
        .validation-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 30px;
          padding: 0 11px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--text);
          font-size: 12px;
          font-weight: 600;
        }
        .validation-pill.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
          color: #166534;
        }
        .validation-pill.warn {
          border-color: #fed7aa;
          background: #fff7ed;
          color: #9a3412;
        }
        .validation-mini-list {
          display: grid;
          gap: var(--space-2);
        }
        .validation-mini-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 8px 0;
          border-top: 1px dashed rgba(221, 213, 198, 0.8);
        }
        .validation-mini-row:first-child {
          border-top: 0;
          padding-top: 0;
        }
        .validation-mini-copy {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }
        .validation-mini-label {
          font-size: 13px;
          line-height: 1.4;
          color: var(--text);
          font-weight: 600;
        }
        .validation-mini-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 26px;
          padding: 0 10px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: var(--muted);
          font-size: 12px;
          font-weight: 700;
          white-space: nowrap;
        }
        .validation-mini-badge.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
          color: #166534;
        }
        .validation-mini-badge.warn {
          border-color: #fed7aa;
          background: #fff7ed;
          color: #9a3412;
        }
        .validation-mini-badge.neutral {
          border-color: var(--border);
          background: var(--surface-soft);
          color: var(--muted);
        }
        .validation-footnote {
          margin-top: var(--space-3);
          padding-top: var(--space-2);
          border-top: 1px solid var(--border);
          color: var(--muted);
          font-size: 13px;
          line-height: 1.5;
        }
        .validation-requirement-grid {
          display: grid;
          gap: 8px;
          margin-bottom: var(--space-3);
        }
        .validation-requirement-item {
          min-height: 34px;
          display: flex;
          align-items: center;
          padding: 0 12px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: #ffffff;
          color: var(--muted);
          font-size: 12px;
          font-weight: 600;
          line-height: 1.4;
        }
        .validation-requirement-item.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
          color: #166534;
        }
        .validation-requirement-item.warn {
          border-color: #fed7aa;
          background: #fff7ed;
          color: #9a3412;
        }
        .check-row {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          padding: 14px 0;
        }
        .check-row.highlight {
          padding-top: 16px;
          padding-bottom: 6px;
        }
        .check-copy {
          flex: 1 1 auto;
          min-width: 0;
        }
        .check-title {
          font-size: 18px;
          line-height: 1.35;
          font-weight: 600;
          color: #374151;
          margin-bottom: 3px;
        }
        .check-detail {
          color: var(--muted);
          font-size: 14px;
          line-height: 1.5;
          word-break: break-word;
        }
        .check-badge {
          flex: 0 0 auto;
          min-height: 36px;
          padding: 0 14px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--surface-soft);
          color: #6b7280;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 14px;
          font-weight: 600;
        }
        .summary-divider {
          height: 1px;
          background: var(--border);
          margin: 8px 0 0 0;
        }
        .status-dot {
          width: 16px;
          height: 16px;
          border-radius: 999px;
          flex: 0 0 auto;
          margin-top: 4px;
          border: 2px solid #9ca3af;
          background: white;
        }
        .status-dot.ok {
          border-color: #268CA0;
          background: #E8F4F9;
        }
        .status-dot.warn {
          border-color: #d97706;
          background: #fef3c7;
        }
        .status-dot.neutral {
          border-color: #9ca3af;
          background: white;
        }
        .action-row {
          align-items: center !important;
          margin-top: 8px;
        }
        .action-note {
          margin-top: 12px;
          color: var(--muted);
          font-size: 14px;
          line-height: 1.55;
          text-align: center;
        }
        .compact-note {
          text-align: left;
          margin-top: 10px;
          font-size: 13px;
          line-height: 1.5;
        }
        button[aria-label],
        button.lg,
        .gr-button {
          border-radius: var(--radius-sm) !important;
        }
        button.primary,
        .gr-button-primary {
          background: var(--accent) !important;
          border: 1px solid var(--accent) !important;
          color: white !important;
          box-shadow: none !important;
          min-height: 48px !important;
          font-size: 15px !important;
          font-weight: 700 !important;
        }
        button.secondary,
        .gr-button-secondary {
          background: var(--surface) !important;
          border: 1px solid var(--border) !important;
          color: var(--text) !important;
          min-height: 48px !important;
          font-size: 15px !important;
          font-weight: 600 !important;
        }
        input, textarea, select {
          border-radius: var(--radius-sm) !important;
          border: 1px solid var(--border) !important;
          background: var(--surface) !important;
          box-shadow: none !important;
        }
        textarea, input[type="text"], input[type="password"], select {
          padding: 13px 15px !important;
          min-height: 48px !important;
        }
        label {
          color: var(--text) !important;
          font-weight: 600 !important;
          font-size: 14px !important;
        }
        .wrap.svelte-1ipelgc,
        .form,
        .gr-box,
        .gr-group {
          gap: var(--space-3) !important;
        }
        .soft-field {
          margin-bottom: 2px;
        }
        .file-uploader {
          border: 1px solid var(--border) !important;
          border-radius: 18px !important;
          padding: 12px 14px !important;
          background: #fffdfa !important;
          box-shadow: var(--shadow-soft);
        }
        .file-uploader .wrap,
        .file-uploader .orwrap {
          border: 0 !important;
          background: transparent !important;
        }
        .file-uploader button {
          min-height: 46px !important;
          font-size: 15px !important;
        }
        .run-grid-shell,
        .run-lower-stack {
          gap: var(--space-4) !important;
        }
        .upload-tab-pane,
        .upload-tab-pane > div,
        .upload-tab-pane > div > div {
          background: transparent !important;
          margin-top: 0 !important;
          padding-top: 0 !important;
        }
        .upload-tab-pane iframe {
          display: block;
          margin-top: -6px;
        }

        .upload-tab-pane .surface-card > div,
        .upload-tab-pane .surface-card > div > div,
        .upload-tab-pane .surface-card > div > div > div,
        .upload-tab-pane .surface-card > div > div > div > div {
          background: #ffffff !important;
        }
        .run-workflow-shell {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
          margin-bottom: 10px;
        }
        .workflow-step {
          border: 1px solid var(--border);
          border-radius: 999px;
          background: #ffffff;
          padding: 10px 14px;
          box-shadow: var(--shadow-soft);
          display: flex;
          align-items: center;
          gap: 10px;
          min-height: 48px;
        }
        .workflow-step.is-active {
          border-color: rgba(24, 24, 27, 0.12);
          box-shadow: var(--shadow-card);
        }
        .workflow-step-index {
          width: 24px;
          height: 24px;
          border-radius: 999px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: #18181b;
          color: #ffffff;
          font-size: 11px;
          font-weight: 800;
          flex: 0 0 auto;
        }
        .workflow-step-kicker,
        .step-kicker {
          font-size: 11px;
          line-height: 1.2;
          font-weight: 800;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 6px;
        }
        .workflow-step-title {
          font-size: 14px;
          line-height: 1.25;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 0;
        }
        .run-step-card {
          display: flex;
          flex-direction: column;
          gap: 12px;
          background: #ffffff;
          border: 1px solid rgba(24, 24, 27, 0.08);
          border-radius: 20px;
          box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06), 0 2px 8px rgba(15, 23, 42, 0.04);
          padding: 14px 16px;
        }
        .run-step-card .section-title {
          font-size: 16px;
          line-height: 1.15;
          font-weight: 800;
        }
        .run-panel-card .section-head.compact {
          margin-bottom: 8px !important;
        }
        .run-panel-card .step-kicker {
          margin-bottom: 4px !important;
        }
        .step-head {
          margin-bottom: 0 !important;
        }
        .step-head .section-copy { display: none; }
        .run-upload-list {
          display: grid;
          gap: 10px;
        }
        .run-upload-row {
          border: 1px solid rgba(24, 24, 27, 0.08) !important;
          border-radius: 16px !important;
          background: #ffffff !important;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05) !important;
          padding: 10px 12px !important;
        }
        .run-upload-row > div,
        .run-upload-row > div > div,
        .run-upload-row > div > div > div {
          background: transparent !important;
          box-shadow: none !important;
          border-color: transparent !important;
        }
        .run-upload-row-inline {
          gap: 10px !important;
          margin: 0 !important;
          align-items: center !important;
        }
        .file-row-inline-shell {
          flex: 1 1 auto;
          min-width: 0;
        }
        .file-row-inline-title,
        .file-row-label-line {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
          margin-bottom: 0;
        }
        .file-row-chip {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 20px;
          padding: 0 8px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: #ffffff;
          color: var(--muted);
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }
        .file-row-chip.required {
          border-color: #d4d4d8;
          color: var(--text);
        }
        .file-row-chip.optional {
          color: var(--muted);
        }
        .run-inline-note {
          color: var(--muted);
          font-size: 11px;
          line-height: 1.35;
          margin-top: 0;
        }
        .template-download-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 4px 8px;
          border: 1px solid var(--border);
          border-radius: 14px;
          background: #ffffff;
        }
        .template-download-copy {
          color: var(--text);
          font-size: 12px;
          line-height: 1.3;
          font-weight: 700;
        }
        .template-download-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 32px;
          padding: 0 11px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: #ffffff;
          color: var(--text);
          text-decoration: none;
          font-size: 13px;
          font-weight: 700;
          white-space: nowrap;
        }
        .template-download-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 4px 8px;
          border: 1px solid var(--border);
          border-radius: 16px;
          background: #ffffff;
        }
        .template-download-copy {
          color: var(--text);
          font-size: 12px;
          line-height: 1.3;
          font-weight: 700;
        }
        .template-download-button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 32px;
          padding: 0 11px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: #ffffff;
          color: var(--text);
          text-decoration: none;
          font-size: 13px;
          font-weight: 700;
          white-space: nowrap;
        }
        .run-accordion {
          border: 1px solid var(--border);
          border-radius: 14px !important;
          background: #ffffff !important;
          box-shadow: none !important;
          overflow: hidden;
        }
        .run-accordion > .block,
        .run-accordion > .block > div,
        .run-accordion > .block > div > div {
          background: transparent !important;
          box-shadow: none !important;
        }
        .run-accordion .label-wrap,
        .run-accordion .accordion-header {
          min-height: 34px !important;
          background: #ffffff !important;
        }
        .run-accordion .label-wrap {
          padding-left: 12px !important;
          padding-right: 12px !important;
        }
        .run-columns-accordion .label-wrap,
        .run-columns-accordion .accordion-header {
          justify-content: center !important;
          text-align: center !important;
        }
        .run-columns-accordion .label-wrap > *,
        .run-columns-accordion .accordion-header > * {
          margin-left: auto !important;
          margin-right: auto !important;
          text-align: center !important;
        }
        .run-columns-accordion .label-wrap,
        .run-columns-accordion .accordion-header {
          justify-content: center !important;
          text-align: center !important;
        }
        .run-columns-accordion .label-wrap > *,
        .run-columns-accordion .accordion-header > * {
          margin-left: auto !important;
          margin-right: auto !important;
          text-align: center !important;
        }
        .accordion-helper-copy {
          color: var(--muted);
          font-size: 12px;
          line-height: 1.45;
          margin-bottom: 6px;
        }
        .config-helper-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: -6px;
        }
        .config-helper-pill {
          display: inline-flex;
          align-items: center;
          min-height: 28px;
          padding: 0 10px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: #fafafa;
          color: var(--muted);
          font-size: 12px;
          font-weight: 600;
          line-height: 1.4;
        }
        .generation-status-shell {
          border: 1px solid var(--border);
          border-radius: 18px;
          padding: 6px 8px;
          background: #ffffff !important;
          box-shadow: none;
        }
        .generation-status-shell > div,
        .generation-status-shell > div > div,
        .generation-status-shell > div > div > div {
          background: transparent !important;
          box-shadow: none !important;
        }
        .generation-cta-row {
          gap: 8px !important;
          align-items: center !important;
          margin: 0 !important;
        }
        .generation-meta-shell {
          flex: 1 1 auto;
          min-width: 0;
        }
        .generate-primary-button {
          flex: 0 0 auto;
          min-height: 30px !important;
          height: 30px !important;
          padding: 0 12px !important;
        }
        .generation-estimate-row {
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
        }
        .generation-estimate-copy {
          color: var(--muted);
          font-size: 11px;
          line-height: 1.3;
          font-weight: 600;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .validation-next {
          display: grid;
          gap: 4px;
          padding: 10px 12px;
          border: 1px solid var(--border);
          border-radius: 16px;
          background: #ffffff;
          margin-bottom: var(--space-3);
        }
        .validation-next.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
        }
        .validation-next.warn {
          border-color: #fed7aa;
          background: #fff7ed;
        }
        .validation-next.block {
          border-color: #fecaca;
          background: #fef2f2;
        }
        .validation-next-label {
          font-size: 11px;
          line-height: 1.2;
          font-weight: 800;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--muted);
        }
        .validation-next-copy {
          color: var(--text);
          font-size: 13px;
          line-height: 1.5;
          font-weight: 600;
        }
        .validation-pill.block,
        .validation-mini-badge.block,
        .validation-requirement-item.block {
          border-color: #fecaca;
          background: #fef2f2;
          color: #991b1b;
        }
        .validation-console-card .validation-pill-row {
          margin-bottom: 8px;
        }
        .validation-short-list {
          display: grid;
          gap: 4px;
          margin-bottom: 0;
        }
        .validation-short-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          min-height: 26px;
          padding: 0;
        }
        .validation-short-label {
          color: var(--text);
          font-size: 12px;
          line-height: 1.3;
          font-weight: 600;
        }
        .validation-footnote {
          display: none !important;
        }
        .preflight-card {
          border: 1px solid var(--border);
          border-radius: 18px;
          background: #ffffff;
          padding: 8px 10px;
          margin-bottom: 0;
        }
        .preflight-card.is-ready {
          border-color: rgba(22, 101, 52, 0.18);
        }
        .preflight-card.is-pending {
          border-color: rgba(217, 119, 6, 0.18);
        }
        .preflight-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 6px;
        }
        .preflight-title {
          font-size: 14px;
          line-height: 1.25;
          font-weight: 800;
          color: var(--text);
        }
        .preflight-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
        }
        .preflight-chip {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          min-height: 26px;
          padding: 0 8px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: #ffffff;
          min-width: 0;
          max-width: 100%;
        }
        .preflight-label {
          font-size: 11px;
          line-height: 1.2;
          font-weight: 800;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--muted-soft);
          white-space: nowrap;
        }
        .preflight-value {
          color: var(--text);
          font-size: 12px;
          line-height: 1.35;
          font-weight: 700;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 280px;
        }
        .preflight-chip-status.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
        }
        .preflight-chip-status.ok .preflight-value {
          color: #166534;
        }
        .preflight-chip-status.warn {
          border-color: #fed7aa;
          background: #fff7ed;
        }
        .preflight-chip-status.warn .preflight-value {
          color: #9a3412;
        }
        .run-launch-bar {
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          margin-top: -22px !important;
        }
        .run-launch-bar .section-head.compact {
          margin-bottom: 2px !important;
        }
        .run-launch-bar-full {
          margin-top: -18px !important;
        }
        .run-launch-row {
          align-items: center !important;
          gap: 10px !important;
          margin: 0 !important;
        }
        .run-launch-summary-col,
        .run-launch-actions-col {
          min-width: 0 !important;
        }
        .run-launch-actions-col {
          display: flex !important;
          flex-direction: column !important;
          justify-content: center !important;
          gap: 8px !important;
        }
        .run-action-card .action-panel-buttons {
          gap: 10px !important;
          margin-top: 0 !important;
        }
        .run-action-card .link-bar {
          margin-top: 0;
        }
        .run-action-card .nav-link {
          min-height: 40px;
          padding: 0 12px;
          font-size: 13px;
        }
        .run-action-card .compact-note {
          display: none;
        }
        .preflight-inline-label {
          display: none;
        }
        .compact-upload-card .section-head.compact {
          margin-bottom: 8px !important;
        }
        .compact-config-card .section-head.compact {
          margin-bottom: 0 !important;
        }
        .compact-config-card .section-title {
          font-size: 15px !important;
          line-height: 1.15 !important;
        }
        .required-data-card {
          margin-bottom: 0;
          padding: 8px 10px;
          border: 1px solid var(--border);
          border-radius: 14px;
          background: #ffffff !important;
        }
        .required-data-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 6px 8px;
        }
        .required-data-group {
          display: grid;
          gap: 3px;
        }
        .required-data-group-title {
          font-size: 11px;
          font-weight: 700;
          color: #52525b;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .field-chip-row {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 4px;
        }
        .field-chip {
          display: inline-flex;
          align-items: center;
          gap: 0;
          min-height: 0;
          width: 100%;
          padding: 5px 7px;
          border-radius: 10px;
          border: 1px solid var(--border);
          background: #ffffff;
        }
        .field-chip-label {
          font-size: 10px;
          line-height: 1.25;
          font-weight: 600;
          color: var(--text);
        }
        .field-chip-code {
          font-size: 11px;
          font-weight: 700;
          color: var(--muted);
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        }
        .required-data-note {
          color: var(--muted);
          font-size: 12px;
          line-height: 1.5;
          padding-top: 2px;
          grid-column: 1 / -1;
        }
        .compact-upload-card {
          display: flex;
          flex-direction: column;
        }
        .compact-upload-card .section-copy,
        .compact-config-card .section-copy,
        .validation-card .section-copy,
        .run-action-card .section-copy {
          display: block;
          color: var(--muted);
        }
        .gradio-container .toast-wrap,
        .gradio-container .toast-wrap > *,
        .gradio-container .toast,
        .gradio-container .toast-body,
        .gradio-container .toast-body > div,
        .gradio-container .toast-text,
        .gradio-container .toast-title,
        .gradio-container [role="dialog"],
        .gradio-container [role="dialog"] > *,
        .gradio-container [aria-modal="true"],
        .gradio-container [aria-modal="true"] > *,
        .gradio-container [role="alert"],
        .gradio-container [role="alertdialog"] {
          background: #ffffff !important;
          color: var(--text) !important;
          backdrop-filter: none !important;
          box-shadow: var(--shadow-card) !important;
          border-color: var(--border) !important;
        }
        .gradio-container .toast-body pre,
        .gradio-container .toast-body code {
          background: #ffffff !important;
          color: var(--text) !important;
        }
        .gradio-container [role="dialog"] pre,
        .gradio-container [role="dialog"] code,
        .gradio-container [aria-modal="true"] pre,
        .gradio-container [aria-modal="true"] code {
          background: #ffffff !important;
          color: var(--text) !important;
        }
        .compact-config-card label,
        .compact-config-card [class*="label"],
        .validation-card label,
        .validation-card [class*="label"],
        .run-action-card label,
        .run-action-card [class*="label"] {
          background: transparent !important;
          box-shadow: none !important;
        }
        .compact-file-grid {
          gap: 10px !important;
          background: #ffffff !important;
        }
        .compact-file-grid-row {
          gap: 10px !important;
          margin: 0 !important;
          background: #ffffff !important;
        }
        .compact-file-grid-row > div {
          padding: 0 !important;
          min-width: 0 !important;
          background: #ffffff !important;
        }
        .compact-file-tile {
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          gap: 4px !important;
          min-height: 78px;
          height: 100%;
          padding: 12px 14px !important;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: #ffffff !important;
          box-shadow: none;
        }
        .file-tile-head {
          align-items: center !important;
          gap: 8px !important;
          margin: 0 !important;
          background: #ffffff !important;
        }
        .file-tile-head > *:first-child {
          flex: 1 1 auto;
          min-width: 0;
        }
        .compact-file-row {
          align-items: center !important;
          gap: var(--space-4) !important;
          padding: var(--space-4) !important;
          border: 1px solid var(--border);
          border-radius: 18px;
          background: var(--surface);
          box-shadow: var(--shadow-soft);
        }
        .compact-file-row:first-child {
          padding-top: var(--space-4) !important;
        }
        .compact-file-row:last-child {
          padding-bottom: var(--space-4) !important;
        }
        .file-row-label-shell,
        .file-row-meta-shell {
          min-width: 0 !important;
        }
        .file-row-label-shell {
          flex: 0 0 210px !important;
        }
        .file-row-meta-shell {
          flex: 1 1 auto !important;
        }
        .file-tile-meta-shell {
          min-height: 0;
          margin: 0 !important;
          padding: 0 !important;
        }
        .file-tile-meta-shell > div {
          margin: 0 !important;
          padding: 0 !important;
        }
        .file-row-label-block {
          min-width: 0;
        }
        .file-row-label {
          font-size: 17px;
          font-weight: 800;
          color: var(--text);
          margin-bottom: 0;
          line-height: 1.2;
        }
        .file-row-copy {
          font-size: 11px;
          line-height: 1.35;
          color: var(--muted);
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .upload-meta-card {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr);
          align-items: center;
          gap: 6px;
          min-height: 0;
          padding: 0;
          border: 0;
          border-radius: 0;
          background: transparent;
        }
        .upload-meta-inline {
          grid-template-columns: auto minmax(0, 1fr) auto;
          align-items: center;
          gap: 8px;
        }
        .file-row-inline-shell .upload-meta-card {
          grid-template-columns: auto minmax(0, 1fr) auto;
        }
        .generated-agent-note {
          min-height: 48px;
          display: flex;
          align-items: center;
          padding: 12px 14px;
          border: 1px solid var(--border);
          border-radius: 16px;
          background: #ffffff !important;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.5;
        }
        .upload-meta-card.ok {
          background: transparent;
        }
        .upload-meta-card.warn {
          background: transparent;
        }
        .upload-meta-path {
          font-size: 11px;
          line-height: 1.25;
          color: #52525b;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .upload-meta-footer {
          display: flex;
          align-items: center;
          gap: 5px;
          flex-wrap: wrap;
        }
        .upload-meta-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 20px;
          padding: 0 7px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--surface);
          color: var(--muted);
          font-size: 11px;
          font-weight: 700;
          white-space: nowrap;
        }
        .upload-meta-badge.ok {
          border-color: #CFEAF0;
          background: #f0fdf4;
          color: #166534;
        }
        .upload-meta-badge.warn {
          border-color: #fed7aa;
          background: #fff7ed;
          color: #9a3412;
        }
        .upload-meta-badge.neutral {
          border-color: var(--border);
          background: var(--surface);
          color: var(--muted);
        }
        .upload-meta-note {
          font-size: 11px;
          line-height: 1.35;
          color: var(--muted);
        }
        .upload-meta-note-inline {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .utility-grid-row {
          gap: 12px !important;
        }
        .utility-grid-row.single > div {
          width: 100% !important;
        }
        .utility-checklist,
        .utility-checklist > div,
        .utility-checklist > div > div,
        .utility-checklist .wrap,
        .utility-checklist .block {
          background: transparent !important;
          box-shadow: none !important;
          border-color: transparent !important;
        }
        .utility-checklist .label-wrap {
          min-height: 0 !important;
          padding-left: 0 !important;
          padding-right: 0 !important;
          margin-bottom: 6px !important;
        }
        .utility-checklist .label-wrap label,
        .utility-checklist .label-wrap span,
        .utility-checklist label {
          background: transparent !important;
        }
        .utility-checklist .wrap.secondary-wrap,
        .utility-checklist .checkboxgroup,
        .utility-checklist .checkbox-group {
          gap: 8px !important;
        }
        .utility-checklist .wrap label,
        .utility-checklist .checkbox-item,
        .utility-checklist .select-item {
          min-height: 32px !important;
          padding: 6px 10px !important;
          border: 1px solid var(--border) !important;
          border-radius: 12px !important;
          background: #ffffff !important;
        }
        .value-flow-shell {
          margin: 0 !important;
          padding: 0 !important;
        }
        .value-flow-card {
          display: grid;
          gap: 10px;
          padding: 4px 0 0;
        }
        .value-flow-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
        }
        .value-flow-title-row {
          display: flex;
          align-items: baseline;
          gap: 10px;
          flex-wrap: wrap;
        }
        .value-flow-title {
          font-size: 14px;
          line-height: 1.25;
          font-weight: 800;
          color: var(--text);
        }
        .value-flow-subtitle,
        .value-flow-meta {
          font-size: 12px;
          line-height: 1.4;
          color: var(--muted);
          font-weight: 600;
        }
        .value-flow-table-shell {
          border: 1px solid var(--border);
          border-radius: 14px;
          overflow: hidden;
          background: #ffffff;
        }
        .value-flow-table {
          width: 100%;
          border-collapse: collapse;
        }
        .value-flow-table th,
        .value-flow-table td {
          padding: 10px 12px;
          border-bottom: 1px solid var(--border);
          text-align: left;
          vertical-align: middle;
        }
        .value-flow-table th {
          font-size: 12px;
          line-height: 1.25;
          font-weight: 700;
          color: var(--muted);
          background: #fcfcfd;
        }
        .value-flow-table tr:last-child td {
          border-bottom: 0;
        }
        .flow-factor-cell {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 14px;
          line-height: 1.35;
          font-weight: 700;
          color: var(--text);
        }
        .flow-factor-dot {
          width: 10px;
          height: 10px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: #ffffff;
          flex: 0 0 auto;
        }
        .flow-factor-dot.outflow {
          background: #f87171;
          border-color: #ef4444;
        }
        .flow-factor-dot.neutral {
          background: #ffffff;
          border-color: #d4d4d8;
        }
        .flow-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          min-height: 26px;
          padding: 0 8px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: #ffffff;
          font-size: 12px;
          line-height: 1.2;
          font-weight: 700;
          white-space: nowrap;
        }
        .flow-pill-symbol {
          font-weight: 900;
        }
        .flow-pill.inflow {
          border-color: #CFEAF0;
          color: #166534;
          background: #f0fdf4;
        }
        .flow-pill.outflow {
          border-color: #fecaca;
          color: #b91c1c;
          background: #fef2f2;
        }
        .flow-pill.input {
          border-color: #d4d4d8;
          color: #3f3f46;
          background: #fafafa;
        }
        .flow-pill.transfer {
          border-color: #c7d2fe;
          color: #3730a3;
          background: #eef2ff;
        }
        .flow-pill.neutral {
          border-color: #e4e4e7;
          color: #71717a;
          background: #ffffff;
        }
        .flow-empty-cell {
          font-size: 13px;
          line-height: 1.5;
          color: var(--muted);
        }
        .file-picker-inline {
          min-width: 0 !important;
          flex: 0 0 auto !important;
        }
        .file-picker-tile {
          width: fit-content !important;
          align-self: flex-start;
          margin-top: auto;
        }
        .file-picker-inline > .block,
        .file-picker-inline .block,
        .file-picker-inline .wrap {
          border: 0 !important;
          box-shadow: none !important;
          background: transparent !important;
          padding: 0 !important;
          min-height: 0 !important;
        }
        .file-picker-inline .orwrap,
        .file-picker-inline .or {
          display: none !important;
        }
        .file-picker-inline button {
          min-height: 28px !important;
          height: 28px !important;
          padding: 0 9px !important;
          border-radius: 9px !important;
          font-size: 11px !important;
          font-weight: 700 !important;
        }
        .file-picker-tile button {
          min-width: 64px !important;
        }
        .file-picker-inline [data-testid="file-preview"],
        .file-picker-inline .file-preview {
          min-height: 0 !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          background: transparent !important;
        }
        .config-grid-row,
        .policy-grid-row,
        .action-panel-buttons {
          gap: 12px !important;
        }
        .compact-config-card .config-grid-row,
        .compact-config-card .policy-grid-row {
          padding-top: 0;
          gap: 2px !important;
          margin: 0 !important;
        }
        .compact-config-card .configure-row-top,
        .compact-config-card .configure-row-middle,
        .compact-config-card .configure-row-fixed {
          min-height: 0 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          margin-bottom: -8px !important;
        }
        .compact-config-card .config-grid-row > div,
        .compact-config-card .policy-grid-row > div {
          padding-top: 0 !important;
          padding-bottom: 0 !important;
          min-height: 0 !important;
        }
        .configure-advanced-accordion {
          margin-top: 0 !important;
        }
        .generation-advanced-accordion {
          margin-top: 0 !important;
        }
        .generation-advanced-accordion .label-wrap,
        .generation-advanced-accordion .accordion-header,
        .run-columns-accordion .label-wrap,
        .run-columns-accordion .accordion-header {
          min-height: 26px !important;
        }
        .configure-advanced-accordion .label-wrap,
        .configure-advanced-accordion .accordion-header {
          min-height: 26px !important;
        }
        .field-medium,
        .field-medium > div,
        .field-medium > div > div {
          max-width: 220px !important;
        }
        .field-compact,
        .field-compact > div,
        .field-compact > div > div {
          max-width: 96px !important;
        }
        .field-long,
        .field-long > div,
        .field-long > div > div {
          max-width: none !important;
          width: 100% !important;
        }
        .field-path textarea,
        .field-path input,
        .field-path .wrap,
        .field-path .block {
          min-height: 36px !important;
        }
        .field-numeric input {
          text-align: left !important;
        }
        .compact-config-card label {
          font-size: 10px !important;
          line-height: 1.05 !important;
          margin-bottom: 0 !important;
        }
        .compact-config-card .label-wrap,
        .compact-config-card .label-wrap.svelte-1gfkn6j,
        .compact-config-card .block-label {
          min-height: 0 !important;
          margin-bottom: 0 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
        }
        .compact-config-card textarea,
        .compact-config-card input[type="text"],
        .compact-config-card input[type="password"],
        .compact-config-card select {
          min-height: 26px !important;
          height: 26px !important;
          padding: 1px 7px !important;
          background: #ffffff !important;
        }
        .compact-config-card select,
        .compact-config-card [role="combobox"],
        .compact-config-card [data-testid="dropdown"] input,
        .compact-config-card [data-testid="dropdown"] button {
          background: #ffffff !important;
          min-height: 26px !important;
          height: 26px !important;
        }
        .compact-config-card [data-testid="dropdown"] .wrap,
        .compact-config-card [data-testid="dropdown"] .block,
        .compact-config-card [data-testid="dropdown"] .inner,
        .compact-config-card [data-testid="dropdown"] > div,
        .compact-config-card [data-testid="dropdown"] > div > div {
          background: #ffffff !important;
          min-height: 26px !important;
        }
        .compact-config-card .field-numeric,
        .compact-config-card .field-numeric > div,
        .compact-config-card .field-numeric > div > div,
        .compact-config-card .field-numeric [data-testid="number-input"],
        .compact-config-card .field-numeric .wrap,
        .compact-config-card .field-numeric .block {
          min-height: 26px !important;
          height: auto !important;
        }
        .compact-config-card .field-numeric input {
          min-height: 26px !important;
          height: 26px !important;
          padding: 1px 7px !important;
        }
        .gradio-container [role="listbox"],
        .gradio-container [role="option"],
        .gradio-container .options,
        .gradio-container .choices,
        .gradio-container .menu,
        .gradio-container .menu *,
        .gradio-container .dropdown-menu,
        .gradio-container .dropdown-menu * {
          background: #ffffff !important;
        }
        .compact-config-card .soft-field {
          margin-bottom: 0 !important;
        }
        .compact-config-card .compact-slider-block {
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          min-width: 0;
        }
        .compact-config-card .compact-slider-field,
        .compact-config-card .compact-slider-field > div,
        .compact-config-card .compact-slider-field > div > div {
          background: transparent !important;
        }
        .compact-config-card .compact-slider-field .label-wrap {
          min-height: 0 !important;
          margin-bottom: 0 !important;
        }
        .compact-config-card .compact-slider-field input[type="number"],
        .compact-config-card .compact-slider-field input[type="text"] {
          min-height: 22px !important;
          padding: 2px 6px !important;
        }
        .compact-config-card .compact-slider-field [data-testid="number-input"],
        .compact-config-card .compact-slider-field [data-testid="slider"],
        .compact-config-card .compact-slider-field .wrap,
        .compact-config-card .compact-slider-field .block {
          gap: 1px !important;
        }
        .compact-config-card .compact-slider-field .container,
        .compact-config-card .compact-slider-field .slider-container {
          gap: 1px !important;
        }
        .compact-config-card .compact-slider-field .container,
        .compact-config-card .compact-slider-field .slider-container,
        .compact-config-card .compact-slider-field [data-testid="number-input"] {
          margin-top: 0 !important;
          margin-bottom: 0 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
        }
        .compact-config-card .compact-slider-block .label-wrap {
          margin-bottom: 0 !important;
        }
        .compact-config-card .configure-row-top,
        .compact-config-card .configure-row-middle,
        .compact-config-card .configure-row-fixed,
        .compact-config-card .configure-row-bottom {
          align-items: end !important;
        }
        .compact-config-card .configure-row-middle {
          flex-wrap: nowrap !important;
          gap: 8px !important;
        }
        .compact-config-card .configure-row-fixed {
          margin-top: -20px !important;
          margin-bottom: -8px !important;
        }
        .compact-config-card .configure-row-top > div,
        .compact-config-card .configure-row-middle > div,
        .compact-config-card .configure-row-fixed > div,
        .compact-config-card .configure-row-bottom > div {
          display: flex !important;
          flex-direction: column !important;
          justify-content: flex-end !important;
          gap: 1px !important;
        }
        .compact-config-card .configure-row-output {
          margin-top: -18px !important;
          align-items: center !important;
          gap: 8px !important;
          flex-wrap: nowrap !important;
        }
        .compact-config-card .configure-output-label-col,
        .compact-config-card .configure-output-field-col {
          min-width: 0 !important;
        }
        .compact-config-card .configure-output-label-col {
          flex: 0 0 126px !important;
          width: 126px !important;
          max-width: 126px !important;
        }
        .compact-config-card .configure-output-field-col {
          flex: 1 1 0 !important;
          width: auto !important;
          max-width: none !important;
          min-width: 0 !important;
        }
        .compact-config-card .configure-row-output .field-output-inline,
        .compact-config-card .configure-row-output .field-output-inline > div,
        .compact-config-card .configure-row-output .field-output-inline > div > div,
        .compact-config-card .configure-row-output .field-output-inline .wrap,
        .compact-config-card .configure-row-output .field-output-inline .block {
          margin-top: 0 !important;
          padding-top: 0 !important;
          align-self: center !important;
        }
        .compact-config-card .configure-output-inline-label-shell,
        .compact-config-card .configure-output-inline-label-shell > div,
        .compact-config-card .configure-output-inline-label-shell .prose {
          width: 126px !important;
          max-width: 126px !important;
          min-width: 126px !important;
          margin: 0 !important;
          padding: 0 !important;
          border: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        .compact-config-card .configure-inline-label-inline {
          font-size: 10px !important;
          line-height: 1.05 !important;
          font-weight: 600 !important;
          color: #64748b !important;
          white-space: nowrap !important;
          display: flex !important;
          align-items: center !important;
          min-height: 26px !important;
        }
        .compact-config-card .configure-row-output > div {
          width: auto !important;
          max-width: none !important;
        }
        .compact-config-card .configure-row-output .field-output-inline,
        .compact-config-card .configure-row-output .field-output-inline > div,
        .compact-config-card .configure-row-output .field-output-inline > div > div {
          flex: 1 1 auto !important;
          width: 100% !important;
          max-width: none !important;
          min-width: 0 !important;
        }
        .compact-config-card .configure-row-output .field-output-inline input,
        .compact-config-card .configure-row-output .field-output-inline textarea {
          min-height: 24px !important;
          height: 24px !important;
        }
        .compact-config-card .config-row-tight + .config-row-tight {
          margin-top: -22px !important;
        }
        .compact-config-card .configure-row-top .soft-field,
        .compact-config-card .configure-row-middle .soft-field {
          margin-top: 0 !important;
        }
        .compact-config-card .configure-min-profit-col label,
        .compact-config-card .configure-min-profit-col [class*="label"] {
          white-space: nowrap !important;
          word-break: keep-all !important;
          overflow-wrap: normal !important;
        }
        .compact-config-card .configure-min-profit-col {
          align-self: end !important;
        }
        .compact-config-card .configure-api-col {
          align-self: end !important;
          min-width: 0 !important;
        }
        .compact-config-card .field-api-key,
        .compact-config-card .field-api-key > div,
        .compact-config-card .field-api-key > div > div,
        .compact-config-card .field-api-key .wrap,
        .compact-config-card .field-api-key .block,
        .compact-config-card .field-api-key [data-testid="textbox"],
        .compact-config-card .field-api-key textarea,
        .compact-config-card .field-api-key input {
          min-height: 24px !important;
          height: 24px !important;
          max-height: 24px !important;
        }
        .compact-config-card .field-api-key textarea,
        .compact-config-card .field-api-key input {
          padding: 1px 7px !important;
          resize: none !important;
        }
        .compact-config-card .configure-row-middle {
          grid-template-columns: 1.6fr 0.9fr 1.25fr !important;
        }
        .compact-config-card .configure-target-col label,
        .compact-config-card .configure-agreement-col label,
        .compact-config-card .configure-target-col [class*="label"],
        .compact-config-card .configure-agreement-col [class*="label"] {
          min-height: 10px !important;
        }
        .compact-config-card .configure-agreement-col {
          min-width: 0 !important;
        }
        .compact-config-card .configure-target-col,
        .compact-config-card .configure-agreement-col {
          padding-left: 0 !important;
          margin-left: 0 !important;
        }
        .compact-config-card .configure-target-col .soft-field,
        .compact-config-card .configure-agreement-col .soft-field {
          margin-left: 0 !important;
        }
        .compact-config-card .agreement-inline-row {
          gap: 8px !important;
          margin: 0 !important;
          padding: 0 !important;
          flex-wrap: nowrap !important;
        }
        .compact-config-card .agreement-inline-row > div {
          min-width: 0 !important;
          padding-top: 0 !important;
          padding-bottom: 0 !important;
        }
        .compact-config-card .configure-fixed-inline-shell {
          align-self: end !important;
        }
        .compact-config-card .configure-fixed-inline-shell label,
        .compact-config-card .configure-fixed-inline-shell [class*="label"] {
          white-space: nowrap !important;
          word-break: keep-all !important;
        }
        .compact-config-card .field-path textarea,
        .compact-config-card .field-path input {
          min-height: 26px !important;
          height: 26px !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
        }
        .compact-label {
          margin-top: 2px;
          margin-bottom: 8px;
        }
        .validation-pill {
          background: var(--surface) !important;
        }
        .validation-mini-row {
          border-top: 1px solid var(--border);
        }
        .validation-mini-badge,
        .check-badge,
        .chip,
        .inline-table-link {
          background: var(--surface) !important;
        }
        .log-console textarea {
          background: #111827 !important;
          color: #f9fafb !important;
          border: 0 !important;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace !important;
          font-size: 15px !important;
          line-height: 1.65 !important;
          min-height: 320px !important;
          padding: 18px !important;
        }
        .summary-markdown {
          color: var(--text);
        }
        .summary-markdown h3 {
          font-size: 18px !important;
          margin-bottom: 14px !important;
        }
        .summary-markdown p,
        .summary-markdown li {
          color: var(--muted);
          font-size: 15px;
          line-height: 1.7;
        }
        .table-shell table {
          border-radius: 18px !important;
          overflow: hidden !important;
          border: 1px solid var(--border) !important;
        }
        .table-shell th {
          background: #fafafa !important;
          color: #6b7280 !important;
          font-weight: 600 !important;
        }
        .table-shell td, .table-shell th {
          padding: 18px 16px !important;
        }
        .iframe-wrap {
          border-radius: var(--radius-xl);
          overflow: hidden;
          border: 1px solid var(--border);
          background: white;
          box-shadow: var(--shadow-soft);
        }
        .iframe-wrap.frameless {
          border: 0;
          background: transparent;
          box-shadow: none;
          border-radius: 0;
        }
        .iframe-empty {
          min-height: 220px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: var(--radius-xl);
          background: var(--surface);
          border: 1px dashed var(--border-strong);
          color: var(--muted);
          font-weight: 600;
        }
        .iframe-host-shell {
          padding: 0 !important;
          border: 0 !important;
          box-shadow: none !important;
          background: transparent !important;
        }
        .iframe-host-shell .block {
          padding: 0 !important;
          border: 0 !important;
          box-shadow: none !important;
          background: transparent !important;
        }
        @media (max-width: 960px) {
          .gradio-container {
            padding: var(--space-4) var(--container-mobile) var(--space-6) var(--container-mobile) !important;
          }
          .topbar-shell {
            margin-left: calc(-1 * var(--container-mobile));
            margin-right: calc(-1 * var(--container-mobile));
            padding: var(--space-4) var(--container-mobile);
          }
          .topbar-inner,
          .brand-lockup {
            flex-direction: column;
            align-items: flex-start;
          }
          .topbar-aside {
            width: 100%;
            flex-direction: column;
            align-items: flex-start;
          }
          .topbar-viz {
            width: 100%;
            min-width: 0;
          }
          .app-title {
            font-size: 28px;
          }
          .run-workflow-shell { grid-template-columns: 1fr; }
          .config-helper-row,
          .generation-cta-row,
          .run-upload-row-inline {
            flex-direction: column;
            align-items: stretch !important;
          }
          .run-control-panel-row {
            flex-direction: column;
          }
          .required-data-grid,
          .field-chip-row,
          .utility-grid-row {
            grid-template-columns: 1fr !important;
          }
          .run-launch-row {
            flex-direction: column;
            align-items: stretch !important;
          }
          .compact-file-row {
            flex-direction: column;
            align-items: stretch !important;
          }
          .compact-file-grid-row {
            flex-direction: column;
          }
          .compact-file-tile {
            min-height: 0;
          }
          .file-row-label-shell {
            flex: 1 1 auto !important;
          }
        }
        @media (max-width: 1240px) {
          .run-workflow-shell { grid-template-columns: repeat(3, minmax(0, 1fr)); }
          .run-control-panel-row {
            flex-direction: column;
          }
          .run-launch-row {
            flex-direction: column;
            align-items: stretch !important;
          }
        }
        .upload-tab-pane .run-workflow-board {
          background: transparent !important;
          border: none !important;
          border-radius: 0 !important;
          box-shadow: none !important;
          padding: 0 !important;
          margin-top: 8px !important;
        }
        .upload-tab-pane .run-control-panel-row {
          margin: 0 !important;
          gap: 18px !important;
          align-items: stretch !important;
        }
        .upload-tab-pane .run-control-col {
          display: flex;
          flex-direction: column;
          gap: 18px !important;
          min-width: 0 !important;
        }
        .upload-tab-pane .run-config-col {
          gap: 18px !important;
        }
        .upload-tab-pane .workflow-step-module {
          background: #ffffff !important;
          border: 1px solid rgba(24, 24, 27, 0.08) !important;
          border-radius: 28px !important;
          box-shadow: 0 14px 36px rgba(15, 23, 42, 0.06), 0 3px 10px rgba(15, 23, 42, 0.04) !important;
          padding: 20px !important;
          overflow: visible !important;
          min-height: 100% !important;
        }
        .upload-tab-pane .workflow-step-module > div,
        .upload-tab-pane .workflow-step-module > div > div,
        .upload-tab-pane .workflow-step-module > div > div > div {
          background: transparent !important;
        }
        .upload-tab-pane .workflow-step-module .block {
          background: transparent !important;
          border: 0 !important;
          box-shadow: none !important;
        }
        .upload-tab-pane .run-launch-bar,
        .upload-tab-pane .run-launch-bar-full {
          margin-top: 18px !important;
        }
        """,
    )


DEFAULT_GITHUB_PAGES_EXPORT_DIR = ROOT / "docs"
