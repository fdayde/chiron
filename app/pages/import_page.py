"""Page Import — Upload et import des bulletins PDF."""

from __future__ import annotations

from cache import (
    clear_eleves_cache,
    delete_eleve_direct,
    fetch_classe,
    fetch_eleves_with_syntheses,
    get_status_counts,
    import_pdf_direct,
)
from components.metric_card_ng import metric_card
from layout import page_layout
from nicegui import run, ui
from state import get_classe_id, get_trimestre


@ui.page("/import")
def import_page():
    with page_layout("Import des bulletins"):
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

        ui.separator()

        # --- Parser warning ---
        try:
            from src.llm.config import settings as _llm_settings

            if _llm_settings.pdf_parser_type.lower() == "mistral_ocr":
                with ui.card().classes("w-full bg-blue-10 q-mb-md"):
                    ui.label(
                        "Parser actif : Mistral OCR. "
                        "Les matieres, notes et absences ne seront pas extraites "
                        "automatiquement. Seul le texte brut sera disponible."
                    ).classes("text-body2")
        except Exception:
            pass

        # =============================================================
        # SECTION 1: FILE UPLOAD & IMPORT
        # =============================================================

        # Collected files (name, bytes) — filled by on_upload callback (per file)
        pending_files: list[tuple[str, bytes]] = []

        upload_results = ui.column().classes("w-full q-mt-md")
        overwrite_checkbox = ui.checkbox(
            "Ecraser les donnees existantes en cas de doublon", value=True
        )

        file_count_label = ui.label("").classes("text-caption text-grey-7")

        async def _on_file_uploaded(e):
            """Called once per file after it is uploaded to the NiceGUI server."""
            content = await e.file.read()
            pending_files.append((e.file.name, content))
            file_count_label.text = f"{len(pending_files)} fichier(s) pret(s)"
            import_btn.props(remove="disable")
            import_btn.update()

        ui.upload(
            label="Deposez les fichiers PDF des bulletins",
            multiple=True,
            auto_upload=True,
            on_upload=_on_file_uploaded,
        ).props('accept=".pdf"').classes("w-full q-mt-md")

        progress = ui.linear_progress(value=0, show_value=False).classes(
            "w-full hidden"
        )
        status_label = ui.label("").classes("hidden")

        async def do_import():
            """Import collected files via HTTP API."""
            if not pending_files:
                ui.notify("Aucun fichier selectionne", type="warning")
                return

            force_overwrite = overwrite_checkbox.value
            progress.set_visibility(True)
            status_label.set_visibility(True)
            import_btn.props(add="loading")

            results = []
            imported_count = 0
            error_count = 0
            overwritten_count = 0
            total = len(pending_files)

            for i, (filename, content) in enumerate(pending_files):
                status_label.text = f"Import de {filename}..."
                progress.value = (i + 0.5) / total

                try:
                    result = await run.io_bound(
                        import_pdf_direct,
                        content,
                        filename,
                        classe_id,
                        trimestre,
                        force_overwrite=force_overwrite,
                    )
                    results.append(
                        {"file": filename, "status": "success", "result": result}
                    )
                    imported_count += len(result.get("eleve_ids", []))
                    overwritten_count += result.get("overwritten_count", 0)
                except Exception as e:
                    results.append(
                        {"file": filename, "status": "error", "error": str(e)}
                    )
                    error_count += 1

                progress.value = (i + 1) / total

            progress.set_visibility(False)
            status_label.set_visibility(False)
            pending_files.clear()
            file_count_label.text = ""
            import_btn.props(remove="loading")
            import_btn.props(add="disable")

            clear_eleves_cache()

            # Refresh class overview
            _render_overview()

            # Display results
            with upload_results:
                upload_results.clear()

                ui.label("Resultats de l'import").classes("text-h6 q-mt-md")

                with ui.row().classes("gap-4 q-mt-sm"):
                    metric_card("PDFs traites", len(results))
                    metric_card("Eleves importes", imported_count)
                    metric_card("Ecrases", overwritten_count)
                    metric_card("Erreurs", error_count)

                if overwritten_count > 0:
                    ui.label(
                        f"{overwritten_count} eleve(s) existant(s) ecrase(s)."
                    ).classes("text-body2 text-info q-mt-sm")

                if error_count > 0:
                    for r in results:
                        if r["status"] == "error":
                            ui.label(f"{r['file']}: {r['error']}").classes(
                                "text-negative"
                            )

                # Detail per file
                with ui.expansion("Detail par fichier").classes("w-full q-mt-sm"):
                    for r in results:
                        if r["status"] == "success":
                            result = r["result"]
                            eleve_ids = result.get("eleve_ids", [])
                            skipped_ids = result.get("skipped_ids", [])
                            overwritten_ids = result.get("overwritten_ids", [])
                            parsed = result.get("parsed_count", 0)

                            if skipped_ids:
                                ui.label(
                                    f"{r['file']}: eleve ignore (deja existant)"
                                ).classes("text-info")
                            elif overwritten_ids:
                                ui.label(
                                    f"{r['file']}: {len(eleve_ids)} eleve(s) ecrase(s)"
                                ).classes("text-info")
                            elif eleve_ids:
                                ui.label(
                                    f"{r['file']}: {len(eleve_ids)} eleve(s) importe(s)"
                                ).classes("text-positive")
                            elif parsed == 0:
                                ui.label(f"{r['file']}: aucun eleve detecte").classes(
                                    "text-warning"
                                )

                            for w in result.get("warnings", []):
                                ui.label(f"{r['file']}: {w}").classes("text-warning")
                        else:
                            ui.label(f"{r['file']}: {r['error']}").classes(
                                "text-negative"
                            )

                if error_count == 0:
                    ui.notify("Import termine. Passez aux syntheses.", type="positive")
                elif error_count == len(results):
                    ui.notify("Aucun fichier importe.", type="negative")
                else:
                    ui.notify(
                        f"Import partiel : {len(results) - error_count} OK, "
                        f"{error_count} erreur(s).",
                        type="warning",
                    )

        import_btn = (
            ui.button("Importer les fichiers", icon="upload", on_click=do_import)
            .props("color=primary disable")
            .classes("q-mt-md")
        )

        # Instructions
        with ui.expansion("Instructions").classes("w-full q-mt-md"):
            ui.markdown(
                "1. Selectionnez la classe et le trimestre dans la barre laterale\n"
                "2. Deposez les fichiers PDF des bulletins ci-dessus\n"
                "3. Cliquez sur **Importer les fichiers**\n"
                "4. Verifiez les resultats\n"
                "5. Passez a la page **Syntheses** pour generer et revoir\n\n"
                "Les noms des eleves sont pseudonymises automatiquement (conformite RGPD)."
            )

        # =============================================================
        # SECTION 2: CLASS OVERVIEW (refreshable)
        # =============================================================

        ui.separator().classes("q-mt-md")
        ui.label("Vue de la classe").classes("text-h6 q-mt-sm")

        overview_container = ui.column().classes("w-full")

        def _render_overview():
            overview_container.clear()
            with overview_container:
                try:
                    eleves_data = fetch_eleves_with_syntheses(classe_id, trimestre)
                    counts = get_status_counts(eleves_data)
                except Exception:
                    eleves_data = []
                    counts = {
                        "total": 0,
                        "with_synthese": 0,
                        "validated": 0,
                        "pending": 0,
                        "missing": 0,
                    }

                if counts["total"] == 0:
                    ui.label(
                        "Aucun eleve importe pour cette classe/trimestre."
                    ).classes("text-grey-6 q-mt-sm")
                else:
                    with ui.row().classes("gap-4 q-mt-sm"):
                        metric_card("Eleves", counts["total"])
                        metric_card("Syntheses", counts["with_synthese"])
                        metric_card("Validees", counts["validated"])
                        metric_card("Manquantes", counts["missing"])

                    rows = []
                    for e in eleves_data:
                        prenom = e.get("prenom") or ""
                        nom = e.get("nom") or ""
                        display_name = f"{prenom} {nom}".strip() or e["eleve_id"]
                        rows.append(
                            {
                                "eleve_id": e["eleve_id"],
                                "eleve": display_name,
                                "genre": e.get("genre") or "?",
                                "absences": e.get("absences_demi_journees", 0) or 0,
                                "synthese": ("ok" if e.get("has_synthese") else "-"),
                                "statut": e.get("synthese_status", "-") or "-",
                            }
                        )

                    table = ui.table(
                        columns=[
                            {"name": "eleve", "label": "Eleve", "field": "eleve"},
                            {"name": "genre", "label": "Genre", "field": "genre"},
                            {
                                "name": "absences",
                                "label": "Abs.",
                                "field": "absences",
                            },
                            {
                                "name": "synthese",
                                "label": "Synthese",
                                "field": "synthese",
                            },
                            {
                                "name": "statut",
                                "label": "Statut",
                                "field": "statut",
                            },
                            {
                                "name": "actions",
                                "label": "Actions",
                                "field": "actions",
                            },
                        ],
                        rows=rows,
                    ).classes("w-full q-mt-sm")

                    table.add_slot(
                        "body-cell-actions",
                        r"""
                        <q-td :props="props">
                            <q-btn flat dense round icon="delete" color="negative"
                                   @click="$parent.$emit('delete', props.row)" />
                        </q-td>
                        """,
                    )

                    def _on_delete(e):
                        row = e.args
                        eid = row["eleve_id"]
                        name = row["eleve"]

                        with ui.dialog() as dlg, ui.card():
                            ui.label(f"Supprimer {name} ?").classes("text-h6")
                            ui.label(
                                "L'eleve et ses syntheses seront definitivement supprimes."
                            ).classes("text-body2 text-grey-7")

                            def _confirm():
                                dlg.close()
                                try:
                                    delete_eleve_direct(eid, trimestre)
                                    clear_eleves_cache()
                                    ui.notify(f"{name} supprime", type="positive")
                                    _render_overview()
                                except Exception as exc:
                                    ui.notify(
                                        f"Erreur suppression: {exc}", type="negative"
                                    )

                            with ui.row().classes("justify-end q-mt-md gap-2"):
                                ui.button("Annuler", on_click=dlg.close).props("flat")
                                ui.button("Supprimer", on_click=_confirm).props(
                                    "color=negative"
                                )
                        dlg.open()

                    table.on("delete", _on_delete)

                    ui.separator().classes("q-mt-md")

                    if counts["missing"] > 0:
                        ui.label(f"{counts['missing']} eleve(s) sans synthese").classes(
                            "text-info"
                        )

                    ui.button(
                        "Generer et revoir les syntheses",
                        icon="arrow_forward",
                        on_click=lambda: ui.navigate.to("/syntheses"),
                    ).props("color=primary").classes("q-mt-sm")

        _render_overview()
