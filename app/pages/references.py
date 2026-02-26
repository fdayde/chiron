"""Page Fondements scientifiques — références académiques de Chiron."""

from layout import page_layout
from nicegui import ui

_REFERENCES = [
    {
        "number": "1",
        "title": "Growth mindset",
        "accent": "#D4843E",
        "icon": "psychology",
        "citation": (
            "Dweck, C. S. (2006). "
            "*Mindset: The New Psychology of Success.* Random House."
        ),
        "usage": (
            "Les synthèses décrivent ce que l'élève **fait** "
            "(travaille régulièrement, participe activement), "
            "jamais ce qu'il/elle **est** (brillant, doué, faible)."
        ),
    },
    {
        "number": "2",
        "title": "Feed-up / feed-back / feed-forward",
        "accent": "#4A5899",
        "icon": "sync_alt",
        "citation": (
            "Hattie, J. & Timperley, H. (2007). The Power of Feedback. "
            "*Review of Educational Research*, 77(1), 81-112."
        ),
        "usage": (
            "Structure tripartite de chaque synthèse : "
            "où en est l'élève (feed-up), "
            "constats observables (feed-back), "
            "direction concrète pour progresser (feed-forward)."
        ),
    },
    {
        "number": "3",
        "title": "Engagement contextuel",
        "accent": "#C8A45C",
        "icon": "emoji_objects",
        "citation": (
            "Ryan, R. M. & Deci, E. L. (2000). "
            "Self-determination theory and the facilitation of intrinsic "
            "motivation, social development, and well-being. "
            "*American Psychologist*, 55(1), 68-78."
        ),
        "usage": (
            "Le profil d'engagement est un **instantané** du trimestre, "
            "pas une étiquette de personnalité. "
            "L'engagement varie selon les matières et les contextes."
        ),
    },
    {
        "number": "4",
        "title": "Biais de genre dans les appréciations",
        "accent": "#9C27B0",
        "icon": "balance",
        "citation": (
            "Charousset, P. & Monnet, M. (2026). "
            "À niveau égal, appréciation égale ? "
            "Comment les appréciations scolaires varient en fonction "
            "du sexe des élèves. *Note IPP*, janvier 2026."
        ),
        "usage": (
            "Signalement — pas diagnostic — des formulations "
            "potentiellement genrées (effort vs talent, comportement, "
            "registre émotionnel). Outil de vigilance pour le professeur principal."
        ),
    },
]


@ui.page("/references")
def references_page():
    """Page des fondements scientifiques."""
    with page_layout("Fondements scientifiques"):
        ui.label("Les principes de recherche sur lesquels s'appuie Chiron").classes(
            "text-subtitle1 text-grey-7"
        )

        for ref in _REFERENCES:
            with (
                ui.card()
                .classes("w-full q-mt-md")
                .style(f"border-left: 3px solid {ref['accent']}")
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.icon(ref["icon"]).style(f"color: {ref['accent']}")
                    ui.label(f"{ref['number']}. {ref['title']}").classes("text-h6")
                ui.markdown(ref["citation"]).classes("text-body2 text-grey-5 q-mt-xs")
                ui.separator().classes("q-my-sm")
                with ui.row().classes("items-center gap-1"):
                    ui.icon("arrow_right", size="xs").classes("text-grey-6")
                    ui.label("Usage dans Chiron").classes(
                        "text-caption text-weight-bold text-grey-5"
                    )
                ui.markdown(ref["usage"]).classes("text-body2 q-ml-md")

        # Limites
        with (
            ui.card()
            .classes("w-full q-mt-lg")
            .style(
                "background: rgba(74, 88, 153, 0.12); "
                "border: 1px solid rgba(74, 88, 153, 0.3)"
            )
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("info").style("color: #C8A45C")
                ui.label("Limites et précautions").classes(
                    "text-weight-bold text-grey-4"
                )
            ui.markdown(
                "- Les appréciations enseignantes sont souvent brèves "
                "et partielles. Chiron n'a accès qu'à un trimestre, "
                "sans contexte familial, social ou médical.\n"
                "- Les constats sont formulés avec prudence "
                '("les résultats suggèrent", "on observe ce trimestre").\n'
                '- Le profil "insuffisant" (données trop brèves) '
                "est préféré à une interprétation forcée."
            ).classes("text-body2 text-grey-5 q-mt-sm")

        # Lien vers docs completes
        with ui.row().classes("q-mt-lg justify-center"):
            ui.link(
                "Documentation complète (docs/references.md)",
                "https://github.com/fdayde/chiron/blob/main/docs/references.md",
                new_tab=True,
            ).classes("text-caption")
