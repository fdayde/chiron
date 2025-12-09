"""Générateur de synthèses avec orchestration LLM."""

import logging

from src.core.models import EleveExtraction, EleveGroundTruth, SyntheseGeneree
from src.generation.prompt_builder import PromptBuilder
from src.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class SyntheseGenerator:
    """Génère des synthèses pour les élèves via LLM.

    Usage:
        generator = SyntheseGenerator()
        generator.set_exemples(exemples_fewshot)
        synthese = generator.generate(eleve)
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
    ) -> None:
        """Initialise le générateur.

        Args:
            provider: Provider LLM (openai, anthropic, mistral).
            model: Modèle spécifique (None = défaut du provider).
        """
        self.provider = provider
        self.model = model
        self._llm = LLMManager()
        self._prompt_builder = PromptBuilder()

    def set_exemples(self, exemples: list[EleveGroundTruth]) -> None:
        """Définit les exemples few-shot.

        Args:
            exemples: Liste d'élèves avec synthèses de référence.
        """
        self._prompt_builder = PromptBuilder(exemples=exemples)
        logger.info(f"Few-shot configuré avec {len(exemples)} exemple(s)")

    def generate(
        self,
        eleve: EleveExtraction,
        classe_info: str | None = None,
        max_tokens: int = 5000,
    ) -> SyntheseGeneree:
        """Génère une synthèse avec insights pour un élève.

        Args:
            eleve: Données de l'élève.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens en sortie.

        Returns:
            SyntheseGeneree avec texte et insights structurés.
        """
        messages = self._prompt_builder.build_messages(eleve, classe_info)

        logger.info(
            f"Génération synthèse pour {eleve.eleve_id or 'élève'} "
            f"via {self.provider}/{self.model or 'default'}"
        )

        # Appel LLM avec parsing JSON automatique
        parsed_json, metadata = self._llm.call_with_json_parsing_sync(
            provider=self.provider,
            messages=messages,
            model=self.model,
            max_tokens=max_tokens,
            context_name=f"synthese_{eleve.eleve_id or 'eleve'}",
        )

        # Valider avec Pydantic
        synthese = SyntheseGeneree(**parsed_json)

        logger.info(
            f"Synthèse générée: {len(synthese.synthese_texte)} chars, "
            f"{len(synthese.alertes)} alertes, {len(synthese.reussites)} réussites, "
            f"posture={synthese.posture_generale}, "
            f"{metadata.get('total_tokens', 0)} tokens"
        )

        return synthese

    def generate_batch(
        self,
        eleves: list[EleveExtraction],
        classe_info: str | None = None,
        max_tokens: int = 5000,
    ) -> list[SyntheseGeneree | None]:
        """Génère des synthèses pour plusieurs élèves.

        Args:
            eleves: Liste d'élèves.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens.

        Returns:
            Liste de SyntheseGeneree (None si erreur).
        """
        logger.info(f"Batch génération: {len(eleves)} élèves")

        results = []
        for eleve in eleves:
            try:
                synthese = self.generate(eleve, classe_info, max_tokens)
                results.append(synthese)
            except Exception as e:
                logger.error(f"Erreur pour {eleve.eleve_id}: {e}")
                results.append(None)

        success_count = sum(1 for r in results if r is not None)
        logger.info(f"Batch terminé: {success_count}/{len(eleves)} succès")

        return results
