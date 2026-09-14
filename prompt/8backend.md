Prépare la migration du jeu React + TypeScript existant vers un futur moteur Python indépendant du front et de FastAPI.

Cette tâche comporte deux livrables, dans cet ordre :

1. Corriger la première case rose dans le code actuel.
2. Créer un fichier **`REGLES_DU_JEU.md`** décrivant précisément les règles de notre variante et leur fonctionnement, pour servir de référence à l’implémentation du moteur Python.

**Ne commence pas encore la migration ni l’implémentation du moteur Python.**

**1. Correction préalable : première case rose**

La première case rose doit obligatoirement recevoir :

`Math.ceil(valeurEffective / 2)`

Elle ne propose aucun choix de multiplicateur et n’accorde aucun bonus.

Exemples : 1 → 1, 2 → 1, 3 → 2, 4 → 2, 5 → 3, 6 → 3.

Cette règle remplace toutes les instructions précédentes indiquant d’y inscrire directement la valeur du dé.

Appliquer la correction à tous les chemins permettant de jouer en rose :

* Dé rose.
* Dé blanc utilisé en rose.
* Action active ou passive.
* Utilisation d’un +1.
* Utilisation avec un joker chiffre.
* Bonus immédiat rose ou noir utilisé en rose.
* Avance automatique.

Utiliser la valeur effective après application éventuelle d’un joker, ou la valeur choisie pour un bonus virtuel.

Conserver la confirmation habituelle du coup en mode manuel et sa validation automatique pendant l’avance rapide. Seul le choix « points ou bonus » est absent sur cette première case.

Vérifier que le score rose additionne la valeur déjà inscrite sans la diviser une seconde fois. Ajouter une vérification ciblée et mettre à jour toute indication visuelle devenue incorrecte.

**2. Méthode de synthèse des règles**

Avant de rédiger, examiner :

* Les instructions et corrections disponibles dans cette conversation.
* Le code actuel : état du jeu, transitions, coups légaux, bonus, scores et automatisation.
* Les tests et documents déjà présents dans le projet.

Appliquer l’ordre de priorité suivant :

1. La correction de la première case rose donnée dans ce prompt.
2. Les dernières instructions explicites de l’utilisateur.
3. Les instructions antérieures qui n’ont pas été remplacées.
4. Le comportement du code, comme preuve de l’implémentation actuelle, sans le considérer automatiquement comme la règle souhaitée.

Les reformulations précédentes peuvent contenir des hypothèses : ne pas les présenter comme des décisions explicites de l’utilisateur si elles n’ont pas été confirmées.

Documenter **notre variante**, sans la remplacer par les règles officielles du jeu commercial.

En cas de divergence entre le code et une règle explicite, documenter la règle attendue et signaler l’écart. En dehors du correctif rose demandé, ne pas modifier silencieusement les autres mécanismes.

Si une règle reste indéterminée, inscrire **« À confirmer »**, expliquer précisément les interprétations possibles et les conséquences. Ne pas inventer une règle pour rendre le document artificiellement complet.

**3. Objectif et qualité du document**

Le fichier doit permettre à une personne de construire le moteur Python **sans lire les composants React ni reconstituer l’historique de la conversation**.

Rédiger en français, avec :

* Un vocabulaire uniforme.
* Des règles normatives et vérifiables.
* Des tableaux exhaustifs pour les cases, bonus et barèmes.
* Des exemples pour les interactions complexes.
* Une séparation nette entre règles du jeu, décisions d’interface et stratégie automatique.

Éviter les formulations telles que « comme précédemment », « selon la règle habituelle » ou « utiliser la logique existante ». Décrire intégralement ce qu’elles signifient.

Attribuer des identifiants stables aux règles importantes, par exemple `ROSE-001`, `TOUR-003` ou `BONUS-012`, pour pouvoir les référencer dans les futurs tests.

**4. Structure attendue de `REGLES_DU_JEU.md`**

