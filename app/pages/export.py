"""Page Export — Recapitulatif et export CSV."""

from __future__ import annotations

from cache import (
    fetch_classe,
    fetch_classe_stats,
    fetch_eleve_synthese,
    fetch_eleves_with_syntheses,
    get_status_counts,
)
from components.metric_card_ng import metric_card
from layout import page_layout
from nicegui import ui
from state import get_classe_id, get_trimestre


@ui.page("/export")
def export_page():
    with page_layout("Export & Bilan"):
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

        # =============================================================
        # RECAPITULATIF
        # =============================================================

        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("assessment").classes("text-primary")
            ui.label("Recapitulatif").classes("text-h6")

        try:
            eleves_data = fetch_eleves_with_syntheses(classe_id, trimestre)
            counts = get_status_counts(eleves_data)
        except Exception as e:
            ui.label(f"Erreur: {e}").classes("text-negative")
            return

        with ui.row().classes("gap-4 q-mt-md"):
            metric_card("Eleves", counts["total"])
            metric_card("Syntheses generees", counts["with_synthese"])
            metric_card("Syntheses validees", counts["validated"])
            metric_card("En attente", counts["pending"])

        # Cost stats
        stats = fetch_classe_stats(classe_id, trimestre)
        if stats:
            with ui.row().classes("items-center gap-2 q-mt-md"):
                ui.icon("payments").classes("text-primary")
                ui.label("Couts de generation").classes("text-h6")
            with ui.row().classes("gap-4"):
                metric_card("Tokens entree", f"{stats.get('tokens_input', 0):,}")
                metric_card("Tokens sortie", f"{stats.get('tokens_output', 0):,}")
                metric_card("Tokens total", f"{stats.get('tokens_total', 0):,}")
                metric_card("Cout total", f"${stats.get('cost_usd', 0):.4f}")

        ui.separator()

        # =============================================================
        # WARNINGS
        # =============================================================

        if counts["missing"] > 0:
            missing_ids = [
                e["eleve_id"] for e in eleves_data if not e.get("has_synthese")
            ]
            with ui.card().classes("w-full bg-orange-10 q-mt-md"):
                ui.label(f"{counts['missing']} eleve(s) sans synthese").classes(
                    "text-weight-bold text-warning"
                )
                ui.label(f"IDs: {', '.join(missing_ids[:10])}").classes(
                    "text-caption text-grey-7"
                )
                if len(missing_ids) > 10:
                    ui.label(f"... et {len(missing_ids) - 10} autre(s)").classes(
                        "text-caption text-grey-7"
                    )
                ui.button(
                    "Aller generer",
                    icon="arrow_forward",
                    on_click=lambda: ui.navigate.to("/syntheses"),
                ).props("flat size=sm")

        if counts["pending"] > 0:
            pending_ids = [
                e["eleve_id"]
                for e in eleves_data
                if e.get("has_synthese") and e.get("synthese_status") != "validated"
            ]
            with ui.card().classes("w-full bg-blue-10 q-mt-md"):
                ui.label(f"{counts['pending']} synthese(s) non validee(s)").classes(
                    "text-weight-bold text-info"
                )
                ui.label(f"IDs: {', '.join(pending_ids[:10])}").classes(
                    "text-caption text-grey-7"
                )
                if len(pending_ids) > 10:
                    ui.label(f"... et {len(pending_ids) - 10} autre(s)").classes(
                        "text-caption text-grey-7"
                    )

        if counts["total"] == 0:
            ui.label(
                "Aucun eleve importe. Commencez par importer des bulletins."
            ).classes("text-grey-6 q-mt-md")
            ui.button(
                "Aller a Import",
                icon="upload",
                on_click=lambda: ui.navigate.to("/import"),
            )
            return

        if counts["validated"] == 0:
            ui.label("Aucune synthese validee a exporter.").classes(
                "text-warning q-mt-md"
            )
            ui.button(
                "Aller valider",
                icon="arrow_forward",
                on_click=lambda: ui.navigate.to("/syntheses"),
            )
            return

        ui.separator()

        # =============================================================
        # PREVIEW
        # =============================================================

        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("visibility").classes("text-primary")
            ui.label("Apercu").classes("text-h6")

        # Load syntheses for preview
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

        # Filter
        filter_options = {
            "all": "Toutes",
            "validated": "Validees uniquement",
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
                ui.label(f"{len(filtered)} synthese(s)").classes(
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

        ui.separator()

        # =============================================================
        # EXPORT
        # =============================================================

        with ui.row().classes("items-center gap-2 q-mt-md"):
            ui.icon("download").classes("text-primary")
            ui.label("Export").classes("text-h6")

        with ui.row().classes("w-full gap-8"):
            # CSV export
            with ui.column().classes("flex-1"):
                ui.label("CSV").classes("text-h6")
                ui.label("Export des syntheses validees au format CSV").classes(
                    "text-caption text-grey-7"
                )

                if counts["validated"] == 0:
                    ui.label("Aucune synthese validee").classes("text-warning")
                else:

                    async def _download_csv():
                        url = f"/export/csv?classe_id={classe_id}&trimestre={trimestre}"
                        await ui.run_javascript(
                            f'window.open("{url}", "_blank")',
                        )

                    ui.button(
                        f"Telecharger CSV ({counts['validated']} syntheses)",
                        icon="download",
                        on_click=_download_csv,
                    ).props("color=primary")

            # Clipboard copy
            with ui.column().classes("flex-1"):
                ui.label("Presse-papiers").classes("text-h6")
                ui.label("Copier les syntheses pour coller dans un document").classes(
                    "text-caption text-grey-7"
                )

                async def _copy_to_clipboard():
                    validated = [
                        s for s in syntheses_data if s["status"] == "validated"
                    ]
                    lines = []
                    for item in validated:
                        lines.append(f"# {item['display_name']}")
                        lines.append(item["synthese"].get("synthese_texte", ""))
                        lines.append("")
                    text = "\n".join(lines)
                    escaped = (
                        text.replace("\\", "\\\\")
                        .replace("`", "\\`")
                        .replace("$", "\\$")
                    )
                    await ui.run_javascript(
                        f"navigator.clipboard.writeText(`{escaped}`)"
                    )
                    ui.notify("Copie dans le presse-papiers", type="positive")

                ui.button(
                    "Copier dans le presse-papiers",
                    icon="content_copy",
                    on_click=_copy_to_clipboard,
                ).props("outline")
