Ajoute un dossier **`backend/rl_env/`** contenant un environnement Gymnasium pour le **jeu complet à deux joueurs**, ainsi qu’un README expliquant son fonctionnement et son interaction avec un agent RL.

Implémente le code et les tests. Ne te limite pas à une proposition d’architecture. Ne lance pas encore d’entraînement long et ne développe pas d’algorithme RL.

**1. Architecture existante à respecter**

Le backend est organisé ainsi :

* `game_engine/` : état, règles, actions légales, transitions, bonus, scores et façade `GameEngine`.
* `api/` : FastAPI, transport HTTP et gestion des parties web.
* `simulation/` : politique automatique et parties sans HTTP.
* `tests/` : tests du moteur, de l’API et des simulations.

Dans le moteur :

* `types.py` définit les types et constantes.
* `rules.py` contient les contraintes et helpers purs.
* `legal.py` fournit les actions légales et les décisions courantes.
* `reducer.py` applique les transitions.
* `bonuses.py` gère les récompenses.
* `score.py` calcule les scores.
* `serialize.py` produit la vue JSON pour React.
* `engine.py` expose `GameEngine`, son état observable, les actions et les scores.

Le nouvel environnement doit appeler **directement le moteur Python**, sans HTTP, navigateur ou store FastAPI.

Les règles restent exclusivement dans `game_engine/`. Le dossier `rl_env/` adapte ces règles aux observations, actions et récompenses attendues par Gymnasium.

**2. Examiner le moteur avant de définir les espaces**

Lire le code réel et `REGLES_DU_JEU.md` s’il existe.

Inventorier :

* Toutes les phases et décisions.
* Tous les types d’actions et leurs paramètres.
* Les overlays : rose, joker, blanc, bonus immédiats et autres choix intermédiaires.
* Les décisions du joueur passif pendant la séquence de l’autre joueur.
* Les conditions de fin de partie.
* Les données nécessaires pour reprendre une chaîne de bonus.
* Les commandes uniquement destinées à l’interface.

Ne pas supposer que les méthodes ou structures proposées ci-dessous existent déjà : adapter leur intégration au code réel.

Si une information nécessaire manque dans la façade publique, ajouter un accès minimal et documenté au moteur. Éviter de dépendre de ses attributs privés.

Signaler toute incohérence bloquante sans modifier silencieusement les règles.

**3. Organisation proposée**

Créer une structure équivalente à :

* `rl_env/__init__.py` : exports publics.
* `rl_env/env.py` : environnement `DiceGameEnv`.
* `rl_env/observations.py` : encodage des observations et définition des espaces.
* `rl_env/actions.py` : catalogue stable, encodage, décodage et masquage.
* `rl_env/opponents.py` : adaptateurs des politiques adverses.
* `rl_env/rewards.py` : calcul des récompenses.
* `rl_env/run_episode.py` : exemple exécutable sans entraînement.
* `rl_env/README.md` : documentation complète.
* Tests dédiés dans `tests/`, selon les conventions du projet.

Adapter les noms si nécessaire, en conservant cette séparation des responsabilités.

**4. Périmètre : un agent appris contre un adversaire fixe**

Créer une sous-classe de `gymnasium.Env`.

Une instance représente :

* Une partie complète à deux joueurs.
* Un joueur contrôlé par l’agent externe.
* Un adversaire contrôlé par une politique Python fixe.

Le joueur contrôlé par l’agent doit être configurable : joueur 1, joueur 2 ou place tirée au début de chaque épisode.

L’agent contrôle toutes les décisions de son joueur : actions actives, passives, bonus et +1.

L’environnement pilote automatiquement l’adversaire jusqu’à la prochaine décision de l’agent.

Réutiliser la politique réellement disponible dans `simulation/`. Ne pas prétendre qu’une heuristique plus récente est implémentée si le code ne contient que l’ancien filtre « éviter le maximum ».

Prévoir aussi un adversaire aléatoire légal simple, utile pour les tests. Documenter le mode d’échantillonnage utilisé.

**5. Définir une observation numérique structurée**

Utiliser un **`gymnasium.spaces.Dict` plat**, dont les valeurs sont des tableaux numériques de dimensions fixes. Éviter les dictionnaires imbriqués, chaînes de caractères et listes de longueur variable dans les observations.

Le point de vue doit rester constant :

* Index 0 : joueur contrôlé par l’agent.
* Index 1 : adversaire.

Ce repérage ne change pas lorsque les rôles actif et passif s’inversent.

Inclure au minimum :

