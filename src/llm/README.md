# Module LLM - Multi-Provider avec Rate Limiting

Module centralisé pour les appels LLM avec support multi-provider, rate limiting robuste, retry automatique et métriques.

---

## Architecture

```
src/llm/
├── manager.py              # LLMManager - Orchestration centrale
├── config.py               # Configuration (API keys, modèles, limites)
├── rate_limiter.py         # SimpleRateLimiter (fenêtre glissante RPM)
├── clients/
│   ├── openai.py          # Client OpenAI
│   ├── anthropic.py       # Client Anthropic
│   └── mistral.py         # Client Mistral
└── metrics.py             # Collection métriques
```

**Flux d'appel** :
```
User → LLMManager.call() → Rate Limiter → Client → API Provider → Response
```

---

## Providers Supportés

| Provider | Modèles | Tier 1 Limits | Usage |
|----------|---------|---------------|-------|
| **OpenAI** | gpt-5-mini, gpt-5-nano | 500 RPM | Génération synthèses |
| **Anthropic** | claude-sonnet-4-5, claude-haiku-4-5 | 50 RPM | Génération synthèses |
| **Mistral** | mistral-large-latest | 100 RPM | Génération synthèses |

---

## Rate Limiting

### Stratégie : SimpleRateLimiter (RPM uniquement)

**Principe** : Fenêtre glissante de 60 secondes par provider avec `time.monotonic()` (immunisé contre changements d'horloge système).

```python
class SimpleRateLimiter:
    """Rate limiter basé sur RPM avec fenêtre glissante."""

    def __init__(self, rpm: int, verbose: bool = True):
        """
        Args:
            rpm: Requêtes par minute max
            verbose: Afficher les messages rate limiting (True par défaut)
        """
        ...

    async def acquire(self, timeout: float | None = None) -> None:
        """Attend jusqu'à pouvoir faire une requête sans dépasser RPM.

        Args:
            timeout: Temps max d'attente en secondes (None = illimité)
        """
        ...
```

**Fonctionnalités** :
- Fenêtre glissante précise (pas de "burst" en début de minute)
- Timeout optionnel pour éviter blocages infinis
- Messages contrôlables via `verbose` (pratique notebooks vs production)
- Gestion propre de la cancellation asyncio
- Utilise `time.monotonic()` (immunisé NTP, changements d'heure)

**Pourquoi RPM uniquement (pas TPM)** :
- Simplifié : Pas besoin de compter tokens avant l'appel
- Suffisant : Pour 2000 PDFs (~400 arbitrages Sonnet)
- Robuste : Retry + backoff gère les dépassements TPM occasionnels

**Limites configurées** :
```python
self.rate_limiters = {
    "openai": SimpleRateLimiter(rpm=500),
    "anthropic": SimpleRateLimiter(rpm=50),
    "mistral": SimpleRateLimiter(rpm=100),
}
```

---

## Usage

### Appel Simple

```python
from src.llm.manager import LLMManager

manager = LLMManager()

# Appel synchrone (notebooks)
response = manager.call_sync(
    provider="anthropic",
    messages=[{"role": "user", "content": "Extrait les informations..."}],
    model="claude-sonnet-4-5"
)

print(response["content"])
print(f"Tokens: {response['total_tokens']}")
```

### Appel Asynchrone

```python
import asyncio

async def extract_info():
    manager = LLMManager()
    response = await manager.call(
        provider="openai",
        messages=[{"role": "user", "content": "..."}],
        model="gpt-5-mini"
    )
    return response

result = asyncio.run(extract_info())
```

## Configuration

### Variables d'Environnement (.env)

```bash
# API Keys (obligatoires selon le provider choisi)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...

# Provider par défaut
DEFAULT_PROVIDER=anthropic
```

---

## Métriques

Les métriques (tokens, coûts, latence) sont collectées automatiquement par `LLMClient.call()` et stockées avec chaque synthèse dans `chiron.duckdb`.

---

## Troubleshooting

### Rate Limit Exceeded (429)

**Symptôme** : Erreur 429 ou messages `⏳ Rate limit atteint`

**Solution** : Le rate limiter attend automatiquement. Options :
```python
# Option 1 : Réduire max_concurrent
results = await manager.batch_call(requests, max_concurrent=20)

# Option 2 : Désactiver messages verbose (production)
manager.rate_limiters["anthropic"] = SimpleRateLimiter(rpm=50, verbose=False)

# Option 3 : Ajouter timeout pour éviter attentes infinies
limiter = SimpleRateLimiter(rpm=50)
await limiter.acquire(timeout=120.0)  # Max 2 minutes d'attente
```

### Provider Inconnu

**Symptôme** : `ValueError: Provider xxx non implémenté`

**Solution** : Utiliser `"openai"`, `"anthropic"` ou `"mistral"` (lowercase)

### Tokens Dépassent Limites

**Symptôme** : Document trop long (>200K tokens)

**Solution** : Découper le document ou filtrer le contenu avant extraction

---
