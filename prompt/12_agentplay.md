
## Contexte

Le projet est un jeu de dés *Très Futé* avec :
- `backend/game_engine/` : moteur de règles (source de vérité, ne pas modifier),
- `backend/rl_env/` : environnement Gymnasium original (obs 1.0, 316 actions),
- `backend/rl_env_2/` : environnement simplifié (obs 2.0, actions réduites),
- `backend/runs/` : checkpoints d'entraînement (dont `essai_01/best_model.zip` et les runs `solo_*` / `shaped_*`),
- `backend/rl_env/replay.py` : générateur de replays JSON,
- `backend/api/` : API FastAPI read-only,
- `frontend/` : UI React avec un onglet **Replay**.

L'objectif est d'ajouter au backend **trois modes de jeu** accessibles depuis l'interface existante.

## Objectif

Créer dans `backend/` un module `human_play/` qui expose trois modes :

1. **`replay`** — visualiser une partie déjà enregistrée (déjà partiellement existant).
2. **`play`** — jouer une partie **humain contre humain** (hot-seat sur le même écran).
3. **`play against AI`** — jouer une partie **humain contre le meilleur modèle disponible**.

Le mode `replay` existe déjà via `rl_env/replay.py` et le frontend ; l'objectif est de **l'unifier** avec les deux autres modes sous une même interface, sans le casser.

## Contraintes générales

- Ne modifie **aucun** fichier de `game_engine/`, `rl_env/`, `rl_env_2/`. Tout le nouveau code vit dans `backend/human_play/` et, si nécessaire, dans `backend/api/`.
- Le moteur de règles reste `game_engine/`. `human_play/` ne fait qu'orchestrer.
- Réutilise au maximum l'existant : `game_engine.GameEngine`, `rl_env_2.DiceGameEnv2`, `rl_env_2.opponents.DEFAULT_CHECKPOINT`, `rl_env/actions.py`, `rl_env/observations.py`.
- Avant d'écrire du code, lis `backend/rl_env/README.md`, `backend/rl_env_2/README.md`, `backend/api/app.py` et `backend/rl_env/replay.py` en entier. Résume en 10 lignes ce que tu as compris avant de coder.
- À chaque étape, exécute les commandes que tu proposes et montre la sortie réelle. N'invente pas de résultats.
- Si une contrainte est irréalisable ou ambiguë, arrête-toi et pose la question au lieu de deviner.

## Décisions à clarifier avant de coder

Pose-moi ces questions (ou tranche et documente ton choix dans le README) :

1. **Interface cible** : CLI seule, API REST + frontend React, ou les deux ?
   - Recommandation : API REST + frontend, en réutilisant l'onglet existant.
2. **Choix de l'adversaire IA** : quel checkpoint utiliser par défaut ?
   - Recommandation : le `best_model.zip` le plus récent sous `runs/solo_*/` ou `runs/shaped_*/`, avec `--checkpoint` pour override.
3. **Siège du joueur humain** : toujours joueur 1, toujours joueur 2, ou choix au démarrage ?
   - Recommandation : choix au démarrage.
4. **Rendu** : texte CLI, JSON pour le frontend, ou les deux ?
   - Recommandation : JSON côté API, affichage React côté frontend.
5. **Reprise de partie** : peut-on sauver/recharger une partie humaine en cours ?
   - Recommandation : oui, même format que les replays (`initial_state` + frames atomiques).

## Étape 1 — Module `human_play/`

Crée `backend/human_play/` avec :

- `session.py` : une classe `HumanGameSession` qui encapsule un `GameEngine` et expose :
  - `reset(agent_player, opponent_kind, checkpoint=None, seed=None)`,
  - `legal_actions() -> list[dict]` (labels + ids, lisibles par un humain),
  - `step(action_id) -> dict` (nouvel état, événements, scores, phase, décision),
  - `state_json() -> dict` (état sérialisable pour le frontend),
  - `is_over() -> bool`, `final_scores() -> dict`.
- `opponent.py` : un adaptateur qui charge un checkpoint `MaskablePPO` (via `rl_env_2.opponents`) et joue automatiquement quand c'est à l'IA. Doit gérer la conversion obs 2.0 ↔ obs du checkpoint si nécessaire (cf. `rl_env_2/opponents/`).
- `replay_bridge.py` : pont vers `rl_env/replay.py` pour que le mode `replay` et le mode `play against AI` partagent le même format de trace JSON.
- `README.md` : documente l'API de `HumanGameSession`, les trois modes, et les décisions prises ci-dessus.

**Test obligatoire** : `tests/test_human_play.py` qui vérifie :
- une partie humain vs humain complète se termine sans erreur,
- une partie humain vs IA complète se termine sans erreur,
- toutes les actions proposées par `legal_actions()` sont acceptées par `step()`,
- `state_json()` est stable et contient les champs attendus,
- le format de trace est identique à celui de `rl_env/replay.py` (mêmes clés racine).

## Étape 2 — Modes `play` et `play against AI` (CLI)

Crée `backend/human_play/cli.py` avec :

```
python -m human_play.cli play          # humain vs humain, hot-seat
python -m human_play.cli vs-ai         # humain vs meilleur modèle
python -m human_play.cli replay --run runs/essai_01 --seed 1000000
```

Comportement :

- **`play`** : affiche le plateau, la phase, la décision attendue, puis propose les actions légales numérotées. L'utilisateur saisit un numéro, la partie avance, on passe au joueur suivant. À la fin, affiche les scores et propose d'enregistrer la trace.
- **`vs-ai`** : l'humain choisit son siège au démarrage. Quand c'est à l'IA, l'environnement joue automatiquement et affiche le coup joué (action + label) avant de rendre la main. Même rendu que `play`.
- **`replay`** : affiche les frames d'une trace existante, avec ◀/▶ pour naviguer (en CLI : `n`/`p` puis Entrée). Réutilise la logique de `rl_env/replay.py`.