| Champ conceptuel       | Informations                                                                                   |
| ---------------------- | ---------------------------------------------------------------------------------------------- |
| Jaune                  | Cases cochées des deux joueurs                                                                 |
| Turquoise              | Cases cochées des deux joueurs                                                                 |
| Bleu                   | Valeurs inscrites et cases vides                                                               |
| Marron                 | Cases cochées et informations nécessaires pour déduire les destinations restantes              |
| Rose                   | Valeurs inscrites                                                                              |
| Dés                    | Identité fixe par couleur, valeur physique, emplacement et position de sélection si nécessaire |
| Ressources             | État individuel des emplacements de relance, joker et +1                                       |
| Récompenses            | Renards, sources déjà déclenchées et choix non déductibles des valeurs inscrites               |
| Contexte               | Tour, manche, phase, rôle actif/passif et décision attendue                                    |
| Action en cours        | Dé, couleur, valeur effective, sélection provisoire si elle appartient à l’état décisionnel    |
| Résolutions en attente | Bonus, bénéficiaires, ordre et informations nécessaires à la reprise de la phase               |

Respecter les dimensions du plateau complet : jaune 3 × 6, turquoise 5 × 6, bleu 13 cases avec centre fixe, marron 12 et rose 12.

Il est possible d’omettre le centre bleu constant de l’encodage, à condition de documenter la correspondance des indices.

**Contraintes d’encodage :**

* Utiliser `MultiBinary`, `MultiDiscrete` ou `Box` selon la nature des données.
* Choisir des bornes exactes et des `dtype` cohérents.
* Encoder explicitement les catégories, sans leur attribuer accidentellement une signification numérique ordonnée.
* Distinguer une case vide d’une valeur valide.
* Conserver l’identité des dés indépendamment de leur valeur : ne pas les trier.
* Ne pas inclure l’état interne des générateurs aléatoires ni les futurs lancers.
* Ne pas utiliser la sérialisation JSON destinée au front comme format d’apprentissage.

Si une file de bonus doit être encodée, déterminer une borne justifiée par le moteur et utiliser un remplissage avec indicateur de présence. Ne jamais tronquer silencieusement une file.

Une représentation compacte équivalente est acceptable si elle conserve toute l’information pertinente.

Les scores et caractéristiques dérivées peuvent être ajoutés, mais ne remplacent pas les données nécessaires aux transitions.

Définir une constante `OBSERVATION_VERSION`.

**6. Définir un catalogue d’actions fixe**

Utiliser :

`action_space = gymnasium.spaces.Discrete(N_ACTIONS)`

Construire `N_ACTIONS` à partir d’un catalogue complet et déterministe des décisions du jeu.

Chaque identifiant doit avoir une signification stable entre les états, épisodes et instances. Ne pas utiliser « l’indice dans la liste des actions légales actuelles ».

Couvrir tous les choix nécessaires, notamment :

* Choix d’un des six dés physiques.
* Choix de couleur pour le blanc ou un bonus noir.
* Choix de destination.
* Choix de valeur.
* Option rose points ou bonus.
* Sélection des cases turquoise.
* Utilisation d’une relance, d’un joker ou d’un +1.
* Fin d’une fenêtre facultative.
* Passage autorisé.
* Complément des emplacements actifs sans effet.

Adapter cette décomposition aux actions réelles du moteur. Des décisions successives sont acceptables lorsqu’elles correspondent à de vrais choix.

Pour le turquoise, envisager une action par sous-ensemble non vide des cinq lignes lorsque la colonne est déjà déterminée : au maximum 31 sous-ensembles. Vérifier que cette représentation préserve tous les choix autorisés. Sinon, documenter l’encodage retenu.

Ne pas exposer comme décisions RL les opérations purement visuelles : ouverture de fenêtre, survol ou confirmation redondante d’un choix déjà complet.

Si le moteur exige plusieurs commandes pour appliquer une décision complète, l’adaptateur peut les orchestrer avec validation préalable, sans reproduire les règles.

Éviter les actions d’annulation purement liées à l’interface, qui pourraient créer des boucles sans effet.

Définir :

* Un encodeur action moteur → identifiant RL, lorsque pertinent.
* Un décodeur identifiant RL → décision moteur.
* Des libellés lisibles pour le débogage.
* Une constante `ACTION_VERSION`.

Documenter les plages d’identifiants et la valeur finale de `N_ACTIONS`.

**7. Masquage des actions**

Implémenter :

`action_masks() -> numpy.ndarray`

Le résultat doit être un tableau booléen de taille `N_ACTIONS` :