**A. Périmètre et statut**

Préciser :

* Le jeu à deux joueurs et sa variante.
* L’objectif du document.
* La date de rédaction et la version des règles.
* Les sources effectivement consultées.
* Les éventuelles limites de vérification.

**B. Glossaire**

Définir sans ambiguïté :

* Tour global.
* Manche active.
* Séquence active.
* Joueur actif.
* Joueur passif.
* Joueur qui doit prendre la décision courante.
* Dé disponible, choisi et écarté.
* Dé ajouté sans effet pour compléter les emplacements actifs.
* Valeur physique et valeur effective.
* Bonus stockable, bonus immédiat et renard.
* Sélection provisoire et action validée.

Distinguer les positions des cases de leurs valeurs imprimées ou inscrites.

**C. Matériel et structure des plateaux**

Décrire les six dés et les éléments propres à chaque joueur.

Inclure :

* Jaune : 3 × 6 cases.
* Turquoise : 5 × 6 cases.
* Bleu : 13 cases, avec le 7 central fixe en position 7.
* Marron : les 12 valeurs préimprimées dans leur ordre exact.
* Rose : 12 cases.
* Les trois emplacements de dés sélectionnés.
* Le carré gris.
* Les compteurs de bonus et leur capacité.
* Les identifiants des cases et leur correspondance avec les coordonnées du plateau.

Documenter les cases jaunes accessibles en phase passive et le motif turquoise foncé **6, 5, 3, 2, 1**, depuis la gauche.

Distinguer les données fixes des données qui évoluent pendant une partie.

**D. Initialisation et déroulement complet**

Décrire chronologiquement :

1. Initialisation des deux plateaux.
2. Attribution des bonus de début de tour global.
3. Résolution éventuelle de ces bonus avant le premier lancer.
4. Manches actives du joueur 1.
5. Action passive du joueur 2.
6. Fenêtres +1.
7. Manches actives du joueur 2.
8. Action passive du joueur 1.
9. Fenêtres +1.
10. Fin du tour global.
11. Fin de partie après le sixième tour et toutes les résolutions restantes.

Vérifier et préciser l’ordre exact des fenêtres +1 d’après les sources disponibles.

Expliquer les conditions de passage entre les phases, les cas où il faut attendre une décision et les transitions purement automatiques.

**E. Cycle des dés**

Spécifier :

* Quels dés sont lancés ou relancés.
* La sélection d’un dé.
* L’élimination selon les valeurs strictement inférieures.
* La conservation des valeurs des dés choisis et écartés.
* Le transfert des dés restants à la fin de la séquence active.
* Le complément sans effet des emplacements actifs manquants.
* La répartition finale de trois dés actifs et trois dés passifs.
* Le recours aux dés actifs lorsque les dés passifs ne permettent aucun coup.
* Le traitement d’une absence totale de coup légal.

Préciser les conséquences du placement d’un dé sans effet sur ses utilisations ultérieures, notamment en turquoise et avec un +1.

**F. Règles de chaque couleur**

Pour chaque couleur, détailler :

* Les entrées nécessaires.
* Les destinations autorisées.
* La valeur utilisée.
* Les choix du joueur.
* Les modifications du plateau.
* Les causes d’impossibilité.
* Les différences entre action active, passive, +1 et bonus virtuel.

Couvrir notamment :

* Jaune : ligne liée à la manche active, restrictions passives et exception du +1.
* Turquoise : colonne choisie, nombre de coches autorisé et groupe de dés pris en compte selon le contexte.
* Bleu : somme blanc + bleu, deux branches indépendantes, progression exacte de ±1, retour à 7 et cas de branche pleine.
* Marron : correspondance de valeur, progression vers la droite et cases devenues inaccessibles.
* Rose : première case obligatoirement divisée par deux, puis choix points ou bonus.
* Blanc : choix de couleur et conservation de son identité physique.

