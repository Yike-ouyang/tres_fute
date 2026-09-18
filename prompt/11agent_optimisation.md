

## Contexte

Le projet est un environnement Gymnasium pour le jeu de dés *Très Futé*, situé dans `backend/rl_env/`. Le moteur de règles est dans `backend/game_engine/`. Les runs d'entraînement existants sont dans `backend/runs/`, dont `backend/runs/essai_01/best_model.zip` (checkpoint MaskablePPO) avec ses métadonnées (versions d'observation, d'action, `n_actions`).

Objectif : créer un nouveau package `backend/rl_env_2/` qui améliore l'apprentissage par rapport à `rl_env/`, puis entraîner séquentiellement plusieurs variantes de reward et reporter les résultats.

## Contraintes générales

- Ne modifie **aucun** fichier de `game_engine/`, `rl_env/`, `api/`, `frontend/`. Tout le nouveau code vit dans `backend/rl_env_2/`.
- Toutes les règles restent dans `game_engine/`. `rl_env_2/` ne fait qu'adapter.
- Avant d'écrire du code, lis `backend/rl_env/` en entier (README + tous les modules) et `backend/game_engine/` pour comprendre `legal_actions()`, `game_reducer()`, `compute_score()`, `PHASE_KINDS`, `DECISION_KINDS`.
- À chaque étape, exécute les commandes que tu proposes et montre la sortie réelle. N'invente pas de résultats.
- Si une contrainte est irréalisable ou ambiguë, arrête-toi et pose la question au lieu de deviner.

## Étape 1 — `rl_env_2/` : observations simplifiées

Crée un `DiceGameEnv2` qui hérite ou enveloppe `DiceGameEnv` et produit une observation **plate** (`gymnasium.spaces.Dict` aplati ou `Box` 1-D) selon les règles suivantes :

**Retirer entièrement** (axe 1 = adversaire) :
- `yellow_checks`, `turquoise_checks`, `blue_values`, `brown_checks`, `brown_last_checked`, `brown_disabled`, `pink_values`, `slots_unlocked`.

