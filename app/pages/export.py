"""Page Export — Récapitulatif et export presse-papiers."""

from __future__ import annotations

from cache import (
    delete_trimestre_data,
    fetch_classe,
    fetch_classe_stats,
    fetch_eleve_synthese,
    fetch_eleves_with_syntheses,
    get_status_counts,
)
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre


@ui.page("/export")
def export_page():
    with page_layout("Export & Bilan"):
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

        ui.separator()

        # =============================================================
        # RECAPITULATIF
        # =============================================================

        try:
            eleves_data = fetch_eleves_with_syntheses(classe_id, trimestre)
            counts = get_status_counts(eleves_data)
        except Exception as e:
            ui.label(f"Erreur: {e}").classes("text-negative")
            return

        # Recapitulatif + couts sur une seule ligne
        stats = fetch_classe_stats(classe_id, trimestre)
        with ui.row().classes("items-center gap-4 q-mt-md flex-wrap"):
            ui.label(
                f"{counts['total']} élèves · "
                f"{counts['with_synthese']} générées · "
                f"{counts['validated']} validées · "
                f"{counts['pending']} en attente"
            ).classes("text-body2")

            if stats:
                cost_usd = stats.get("cost_usd", 0)
                tokens_in = stats.get("tokens_input", 0)
                tokens_out = stats.get("tokens_output", 0)
                tokens_total = stats.get("tokens_total", 0)
                cost_label = ui.label(f"Coût total : ${cost_usd:.4f}").classes(
                    "text-body2 text-weight-bold"
                )
                cost_label.tooltip(
                    f"Tokens entrée : {tokens_in:,} · "
                    f"Tokens sortie : {tokens_out:,} · "
                    f"Tokens total : {tokens_total:,}"
                )

        ui.separator()

        # =============================================================
        # WARNINGS
        # =============================================================

        if counts["missing"] > 0:
            missing_ids = [
                e["eleve_id"] for e in eleves_data if not e.get("has_synthese")
            ]
            with (
                ui.card()
                .classes("w-full q-mt-md")
                .style(
                    "background: rgba(212, 132, 62, 0.12); border-left: 3px solid #D4843E"
                )
            ):
                ui.label(f"{counts['missing']} élève(s) sans synthèse").classes(
                    "text-weight-bold text-amber-3"
                )
                ui.label(f"IDs: {', '.join(missing_ids[:10])}").classes(
                    "text-caption text-grey-5"
                )
                if len(missing_ids) > 10:
                    ui.label(f"... et {len(missing_ids) - 10} autre(s)").classes(
                        "text-caption text-grey-5"
                    )
                ui.button(
                    "Aller générer",
                    icon="arrow_forward",
                    on_click=lambda: ui.navigate.to("/syntheses"),
                ).props("flat size=sm rounded")

        if counts["pending"] > 0:
            pending_ids = [
                e["eleve_id"]
                for e in eleves_data
                if e.get("has_synthese") and e.get("synthese_status") != "validated"
            ]
            with (
                ui.card()
                .classes("w-full q-mt-md")
                .style(
                    "background: rgba(74, 88, 153, 0.15); border-left: 3px solid #4A5899"
                )
            ):
                ui.label(f"{counts['pending']} synthèse(s) non validée(s)").classes(
                    "text-weight-bold text-light-blue-3"
                )
                ui.label(f"IDs: {', '.join(pending_ids[:10])}").classes(
                    "text-caption text-grey-5"
                )
                if len(pending_ids) > 10:
                    ui.label(f"... et {len(pending_ids) - 10} autre(s)").classes(
                        "text-caption text-grey-5"
                    )

        if counts["total"] == 0:
            ui.label(
                "Aucun élève importé. Commencez par importer des bulletins."
            ).classes("text-grey-6 q-mt-md")
            ui.button(
                "Aller à Classe",
                icon="upload",
                on_click=lambda: ui.navigate.to("/import"),
            ).props("rounded")
            return

        if counts["validated"] == 0:
            ui.label("Aucune synthèse validée à exporter.").classes(
                "text-warning q-mt-md"
            )
            ui.button(
                "Aller valider",
                icon="arrow_forward",
                on_click=lambda: ui.navigate.to("/syntheses"),
            ).props("rounded")
            return

        # Load syntheses for preview & export
        syntheses_data = []
        for eleve in eleves_data:
            if not eleve.get("has_synthese"):
                continue
            try:
                data = fetch_eleve_synthese(eleve["eleve_id"], trimestre)
                syn = data.get("synthese")
                if syn:
                    prenom = eleve.get("prenom") or ""
                    nom = eleve.get("nom") or ""
                    display = f"{prenom} {nom}".strip() or eleve["eleve_id"]
                    syntheses_data.append(
                        {
                            "eleve_id": eleve["eleve_id"],
                            "display_name": display,
                            "synthese": syn,
                            "status": data.get("status", "unknown"),
                        }
                    )
            except Exception:
                pass

        # =============================================================
        # EXPORT (above preview)
        # =============================================================

        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("content_copy").classes("text-primary")
            ui.label("Export").classes("text-h6")

        async def _copy_to_clipboard():
            validated = [s for s in syntheses_data if s["status"] == "validated"]
            lines = []
            for item in validated:
                lines.append(f"# {item['display_name']}")
                lines.append(item["synthese"].get("synthese_texte", ""))
                lines.append("")
            text = "\n".join(lines)
            escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            await ui.run_javascript(f"navigator.clipboard.writeText(`{escaped}`)")
            ui.notify("Copie dans le presse-papiers", type="positive")

        ui.button(
            f"Copier les synthèses ({counts['validated']} validées)",
            icon="content_copy",
            on_click=_copy_to_clipboard,
        ).props("color=primary rounded")

        # =============================================================
        # SUPPRESSION DES DONNÉES (RGPD)
        # =============================================================

        if counts["missing"] == 0 and counts["pending"] == 0:
            ui.separator().classes("q-mt-md")
            with (
                ui.card()
                .classes("w-full q-mt-md")
                .style(
                    "background: rgba(244, 67, 54, 0.05); "
                    "border-left: 3px solid #f44336"
                )
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("delete_forever", color="negative")
                    ui.label("Supprimer les données du trimestre").classes(
                        "text-lg font-bold"
                    )
                ui.label(
                    f"Toutes les synthèses T{trimestre} sont validées. "
                    f"Vous pouvez supprimer les données de ce trimestre "
                    f"({counts['total']} élèves). Cette action est irréversible."
                ).classes("text-body2")
                ui.label(
                    "Les données de plus de 30 jours sont également "
                    "supprimées automatiquement au lancement."
                ).classes("text-caption text-grey-7")

                def _open_delete_dialog():
                    with ui.dialog() as dlg, ui.card():
                        ui.label(
                            f"Supprimer les données du trimestre {trimestre} ?"
                        ).classes("text-h6")
                        ui.label(
                            f"{counts['total']} élèves et "
                            f"{counts['validated']} synthèses seront "
                            f"définitivement supprimés."
                        ).classes("text-body2 text-grey-7")
                        ui.label(
                            "Assurez-vous d'avoir exporté les synthèses "
                            "avant de continuer."
                        ).classes("text-caption text-warning")

                        def _confirm_delete():
                            dlg.close()
                            try:
                                result = delete_trimestre_data(classe_id, trimestre)
                                ui.notify(
                                    f"T{trimestre} : "
                                    f"{result['deleted_eleves']} élèves, "
                                    f"{result['deleted_syntheses']} synthèses, "
                                    f"{result['deleted_mappings']} mappings "
                                    f"supprimés.",
                                    type="positive",
                                )
                                ui.navigate.to("/home")
                            except Exception as exc:
                                ui.notify(
                                    f"Erreur lors de la suppression : {exc}",
                                    type="negative",
                                )

                        with ui.row().classes("justify-end q-mt-md gap-2"):
                            ui.button("Annuler", on_click=dlg.close).props(
                                "flat rounded"
                            )
                            ui.button(
                                "Supprimer",
                                icon="delete_forever",
                                on_click=_confirm_delete,
                            ).props("color=negative rounded")
                    dlg.open()

                ui.button(
                    f"Supprimer les données T{trimestre}",
                    icon="delete_forever",
                    on_click=_open_delete_dialog,
                ).props("color=negative rounded")

        ui.separator().classes("q-mt-md")

        # =============================================================
        # PREVIEW
        # =============================================================

        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("visibility").classes("text-primary")
            ui.label("Aperçu").classes("text-h6")

        # Filter
        filter_options = {
            "all": "Toutes",
            "validated": "Validées uniquement",
            "pending": "En attente uniquement",
        }
        preview_filter = ui.select(
            options=filter_options,
            label="Filtrer par statut",
            value="all",
        ).classes("w-48")

        preview_container = ui.column().classes("w-full q-mt-sm")

        def _render_preview():
            preview_container.clear()
            f = preview_filter.value
            if f == "validated":
                filtered = [s for s in syntheses_data if s["status"] == "validated"]
            elif f == "pending":
                filtered = [s for s in syntheses_data if s["status"] != "validated"]
            else:
                filtered = syntheses_data

            with preview_container:
                ui.label(f"{len(filtered)} synthèse(s)").classes(
                    "text-caption text-grey-7"
                )

                for item in filtered[:5]:
                    with ui.card().classes("w-full p-3 q-mb-xs"):
                        with ui.row().classes("w-full gap-4"):
                            with ui.column().classes("gap-0"):
                                ui.label(item["display_name"]).classes(
                                    "text-weight-bold"
                                )
                                status_icon = (
                                    "check_circle"
                                    if item["status"] == "validated"
                                    else "pending"
                                )
                                with ui.row().classes("items-center gap-1"):
                                    ui.icon(status_icon).classes(
                                        "text-positive"
                                        if item["status"] == "validated"
                                        else "text-warning"
                                    )
                                    ui.label(item["status"]).classes("text-caption")

                            text = item["synthese"].get("synthese_texte", "")
                            display_text = (
                                text[:250] + "..." if len(text) > 250 else text
                            )
                            ui.label(display_text).classes("text-body2 flex-1")

                if len(filtered) > 5:
                    ui.label(f"... et {len(filtered) - 5} autre(s)").classes(
                        "text-caption text-grey-6"
                    )

        preview_filter.on_value_change(lambda _: _render_preview())
        _render_preview()
