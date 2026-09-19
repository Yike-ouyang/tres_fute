# Backend Très Futé (moteur Python + FastAPI)

Les règles (REGLES_DU_JEU.md v1.2) vivent uniquement dans `game_engine/`.
FastAPI transporte l’état ; `simulation/` joue des parties sans HTTP.

## Limites (à lire avant de lancer)

- **Un seul worker uvicorn.** Le store est un dictionnaire en mémoire : plusieurs workers = plusieurs mondes.
- **Perte au redémarrage.** Aucune persistance disque.
- **Pas d’authentification.** Les deux plateaux d’une partie sont publics ; le navigateur envoie le `game_id`.
- Le RNG des dés est une `random.Random` **par partie**. La politique autoplay a un RNG **séparé**. L’observation n’expose pas l’état interne du générateur.

## Installation

Venv **partagé à la racine du dépôt** (utilisé par `backend/` et `agent/`) :

```bash
cd <racine du dépôt>          # dossier qui contient backend/ et agent/
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r backend/requirements.txt
```

## Lancer l’API

```bash
cd backend
source ../.venv/bin/activate
uvicorn api.app:app --reload --host 127.0.0.1 --port 8000
```

Santé : `GET http://127.0.0.1:8000/health`

CORS : tout `http://localhost:<port>` et `http://127.0.0.1:<port>` (Vite 5173 par défaut).

## Lancer l’interface React

Dans un second terminal, avec l’API déjà démarrée :

```bash
cd frontend
npm install
npm run dev
```

Vite proxifie `/api` vers `http://127.0.0.1:8000`. Pour pointer ailleurs :

```bash
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

(`VITE_API_URL` par défaut : `/api`.)

## Tests

```bash
cd backend
source ../.venv/bin/activate
pytest
```

Le front conserve des tests Vitest du moteur TypeScript historique (`npm test` dans `frontend/`) ; le runtime React n’importe plus `reducer.ts`, `rules.ts`, `autoplay.ts` ni `score.ts`.

## Simulation sans navigateur ni FastAPI

```bash
cd backend
source ../.venv/bin/activate
python simulation/run_game.py --seeds 1,2,3 --turns 6
```

L’avance rapide utilise `HeuristicPolicy` (`simulation/policy.py`) : elle applique les préférences hiérarchisées (manche 1 ≤ 3 dés retirés, manche 2 conserve un dé puis un rose/blanc/jaune, marron évite les positions 4/5/6, bleu privilégie la branche droite, tirage marron/bleu à 75 %, bonus rose, turquoise par valeur commune) puis départage au hasard. Elle peut aussi servir d’adversaire fixe pour un joueur.

- RNG **dédié** (graine via `HeuristicPolicy(seed=…)`), indépendant du RNG des dés : une même graine rejoue la même partie.
- Les règles sont des **préférences** filtrant les coups légaux du moteur ; elles ne bloquent jamais le jeu (repli si une préférence est impossible).
- **Ressources facultatives** (relance, joker, +1) : probabilités configurables (`relance_probability`, `joker_probability`, `plus1_probability`), **0 par défaut** — jamais consommées automatiquement. Mode debug : `HeuristicPolicy(seed=…, debug=True)` puis `drain_log()`.
- L’ancien filtre « éviter le max physique » est conservé comme helper de compatibilité (`restrict_active_die_select`) mais n’est plus utilisé par l’avance rapide.

## Routes

| Méthode | Chemin | Rôle |
| ------- | ------ | ---- |
| `POST` | `/games` | Créer (`seed` optionnel) |
| `GET` | `/games/{id}` | État visible, `legalActions`, scores, `decision`, `events`, `advance` |
| `POST` | `/games/{id}/actions` | `{command_id, expected_version, action}` |
| `POST` | `/games/{id}/reset` | Nouvelle partie, même contrat |
| `POST` | `/games/{id}/advance` | `{n, command_id, expected_version}` — autoplay en tâche de fond |
| `GET` | `/replays` | Parties rejouables (traces JSON pré-générées) |
| `GET` | `/replays/{id}` | Trace complète d’une partie rejouée |
| `GET` | `/health` | OK |

Une commande répétée (`command_id`) renvoie le résultat déjà produit. Une `expected_version` dépassée répond `409` avec l’état courant. Pendant une avance, les actions manuelles répondent `409`.

## Replay d’un modèle entraîné

Un checkpoint ne contient pas la partie, mais l’environnement est déterministe :
on la régénère à l’identique depuis la graine d’évaluation.

```bash
# depuis la racine du dépôt, venv partagé activé
python agent/rl_env/replay.py --run agent/runs/essai_01 --checkpoint best_model.zip --seed 1000000 --agent-player 1
```

La trace (états sérialisés, actions atomiques, résumé d’observation) est servie
par `GET /replays` et visualisée dans l’onglet **Replay** du front (flèches
avant/arrière). Détails : `agent/rl_env/README.md` §16.

Pour un modèle `rl_env_2` (adversaire checkpoint, observation/action 2.0), la
même trace minimale est produite par `watch_best_model.py` et écrite dans
`agent/runs/<run>/replays/` (découvert par `GET /replays`) :

```bash
# depuis la racine du dépôt, venv partagé activé
python agent/rl_env_2/watch_best_model.py --model agent/runs/solo_<ts>/score_delta_solo/best_model.zip --seed 2000000
```

## Environnement RL (Gymnasium)

`agent/rl_env/` expose la partie complète à deux joueurs comme environnement Gymnasium (agent appris contre adversaire fixe, sans HTTP). Voir `agent/rl_env/README.md`. Démonstration :

```bash
# depuis la racine du dépôt, venv partagé activé
python agent/rl_env/run_episode.py --episodes 3 --agent-player random --opponent heuristic
```

`gymnasium` et `numpy` sont dans `requirements.txt` ; `sb3-contrib` (MaskablePPO) est optionnel.