* `True` : action légale dans la décision courante.
* `False` : action interdite.

Le masque doit provenir des actions et contraintes exposées par le moteur.

Ne pas intégrer la stratégie de l’adversaire au masque. Un coup peu conseillé reste légal pour l’agent.

Lorsque l’environnement retourne un état non terminal où l’agent doit agir, au moins une action doit être autorisée.

Les masques peuvent être fournis dans `info` pour inspection, mais la méthode `action_masks()` doit être disponible pour une intégration ultérieure avec MaskablePPO.

Une action masquée ou un identifiant invalide doit produire une erreur claire en mode normal de développement, sans mutation du moteur ni consommation d’aléatoire. Ne pas remplacer silencieusement le choix par une action aléatoire.

**8. Définir précisément `reset()`**

Respecter :

`reset(*, seed=None, options=None) -> (observation, info)`

La méthode doit :

1. Appeler l’initialisation Gymnasium appropriée.
2. Créer une nouvelle partie complète.
3. Choisir la place de l’agent selon la configuration.
4. Initialiser les générateurs de manière reproductible.
5. Accorder et résoudre les événements automatiques de démarrage.
6. Faire agir l’adversaire si nécessaire.
7. S’arrêter à la première décision de l’agent.
8. Retourner son observation et les informations de diagnostic.

Utiliser des flux aléatoires distincts pour les dés, la politique adverse et le choix éventuel de place.

Deux instances réinitialisées avec la même configuration et la même graine, puis recevant les mêmes actions, doivent produire les mêmes trajectoires.

Ne pas réinitialiser systématiquement les graines à une constante entre les épisodes.

**9. Définir précisément `step()`**

Respecter :

`step(action_id) -> (observation, reward, terminated, truncated, info)`

Une étape correspond à une décision de l’agent, suivie des conséquences nécessaires jusqu’à sa prochaine décision.

Déroulement :

1. Vérifier l’action et son masque.
2. Appliquer la décision de l’agent.
3. Résoudre les conséquences automatiques.
4. Faire jouer l’adversaire lorsqu’il doit décider.
5. Résoudre les événements et bonus déclenchés.
6. S’arrêter dès que l’agent doit à nouveau choisir, ou que la partie se termine.
7. Calculer la récompense sur l’ensemble de cette transition.
8. Retourner l’observation et les indicateurs.

Ne pas exécuter aveuglément tout le tour de l’adversaire : une décision passive ou un bonus de l’agent peut interrompre la progression.

Un bonus exigeant un choix du joueur contrôlé doit rendre la main à l’agent.

Les confirmations purement techniques peuvent être automatiques. Pour cette première version, il n’est pas nécessaire de supprimer toutes les décisions à choix unique : privilégier un comportement cohérent et documenté.

**Fin et erreurs :**

* `terminated=True` uniquement après la fin réelle de la partie, toutes les résolutions obligatoires comprises.
* `truncated=True` uniquement pour une limite externe explicitement configurée.
* Une boucle interne anormale ou une incohérence du moteur doit produire une erreur diagnostiquable, pas une fausse fin de partie.
* Refuser un appel à `step()` après la fin tant que `reset()` n’a pas été appelé.

**10. Récompense configurable**

La récompense appartient à `rl_env/`, pas au moteur.

Prévoir deux modes :

* `score_delta`, mode par défaut :
  `reward = (score_agent_apres - score_agent_avant) / reward_scale`
* `terminal_score` :
  zéro avant la fin, puis `score_final_agent / reward_scale`

`reward_scale` est une constante positive configurable, valant 1 par défaut.

Utiliser le score complet, renards inclus. Le calcul doit couvrir les conséquences automatiques et actions adverses exécutées à l’intérieur du `step()`.

Ne pas ajouter de prime artificielle pour les bonus, les coups légaux ou la vitesse de jeu.

Ne pas verser une seconde récompense terminale en mode `score_delta`.

Documenter que, avec `gamma=1`, la somme des différences de score vaut le score final moins le score au premier état retourné par `reset()`. Signaler toute progression automatique antérieure à cet état.

Expliquer que l’actualisation avec `gamma<1` dépend de la décomposition en décisions.

Une interruption externe ne doit pas être traitée comme une victoire ou une partie naturellement terminée.

**11. Informations, performances et indépendance**

Dans `info`, fournir au minimum :

* Place de l’agent.
* Tour, manche et phase.
* Scores des deux joueurs.
* Nombre d’actions moteur et adverses exécutées depuis le dernier retour.
* Versions des règles, observations et actions.
* À la fin : scores finaux et résultat.

