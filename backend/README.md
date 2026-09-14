# Backend Très Futé (moteur Python + FastAPI)

Les règles (REGLES_DU_JEU.md v1.1) vivent uniquement dans `game_engine/`.
FastAPI transporte l’état ; `simulation/` joue des parties sans HTTP.

## Limites (à lire avant de lancer)

- **Un seul worker uvicorn.** Le store est un dictionnaire en mémoire : plusieurs workers = plusieurs mondes.
- **Perte au redémarrage.** Aucune persistance disque.
- **Pas d’authentification.** Les deux plateaux d’une partie sont publics ; le navigateur envoie le `game_id`.
- Le RNG des dés est une `random.Random` **par partie**. La politique autoplay a un RNG **séparé**. L’observation n’expose pas l’état interne du générateur.

## Installation

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancer l’API

```bash
cd backend
source .venv/bin/activate
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
source .venv/bin/activate
pytest
```

Le front conserve des tests Vitest du moteur TypeScript historique (`npm test` dans `frontend/`) ; le runtime React n’importe plus `reducer.ts`, `rules.ts`, `autoplay.ts` ni `score.ts`.

## Simulation sans navigateur ni FastAPI

```bash
cd backend
source .venv/bin/activate
python simulation/run_game.py --seeds 1,2,3 --turns 6
```

La politique « éviter le max physique » sur les manches actives 1–2 est dans `simulation/policy.py`, pas dans `legal_actions()` du moteur.

## Routes

| Méthode | Chemin | Rôle |
| ------- | ------ | ---- |
| `POST` | `/games` | Créer (`seed` optionnel) |
| `GET` | `/games/{id}` | État visible, `legalActions`, scores, `decision`, `events`, `advance` |
| `POST` | `/games/{id}/actions` | `{command_id, expected_version, action}` |
| `POST` | `/games/{id}/reset` | Nouvelle partie, même contrat |
| `POST` | `/games/{id}/advance` | `{n, command_id, expected_version}` — autoplay en tâche de fond |
| `GET` | `/health` | OK |

Une commande répétée (`command_id`) renvoie le résultat déjà produit. Une `expected_version` dépassée répond `409` avec l’état courant. Pendant une avance, les actions manuelles répondent `409`.
