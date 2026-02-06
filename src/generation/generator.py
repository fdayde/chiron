"""Générateur de synthèses avec orchestration LLM."""

import logging
from dataclasses import dataclass

from src.core.models import EleveExtraction, EleveGroundTruth, SyntheseGeneree
from src.generation.prompt_builder import PromptBuilder
from src.llm.config import settings as llm_settings
from src.llm.manager import LLMManager

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Résultat de génération avec métadonnées LLM."""

    synthese: SyntheseGeneree
    """Synthèse générée."""

    metadata: dict
    """Métadonnées LLM (tokens, model, etc.)."""


class SyntheseGenerator:
    """Génère des synthèses pour les élèves via LLM.

    Usage:
        generator = SyntheseGenerator()
        generator.set_exemples(exemples_fewshot)
        synthese = generator.generate(eleve)

        # Ou avec métadonnées complètes
        result = generator.generate_with_metadata(eleve)
        print(result.synthese, result.metadata)

        # Pour les tests, injecter un mock LLMManager
        mock_llm = MockLLMManager()
        generator = SyntheseGenerator(llm_manager=mock_llm)
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        *,
        llm_manager: LLMManager | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        """Initialise le générateur.

        Args:
            provider: Provider LLM (openai, anthropic, mistral).
            model: Modèle spécifique (None = défaut du provider).
            llm_manager: LLMManager à utiliser (optionnel, pour tests/DI).
            prompt_builder: PromptBuilder à utiliser (optionnel, pour tests/DI).
        """
        self.provider = provider
        self.model = model
        self._llm = llm_manager or LLMManager()
        self._prompt_builder = prompt_builder or PromptBuilder()

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
        max_tokens: int | None = None,
    ) -> SyntheseGeneree:
        """Génère une synthèse avec insights pour un élève.

        Args:
            eleve: Données de l'élève.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens en sortie (défaut: config synthese_max_tokens).

        Returns:
            SyntheseGeneree avec texte et insights structurés.

        Note:
            Use generate_with_metadata() to also get LLM metadata.
        """
        result = self.generate_with_metadata(eleve, classe_info, max_tokens)
        return result.synthese

    def generate_with_metadata(
        self,
        eleve: EleveExtraction,
        classe_info: str | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Génère une synthèse avec métadonnées LLM complètes.

        Args:
            eleve: Données de l'élève.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens en sortie (défaut: config synthese_max_tokens).

        Returns:
            GenerationResult avec synthèse et métadonnées.
        """
        if max_tokens is None:
            max_tokens = llm_settings.synthese_max_tokens

        messages = self._prompt_builder.build_messages(eleve, classe_info)

        logger.info(
            f"Génération synthèse pour {eleve.eleve_id or 'élève'} "
            f"via {self.provider}/{self.model or 'default'}"
        )

        # Appel LLM avec parsing JSON automatique
        parsed_json, llm_metadata = self._llm.call_with_json_parsing_sync(
            provider=self.provider,
            messages=messages,
            model=self.model,
            max_tokens=max_tokens,
            context_name=f"synthese_{eleve.eleve_id or 'eleve'}",
        )

        # Valider avec Pydantic
        synthese = SyntheseGeneree(**parsed_json)

        # Construire les métadonnées normalisées
        metadata = {
            "llm_provider": self.provider,
            "llm_model": llm_metadata.get("model", self.model),
            "llm_response_raw": llm_metadata.get("content", ""),
            "tokens_input": llm_metadata.get("input_tokens"),
            "tokens_output": llm_metadata.get("output_tokens"),
            "tokens_total": llm_metadata.get("total_tokens"),
            "cost_usd": llm_metadata.get("cost_usd"),
            "retry_count": llm_metadata.get("retry_count", 1),
        }

        logger.info(
            f"Synthèse générée: {len(synthese.synthese_texte)} chars, "
            f"{len(synthese.alertes)} alertes, {len(synthese.reussites)} réussites, "
            f"posture={synthese.posture_generale}, "
            f"{metadata.get('tokens_total', 0)} tokens"
        )

        return GenerationResult(synthese=synthese, metadata=metadata)

    def generate_batch(
        self,
        eleves: list[EleveExtraction],
        classe_info: str | None = None,
        max_tokens: int | None = None,
    ) -> list[SyntheseGeneree | None]:
        """Génère des synthèses pour plusieurs élèves.

        Args:
            eleves: Liste d'élèves.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens (défaut: config synthese_max_tokens).

        Returns:
            Liste de SyntheseGeneree (None si erreur).
        """
        results = self.generate_batch_with_metadata(eleves, classe_info, max_tokens)
        return [r.synthese if r is not None else None for r in results]

    def generate_batch_with_metadata(
        self,
        eleves: list[EleveExtraction],
        classe_info: str | None = None,
        max_tokens: int | None = None,
    ) -> list[GenerationResult | None]:
        """Génère des synthèses pour plusieurs élèves avec métadonnées.

        Args:
            eleves: Liste d'élèves.
            classe_info: Contexte classe optionnel.
            max_tokens: Limite de tokens (défaut: config synthese_max_tokens).

        Returns:
            Liste de GenerationResult (None si erreur).
        """
        logger.info(f"Batch génération avec métadonnées: {len(eleves)} élèves")

        results = []
        for eleve in eleves:
            try:
                result = self.generate_with_metadata(eleve, classe_info, max_tokens)
                results.append(result)
            except Exception as e:
                logger.error(f"Erreur pour {eleve.eleve_id}: {e}")
                results.append(None)

        success_count = sum(1 for r in results if r is not None)
        logger.info(f"Batch terminé: {success_count}/{len(eleves)} succès")

        return results