Rendre les traces détaillées optionnelles. Éviter de recopier un historique croissant dans chaque `info`.

Les instances doivent être indépendantes et pouvoir être créées en parallèle sans store HTTP partagé.

Limiter ou désactiver le journal détaillé du moteur pendant l’entraînement si celui-ci accumule toutes les actions. Conserver un mode de débogage explicite.

Prévoir `close()` et, si utile, un rendu textuel léger. Ne pas ajouter de dépendance au navigateur.

**12. Script de démonstration**

Créer une commande documentée permettant de jouer plusieurs épisodes complets :

* Agent de démonstration choisissant aléatoirement parmi les actions non masquées.
* Adversaire configurable.
* Graine et place de l’agent configurables.
* Affichage des scores finaux, du nombre d’étapes et du temps d’exécution.
* Option pour afficher les décisions.

Le script doit fonctionner sans FastAPI et sans agent entraîné.

Préciser que le tirage uniforme sur les identifiants légaux n’est pas nécessairement uniforme sur les stratégies ou les coups complets.

**13. Tests et validation**

Ajouter des tests pour :

* Conformité des observations à `observation_space`.
* Dimensions, types et bornes stables.
* Encodage et décodage des actions.
* Cohérence entre masque et légalité moteur.
* Prise en charge de toutes les phases du jeu complet.
* Arrêt à la bonne décision du joueur contrôlé.
* Parties jouées depuis les deux places.
* Bonus en chaîne et décisions passives.
* Valeur physique et valeur effective avec joker.
* Reproductibilité et indépendance entre instances.
* Absence de mutation sur action invalide.
* Récompenses et identité télescopique de `score_delta`.
* Terminaison de plusieurs parties complètes.
* Limite externe et distinction entre terminaison et troncature.

Exécuter les tests existants pour détecter les régressions pertinentes.

Vérifier la conformité avec les outils Gymnasium dans la mesure où ils respectent le contrat des actions masquées. Certains vérificateurs échantillonnent des actions sans tenir compte du masque : identifier explicitement cette limite, sans rendre les actions illégales acceptables pour contourner le problème.

Si Stable-Baselines3 / SB3-Contrib est disponible, ajouter un court test d’intégration avec `MaskablePPO` et `MultiInputPolicy`. Sinon, le proposer comme dépendance optionnelle et documenter son lancement. Ne pas lancer un entraînement prolongé.

**14. README détaillé**

Écrire `backend/rl_env/README.md`, compréhensible sans lire tout le code.

Inclure :

1. Le rôle de l’environnement et ses relations avec le moteur, l’agent et l’adversaire.
2. L’installation et les commandes exactes.
3. Un exemple minimal `reset()` → masque → choix → `step()`.
4. Le tableau complet des observations : nom, forme, type, bornes, signification et indices.
5. Le catalogue d’actions et son versionnement.
6. Le fonctionnement du masque et son utilisation avec MaskablePPO.
7. Un exemple de séquence avec blanc, choix rose et bonus immédiat.
8. Le déroulement des actions adverses entre deux étapes.
9. Les récompenses et leurs implications.
10. La gestion des graines et la reproductibilité.
11. Les indicateurs `terminated` et `truncated`.
12. Le contenu de `info`.
13. Les tests, la mesure du débit de simulation et le débogage.
14. Les limites actuelles et les décisions d’encodage.
15. Les précautions de compatibilité lors d’un changement de règles ou de catalogue d’actions.

Expliquer explicitement :

* L’agent reçoit une observation numérique et un masque.
* Il choisit un identifiant d’action.
* L’environnement traduit cette décision et appelle le moteur.
* Le moteur applique les règles.
* L’environnement retourne la prochaine observation et la récompense.
* L’algorithme d’apprentissage, extérieur à l’environnement, utilise cette transition pour mettre à jour son réseau.
* Gymnasium ne sauvegarde pas automatiquement les modèles ; cela relève du futur script d’entraînement.

**15. Livraison**

Livrer le code, les tests et le README, puis résumer :

* Les fichiers créés ou modifiés.
* Les dimensions effectives des observations.
* Le nombre exact d’actions.
* La politique adverse disponible.
* Les vérifications exécutées et leurs résultats.
* Les éventuels points bloquants.
* La commande permettant de lancer immédiatement un épisode de démonstration.

Le résultat doit permettre de jouer et d’évaluer des épisodes complets via Gymnasium, avec toutes les couleurs, les bonus, les renards et les deux joueurs, sans interface web.
