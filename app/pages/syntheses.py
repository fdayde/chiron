"""Page Syntheses — Generation & Review."""

from __future__ import annotations

from cache import (
    clear_eleves_cache,
    fetch_classe,
    fetch_eleve,
    fetch_eleve_synthese,
    fetch_eleves_with_syntheses,
    generate_batch_direct,
    get_status_counts,
)
from components.appreciations_view_ng import appreciations, eleve_header
from components.llm_selector_ng import cost_estimate_label, llm_selector
from components.metric_card_ng import metric_card
from components.synthese_editor_ng import synthese_editor
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre


@ui.page("/syntheses")
def syntheses_page():
    with page_layout("Generation & Review"):
        classe_id = get_classe_id()
        trimestre = get_trimestre()

        if not classe_id:
            ui.label("Selectionnez une classe dans la barre laterale.").classes(
                "text-grey-6"
            )
            return

        # Class name
        classe_info = fetch_classe(classe_id)
        classe_nom = classe_info.get("nom", classe_id) if classe_info else classe_id

        ui.label(f"Classe : {classe_nom} | Trimestre : T{trimestre}").classes(
            "text-body1"
        )

        # Fetch data (mutable container so refresh can update it)
        page_data = {"eleves": [], "counts": {}}
        try:
            page_data["eleves"] = fetch_eleves_with_syntheses(classe_id, trimestre)
            page_data["counts"] = get_status_counts(page_data["eleves"])
        except Exception as e:
            ui.label(f"Erreur: {e}").classes("text-negative")
            return
        counts = page_data["counts"]

        if counts["total"] == 0:
            ui.label(
                "Aucun eleve dans cette classe. Importez des bulletins d'abord."
            ).classes("text-grey-6")
            ui.button(
                "Aller a Import",
                icon="upload",
                on_click=lambda: ui.navigate.to("/import"),
            )
            return

        # Metrics
        with ui.row().classes("gap-4 q-mt-md"):
            metric_card("Eleves", counts["total"])
            metric_card("Generees", counts["with_synthese"])
            metric_card("Validees", counts["validated"])
            metric_card("En attente", counts["pending"])

        ui.separator()

        # =============================================================
        # LLM CONFIG
        # =============================================================

        # Store selected provider/model in a mutable container
        llm_state = {"provider": "anthropic", "model": None}

        def _on_llm_change(provider, model):
            llm_state["provider"] = provider
            llm_state["model"] = model

        provider_sel, model_sel = llm_selector(on_change=_on_llm_change)
        # Initialize state from default values
        llm_state["provider"] = provider_sel.value
        llm_state["model"] = model_sel.value

        # =============================================================
        # BATCH GENERATION
        # =============================================================

        with ui.expansion(
            "Generation batch",
            icon="smart_toy",
            value=counts["missing"] > 0,
        ).classes("w-full q-mt-md"):
            with ui.row().classes("w-full gap-8"):
                with ui.column().classes("flex-1"):
                    cost_estimate_label(
                        llm_state["provider"],
                        llm_state["model"] or "",
                        counts["missing"],
                    )

                    async def _generate_missing():
                        gen_missing_btn.props(add="loading")
                        try:
                            result = await generate_batch_direct(
                                classe_id=classe_id,
                                trimestre=trimestre,
                                provider=llm_state["provider"],
                                model=llm_state["model"],
                            )
                            clear_eleves_cache()
                            success = result.get("total_success", 0)
                            errors = result.get("total_errors", 0)
                            duration = result.get("duration_ms", 0)
                            if errors > 0:
                                ui.notify(
                                    f"{success} generee(s), {errors} erreur(s) "
                                    f"({duration / 1000:.0f}s)",
                                    type="warning",
                                )
                            else:
                                ui.notify(
                                    f"{success} synthese(s) generee(s) ({duration / 1000:.0f}s)",
                                    type="positive",
                                )
                            ui.navigate.to("/syntheses")
                        except Exception as e:
                            ui.notify(f"Erreur batch: {e}", type="negative")
                        finally:
                            gen_missing_btn.props(remove="loading")

                    gen_missing_btn = ui.button(
                        f"Generer manquantes ({counts['missing']})",
                        icon="auto_awesome",
                        on_click=_generate_missing,
                    ).props(
                        f"color=primary {'disable' if counts['missing'] == 0 else ''}"
                    )

                with ui.column().classes("flex-1"):
                    cost_estimate_label(
                        llm_state["provider"],
                        llm_state["model"] or "",
                        counts["total"],
                    )

                    async def _regenerate_all():
                        regen_all_btn.props(add="loading")
                        try:
                            all_ids = [e["eleve_id"] for e in page_data["eleves"]]
                            result = await generate_batch_direct(
                                classe_id=classe_id,
                                trimestre=trimestre,
                                eleve_ids=all_ids,
                                provider=llm_state["provider"],
                                model=llm_state["model"],
                            )
                            clear_eleves_cache()
                            success = result.get("total_success", 0)
                            errors = result.get("total_errors", 0)
                            duration = result.get("duration_ms", 0)
                            if errors == 0:
                                ui.notify(
                                    f"{success} regeneree(s) ({duration / 1000:.0f}s)",
                                    type="positive",
                                )
                            else:
                                ui.notify(
                                    f"{success} regeneree(s), {errors} erreur(s) "
                                    f"({duration / 1000:.0f}s)",
                                    type="warning",
                                )
                            ui.navigate.to("/syntheses")
                        except Exception as e:
                            ui.notify(f"Erreur batch: {e}", type="negative")
                        finally:
                            regen_all_btn.props(remove="loading")

                    async def _confirm_regen():
                        with ui.dialog() as dlg, ui.card():
                            ui.label(
                                f"Regenerer toutes les {counts['total']} syntheses ?"
                            ).classes("text-h6")
                            ui.label(
                                "Les syntheses existantes seront supprimees et recreees."
                            ).classes("text-body2 text-grey-7")

                            async def _do_regen():
                                dlg.close()
                                await _regenerate_all()

                            with ui.row().classes("justify-end q-mt-md gap-2"):
                                ui.button("Annuler", on_click=dlg.close).props("flat")
                                ui.button(
                                    "Confirmer",
                                    on_click=_do_regen,
                                ).props("color=warning")
                        dlg.open()

                    regen_all_btn = ui.button(
                        "Tout regenerer",
                        icon="refresh",
                        on_click=_confirm_regen,
                    ).props(
                        f"outline color=orange {'disable' if counts['with_synthese'] == 0 else ''}"
                    )
                    if counts["with_synthese"] == 0:
                        regen_all_btn.tooltip(
                            "Aucune synthese a regenerer. Utilisez 'Generer manquantes'."
                        )

        ui.separator()

        # =============================================================
        # FILTERS
        # =============================================================

        filter_options = {
            "all": "Tous",
            "missing": "Sans synthese",
            "pending": "Non validees",
            "validated": "Validees",
        }

        filter_select = ui.toggle(filter_options, value="all").classes("q-mt-md")

        # Student view container — refreshed when filter or navigation changes
        student_container = ui.column().classes("w-full q-mt-md")

        # Navigation state
        nav_state = {"index": 0}

        def _get_filtered():
            eleves = page_data["eleves"]
            f = filter_select.value
            if f == "missing":
                return [e for e in eleves if not e.get("has_synthese")]
            elif f == "pending":
                return [
                    e
                    for e in eleves
                    if e.get("has_synthese") and e.get("synthese_status") != "validated"
                ]
            elif f == "validated":
                return [e for e in eleves if e.get("synthese_status") == "validated"]
            return eleves

        def _render_student_view():
            student_container.clear()
            filtered = _get_filtered()

            if not filtered:
                with student_container:
                    ui.label("Aucun eleve ne correspond au filtre.").classes(
                        "text-grey-6"
                    )
                return

            if nav_state["index"] >= len(filtered):
                nav_state["index"] = 0

            current = filtered[nav_state["index"]]
            eleve_id = current["eleve_id"]

            with student_container:
                # Navigation
                with ui.row().classes("w-full items-center justify-between"):
                    ui.button(
                        icon="chevron_left",
                        on_click=lambda: (_nav(-1),),
                    ).props(f"flat {'disable' if nav_state['index'] == 0 else ''}")

                    ui.label(f"{nav_state['index'] + 1} / {len(filtered)}").classes(
                        "text-h6"
                    )

                    ui.button(
                        icon="chevron_right",
                        on_click=lambda: (_nav(1),),
                    ).props(
                        f"flat {'disable' if nav_state['index'] >= len(filtered) - 1 else ''}"
                    )

                ui.separator()

                # Fetch full student data
                try:
                    eleve_full = fetch_eleve(eleve_id)
                except Exception:
                    eleve_full = None

                try:
                    synthese_data = fetch_eleve_synthese(eleve_id, trimestre)
                    syn = synthese_data.get("synthese")
                    syn_id = synthese_data.get("synthese_id")
                except Exception:
                    syn = None
                    syn_id = None

                # Student header with real name
                status_badge = ""
                if current.get("synthese_status") == "validated":
                    status_badge = " (validee)"
                elif current.get("has_synthese"):
                    status_badge = " (en attente)"

                # Real names come from current (fetch_eleves_with_syntheses)
                prenom = current.get("prenom") or ""
                nom = current.get("nom") or ""
                nom_complet = f"{prenom} {nom}".strip()
                display_name = nom_complet if nom_complet else eleve_id

                ui.label(f"{display_name}{status_badge}").classes("text-h5")
                ui.label(f"ID: {eleve_id}").classes("text-caption text-grey-7")

                # Two columns: Appreciations | Synthese
                with ui.row().classes("w-full gap-4 q-mt-md"):
                    with ui.column().classes("flex-1"):
                        ui.label("Appreciations").classes("text-h6")
                        if eleve_full:
                            eleve_header(eleve_full)
                            appreciations(eleve_full)
                        else:
                            ui.label("Donnees eleve non disponibles").classes(
                                "text-warning"
                            )

                    with ui.column().classes("flex-1"):
                        ui.label("Synthese").classes("text-h6")
                        synthese_editor(
                            eleve_id=eleve_id,
                            synthese=syn,
                            synthese_id=syn_id,
                            trimestre=trimestre,
                            provider=llm_state["provider"],
                            model=llm_state["model"] or "",
                            on_action=_on_editor_action,
                        )

        def _on_editor_action():
            """Re-fetch data and re-render student view in place (keeps index)."""
            clear_eleves_cache()
            try:
                page_data["eleves"] = fetch_eleves_with_syntheses(classe_id, trimestre)
                page_data["counts"] = get_status_counts(page_data["eleves"])
            except Exception:
                pass
            _render_student_view()

        def _nav(delta):
            nav_state["index"] += delta
            _render_student_view()

        filter_select.on_value_change(lambda _: _render_student_view())

        # Initial render
        _render_student_view()

        # =============================================================
        # FOOTER: PROGRESS
        # =============================================================

        ui.separator().classes("q-mt-md")

        progress_value = (
            counts["validated"] / counts["total"] if counts["total"] > 0 else 0
        )
        ui.linear_progress(value=progress_value, show_value=False).classes("w-full")
        ui.label(
            f"Progression : {counts['validated']}/{counts['total']} validees"
        ).classes("text-caption text-grey-7")

        if counts["validated"] > 0:
            ui.button(
                "Aller a Export",
                icon="arrow_forward",
                on_click=lambda: ui.navigate.to("/export"),
            ).props("color=primary").classes("q-mt-sm")