Décrire le turquoise avec un tableau comparant les contextes, pour éviter toute ambiguïté entre dés actifs, passifs et dé sélectionné.

**G. Bonus stockables**

Pour relance, joker chiffre et +1, préciser :

* Capacité et contenu de la piste.
* Conditions d’obtention.
* États « non débloqué », « disponible », « utilisé ».
* Fenêtres d’utilisation.
* Paramètres à choisir.
* Moment exact de consommation.
* Possibilité d’annulation.
* Combinaisons autorisées.
* Comportement lorsque la piste est pleine.
* Récompense éventuelle de fin de piste.

Pour le joker, expliciter les conséquences distinctes de la valeur physique et de la valeur effective sur le placement, l’élimination, le bleu et le turquoise.

Pour le +1, documenter la réutilisation éventuelle d’un même dé et signaler toute règle non confirmée.

**H. Bonus immédiats et enchaînements**

Décrire chaque bonus de couleur et le bonus noir :

* Choix autorisés.
* Valeurs possibles.
* Contraintes de placement.
* Absence d’effet sur les dés physiques.
* Traitement d’un bonus impossible.
* Suspension et reprise de la phase en cours.

Préciser le fonctionnement lorsque plusieurs récompenses sont déclenchées simultanément ou qu’un bonus en déclenche d’autres.

Distinguer une file temporaire de résolution d’un stock de bonus utilisable ultérieurement.

Décrire comment empêcher qu’une même source de bonus soit accordée plusieurs fois.

**I. Table exhaustive des emplacements de récompenses**

Pour chaque source, donner :

| ID de règle/source | Zone | Emplacement exact | Condition | Récompense |
| ------------------ | ---- | ----------------- | --------- | ---------- |

Inclure les bonus :

* De début de tour.
* De fin de compteur.
* Entre les lignes jaunes.
* À droite des lignes et sous les colonnes turquoise.
* Sur les cases bleues.
* Entre les cases marron.
* Sous les cases roses.
* Les cinq emplacements de renards prévus par la variante.

Utiliser les positions des cases plutôt que des paires de valeurs ambiguës.

Intégrer les corrections les plus récentes : renard jaune au dernier emplacement de la première rangée de bonus ; +1 au dernier emplacement de la deuxième.

Pour le rose, fournir un tableau unique réunissant position, multiplicateur, récompense et traitement particulier de la première case.

**J. Scores**

Donner les barèmes complets, y compris zéro case, et les formules pour :

* Jaune.
* Turquoise.
* Bleu, avec progression des deux branches et valeurs spéciales.
* Marron.
* Rose.
* Renards.
* Total final et égalité.

Préciser :

* Ce qui compte et ce qui ne compte pas.
* Le caractère provisoire des scores pendant la partie.
* L’absence de double application des multiplicateurs et divisions.
* La différence entre le nombre de cases remplies et la position atteinte.

Relever explicitement toute contradiction de barème encore non résolue.

**K. Actions et transitions du futur moteur**

Proposer une description conceptuelle indépendante de React et de FastAPI.

Pour chaque action du joueur, préciser :

| Action | Acteur autorisé | Paramètres | Préconditions | Effets | Prochaine décision ou phase |
| ------ | --------------- | ---------- | ------------- | ------ | --------------------------- |

Distinguer :

* Les décisions de jeu à exposer au moteur.
* Les conséquences automatiques.
* Les interactions purement visuelles, comme ouvrir une fenêtre.

Un clic sur « Valider » n’est pas nécessairement une action stratégique distincte. Expliquer comment transmettre une décision complète sans obliger l’agent RL à reproduire les clics du navigateur.

Un coup refusé doit laisser l’état du jeu et les ressources inchangés.

**L. État minimal à représenter en Python**

Décrire les données nécessaires sans implémenter le moteur :

