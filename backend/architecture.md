# Architecture du backend

Les **règles du jeu** vivent uniquement dans `game_engine/`.  
`api/` transporte l’état via HTTP.  
`simulation/` joue des parties (autoplay) sans navigateur ni FastAPI.  
`tests/` vérifie le moteur et l’API.

```
backend/
├── game_engine/   # règles + état (source de vérité)
├── api/           # FastAPI (transport, versions, locks)
├── simulation/    # autoplay / avance de parties
└── tests/         # pytest
```

Flux typique : client React → `api/app.py` → `GameEngine` → observation JSON (`serialize`).

---

## `game_engine/` — moteur de règles

| Fichier | Rôle |
| ------- | ---- |
| `__init__.py` | Exporte `GameEngine` et `RULES_VERSION`. |
| `types.py` | Types et constantes (dés, phases, actions, plateaux, `RULES_VERSION`). |
| `rules.py` | Helpers purs : cases légales, contextes actif/passif, sommes bleu, rose, etc. Ne mute pas l’état. |
| `legal.py` | Liste les **actions légales** et la décision courante selon phase / overlays (rose, bonus, joker…). |
| `reducer.py` | Transitions d’état (`game_reducer`) : appliquer une action, lancer les dés, écrire le plateau. Cœur du moteur. |
| `bonuses.py` | Catalogue des bonus (cases, effets), déblocage, compteurs (relance / joker / +1). |
| `score.py` | Calcul du score à partir du plateau (pas un total incrémental). |
| `serialize.py` | Vue JSON camelCase pour le client React ; n’expose pas le RNG interne. |
| `engine.py` | Facade publique `GameEngine` : seed, `step`, `observe`, journal d’actions, scores. |

**Principe :** `legal` = ce qui est autorisé ; `reducer` = ce qui change l’état ; `rules` = géométrie / contraintes de cases. La politique « éviter le max » en autoplay n’est **pas** ici.

---

## `api/` — HTTP FastAPI

| Fichier | Rôle |
| ------- | ---- |
| `__init__.py` | Réexporte `app`. |
| `app.py` | Routes : créer / lire / action / reset / advance / health. Idempotence (`command_id`), versions (`expected_version`), CORS, tâches d’avance en fond. |
| `schemas.py` | Modèles Pydantic des corps de requête (pas les types internes du moteur). |
| `store.py` | Store **en mémoire** : `GameRecord` (engine, version, events, lock, état d’advance). Perdu au redémarrage. |

**Limite :** un seul worker uvicorn — le store n’est pas partagé entre processus.

---

## `simulation/` — parties sans HTTP

| Fichier | Rôle |
| ------- | ---- |
| `__init__.py` | Exporte `pick_autoplay_action`, `run_autoplay`. |
| `policy.py` | Politique d’autoplay (filtre max physique manches 1–2, choix aléatoire, boucle `run_autoplay`). |
| `run_game.py` | CLI : lance des parties seedées et affiche les scores. |

Utilisé aussi par `POST /games/{id}/advance` via `run_autoplay`.

---

## `tests/`

| Fichier | Rôle |
| ------- | ---- |
| `helpers.py` | États / dés / plateaux de test (dés imposés, sans RNG). |
| `conftest.py` | Imports partagés pytest. |
| `test_pink.py` | Règles rose / joker. |
| `test_colors_plus1.py` | Couleurs, compteurs, chaîne +1. |
| `test_bonuses_flow.py` | Chaînes de bonus, fin de partie, multi-engines. |
| `test_api.py` | Contrats FastAPI (idempotence, versions, conflits). |
| `test_simulation.py` | Autoplay complet sans HTTP. |

---

## Fichiers racine

| Fichier | Rôle |
| ------- | ---- |
| `requirements.txt` | Dépendances (FastAPI, uvicorn, pydantic, pytest…). |
| `pytest.ini` | `pythonpath = .`, chemins de tests. |
| `README.md` | Installation, lancement API / front, routes, limites. |
