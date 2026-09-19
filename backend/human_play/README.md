# `human_play` — parties humaines (hot-seat, vs IA, replay)

Orchestration au-dessus de `game_engine.GameEngine` : **aucune règle** n'est
réimplémentée ici. Le catalogue d'actions est celui de `rl_env_2` (v2, **149
ids**), partagé par l'humain et l'IA ; le format de trace est celui de
`agent/rl_env/replay.py`.

## 1. Les trois modes

| Mode | Entrée | Sortie | Adversaire |
|---|---|---|---|
| `play` | CLI `python -m human_play.cli play` / onglet **Play** | partie hot-seat + trace JSON | humain (même écran) |
| `vs-ai` | CLI `python -m human_play.cli vs-ai` / onglet **Play against AI** | partie + trace JSON | meilleur `MaskablePPO` v2 |
| `replay` | CLI `python -m human_play.cli replay --run ...` / onglet **Replay** | navigation de frames | — (trace existante) |

## 2. API `HumanGameSession` (`human_play/session.py`)

```python
session = HumanGameSession(
    agent_player=1,          # siège humain (1|2)
    opponent_kind="human",   # "human" (hot-seat) | "ai"
    checkpoint=None,         # chemin .zip ; défaut = meilleur v2 sous agent/{,runs/}
    seed=None,               # graine du moteur
)
```

| Méthode | Rôle |
|---|---|
| `reset(agent_player, opponent_kind, checkpoint=None, seed=None)` | réinitialise et renvoie `state_json()` |
| `legal_actions() -> list[dict]` | `{id, label, detail, category, factorised_step1}` |
| `step(action_id) -> dict` | applique la décision humaine (et l'IA en cascade), renvoie l'état |
| `state_json() -> dict` | état sérialisable (compatible composants React) |
| `is_over() -> bool` / `final_scores() -> dict` | fin de partie / scores |
| `human_decisions` | nombre de décisions humaines (pour `agent_decisions`) |

`state_json()` = `engine.observe()` (`state`, `legalActions`, `scores`,
`decision`, `stuck`, `whiteAvailability`, `passiveFlags`, `actingColors`) +
`session_id, seed, human_player, opponent, checkpoint, is_over, human_turn,
acting_player, awaiting_value, human_decisions, last_ai_actions, legal_actions,
final_scores`.

## 3. Adversaire IA (`human_play/opponent.py`)

- **v2 (défaut)** : `AIPolicy` charge un `best_model.zip` v2, reconstruit
  l'observation via `rl_env_2.observations.encode_observation_2`, applique la
  mise à l'échelle du training, masque/décode via `rl_env_2.actions`, et gère le
  `Pending` des décisions factorisées (bonus bleu/turquoise).
- **v1 (repli)** : détecté par `n_actions == 316` → catalogue `rl_env`.
- `find_default_checkpoint()` = dernier `best_model.zip` sous
  `agent/{solo_*,shaped_*}` **ou** `agent/runs/{solo_*,shaped_*}` (les runs
  peuvent vivre directement sous `agent/` ou sous `agent/runs/`).

## 4. Routes REST (`backend/api/human_play_routes.py`, montées sur l'app)

| Route | Méthode | Corps / Réponse |
|---|---|---|
| `/human_play/models` | GET | `{models: [{path, relpath, run, subdir, file, mtime, catalogue, is_default}]}` |
| `/human_play/sessions` | POST | `{agent_player, opponent, checkpoint?, seed?}` → `{session_id, state}` |
| `/human_play/sessions/{id}` | GET | `state_json()` |
| `/human_play/sessions/{id}/legal_actions` | GET | `{actions: [...]}` |
| `/human_play/sessions/{id}/step` | POST | `{action_id}` **ou** `{cancel: true}` → état + `events` |
| `/human_play/sessions/{id}/save` | POST | `{path?}` → `{replay_id, file}` |
| `/human_play/sessions/{id}` | DELETE | `{deleted}` |
| `/replays`, `/replays/{id}` | GET | inchangés |

`state_json()` expose en plus des champs optionnels `opponent_name`
(`run / sous-dossier (fichier)`) et `opponent_relpath` (chemin relatif à
`agent/runs`). `{cancel: true}` annule la sélection en cours (décision
factorisée ou sélection moteur via `cancel_selection`) sans consommer de
décision humaine.

Une session est un objet en mémoire (`{session_id: HumanGameSession}`), sans
persistance. L'IA joue **dans `step`** : le frontend ne voit que les décisions
humaines.

## 5. Exemple complet (création → step → save → reload)

```python
from human_play import HumanGameSession, save_trace

s = HumanGameSession(agent_player=1, opponent_kind="human", seed=42)
while not s.is_over():
    s.step(s.legal_actions()[0]["id"])
print(s.final_scores())
info = save_trace(s)          # agent/runs/human_play/replays/<id>.json + index.json
print(info["replay_id"])
```

En HTTP (équivalent) :

```bash
SID=$(curl -s localhost:8000/human_play/sessions -H 'content-type: application/json' \
  -d '{"agent_player":1,"opponent":"human","seed":42}' | python -c 'import sys,json;print(json.load(sys.stdin)["session_id"])')
curl -s localhost:8000/human_play/sessions/$SID/legal_actions
curl -s localhost:8000/human_play/sessions/$SID/step -H 'content-type: application/json' -d '{"action_id":0}'
curl -s localhost:8000/human_play/sessions/$SID/save -H 'content-type: application/json' -d '{}'
curl -s localhost:8000/replays
```

La trace sauvegardée est servie par `GET /replays/{replay_id}` et s'affiche dans
l'onglet **Replay** (mêmes clés racine que `rl_env/replay.py`).

## 6. Changer de checkpoint

- **Lister** les modèles : `GET /human_play/models` (ou `list_checkpoints()`).
  Critère de « meilleur » : `best_model.zip` **le plus récent** sous
  `agent/runs/{solo_*,shaped_*}` (les modèles v2 ; `essai_01` est v1 et reste
  listé avec `catalogue: "v1"`).
- CLI : `python -m human_play.cli vs-ai --checkpoint agent/runs/<...>/best_model.zip`
- API : `POST /human_play/sessions` avec `{"opponent":"ai","checkpoint":"agent/runs/<...>/best_model.zip"}`
- Sans `checkpoint`, `find_default_checkpoint()` prend le plus récent modèle v2.

Exemple (création avec choix de modèle + affichage du nom) :

```python
from human_play import HumanGameSession
from human_play.opponent import list_checkpoints

best = next((m for m in list_checkpoints() if m["is_default"]), None)
s = HumanGameSession(agent_player=1, opponent_kind="ai", checkpoint=best["path"], seed=7)
state = s.state_json()
print(state["opponent_name"])   # "shaped_<ts> / run_min_zone (best_model.zip)"
```

## 7. Limites connues

- **Pas de persistance serveur** : les sessions vivent en mémoire ; un
  redémarrage de l'API les perd (les replays sauvegardés, eux, restent sur disque).
- **Pas de multi-session concurrente côté frontend** : un seul onglet Play / IA
  à la fois ; l'API, elle, accepte plusieurs `session_id`.
- **Adversaire = politique déterministe** (`deterministic=True`), sans
  entraînement ni gradient (API read-only côté modèle).
- Le catalogue est **v2** ; un checkpoint v1 est accepté en repli mais les ids
  exposés (`legal_actions`) restent alors dans le vocabulaire du checkpoint.
- Tests : `backend/tests/test_human_play*.py`.
