"""HTTP client for Chiron API."""

from __future__ import annotations

import os

import httpx


class ChironAPIClient:
    """Client for interacting with the Chiron API."""

    # Timeout for standard requests (seconds)
    DEFAULT_TIMEOUT = 30.0

    # Extended timeout for LLM generation (can take 30-60s)
    LLM_TIMEOUT = 120.0

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv(
            "CHIRON_UI_API_BASE_URL", "http://localhost:8000"
        )

    def _get(
        self, endpoint: str, params: dict | None = None, timeout: float | None = None
    ) -> dict | list:
        """Make a GET request."""
        with httpx.Client(timeout=timeout or self.DEFAULT_TIMEOUT) as client:
            response = client.get(f"{self.base_url}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()

    def _post(
        self,
        endpoint: str,
        json: dict | None = None,
        files: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Make a POST request."""
        with httpx.Client(timeout=timeout or self.DEFAULT_TIMEOUT) as client:
            response = client.post(f"{self.base_url}{endpoint}", json=json, files=files)
            response.raise_for_status()
            return response.json()

    def _patch(self, endpoint: str, json: dict, timeout: float | None = None) -> dict:
        """Make a PATCH request."""
        with httpx.Client(timeout=timeout or self.DEFAULT_TIMEOUT) as client:
            response = client.patch(f"{self.base_url}{endpoint}", json=json)
            response.raise_for_status()
            return response.json()

    def _delete(self, endpoint: str, timeout: float | None = None) -> dict:
        """Make a DELETE request."""
        with httpx.Client(timeout=timeout or self.DEFAULT_TIMEOUT) as client:
            response = client.delete(f"{self.base_url}{endpoint}")
            response.raise_for_status()
            return response.json()

    # Classes
    def list_classes(
        self, annee_scolaire: str | None = None, niveau: str | None = None
    ) -> list[dict]:
        """List all classes."""
        params = {}
        if annee_scolaire:
            params["annee_scolaire"] = annee_scolaire
        if niveau:
            params["niveau"] = niveau
        return self._get("/classes", params or None)

    def create_classe(
        self, nom: str, niveau: str | None = None, annee_scolaire: str = "2024-2025"
    ) -> dict:
        """Create a new class."""
        return self._post(
            "/classes",
            json={"nom": nom, "niveau": niveau, "annee_scolaire": annee_scolaire},
        )

    def get_classe(self, classe_id: str) -> dict:
        """Get a class by ID."""
        return self._get(f"/classes/{classe_id}")

    def delete_classe(self, classe_id: str) -> dict:
        """Delete a class."""
        return self._delete(f"/classes/{classe_id}")

    # Eleves
    def get_eleves(self, classe_id: str, trimestre: int | None = None) -> list[dict]:
        """Get students for a class."""
        params = {"trimestre": trimestre} if trimestre else None
        return self._get(f"/classes/{classe_id}/eleves", params)

    def get_eleve(self, eleve_id: str) -> dict:
        """Get a student by ID."""
        return self._get(f"/eleves/{eleve_id}")

    def get_eleve_synthese(self, eleve_id: str, trimestre: int | None = None) -> dict:
        """Get the synthesis for a student."""
        params = {"trimestre": trimestre} if trimestre else None
        return self._get(f"/eleves/{eleve_id}/synthese", params)

    def delete_eleve(self, eleve_id: str) -> dict:
        """Delete a student."""
        return self._delete(f"/eleves/{eleve_id}")

    # Syntheses
    def generate_synthese(
        self,
        eleve_id: str,
        trimestre: int,
        provider: str = "openai",
        model: str | None = None,
        temperature: float = 0.7,
    ) -> dict:
        """Generate a synthesis for a student using LLM.

        Args:
            eleve_id: Student identifier.
            trimestre: Trimester number.
            provider: LLM provider (openai, anthropic, mistral).
            model: Specific model (None = provider default).
            temperature: Sampling temperature.

        Returns:
            Generated synthesis with metadata.
        """
        payload = {
            "eleve_id": eleve_id,
            "trimestre": trimestre,
            "provider": provider,
            "temperature": temperature,
        }
        if model:
            payload["model"] = model

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
        """Update a synthesis."""
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
        """Validate a synthesis."""
        return self._post(
            f"/syntheses/{synthese_id}/validate",
            json={"validated_by": validated_by},
        )

    def delete_synthese(self, synthese_id: str) -> dict:
        """Delete a synthesis."""
        return self._delete(f"/syntheses/{synthese_id}")

    def get_pending_syntheses(self, classe_id: str | None = None) -> dict:
        """Get all pending syntheses."""
        params = {"classe_id": classe_id} if classe_id else None
        return self._get("/syntheses/pending", params)

    # Import/Export
    def import_pdf(
        self, file_content: bytes, filename: str, classe_id: str, trimestre: int
    ) -> dict:
        """Import a PDF bulletin."""
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/import/pdf",
                params={"classe_id": classe_id, "trimestre": trimestre},
                files={"file": (filename, file_content, "application/pdf")},
            )
            response.raise_for_status()
            return response.json()

    def import_pdf_batch(
        self,
        files: list[tuple[str, bytes]],
        classe_id: str,
        trimestre: int,
    ) -> dict:
        """Import multiple PDF bulletins."""
        with httpx.Client() as client:
            files_data = [
                ("files", (name, content, "application/pdf")) for name, content in files
            ]
            response = client.post(
                f"{self.base_url}/import/pdf/batch",
                params={"classe_id": classe_id, "trimestre": trimestre},
                files=files_data,
            )
            response.raise_for_status()
            return response.json()

    def export_csv(self, classe_id: str, trimestre: int) -> bytes:
        """Export validated syntheses as CSV."""
        with httpx.Client() as client:
            response = client.get(
                f"{self.base_url}/export/csv",
                params={"classe_id": classe_id, "trimestre": trimestre},
            )
            response.raise_for_status()
            return response.content

    # Health
    def health(self) -> dict:
        """Check API health."""
        return self._get("/health")