* Plateaux des joueurs.
* Dés, valeurs et emplacements.
* Progression et phase.
* Joueur devant agir.
* Ressources et renards.
* Sources de bonus déjà déclenchées.
* Décisions et bonus en attente.
* Informations nécessaires à la reprise d’une phase interrompue.
* Générateur aléatoire propre à chaque partie.

Distinguer les données à stocker des valeurs calculables, comme les scores.

Expliquer les conditions de reproductibilité : mêmes règles, même graine, mêmes actions et même gestion de l’aléatoire. Ne pas inclure l’état interne du générateur dans l’observation destinée à l’agent.

**M. Interface et avance automatique**

Isoler dans cette section ce qui ne constitue pas une règle de légalité :

* Présélection d’une destination unique.
* Confirmation manuelle.
* Mise en évidence des cases.
* Affichage permanent des scores.
* Avance automatique de N tours.
* Choix aléatoires.
* Stratégie évitant si possible les dés les plus élevés aux manches 1 et 2.

Préciser que cette dernière restriction appartient à la politique du joueur automatique et ne doit pas supprimer des coups légaux du futur moteur ou de l’environnement RL.

**N. Invariants et scénarios de référence**

Lister les propriétés que le moteur devra toujours respecter, notamment :

* Les six dés physiques ne sont ni dupliqués ni perdus.
* Un dé appartient à un seul emplacement à un instant donné.
* La répartition 3 actifs / 3 passifs est vérifiée à la fin de la séquence active, pas nécessairement pendant les lancers.
* Une récompense n’est accordée qu’une fois par source.
* Une annulation ne consomme aucune ressource.
* Une action modifie uniquement le plateau de son bénéficiaire.
* Les bonus immédiats sont résolus avant la transition normale.
* La partie ne se termine pas avec des décisions obligatoires en attente.

Ajouter des scénarios concrets avec **état initial, action, résultat attendu**, couvrant au minimum :

* Première case rose avec une valeur impaire et une valeur paire.
* Rose avec joker, puis choix points ou bonus sur une case ultérieure.
* Joker dont la valeur effective diffère de la valeur utilisée pour éliminer les dés.
* Turquoise actif, passif, +1 et bonus immédiat.
* Bleu avec un dé partenaire déjà écarté.
* Redémarrage d’une branche bleue avec un 7.
* Cases marron sautées.
* Enchaînement de bonus.
* Attribution des bonus au début d’un tour.
* Complément des dés actifs sans effet.
* Recours passif aux dés actifs.
* Renard rose obtenu ou non selon l’option choisie.
* Fin de partie après les derniers bonus.

Choisir des états dont les résultats sont calculables précisément.

**O. Écarts et décisions à confirmer**

Terminer par un tableau :

| Sujet | Règle explicite disponible | Comportement du code | Écart ou ambiguïté | Impact sur le moteur |
| ----- | -------------------------- | -------------------- | ------------------ | -------------------- |

Ne pas masquer les inconnues. Distinguer clairement une règle confirmée, une hypothèse issue d’une reformulation et un comportement observé dans le code.

**5. Vérification et livraison**

Avant de terminer :

* Vérifier la correction de la première case rose.
* Relire les tableaux pour repérer les contradictions internes.
* Vérifier que chaque source de bonus et chaque phase sont documentées.
* Vérifier qu’aucune ancienne règle remplacée n’est présentée comme actuelle.
* Faire correspondre les scénarios aux règles identifiées.
* Indiquer les tests réellement exécutés, sans prétendre avoir vérifié ce qui ne l’a pas été.

Livrer le fichier **`REGLES_DU_JEU.md`** dans le projet, avec un lien vers ce fichier, puis un bref compte rendu indiquant :

1. Le correctif rose effectué.
2. Les vérifications réalisées.
3. Les divergences importantes découvertes.
4. Les décisions restant à confirmer avant de construire le moteur Python.

L’objectif est une spécification exploitable et traçable, pas une simple description visuelle du plateau ni une transcription du code actuel.
