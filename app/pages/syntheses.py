"""Page Syntheses — Generation & Review."""

from __future__ import annotations

from cache import (
    clear_eleves_cache,
    fetch_classe,
    fetch_eleve_depseudo,
    fetch_eleve_synthese,
    fetch_eleves_with_syntheses,
    fetch_fewshot_count,
    generate_batch_direct,
    get_status_counts,
    is_fewshot_example_direct,
    toggle_fewshot_example_direct,
    update_eleve_matieres_direct,
)
from components.appreciations_view_ng import appreciations, eleve_header
from components.synthese_editor_ng import synthese_editor
from config_ng import estimate_total_cost
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_llm_model, get_llm_provider, get_trimestre


@ui.page("/syntheses")
def syntheses_page(eleve: str = ""):
    with page_layout("Génération & Review"):
        classe_id = get_classe_id()
        trimestre = get_trimestre()

        if not classe_id:
            ui.label("Sélectionnez une classe dans la barre latérale.").classes(
                "text-grey-6"
            )
            return

        # Class name
        classe_info = fetch_classe(classe_id)
        if not classe_info:
            ui.label("Sélectionnez une classe dans la barre latérale.").classes(
                "text-grey-6"
            )
            return
        classe_nom = classe_info.get("nom", classe_id)

        ui.label(f"Classe : {classe_nom} | Trimestre : T{trimestre}").classes(
            "text-body1"
        )

        with (
            ui.card()
            .classes("w-full q-mt-sm")
            .style(
                "border-left: 4px solid var(--chiron-gold); "
                "background: var(--chiron-navy); "
                "padding: 12px 16px;"
            )
        ):
            ui.html(
                "<b>Appréciations</b> et <b>synthèses</b> sont modifiables "
                "directement sur cette page."
                "<ul style='margin: 4px 0 4px 16px; padding: 0;'>"
                "<li>- Les <b>noms et prénoms</b> sont automatiquement "
                "pseudonymisés avant envoi à l'IA.</li>"
                "<li>- Vérifiez qu'aucune <b>information sensible</b> "
                "(situation médicale, familiale…) ne figure dans les appréciations.</li>"
                "<li>- Les synthèses générées sont des suggestions "
                "à adapter par l'enseignant.</li>"
                "</ul>"
            ).style("color: var(--chiron-gold); font-size: 0.875rem;")

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
                "Aucun élève dans cette classe. Importez des bulletins d'abord."
            ).classes("text-grey-6")
            ui.button(
                "Aller à Classe",
                icon="upload",
                on_click=lambda: ui.navigate.to("/import"),
            ).props("rounded")
            return

        # Few-shot count
        fewshot_count = fetch_fewshot_count(classe_id, trimestre)
        page_data["fewshot_count"] = fewshot_count

        # =============================================================
        # BATCH GENERATION — single row
        # =============================================================

        def _cost_tooltip(nb: int) -> str:
            """Build cost tooltip text for batch buttons."""
            provider = get_llm_provider()
            model = get_llm_model() or ""
            try:
                cost = estimate_total_cost(provider, model, nb)
                return f"Coût estimé : ~${cost:.4f} pour {nb} élève(s)"
            except Exception:
                return f"{nb} élève(s)"

        with ui.row().classes("items-center gap-3 q-mt-md"):
            # --- Generate missing ---
            async def _generate_missing():
                gen_missing_btn.props(add="loading")
                try:
                    provider = get_llm_provider()
                    model = get_llm_model()
                    result = await generate_batch_direct(
                        classe_id=classe_id,
                        trimestre=trimestre,
                        provider=provider,
                        model=model,
                    )
                    clear_eleves_cache()
                    success = result.get("total_success", 0)
                    errors = result.get("total_errors", 0)
                    duration = result.get("duration_ms", 0)
                    if errors > 0:
                        ui.notify(
                            f"{success} générée(s), {errors} erreur(s) "
                            f"({duration / 1000:.0f}s)",
                            type="warning",
                        )
                    else:
                        ui.notify(
                            f"{success} synthèse(s) générée(s) ({duration / 1000:.0f}s)",
                            type="positive",
                        )
                    ui.navigate.to("/syntheses")
                except Exception as e:
                    ui.notify(f"Erreur batch: {e}", type="negative")
                finally:
                    gen_missing_btn.props(remove="loading")

            gen_missing_btn = ui.button(
                f"Générer manquantes ({counts['missing']})",
                icon="auto_awesome",
                on_click=_generate_missing,
            ).props(
                f"color=primary rounded {'disable' if counts['missing'] == 0 else ''}"
            )
            gen_missing_btn.tooltip(_cost_tooltip(counts["missing"]))

            # --- Regenerate all ---
            async def _regenerate_all():
                regen_all_btn.props(add="loading")
                try:
                    provider = get_llm_provider()
                    model = get_llm_model()
                    all_ids = [e["eleve_id"] for e in page_data["eleves"]]
                    result = await generate_batch_direct(
                        classe_id=classe_id,
                        trimestre=trimestre,
                        eleve_ids=all_ids,
                        provider=provider,
                        model=model,
                    )
                    clear_eleves_cache()
                    success = result.get("total_success", 0)
                    errors = result.get("total_errors", 0)
                    duration = result.get("duration_ms", 0)
                    if errors == 0:
                        ui.notify(
                            f"{success} régénérée(s) ({duration / 1000:.0f}s)",
                            type="positive",
                        )
                    else:
                        ui.notify(
                            f"{success} régénérée(s), {errors} erreur(s) "
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
                        f"Régénérer toutes les {counts['total']} synthèses ?"
                    ).classes("text-h6")
                    ui.label(
                        "Les synthèses existantes seront supprimées et recréées."
                    ).classes("text-body2 text-grey-7")

                    async def _do_regen():
                        dlg.close()
                        await _regenerate_all()

                    with ui.row().classes("justify-end q-mt-md gap-2"):
                        ui.button("Annuler", on_click=dlg.close).props("flat")
                        ui.button(
                            "Confirmer",
                            on_click=_do_regen,
                        ).props("color=warning rounded")
                dlg.open()

            regen_all_btn = ui.button(
                "Tout régénérer",
                icon="refresh",
                on_click=_confirm_regen,
            ).props(
                f"outline color=orange rounded {'disable' if counts['with_synthese'] == 0 else ''}"
            )
            regen_all_btn.tooltip(_cost_tooltip(counts["total"]))

        ui.separator()

        # =============================================================
        # FILTERS — counts integrated in labels
        # =============================================================

        filter_options = {
            "all": f"Tous ({counts['total']})",
            "missing": f"Sans synthèse ({counts['missing']})",
            "pending": f"Non validées ({counts['pending']})",
            "validated": f"Validées ({counts['validated']})",
        }

        filter_select = ui.toggle(filter_options, value="all").classes("q-mt-md")

        # Student view container — refreshed when filter or navigation changes
        student_container = ui.column().classes("w-full q-mt-md")

        # Navigation state — check query param for deep-link
        nav_state = {"index": 0}

        # Use ?eleve=<id> query param to auto-select a student
        if eleve:
            for i, e in enumerate(page_data["eleves"]):
                if e["eleve_id"] == eleve:
                    nav_state["index"] = i
                    break

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
                    ui.label("Aucun élève ne correspond au filtre.").classes(
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
                    eleve_full = fetch_eleve_depseudo(eleve_id, classe_id)
                except Exception:
                    eleve_full = None

                try:
                    synthese_data = fetch_eleve_synthese(eleve_id, trimestre)
                    syn = synthese_data.get("synthese")
                    syn_id = synthese_data.get("synthese_id")
                except Exception:
                    syn = None
                    syn_id = None

                # Real names come from current (fetch_eleves_with_syntheses)
                prenom = current.get("prenom") or ""
                nom = current.get("nom") or ""
                nom_complet = f"{prenom} {nom}".strip()
                display_name = nom_complet if nom_complet else eleve_id

                with ui.row().classes("items-center gap-3"):
                    ui.label(display_name).classes("text-h5")
                    if current.get("synthese_status") == "validated":
                        ui.badge("validée", color="positive").props("rounded")
                    elif current.get("has_synthese"):
                        ui.badge("en attente", color="warning").props("rounded")
                ui.label(f"ID: {eleve_id}").classes("text-caption text-grey-7")

                # Two columns: Appreciations | Synthese
                with ui.row().classes("w-full gap-4 q-mt-md"):
                    with ui.column().classes("flex-1"):
                        ui.label("Appréciations").classes("text-h6")
                        if eleve_full:
                            eleve_header(eleve_full)

                            def _on_save_appreciations(
                                matieres_editees,
                                _eid=eleve_id,
                                _cid=classe_id,
                                _tri=trimestre,
                            ):
                                update_eleve_matieres_direct(
                                    _eid, _tri, _cid, matieres_editees
                                )
                                ui.notify(
                                    "Appréciations sauvegardées",
                                    type="positive",
                                )
                                _render_student_view()

                            appreciations(
                                eleve_full,
                                editable=True,
                                on_save=_on_save_appreciations,
                            )
                        else:
                            ui.label("Données élève non disponibles").classes(
                                "text-warning"
                            )

                    with ui.column().classes("flex-1"):
                        ui.label("Synthèse").classes("text-h6")

                        # Read LLM state from sidebar
                        provider = get_llm_provider()
                        model = get_llm_model() or ""

                        synthese_editor(
                            eleve_id=eleve_id,
                            synthese=syn,
                            synthese_id=syn_id,
                            trimestre=trimestre,
                            provider=provider,
                            model=model,
                            on_action=_on_editor_action,
                        )

                        # Few-shot example checkbox (validated syntheses only)
                        if syn_id and current.get("synthese_status") == "validated":
                            is_example = is_fewshot_example_direct(syn_id)
                            current_count = page_data.get("fewshot_count", 0)
                            can_toggle = is_example or current_count < 3

                            def _on_fewshot_toggle(
                                e,
                                sid=syn_id,
                            ):
                                toggle_fewshot_example_direct(sid, e.value)
                                new_count = fetch_fewshot_count(classe_id, trimestre)
                                page_data["fewshot_count"] = new_count

                            fewshot_text = (
                                f"Utiliser comme exemple pour l'IA "
                                f"({current_count}/3 exemples)"
                            )
                            cb = ui.checkbox(
                                fewshot_text,
                                value=is_example,
                                on_change=_on_fewshot_toggle,
                            ).classes("q-mt-sm")
                            if not can_toggle:
                                cb.props("disable")
                                cb.tooltip("Maximum 3 exemples atteint")

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
        ui.linear_progress(value=progress_value, show_value=False).props(
            "rounded color=positive"
        ).classes("w-full")
        ui.label(
            f"Progression : {counts['validated']}/{counts['total']} validées"
        ).classes("text-caption text-grey-7")

        if counts["validated"] > 0:
            ui.button(
                "Aller à Export",
                icon="arrow_forward",
                on_click=lambda: ui.navigate.to("/export"),
            ).props("color=primary rounded").classes("q-mt-sm")
