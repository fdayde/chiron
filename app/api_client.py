"""Client HTTP pour l'API Chiron."""

from __future__ import annotations

import os

import httpx


class ChironAPIClient:
    """Client pour interagir avec l'API Chiron."""

    # Timeout for standard requests (seconds)
    DEFAULT_TIMEOUT = 30.0

    # Extended timeout for LLM generation (can take 30-60s)
    LLM_TIMEOUT = 120.0

    # Extended timeout for PDF import (NER model loading can take 60s+ first time)
    IMPORT_TIMEOUT = 300.0

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv(
            "CHIRON_UI_API_BASE_URL", "http://localhost:8000"
        )
        # Persistent client for connection reuse (avoids TCP handshake overhead)
        self._client = httpx.Client(timeout=self.DEFAULT_TIMEOUT)

    def close(self) -> None:
        """Ferme le client HTTP sous-jacent."""
        self._client.close()

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Lève une exception avec le détail de l'erreur API si disponible."""
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise httpx.HTTPStatusError(detail, request=response.request, response=response)

    def _get(
        self, endpoint: str, params: dict | None = None, timeout: float | None = None
    ) -> dict | list:
        """Effectue une requête GET."""
        response = self._client.get(
            f"{self.base_url}{endpoint}",
            params=params,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    def _post(
        self,
        endpoint: str,
        json: dict | None = None,
        files: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Effectue une requête POST."""
        response = self._client.post(
            f"{self.base_url}{endpoint}",
            json=json,
            files=files,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    def _patch(self, endpoint: str, json: dict, timeout: float | None = None) -> dict:
        """Effectue une requête PATCH."""
        response = self._client.patch(
            f"{self.base_url}{endpoint}",
            json=json,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    def _delete(self, endpoint: str, timeout: float | None = None) -> dict:
        """Effectue une requête DELETE."""
        response = self._client.delete(
            f"{self.base_url}{endpoint}",
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    # Classes
    def list_classes(
        self, annee_scolaire: str | None = None, niveau: str | None = None
    ) -> list[dict]:
        """Lister toutes les classes."""
        params = {}
        if annee_scolaire:
            params["annee_scolaire"] = annee_scolaire
        if niveau:
            params["niveau"] = niveau
        return self._get("/classes", params or None)

    def create_classe(
        self, nom: str, niveau: str | None = None, annee_scolaire: str | None = None
    ) -> dict:
        """Créer une nouvelle classe."""
        data: dict = {"nom": nom, "niveau": niveau}
        if annee_scolaire:
            data["annee_scolaire"] = annee_scolaire
        return self._post("/classes", json=data)

    def get_classe(self, classe_id: str) -> dict:
        """Récupérer une classe par ID."""
        return self._get(f"/classes/{classe_id}")

    def delete_classe(self, classe_id: str) -> dict:
        """Supprimer une classe."""
        return self._delete(f"/classes/{classe_id}")

    def get_classe_stats(self, classe_id: str, trimestre: int) -> dict:
        """Statistiques agrégées pour une classe et un trimestre."""
        return self._get(f"/classes/{classe_id}/stats", {"trimestre": trimestre})

    # Eleves
    def get_eleves(self, classe_id: str, trimestre: int | None = None) -> list[dict]:
        """Récupérer les élèves d'une classe."""
        params = {"trimestre": trimestre} if trimestre else None
        return self._get(f"/classes/{classe_id}/eleves", params)

    def get_eleves_with_syntheses(self, classe_id: str, trimestre: int) -> list[dict]:
        """Récupérer les élèves avec leurs synthèses en un seul appel.

        Optimisé pour éviter les requêtes N+1.
        """
        return self._get(
            f"/classes/{classe_id}/eleves-with-syntheses",
            {"trimestre": trimestre},
        )

    def get_eleve(self, eleve_id: str) -> dict:
        """Récupérer un élève par ID."""
        return self._get(f"/eleves/{eleve_id}")

    def get_eleve_synthese(self, eleve_id: str, trimestre: int | None = None) -> dict:
        """Récupérer la synthèse d'un élève."""
        params = {"trimestre": trimestre} if trimestre else None
        return self._get(f"/eleves/{eleve_id}/synthese", params)

    def delete_eleve(self, eleve_id: str) -> dict:
        """Supprimer un élève."""
        return self._delete(f"/eleves/{eleve_id}")

    # Syntheses
    def generate_synthese(
        self,
        eleve_id: str,
        trimestre: int,
        provider: str = "anthropic",
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Générer une synthèse pour un élève via LLM.

        Args:
            eleve_id: Identifiant de l'élève.
            trimestre: Numéro du trimestre.
            provider: Provider LLM (openai, anthropic, mistral).
            model: Modèle spécifique (None = défaut du provider).
            temperature: Température de sampling (None = défaut backend).

        Returns:
            Synthèse générée avec métadonnées.
        """
        payload: dict = {
            "eleve_id": eleve_id,
            "trimestre": trimestre,
            "provider": provider,
        }
        if model:
            payload["model"] = model
        if temperature is not None:
            payload["temperature"] = temperature

        return self._post(
            "/syntheses/generate",
            json=payload,
            timeout=self.LLM_TIMEOUT,
        )

    def update_synthese(
        self,
        synthese_id: str,
        synthese_texte: str | None = None,
        alertes: list[dict] | None = None,
        reussites: list[dict] | None = None,
    ) -> dict:
        """Modifier une synthèse."""
        data = {}
        if synthese_texte is not None:
            data["synthese_texte"] = synthese_texte
        if alertes is not None:
            data["alertes"] = alertes
        if reussites is not None:
            data["reussites"] = reussites
        return self._patch(f"/syntheses/{synthese_id}", json=data)

    def validate_synthese(
        self, synthese_id: str, validated_by: str | None = None
    ) -> dict:
        """Valider une synthèse."""
        return self._post(
            f"/syntheses/{synthese_id}/validate",
            json={"validated_by": validated_by},
        )

    def delete_synthese(self, synthese_id: str) -> dict:
        """Supprimer une synthèse."""
        return self._delete(f"/syntheses/{synthese_id}")

    def get_pending_syntheses(self, classe_id: str | None = None) -> dict:
        """Récupérer les synthèses en attente de validation."""
        params = {"classe_id": classe_id} if classe_id else None
        return self._get("/syntheses/pending", params)

    # Import/Export
    def import_pdf(
        self, file_content: bytes, filename: str, classe_id: str, trimestre: int
    ) -> dict:
        """Importer un bulletin PDF."""
        response = self._client.post(
            f"{self.base_url}/import/pdf",
            params={"classe_id": classe_id, "trimestre": trimestre},
            files={"file": (filename, file_content, "application/pdf")},
            timeout=self.IMPORT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    def import_pdf_batch(
        self,
        files: list[tuple[str, bytes]],
        classe_id: str,
        trimestre: int,
    ) -> dict:
        """Importer plusieurs bulletins PDF."""
        files_data = [
            ("files", (name, content, "application/pdf")) for name, content in files
        ]
        response = self._client.post(
            f"{self.base_url}/import/pdf/batch",
            params={"classe_id": classe_id, "trimestre": trimestre},
            files=files_data,
            timeout=self.IMPORT_TIMEOUT,
        )
        self._raise_for_status(response)
        return response.json()

    def export_csv(self, classe_id: str, trimestre: int) -> bytes:
        """Exporter les synthèses validées en CSV."""
        response = self._client.get(
            f"{self.base_url}/export/csv",
            params={"classe_id": classe_id, "trimestre": trimestre},
        )
        self._raise_for_status(response)
        return response.content

    # Health
    def health(self) -> dict:
        """Vérifier la santé de l'API."""
        return self._get("/health")
