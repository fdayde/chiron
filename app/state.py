"""State management pour NiceGUI (remplace st.session_state).

Utilise app.storage.user pour un état par utilisateur (identifié par cookie).
Comportement similaire à st.session_state de Streamlit.

Note : app.storage.tab nécessite une connexion WebSocket et n'est pas
disponible au premier rendu HTTP. app.storage.user fonctionne dès la
requête initiale car il s'appuie sur un cookie de session.
"""

from nicegui import app


def get_classe_id() -> str | None:
    """Retourne l'ID de la classe sélectionnée."""
    return app.storage.user.get("classe_id")


def set_classe_id(classe_id: str | None) -> None:
    """Définit la classe sélectionnée."""
    app.storage.user["classe_id"] = classe_id


def get_trimestre() -> int:
    """Retourne le trimestre sélectionné (1, 2 ou 3)."""
    return app.storage.user.get("trimestre", 1)


def set_trimestre(trimestre: int) -> None:
    """Définit le trimestre sélectionné."""
    app.storage.user["trimestre"] = trimestre


def get_llm_provider() -> str:
    """Retourne le provider LLM sélectionné."""
    return app.storage.user.get("llm_provider", "mistral")


def set_llm_provider(provider: str) -> None:
    """Définit le provider LLM sélectionné."""
    app.storage.user["llm_provider"] = provider


def get_llm_model() -> str | None:
    """Retourne le modèle LLM sélectionné."""
    return app.storage.user.get("llm_model")


def set_llm_model(model: str | None) -> None:
    """Définit le modèle LLM sélectionné."""
    app.storage.user["llm_model"] = model
