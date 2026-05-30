
from __future__ import annotations

from . import core as _core

globals().update(
    {k: v for k, v in vars(_core).items() if not (k.startswith('__') and k.endswith('__'))}
)

def build_ui():
    default_metric = "final_agree_ratio"

    with gr.Blocks(title="Urban Renewal Negotiation Local Web App", fill_width=True) as demo:
        gr.HTML(
            _topbar_markup("Negotiation playback, policy comparison, and result analysis dashboard")
        )

        with gr.Tabs(elem_classes=["app-tabs-shell"]):
            with gr.Tab("Upload & Run", elem_classes=["upload-tab-pane"]):
                gr.HTML(
                    f'''
                    <iframe
                      src="{_make_run_setup_url(embedded=True)}"
                      style="width:100%;min-height:2200px;border:0;display:block;background:transparent;"
                      loading="lazy"
                    ></iframe>
                    '''
                )
            with gr.Tab("Upload & Run (Legacy)", elem_classes=["upload-tab-pane"], visible=False):
                with gr.Group(elem_classes=["run-workflow-board"]):
                    with gr.Row(equal_height=True, elem_classes=["run-control-panel-row"]):
                        with gr.Column(scale=5, elem_classes=["run-control-col", "run-input-col"]):
                            with gr.Group(elem_classes=["workflow-step-module", "compact-upload-card"]):
                                gr.HTML(_run_step_intro(1, "Input", None))
                                with gr.Column(elem_classes=["run-upload-list"]):
                                    with gr.Group(elem_classes=["run-upload-row"]):
                                        with gr.Row(equal_height=True, elem_classes=["run-upload-row-inline"]):
                                            gr.HTML(
                                                """
                                                <div class="file-row-inline-shell">
                                                  <div class="file-row-inline-title">
                                                    <span class="file-row-label">Community File</span>
                                                    <span class="file-row-chip required">Required</span>
                                                  </div>
                                                  <div class="file-row-inline-meta">
                                                    <div class="file-row-inline-status" id="community-inline-status-anchor"></div>
                                                  </div>
                                                </div>
                                                """
                                            )
                                            run_community_file = gr.UploadButton(
                                                "Upload",
                                                variant="secondary",
                                                size="sm",
                                                type="filepath",
                                                file_types=[".csv", ".xlsx", ".xls"],
                                                elem_classes=["file-picker-inline", "file-picker-tile"],
                                            )
                                        run_community_meta = gr.HTML(
                                            value="",
                                            elem_classes=["file-row-meta-shell", "file-row-inline-shell"],
                                        )

                                    with gr.Group(elem_classes=["run-upload-row"]):
                                        with gr.Row(equal_height=True, elem_classes=["run-upload-row-inline"]):
                                            gr.HTML(
                                                """
                                                <div class="file-row-inline-shell">
                                                  <div class="file-row-inline-title">
                                                    <span class="file-row-label">Boundary Shapefile</span>
                                                    <span class="file-row-chip optional">Optional</span>
                                                  </div>
                                                </div>
                                                """
                                            )
                                            run_shp_upload = gr.UploadButton(
                                                "Upload",
                                                variant="secondary",
                                                size="sm",
                                                file_count="multiple",
                                                file_types=[".shp", ".dbf", ".shx", ".prj", ".cpg", ".qmd", ".qix", ".geojson", ".gpkg"],
                                                elem_classes=["file-picker-inline", "file-picker-tile"],
                                            )
                                        run_shp_meta = gr.HTML(
                                            value="",
                                            elem_classes=["file-row-meta-shell", "file-row-inline-shell"],
                                        )
                                gr.HTML(_run_template_download_markup())
                                with gr.Accordion("Required columns reference", open=False, elem_classes=["run-accordion", "run-columns-accordion"]):
                                    gr.HTML(_required_upload_data_markup())

                        with gr.Column(scale=5, elem_classes=["run-control-col", "run-validate-col"]):
                            with gr.Group(elem_classes=["workflow-step-module", "validation-card"]):
                                gr.HTML(_run_step_intro(2, "Validate", None))
                                run_input_status = gr.HTML()
                                with gr.Group(elem_classes=["generation-status-shell"]):
                                    with gr.Row(equal_height=True, elem_classes=["generation-cta-row"]):
                                        run_generation_meta = gr.HTML(
                                            value="",
                                            elem_classes=["file-row-meta-shell", "file-tile-meta-shell", "generation-meta-shell"],
                                        )
                                        run_generate_agents = gr.Button(
                                            "Generate Residents",
                                            variant="primary",
                                            elem_classes=["generate-primary-button"],
                                        )
                                with gr.Accordion("Advanced settings", open=False, elem_classes=["run-accordion", "run-advanced-accordion", "generation-advanced-accordion"]):
                                    with gr.Row(equal_height=True, elem_classes=["config-grid-row", "generation-settings-row"]):
                                        run_residents_per_household = gr.Number(
                                            value=DEFAULT_RESIDENTS_PER_HOUSEHOLD,
                                            label="Residents per Household",
                                            precision=2,
                                            elem_classes=["soft-field"],
                                        )
                                        run_representatives = gr.Number(
                                            value=DEFAULT_REPRESENTATIVES_PER_COMMUNITY,
                                            precision=0,
                                            label="Representatives per Community",
                                            elem_classes=["soft-field"],
                                        )
                                    with gr.Row(equal_height=True, elem_classes=["config-grid-row", "generation-settings-row"]):
                                        run_vacancy_ratio = gr.Slider(
                                            0.15,
                                            0.6,
                                            value=DEFAULT_VACANCY_RATIO,
                                            step=0.01,
                                            label="Vacant Unit Ratio",
                                        )
                                        run_hardship_quantile = gr.Slider(
                                            0.05,
                                            0.4,
                                            value=DEFAULT_HARDSHIP_QUANTILE,
                                            step=0.01,
                                            label="Hardship Quantile",
                                        )

                        with gr.Column(scale=12, elem_classes=["run-control-col", "run-config-col"]):
                            with gr.Group(elem_classes=["workflow-step-module", "compact-config-card"]):
                                gr.HTML(_run_step_intro(3, "Configure", None))
                                with gr.Row(equal_height=True, elem_classes=["config-grid-row", "config-row-tight", "configure-row-top"]):
                                    with gr.Column(scale=2, min_width=180, elem_classes=["configure-target-col"]):
                                        run_target_community = gr.Dropdown(
                                            choices=[],
                                            value=None,
                                            label="Target Community",
                                            elem_classes=["soft-field", "field-medium"],
                                        )
                                    with gr.Column(scale=2, min_width=180):
                                        run_model_name = gr.Dropdown(
                                            choices=MODEL_OPTIONS,
                                            value=_default_model_name(),
                                            label="Model Name",
                                            allow_custom_value=True,
                                            elem_classes=["soft-field", "field-medium"],
                                        )
                                    with gr.Column(scale=1, min_width=100):
                                        run_rounds = gr.Number(
                                            value=8,
                                            precision=0,
                                            label="Rounds",
                                            elem_classes=["soft-field", "field-compact", "field-numeric"],
                                        )
                                with gr.Row(equal_height=True, elem_classes=["config-grid-row", "config-row-tight", "configure-row-middle"]):
                                    with gr.Column(scale=2, min_width=180, elem_classes=["configure-agreement-col"]):
                                        run_agreement_mode = gr.Dropdown(
                                            choices=[
                                                ("By Build Year", "by_build_year"),
                                                ("Fixed Ratio", "fixed"),
                                            ],
                                            value="by_build_year",
                                            label="Agreement Mode",
                                            elem_classes=["soft-field", "field-medium"],
                                        )
                                    with gr.Column(scale=1, min_width=152, elem_classes=["configure-min-profit-col"]):
                                        run_developer_min_profit = gr.Number(
                                            value=DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
                                            precision=2,
                                            label="Min Profit Rate",
                                            elem_classes=["soft-field", "field-compact", "field-numeric"],
                                        )
                                    with gr.Column(scale=2, min_width=170, elem_classes=["configure-api-col"]):
                                        run_api_key = gr.Textbox(
                                            label="API Key",
                                            type="password",
                                            lines=1,
                                            max_lines=1,
                                            placeholder="Enter API key",
                                            elem_classes=["soft-field", "field-medium", "field-api-key"],
                                        )
                                    with gr.Column(scale=2, min_width=190, elem_classes=["configure-api-base-col"]):
                                        run_api_base_url = gr.Textbox(
                                            label="API Base URL",
                                            lines=1,
                                            max_lines=1,
                                            value=_default_llm_base_url(),
                                            placeholder="Optional OpenAI-compatible endpoint",
                                            elem_classes=["soft-field", "field-medium"],
                                        )
                                with gr.Row(equal_height=True, elem_classes=["config-grid-row", "config-row-tight", "configure-row-fixed"]):
                                    with gr.Column(scale=1, min_width=140):
                                        run_agreement_fixed_ratio = gr.Number(
                                            value=1.0,
                                            precision=2,
                                            label="Fixed Ratio",
                                            elem_classes=["soft-field", "field-compact", "field-numeric"],
                                            visible=False,
                                        )
                                with gr.Row(equal_height=True, elem_classes=["config-grid-row", "policy-grid-row", "config-row-tight"]):
                                    with gr.Column(scale=1, min_width=160, elem_classes=["compact-slider-block"]):
                                        run_max_extension = gr.Slider(
                                            0.0,
                                            0.6,
                                            value=0.3,
                                            step=0.01,
                                            label="Extension Cap",
                                            elem_classes=["compact-slider-field"],
                                        )
                                    with gr.Column(scale=1, min_width=160, elem_classes=["compact-slider-block"]):
                                        run_subsidy_cap = gr.Slider(
                                            0.0,
                                            0.1,
                                            value=0.1,
                                            step=0.01,
                                            label="Subsidy Cap",
                                            elem_classes=["compact-slider-field"],
                                        )
                                with gr.Row(equal_height=True, elem_classes=["config-grid-row", "config-row-tight", "configure-row-bottom", "configure-row-output"]):
                                    with gr.Column(scale=0, min_width=120, elem_classes=["configure-output-label-col"]):
                                        gr.HTML(
                                            '<div class="configure-inline-label-inline">Output Directory</div>',
                                            elem_classes=["configure-output-inline-label-shell"],
                                        )
                                    with gr.Column(scale=1, min_width=0, elem_classes=["configure-output-field-col"]):
                                        run_output_dir = gr.Textbox(
                                            show_label=False,
                                            value=_default_output_dir_ui(),
                                            elem_classes=["soft-field", "field-long", "field-path", "field-output-inline"],
                                        )
                                run_agreement_current_year = gr.Number(
                                    value=_system_current_year(),
                                    precision=0,
                                    label="Current Year",
                                    elem_classes=["soft-field", "field-compact", "field-numeric"],
                                    visible=False,
                                )
                                with gr.Accordion("Advanced settings", open=False, elem_classes=["run-accordion", "run-advanced-accordion", "configure-advanced-accordion"]):
                                    with gr.Accordion("Agreement by build year", open=False, elem_classes=["run-accordion", "run-advanced-accordion"], visible=True) as run_agreement_rules_box:
                                        run_agreement_rules_table = gr.Dataframe(
                                            headers=["max_age", "ratio"],
                                            datatype=["number", "number"],
                                            value=DEFAULT_AGREEMENT_RULE_ROWS,
                                            row_count=(4, "fixed"),
                                            column_count=(2, "fixed"),
                                            interactive=True,
                                            wrap=True,
                                            max_height=280,
                                            elem_classes=["table-shell", "agreement-rule-table"],
                                        )
                                    with gr.Accordion("Utility Setting", open=False, elem_classes=["run-accordion", "run-advanced-accordion", "utility-accordion"]):
                                        run_value_flow_model = gr.HTML(
                                            value=_derive_value_flow_model(_read_table(_default_community_csv()))[0],
                                            elem_classes=["value-flow-shell"],
                                        )
                                        with gr.Accordion("Advanced override", open=False, elem_classes=["run-accordion", "run-advanced-accordion", "utility-override-accordion"]):
                                            with gr.Row(equal_height=False, elem_classes=["utility-grid-row"]):
                                                run_planner_utility_components = gr.CheckboxGroup(
                                                    choices=PLANNER_COST_BENEFIT_OPTIONS,
                                                    value=[value for _, value in PLANNER_COST_BENEFIT_OPTIONS],
                                                    label="Planner",
                                                    elem_classes=["soft-field", "utility-checklist"],
                                                )
                                                run_developer_utility_components = gr.CheckboxGroup(
                                                    choices=DEVELOPER_COST_BENEFIT_OPTIONS,
                                                    value=[value for _, value in DEVELOPER_COST_BENEFIT_OPTIONS],
                                                    label="Developer",
                                                    elem_classes=["soft-field", "utility-checklist"],
                                                )
                                            with gr.Row(equal_height=False, elem_classes=["utility-grid-row single"]):
                                                run_resident_utility_components = gr.CheckboxGroup(
                                                    choices=RESIDENT_COST_BENEFIT_OPTIONS,
                                                    value=[value for _, value in RESIDENT_COST_BENEFIT_OPTIONS],
                                                    label="Resident",
                                                    elem_classes=["soft-field", "utility-checklist"],
                                                )

                    with gr.Group(elem_classes=["workflow-step-module", "run-action-card", "run-launch-bar", "run-launch-bar-full"]):
                        gr.HTML(_run_step_intro(4, "Launch", None))
                        with gr.Row(equal_height=True, elem_classes=["run-launch-row"]):
                            with gr.Column(scale=5, min_width=480, elem_classes=["run-launch-summary-col"]):
                                run_preflight_summary = gr.HTML(
                                    _run_preflight_markup(
                                        None,
                                        _default_model_name(),
                                        8,
                                        "by_build_year",
                                        0.3,
                                        0.1,
                                        DEFAULT_DEVELOPER_MIN_PROFIT_RATE,
                                        _default_output_dir_ui(),
                                        {},
                                    )
                                )
                            with gr.Column(scale=2, min_width=300, elem_classes=["run-launch-actions-col"]):
                                with gr.Row(equal_height=True, elem_classes=["action-panel-buttons"]):
                                    run_button = gr.Button("Upload & Run", variant="primary")
                                    run_reset = gr.Button("Reset", variant="secondary")
                                run_links = gr.HTML()

                with gr.Column(elem_classes=["run-lower-stack"]):
                    with gr.Group(elem_classes=["surface-card", "surface-card-lg"], visible=False) as run_overview_group:
                        gr.HTML(
                            """
                            <div class="section-head compact">
                              <div class="section-title">Current Run Summary</div>
                              <div class="section-copy">No run executed yet. Results will appear here after running a simulation.</div>
                            </div>
                            """
                        )
                        run_overview = gr.Markdown("### No run executed yet.", elem_classes=["summary-markdown"])

                    with gr.Group(elem_classes=["surface-card", "surface-card-lg"], visible=False) as run_log_group:
                        gr.HTML(
                            """
                            <div class="section-head compact">
                              <div class="section-title">Execution Logs</div>
                            </div>
                            """
                        )
                        run_log = gr.Textbox(
                            label="",
                            lines=16,
                            max_lines=24,
                            autoscroll=True,
                            elem_classes=["log-console"],
                        )

                    with gr.Group(elem_classes=["surface-card", "surface-card-lg"], visible=False) as run_result_group:
                        gr.HTML(
                            """
                            <div class="section-head compact">
                              <div class="section-title">Community Result Summary</div>
                            </div>
                            """
                        )
                        run_community_selector = gr.Dropdown(
                            choices=[],
                            value=None,
                            label="Open Community Detail",
                            elem_classes=["soft-field"],
                        )
                        run_summary_table = gr.Dataframe(
                            label="",
                            interactive=False,
                            wrap=True,
                            max_height=320,
                            elem_classes=["table-shell"],
                        )

                run_result_state = gr.State({})
                run_generated_bundle_state = gr.State({})

            with gr.Tab("Experiment Results Analysis"):
                with gr.Row(visible=False):
                    phase2_root = gr.Textbox(
                        label="Experiment Result Directory",
                        value=_default_output_dir_ui(),
                        elem_classes=["soft-field"],
                    )
                    phase2_shp_upload = gr.File(
                        label="Boundary Shapefile",
                        file_count="multiple",
                        file_types=[".shp", ".dbf", ".shx", ".prj", ".cpg", ".qmd", ".qix", ".geojson", ".gpkg"],
                        elem_classes=["file-uploader"],
                        visible=False,
                    )
                    phase2_metric = gr.Dropdown(
                        choices=[(label, key) for key, label in MAP_METRICS.items()],
                        value=default_metric,
                        label="Color Metric",
                        elem_classes=["soft-field"],
                    )
                    phase2_rule = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="Rule",
                        elem_classes=["soft-field"],
                    )
                    phase2_community = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="Quick Open Community",
                        elem_classes=["soft-field"],
                    )
                    phase2_seed = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="Internal Default Seed",
                        visible=False,
                    )
                    phase2_reload = gr.Button("Refresh Analysis", variant="primary")
                    phase2_links = gr.HTML()
                    phase2_overview = gr.Markdown(elem_classes=["summary-markdown"], visible=False)

                with gr.Row():
                    with gr.Group(elem_classes=["iframe-host-shell"]):
                        phase2_map = gr.HTML()

                phase2_map_state = gr.State({})

            with gr.Tab("Policy Comparison"):
                with gr.Group(elem_classes=["iframe-host-shell"]):
                    gr.HTML(
                        _iframe_html(
                            f"/phase2/compare?{urlencode({'phase2_root': _default_output_dir_ui(), 'mode': 'aggregate_policy', 'embedded': '1'})}",
                            "Loading policy comparison workspace...",
                            height=1960,
                            frameless=True,
                        )
                    )

        phase2_main_outputs = [
            phase2_overview,
            phase2_links,
            phase2_map,
            phase2_map_state,
            phase2_rule,
            phase2_community,
            phase2_seed,
        ]

        demo.load(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )
        demo.load(
            fn=preview_run_main,
            inputs=[
                run_community_file,
                run_shp_upload,
                run_residents_per_household,
                run_vacancy_ratio,
                run_representatives,
                run_hardship_quantile,
                run_target_community,
                run_model_name,
                run_rounds,
                run_agreement_mode,
                run_max_extension,
                run_subsidy_cap,
                run_developer_min_profit,
                run_output_dir,
                run_generated_bundle_state,
            ],
            outputs=[
                run_input_status,
                run_target_community,
                run_links,
                run_overview_group,
                run_log_group,
                run_result_group,
                run_community_meta,
                run_generation_meta,
                run_shp_meta,
                run_preflight_summary,
                run_generated_bundle_state,
                run_agreement_rules_box,
                run_value_flow_model,
                run_planner_utility_components,
                run_developer_utility_components,
                run_resident_utility_components,
            ],
        )

        phase2_reload.click(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )
        phase2_rule.change(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )
        phase2_metric.change(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )
        phase2_community.change(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )
        phase2_seed.change(
            fn=refresh_phase2_main,
            inputs=[phase2_root, phase2_shp_upload, phase2_rule, phase2_metric, phase2_community, phase2_seed],
            outputs=phase2_main_outputs,
        )

        preview_inputs = [
            run_community_file,
            run_shp_upload,
            run_residents_per_household,
            run_vacancy_ratio,
            run_representatives,
            run_hardship_quantile,
            run_target_community,
            run_model_name,
            run_rounds,
            run_agreement_mode,
            run_max_extension,
            run_subsidy_cap,
            run_developer_min_profit,
            run_output_dir,
            run_generated_bundle_state,
        ]
        for component in [run_community_file, run_shp_upload]:
            component.upload(
                fn=preview_run_main,
                inputs=preview_inputs,
                outputs=[
                    run_input_status,
                    run_target_community,
                    run_links,
                    run_overview_group,
                    run_log_group,
                    run_result_group,
                    run_community_meta,
                    run_generation_meta,
                    run_shp_meta,
                    run_preflight_summary,
                    run_generated_bundle_state,
                    run_agreement_rules_box,
                    run_value_flow_model,
                    run_planner_utility_components,
                    run_developer_utility_components,
                    run_resident_utility_components,
                ],
            )
        for component in [run_residents_per_household, run_vacancy_ratio, run_representatives, run_hardship_quantile]:
            component.change(
                fn=preview_run_main,
                inputs=preview_inputs,
                outputs=[
                    run_input_status,
                    run_target_community,
                    run_links,
                    run_overview_group,
                    run_log_group,
                    run_result_group,
                    run_community_meta,
                    run_generation_meta,
                    run_shp_meta,
                    run_preflight_summary,
                    run_generated_bundle_state,
                    run_agreement_rules_box,
                    run_value_flow_model,
                    run_planner_utility_components,
                    run_developer_utility_components,
                    run_resident_utility_components,
                ],
            )

        run_generate_agents.click(
            fn=generate_run_agents_main,
            inputs=[
                run_community_file,
                run_shp_upload,
                run_residents_per_household,
                run_vacancy_ratio,
                run_representatives,
                run_hardship_quantile,
                run_target_community,
                run_model_name,
                run_rounds,
                run_agreement_mode,
                run_max_extension,
                run_subsidy_cap,
                run_developer_min_profit,
                run_output_dir,
            ],
            outputs=[
                run_input_status,
                run_target_community,
                run_community_meta,
                run_generation_meta,
                run_shp_meta,
                run_preflight_summary,
                run_generated_bundle_state,
                run_agreement_rules_box,
                run_value_flow_model,
                run_planner_utility_components,
                run_developer_utility_components,
                run_resident_utility_components,
            ],
        )

        run_agreement_mode.change(
            fn=_agreement_visibility_updates,
            inputs=[run_agreement_mode],
            outputs=[
                run_agreement_fixed_ratio,
                run_agreement_current_year,
                run_agreement_rules_box,
            ],
        )

        for component in [
            run_target_community,
            run_model_name,
            run_rounds,
            run_agreement_mode,
            run_agreement_fixed_ratio,
            run_agreement_current_year,
            run_agreement_rules_table,
            run_max_extension,
            run_subsidy_cap,
            run_developer_min_profit,
            run_output_dir,
        ]:
            component.change(
                fn=refresh_run_preflight_main,
                inputs=[
                    run_target_community,
                    run_model_name,
                    run_rounds,
                    run_agreement_mode,
                    run_max_extension,
                    run_subsidy_cap,
                    run_developer_min_profit,
                    run_output_dir,
                    run_generated_bundle_state,
                ],
                outputs=[run_preflight_summary],
            )

        run_outputs = [
            run_overview,
            run_log,
            run_links,
            run_result_state,
            run_community_selector,
            run_summary_table,
            run_overview_group,
            run_log_group,
            run_result_group,
        ]

        run_button.click(
            fn=run_uploaded_simulation_main,
            inputs=[
                run_community_file,
                run_shp_upload,
                run_target_community,
                run_model_name,
                run_rounds,
                run_agreement_mode,
                run_agreement_fixed_ratio,
                run_agreement_current_year,
                run_agreement_rules_table,
                run_residents_per_household,
                run_vacancy_ratio,
                run_representatives,
                run_hardship_quantile,
                run_max_extension,
                run_subsidy_cap,
                run_developer_min_profit,
                run_planner_utility_components,
                run_developer_utility_components,
                run_resident_utility_components,
                run_api_key,
                run_api_base_url,
                run_output_dir,
                run_generated_bundle_state,
            ],
            outputs=run_outputs,
        )
        run_community_selector.change(
            fn=refresh_run_links,
            inputs=[run_result_state, run_community_selector],
            outputs=[run_links],
        )
        run_reset.click(
            fn=reset_run_page,
            inputs=[],
            outputs=[
                run_community_file,
                run_shp_upload,
                run_target_community,
                run_model_name,
                run_rounds,
                run_agreement_mode,
                run_agreement_fixed_ratio,
                run_agreement_current_year,
                run_agreement_rules_table,
                run_residents_per_household,
                run_vacancy_ratio,
                run_representatives,
                run_hardship_quantile,
                run_max_extension,
                run_subsidy_cap,
                run_developer_min_profit,
                run_planner_utility_components,
                run_developer_utility_components,
                run_resident_utility_components,
                run_api_key,
                run_api_base_url,
                run_output_dir,
                run_input_status,
                run_links,
                run_overview,
                run_log,
                run_result_state,
                run_community_selector,
                run_summary_table,
                run_overview_group,
                run_log_group,
                run_result_group,
                run_community_meta,
                run_generation_meta,
                run_shp_meta,
                run_preflight_summary,
                run_generated_bundle_state,
                run_agreement_rules_box,
                run_value_flow_model,
                run_planner_utility_components,
                run_developer_utility_components,
                run_resident_utility_components,
            ],
        )

    return demo

