# Prompt amélioré

## Contexte

Le projet est un jeu de dés *Très Futé* avec :

- `backend/game_engine/` : moteur de règles (source de vérité, ne pas modifier),
- `backend/rl_env/` : environnement Gymnasium original,
- `backend/rl_env_2/` : environnement simplifié (obs 2.0, actions réduites),
- `backend/runs/` : checkpoints d'entraînement (dont `essai_01/best_model.zip`, les runs `solo_*` et `shaped_*`),
- `backend/human_play/` : module de jeu humain (session, opponent, replay_bridge, cli),
- `backend/api/` : API FastAPI,
- `frontend/` : UI React avec les onglets **Replay**, **Play**, **Play against AI**.

L'objectif est d'**améliorer l'expérience de jeu** dans les trois onglets, sans toucher au moteur ni aux environnements RL.

## Contraintes générales

- Ne modifie **aucun** fichier de `game_engine/`, `rl_env/`, `rl_env_2/`. Toute la logique UX vit dans `frontend/` et, si nécessaire, dans `human_play/` et `api/`.
- Ne casse **aucun** onglet existant : Replay, Play, Play against AI doivent continuer à fonctionner à l'identique (à l'amélioration près).
- Ne change **pas** le format des replays JSON ni les routes REST existantes. Si tu ajoutes des champs, ils doivent être optionnels et rétrocompatibles.
- Avant de coder, lis `frontend/` en entier (surtout les composants de plateau, de dés et de panneau d'actions), `backend/human_play/README.md` et `backend/api/app.py`. Résume en 10 lignes ce que tu as compris.
- À chaque étape, exécute les commandes que tu proposes et montre la sortie réelle. N'invente pas de résultats.
- Si une contrainte est irréalisable ou ambiguë, arrête-toi et pose la question au lieu de deviner.

## Amélioration 1 — Supprimer l'étape de validation

**Problème actuel** : l'utilisateur sélectionne un dé, puis doit confirmer son choix avant que le coup ne soit joué.

**Comportement cible** :

- **Un dé n'a qu'un seul coup possible** (par exemple un dé rose, un dé brun avec une seule case libre, ou un dé dont la couleur impose une unique destination) → **cliquer sur le dé joue immédiatement le coup**. Aucun clic supplémentaire.
- **Un dé a plusieurs coups possibles** → **premier clic sur le dé** = sélection (le dé est mis en surbrillance), **deuxième clic sur la case destination** = joue le coup. Pas de bouton « Confirmer ».
- **Dé blanc** → clic sur le dé, puis clic sur la couleur d'action (les 5 couleurs restent affichées comme cibles cliquables), puis clic sur la case. Pas de confirmation.
- **Bonus bleu** (cellule + valeur) → clic sur le bonus, clic sur la cellule, clic sur la valeur. Pas de confirmation.
- **Bonus turquoise immédiat** → clic sur la ligne, puis clic sur la colonne. Pas de confirmation.
- **Joker chiffre** → clic sur le joker, clic sur la valeur 1–6. Pas de confirmation.
- **Choix rose** (points / bonus) → clic sur l'option. Pas de confirmation.

**Règle générale** : le dernier clic de chaque interaction joue le coup. Il ne doit rester **aucun** bouton « Confirmer », « Valider » ou équivalent dans l'interface.

**Cas d'annulation** : si l'utilisateur s'est trompé en cours de sélection (par exemple il a cliqué sur un dé puis veut changer), un clic ailleurs (sur un autre dé, sur une zone neutre, ou sur Échap) **annule la sélection en cours**. Aucun coup n'est joué tant que le dernier clic n'a pas eu lieu.

**Test obligatoire** : ajoute ou adapte des tests frontend (`npm test`) qui simulent :
- un clic sur un dé à choix unique → le coup est joué, l'état avance ;
- un clic sur un dé à choix multiple → le dé est sélectionné, l'état n'avance pas ;
- un clic sur la case destination → le coup est joué, l'état avance ;
- Échap ou clic neutre → la sélection est annulée.

## Amélioration 2 — Compteurs de bonus en haut

**Problème actuel** : les compteurs de bonus (relances, jokers, +1) sont dispersés ou peu visibles.

**Comportement cible** :

- Déplace **tous les compteurs de bonus** dans la **même zone que le compteur de tour**, en haut de l'écran. Zone compacte, toujours visible, pas de scroll.
- Pour chaque bonus, affiche **deux nombres** : **disponible** et **utilisé**.
  - Format : `Relances 2/3` (2 disponibles sur 3 au total), ou `Relances : 2 dispo, 1 utilisé`.
  - Choisis un format lisible et cohérent pour tous les bonus ; documente-le dans le README frontend.
- Priorité d'affichage (du plus important au moins important) :
  1. **Relances** (relance_unl / relance_used),
  2. **Jokers chiffre** (joker_unl / joker_used),
  3. **+1** (plus1_unl / plus1_used),
  4. Les autres bonus (renard, etc.) si présents.
- Les valeurs proviennent de l'observation : `bonuses[player] = [relance_unl, relance_used, joker_unl, joker_used, plus1_unl, plus1_used]`. Utilise ces indices directement, sans recalcul.
- Quand un bonus est **utilisé**, il doit devenir visuellement inactif (grisé) mais rester affiché avec son compteur mis à jour.
- Quand un bonus est **disponible**, il doit être cliquable si la phase le permet.

**Test obligatoire** : capture d'écran ou test visuel documenté dans le README, montrant le compteur de tour et les compteurs de bonus alignés en haut, avec les deux nombres visibles.

## Amélioration 3 — Visibilité des cases turquoise cochées

**Problème actuel** : les cases turquoise cochées sont peu distinctes des cases vides.

**Comportement cible** :

- Augmente le **contraste** entre case cochée et case vide :
  - case cochée : fond coloré saturé + coche ou point central bien visible,
  - case vide : fond neutre clair, contour discret.
- La couleur reste le turquoise de la charte, mais la saturation ou la luminosité doit être ajustée pour que la différence soit **évidente au premier coup d'œil**, y compris pour un daltonien (teste avec un simulateur deuteranopie/protanopie si tu peux).
- Ajoute un **indicateur textuel ou une coche** (✓) dans les cases cochées, pas seulement une couleur de fond.
- Vérifie que la lisibilité reste bonne en mode clair et en mode sombre (si le frontend supporte les deux).

**Test obligatoire** : capture d'écran avant/après dans le README, ou test de contraste automatisé (ratio WCAG ≥ 3:1 pour le texte, ≥ 1.5:1 pour la distinction de fond entre cochée et vide).

## Amélioration 4 — Expérience contre l'IA

**Problème actuel** : l'utilisateur ne sait pas quel modèle joue contre lui, et la conversion en observation pour l'IA n'est pas transparente.

**Comportement cible** :

- **Affiche clairement quel modèle joue** : dans l'onglet Play against AI, un bandeau en haut indique par exemple :
  ```
  Adversaire : shaped_20260917_203604 / run_min_zone (best_model.zip)
  ```
  Le nom du run, le sous-dossier et le fichier utilisé doivent être visibles. Récupère ces informations via une nouvelle route API `GET /human_play/models` qui liste les checkpoints disponibles, avec leur run d'origine et leur date de modification.
- **Sélection du modèle** : avant de commencer une partie, l'utilisateur peut choisir parmi les checkpoints disponibles. Par défaut, le meilleur modèle le plus récent est présélectionné. Documente le critère de « meilleur » (par exemple : `best_model.zip` le plus récent sous `runs/`).
- **Clic sur les dés** : le joueur humain clique sur les dés **exactement comme dans le mode Play**, sans savoir qu'il joue contre une IA. Aucun clic supplémentaire, aucune validation.
- **Conversion transparente** : c'est le **backend** qui fait la conversion de l'état moteur vers l'observation attendue par le checkpoint (obs 1.0 ou 2.0 selon le modèle), applique le masque, appelle le modèle, décode l'action, et applique le coup au moteur. Le frontend ne fait **aucune** conversion, ne voit **aucune** observation, et n'a **aucune** connaissance du format du modèle.
- **Feedback du coup IA** : quand c'est à l'IA de jouer, affiche brièvement (1–2 secondes ou jusqu'à la prochaine action humaine) :
  - l'action jouée (label lisible, ex. « sélectionne le dé jaune 4 »),
  - la case ciblée si applicable,
  - les scores mis à jour.
- **Pas d'attente perçue** : si le modèle met moins de 100 ms à répondre (cas typique CPU), ne montre pas de spinner. Si plus long, montre un indicateur discret.
- **Pas de fuite d'observation** : le frontend ne doit jamais recevoir l'observation numérique du modèle. Il reçoit uniquement l'état de jeu sérialisé (`state_json`) et les événements d'action.

**Test obligatoire** :
- `pytest backend/tests/test_human_play_api.py` : une partie complète via l'API avec un modèle réel, en vérifiant que les coups de l'IA sont légaux et que le frontend reçoit bien `state_json` (pas d'observation).
- Test frontend : le bandeau « Adversaire : ... » affiche bien le nom du run et du fichier.
- Test de non-régression : le mode Play (humain vs humain) n'est pas affecté.

## Étape 5 — Documentation

Mets à jour :

- `frontend/README.md` : nouvelles interactions (clic sans validation, compteurs en haut, sélection du modèle IA), avec captures d'écran avant/après.
- `backend/human_play/README.md` : nouvelle route `GET /human_play/models`, critère de sélection du meilleur modèle, exemple de session avec choix de modèle.
- Un court `CHANGELOG.md` dans `frontend/` si le projet en a déjà un.

## Étape 6 — Vérification finale

1. `npm run lint` et `npm run build` passent.
2. `npm test` passe, y compris les nouveaux tests d'interaction (clic dé → coup joué, clic dé → sélection → clic case → coup joué, Échap → annulation).
3. `pytest backend/tests/test_human_play*.py` passe.
4. Une partie complète humain vs humain en CLI se termine sans confirmation.
5. Une partie complète humain vs IA via l'API se termine, le modèle utilisé est affiché, les coups IA sont légaux.
6. L'onglet Replay existant fonctionne toujours à l'identique.
7. Les trois onglets sont fonctionnels et cohérents visuellement.

## Livrables attendus

- Frontend modifié : plus aucune étape de confirmation, compteurs de bonus en haut, cases turquoise plus visibles, sélecteur de modèle IA.
- `backend/human_play/` : route `GET /human_play/models`, gestion du choix de modèle par session.
- `backend/api/` : route ajoutée, documentation OpenAPI à jour.
- Tests frontend et backend qui passent.
- Captures d'écran avant/après dans le README.

## Ordre d'exécution imposé

1. Lis `frontend/` (composants plateau, dés, panneau d'actions), `human_play/README.md`, `api/app.py`. Résume en 10 lignes.
2. Implémente Amélioration 1 (suppression des confirmations) + tests. Montre `npm test` qui passe.
3. Implémente Amélioration 2 (compteurs de bonus en haut) + capture.
4. Implémente Amélioration 3 (cases turquoise) + capture avant/après.
5. Implémente Amélioration 4 (sélection du modèle IA + conversion transparente). Montre une partie complète via l'API.
6. Mets à jour la documentation.
7. Fais la vérification finale et montre chaque point.

À chaque étape, si quelque chose ne marche pas comme prévu, arrête-toi et explique le problème avant de continuer. Ne passe pas à l'étape suivante sur une base cassée.