Options communes : `--checkpoint`, `--agent-player {1,2}`, `--seed`, `--save <path>`, `--render {text,json}`.

**Test obligatoire** : script `tests/test_human_play_cli.py` qui simule une entrée utilisateur (via `unittest.mock.patch("builtins.input", ...)`) et vérifie qu'une partie complète se déroule sans erreur pour les trois modes.

## Étape 3 — API REST

Ajoute dans `backend/api/app.py` (ou un nouveau `backend/api/human_play_routes.py` monté sur l'app existante) :

| Route | Méthode | Rôle |
|---|---|---|
| `POST /human_play/sessions` | POST | crée une session (`{agent_player, opponent, checkpoint, seed}`) → `{session_id, state}` |
| `GET /human_play/sessions/{id}` | GET | renvoie `state_json()` |
| `GET /human_play/sessions/{id}/legal_actions` | GET | renvoie les actions légales (id + label + catégorie) |
| `POST /human_play/sessions/{id}/step` | POST | joue une action (`{action_id}`) → nouvel état + événements |
| `DELETE /human_play/sessions/{id}` | DELETE | ferme la session |
| `POST /human_play/sessions/{id}/save` | POST | écrit la trace au format replay (`{path}`) → `{replay_id}` |
| `GET /replays` / `GET /replays/{id}` | GET | existants, ne pas casser |

Points d'attention :
- Une session = un `HumanGameSession` en mémoire, protégé par un dict `{session_id: session}`. Pas de persistance obligatoire.
- Les actions de l'IA sont appliquées automatiquement dans `step()` : le frontend ne voit que les décisions humaines.
- Le format de `legal_actions` doit rester compatible avec le frontend existant (mêmes clés que `rl_env/actions.py::label`).
- L'API doit rester **read-only côté modèle** : aucun entraînement, aucun gradient.

**Test obligatoire** : `tests/test_human_play_api.py` qui démarre un `TestClient`, crée une session, joue une partie complète via l'API, la sauve, et vérifie que le replay généré se recharge via `GET /replays/{id}`.

## Étape 4 — Frontend

Modifie `frontend/` pour ajouter un **sélecteur de mode** en haut de page :

```
[ Replay ]  [ Play ]  [ Play against AI ]
```

Comportement :

- **Replay** : comportement actuel inchangé.
- **Play** : affiche le plateau des deux joueurs, les dés, les actions légales sous forme de boutons. L'humain clique, la partie avance. Hot-seat : un bandeau indique « Tour du joueur 1 / 2 ».
- **Play against AI** : identique à `Play`, mais quand c'est à l'IA, un spinner s'affiche, puis le coup de l'IA est affiché (action + label + scores). Le joueur choisit son siège au démarrage.
- Bouton **Sauvegarder** à tout moment → POST `/human_play/sessions/{id}/save`, puis bascule sur l'onglet Replay.
- Bouton **Nouvelle partie** → DELETE + POST session.

Contraintes frontend :
- Réutilise les composants existants de l'onglet Replay (plateau, dés, panneau d'actions).
- Ne casse pas l'onglet Replay actuel : il doit continuer à fonctionner à l'identique.
- Pas de nouvelle dépendance npm sans justification.

**Test obligatoire** : `npm run lint` et `npm run build` passent. Si tu ajoutes des tests frontend, `npm test` passe.

## Étape 5 — Documentation

Crée `backend/human_play/README.md` avec :

- un tableau des trois modes (nom, entrée, sortie, adversaire),
- l'API de `HumanGameSession`,
- les routes REST ajoutées,
- un exemple de session complète (création → step → save → reload),
- la procédure pour changer de checkpoint (`--checkpoint`, body de `POST /human_play/sessions`),
- les limites connues (pas de multi-session concurrente côté frontend, pas de persistance serveur, etc.).

## Étape 6 — Vérification finale

1. `pytest backend/tests/test_human_play*.py` passe.
2. Une partie complète humain vs humain via CLI se termine.
3. Une partie complète humain vs IA via CLI se termine, l'IA joue des coups légaux.
4. Une partie complète via l'API (TestClient) se termine, la trace est sauvegardée et rechargeable via `GET /replays/{id}`.
5. L'onglet Replay existant fonctionne toujours.
6. Les trois onglets du frontend (Replay, Play, Play against AI) sont fonctionnels.

## Livrables attendus

- `backend/human_play/` complet (session, opponent, replay_bridge, cli, README).
- Routes REST ajoutées dans `backend/api/`.
- Frontend avec sélecteur de mode et les trois onglets.
- `backend/tests/test_human_play*.py` qui passe.
- `backend/human_play/README.md`.

## Ordre d'exécution imposé

1. Lis `rl_env/README.md`, `rl_env_2/README.md`, `api/app.py`, `rl_env/replay.py`. Résume en 10 lignes.
2. Réponds aux 5 questions de la section « Décisions à clarifier ». Si tu ne peux pas, pose-les-moi et arrête-toi.
3. Implémente Étape 1 + tests. Montre `pytest` qui passe.
4. Implémente Étape 2 + tests. Montre une partie complète en CLI.
5. Implémente Étape 3 + tests. Montre les routes dans `/docs`.
6. Implémente Étape 4. Montre `npm run build` qui passe.
7. Implémente Étape 5.
8. Fais la vérification finale (Étape 6) et montre chaque point.

À chaque étape, si quelque chose ne marche pas comme prévu, arrête-toi et explique le problème avant de continuer. Ne passe pas à l'étape suivante sur une base cassée.