**Remplacer par un résumé adverse compact** (5 valeurs) :
- `opp_score_total` (int),
- `opp_fox_count` (int),
- `opp_min_zone` (score de la zone la plus faible de l'adversaire, calculé depuis ses checks/values),
- `opp_max_zone` (score de sa zone la plus forte),
- `opp_zones_completed` (nombre de zones complétées sur 5).

**Retirer car redondant ou déductible** :
- `selection_legal` (redondant avec `action_masks()`),
- `selection_picked` (déductible de l'état du plateau),
- `chosen_colors`, `chosen_values`, `slot_colors`, `slot_values` (déductibles de `dice_*` + `slots_unlocked`),
- `pending_bonus_colors`, `pending_bonus_owner_is_agent` (garder uniquement `pending_bonus_count`).

**Conserver tel quel** : tout ce qui concerne le plateau de l'agent, les dés, la sélection en cours, la phase, la décision, `actor_is_agent`, `active_is_agent`, `score_total` (agent), `fox_count` (agent), `turn`, `round`, plus les overlays pink/bonus/joker.

**Ajouter** deux features utiles calculées :
- `agent_min_zone` et `agent_max_zone` (idem adversaire, pour l'agent),
- `agent_zones_completed`.

Documente le nouveau schéma dans `rl_env_2/README.md` avec un tableau clé → shape → dtype → signification, et définis `OBSERVATION_VERSION_2 = "2.0"`.

**Test obligatoire** : écris `tests/test_rl_env_2_obs.py` qui vérifie :
- conformité au `observation_space`,
- stabilité des shapes sur 100 `step()` aléatoires masqués,
- absence des clés retirées,
- présence et valeurs correctes des 7 nouvelles features (compare avec un calcul manuel depuis `rl_env` original sur la même trajectoire seedée).

## Étape 2 — `rl_env_2/` : actions simplifiées

Reprends le catalogue d'actions de `rl_env/` (316 ids) et applique ces réductions :

**Factorisation du bonus bleu foncé** : remplace `BLUE_BONUS_PLACE` (156 ids = cellule × valeur) par **deux décisions séquentielles** :
1. `BLUE_BONUS_CELL` : 13 ids (cellule 1..13),
2. `BLUE_BONUS_VALUE` : 12 ids (valeur 1..12).

L'environnement enchaîne automatiquement les deux et n'appelle `place_bonus_blue` qu'à la fin. Le masque de la 2ᵉ décision ne contient que les valeurs légales pour la cellule choisie.

**Factorisation du bonus turquoise immédiat** : remplace `TURQUOISE_BONUS` (30 ids = 1 cellule) par **deux décisions séquentielles** :
1. `TURQUOISE_BONUS_ROW` : 5 ids (ligne 1..5),
2. `TURQUOISE_BONUS_COL` : 6 ids (colonne 1..6).

Idem : enchaînement automatique, masque restreint.

**Suppression des ids jamais légaux dans une même décision** : après analyse des `legal_actions()` sur 1000 parties aléatoires, identifie les ids qui ne sont jamais le seul choix possible et ne sont jamais proposés simultanément avec un autre id de la même section. Liste-les dans le README et retire-les du catalogue. Si tu n'en trouves aucun, dis-le explicitement au lieu d'inventer.

**Renumérote** les ids restants en gardant l'ordre sémantique du README original, et expose `N_ACTIONS_2` et `ACTION_VERSION_2 = "2.0"`.

**Test obligatoire** : `tests/test_rl_env_2_actions.py` qui vérifie :
- `encode(decode(id)) == id` pour tout id légal sur 100 parties,
- le masque est cohérent avec `legal_actions()` du moteur (replay),
- `N_ACTIONS_2 < 316`,
- les deux factorisations produisent bien les mêmes coups moteur que `rl_env/` sur les mêmes seeds (test de non-régression moteur).

## Étape 3 — `rl_env_2/` : gamma et hyperparamètres

- `gamma = 0.999` par défaut (au lieu de 0.99).
- Expose `gamma` en paramètre de `DiceGameEnv2` pour pouvoir le varier, mais ne le passe **pas** à l'environnement Gymnasium (Gymnasium n'utilise pas `gamma`). Il doit être lu par le script d'entraînement pour configurer `MaskablePPO`.
- Documente dans le README : avec un horizon de ~50–70 décisions agent, `gamma = 0.999` donne une demi-vie d'environ 690 pas, ce qui couvre largement une partie. `gamma = 0.99` donne une demi-vie de 69 pas, insuffisant pour créditer un renard débloqué au tour 1 et compté au tour 6.

## Étape 4 — Adversaire = checkpoint `essai_01`

Crée `rl_env_2/opponents/checkpoint_policy.py` qui :

1. Charge `backend/runs/essai_01/best_model.zip` via `MaskablePPO.load(..., device="cpu")`.
2. Vérifie les métadonnées du checkpoint (`action_version`, `observation_version`, `n_actions`) et **lève une erreur explicite** si elles ne correspondent pas à celles de l'environnement courant. Précise dans le message quelle version est attendue et quelle version est chargée.
3. Implémente `CheckpointPolicy(opponent)` avec la même interface que `simulation.policy.HeuristicPolicy` : une méthode `choose(state, legal_actions) -> action`.
4. **Point critique** : le checkpoint a été entraîné sur `rl_env/` (316 actions, observation 1.0), pas sur `rl_env_2/`. Tu as deux options :
   - **Option A (recommandée)** : entraîne l'adversaire dans un `rl_env/` *original* encapsulé, en lui passant l'observation 1.0 reconstruite depuis l'état moteur. C'est plus sûr mais nécessite un adaptateur observation 2.0 → 1.0.
   - **Option B** : reconstruis l'observation 1.0 complète depuis l'état du moteur directement (sans passer par `rl_env_2`), appelle le modèle, décode l'action 1.0 vers une action moteur, applique.

Choisis A ou B, justifie ton choix en commentaire, et teste que l'adversaire joue des coups **légaux** sur 100 parties.

Si le checkpoint ne peut pas être chargé (fichier manquant, version incompatible), **arrête-toi** et demande-moi quoi faire. Ne substitue pas `HeuristicPolicy` silencieusement.

## Étape 5 — Script d'entraînement séquentiel

Crée `backend/rl_env_2/train_sequence.py` avec les caractéristiques suivantes :

**Quatre runs consécutifs**, chacun 1 000 000 de timesteps (paramétrable via `--timesteps`), avec des rewards cumulatifs :

1. **Run 1 — `score_delta_normalized`** :
   `r = (score_after - score_before) / 100`

2. **Run 2 — `+ fox`** (reprend le meilleur modèle du run 1) :
   `r = Δ(score)/100 + 0.5 · Δ(fox_count) · min_zone_after`

3. **Run 3 — `+ zone complete`** (reprend le meilleur modèle du run 2) :
   `r = Δ(score)/100 + 0.5 · Δ(fox_count) · min_zone_after + 0.2 · Δ(zones_completed)`

4. **Run 4 — `+ terminal`** (reprend le meilleur modèle du run 3) :
   `r = Δ(score)/100 + 0.5 · Δ(fox_count) · min_zone_after + 0.2 · Δ(zones_completed) + [1.0 si victoire, 0.0 si nul, -1.0 si défaite] à la fin`

Pour chaque run :
- Utilise `MaskablePPO` de `sb3_contrib` avec `ActionMasker`.
- `gamma = 0.999`, `n_steps = 2048`, `batch_size = 128`, `learning_rate = 3e-4`, `ent_coef = 0.01`, `net_arch = [256, 256]`.
- 4 environnements parallèles (`SubprocVecEnv` ou `DummyVecEnv` selon le système).
- Évaluation tous les 50 000 pas sur **200 parties seedées** contre le checkpoint adversaire, en mode greedy (`deterministic=True`).
- Sauvegarde le meilleur modèle (`best_model.zip`) selon le win rate d'évaluation, pas selon le reward. Sauvegarde aussi `last_model.zip` et `checkpoint_<step>.zip` tous les 200 000 pas.
- Écrit un `metadata.json` par run : versions, hyperparamètres, seed, `N_ACTIONS_2`, formule de reward.
- Les seeds d'entraînement et d'évaluation sont fixés et disjoints. Documente-les.

**Logging TensorBoard** :
- `log_dir = backend/runs/sequence_<timestamp>/`
- Un sous-dossier par run : `run1_score_delta/`, `run2_fox/`, `run3_zone/`, `run4_terminal/`.
- Logge au minimum : `train/reward_mean`, `train/ep_len_mean`, `train/entropy_loss`, `train/value_loss`, `train/policy_loss`, `eval/win_rate`, `eval/draw_rate`, `eval/loss_rate`, `eval/mean_score_agent`, `eval/mean_score_opponent`, `eval/mean_fox_agent`, `eval/mean_min_zone_agent`, `time/fps`.
- Lance `tensorboard --logdir backend/runs/sequence_<timestamp>` à la fin et affiche l'URL.

**Reprise entre runs** : le run N+1 charge `best_model.zip` du run N avec `MaskablePPO.load(..., env=env_N+1)` et `reset_num_timesteps=False` pour que les courbes TensorBoard soient continues sur le même axe step.

**Robustesse** : si un run plante, les runs précédents ne sont pas écrasés. Le script reprend au run suivant si `--resume` est passé et qu'un `best_model.zip` existe déjà pour ce run.

## Étape 6 — Rapport final

À la fin des quatre runs, génère `backend/runs/sequence_<timestamp>/REPORT.md` contenant :

1. **Tableau comparatif** : une ligne par run, colonnes = win rate, draw rate, loss rate, score moyen agent, score moyen adversaire, fox moyen agent, min_zone moyen agent, nombre de pas d'entraînement, temps d'entraînement.

2. **Courbes** : capture d'écran ou export PNG des courbes TensorBoard clés (`eval/win_rate`, `eval/mean_score_agent`, `eval/mean_fox_agent`) superposées pour les 4 runs sur le même axe step. Utilise `tensorboard.backend.event_processing` ou `tbparse` pour extraire les séries et `matplotlib` pour les tracer.

3. **Analyse** : pour chaque ajout de reward (renard, zone, terminal), dire s'il a amélioré, stagné ou dégradé le win rate par rapport au run précédent, avec le delta chiffré. Si un ajout dégrade, propose une hypothèse (poids trop fort, reward mal aligné, etc.) et une expérience de suivi.

4. **Comparaison baseline** : rejoue le checkpoint `essai_01/best_model.zip` sur les mêmes 200 seeds d'évaluation et donne son win rate. C'est la référence à battre.

5. **Recommandation** : quel run garder comme meilleur modèle, et quelle prochaine expérience lancer (par exemple : varier le poids du reward renard, ajouter un reward `Δ(min_zone)` pour l'équilibre, tester `gamma = 0.9995`).

Le rapport doit être lisible sans accès au code : un lecteur qui ouvre `REPORT.md` doit comprendre ce qui a été fait, ce qui a marché, et ce qui n'a pas marché.

## Livrables attendus

- `backend/rl_env_2/` complet et testé (`pytest backend/tests/test_rl_env_2*.py` passe).
- `backend/rl_env_2/README.md` documentant observations, actions, versions, et différences avec `rl_env/`.
- `backend/rl_env_2/train_sequence.py` fonctionnel.
- `backend/runs/sequence_<timestamp>/` avec les 4 runs, leurs `metadata.json`, leurs `best_model.zip`, et les logs TensorBoard.
- `backend/runs/sequence_<timestamp>/REPORT.md`.

## Ordre d'exécution imposé

1. Lis `rl_env/` et `game_engine/`, résume ce que tu as compris en 10 lignes.
2. Implémente Étape 1 (observations) + tests. Montre `pytest` qui passe.
3. Implémente Étape 2 (actions) + tests. Montre `pytest` qui passe.
4. Implémente Étape 3 (gamma).
5. Implémente Étape 4 (adversaire checkpoint) + test de légalité. Montre le test.
6. Implémente Étape 5 (script d'entraînement). Lance **un run court** (10 000 pas) pour valider que tout tourne, montrant les logs TensorBoard.
7. Lance les 4 runs complets.
8. Génère `REPORT.md`.

À chaque étape, si quelque chose ne marche pas comme prévu, arrête-toi et explique le problème avant de continuer. Ne passe pas à l'étape suivante sur une base cassée.

