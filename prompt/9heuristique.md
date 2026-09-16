Implémente une politique heuristique pour l’**avance rapide** du jeu. Elle doit également être réutilisable comme adversaire fixe lors du futur entraînement RL.

Utilise le moteur Python existant et ses actions légales. Ne modifie ni les règles du jeu ni les actions accessibles au joueur humain ou à l’agent RL.

**1. Architecture et reproductibilité**

Créer une politique distincte du moteur, par exemple `HeuristicPolicy`, avec une méthode permettant de choisir une action légale à partir de l’observation et du contexte de décision.

* Réutiliser cette politique dans l’avance rapide.
* Prévoir son utilisation par un seul joueur comme adversaire de l’agent.
* Utiliser un générateur aléatoire dédié, initialisable par une graine et indépendant de celui des dés.
* Conserver le fonctionnement entièrement automatique : choix, validation, bonus et transitions.
* Remplacer l’ancienne préférence de l’avance rapide qui évitait simplement le dé maximal par les règles ci-dessous.

**2. Ordre des priorités**

Les règles suivantes sont des **préférences hiérarchisées**, dans cet ordre :

1. Manche active 1 : retirer au maximum trois dés disponibles, dé choisi compris.
2. Manche active 2 : conserver au moins un dé disponible pour la manche 3.
3. Manche active 2 : conserver au moins un dé rose, blanc ou jaune pour la manche 3.
4. Marron : éviter les cases de positions 4, 5 et 6.
5. Bleu : jouer uniquement sur la branche droite.
6. Lorsqu’une utilisation marron ou bleue reste possible, la choisir avec une probabilité de 75 %.
7. Rose : choisir l’option bonus lorsqu’elle existe.
8. Turquoise : privilégier les utilisations accompagnées d’au moins un autre dé de même valeur dans le groupe pertinent.

Une préférence ne doit jamais bloquer le jeu ni conduire à une action illégale.

Pour les contraintes de sélection, partir de l’ensemble des coups légaux puis appliquer les préférences dans l’ordre : conserver les coups satisfaisant une préférence si cet ensemble est non vide ; sinon, ignorer cette préférence pour cette décision et poursuivre.

Une préférence de priorité inférieure ne doit jamais réintroduire un coup déjà écarté par une préférence supérieure.

**3. Évaluer les coups complets avant de choisir un dé**

Ne pas limiter l’analyse à la couleur physique du dé.

Évaluer les utilisations légales possibles, notamment :

* Les différentes couleurs du blanc.
* Les différentes destinations marron.
* Les branches bleues.
* Les choix liés à une utilisation de bonus.

Le blanc joué en marron doit être traité comme un coup marron ; le blanc joué en bleu comme un coup bleu.

Si le moteur expose des décisions successives, conserver un plan cohérent : dé → couleur → destination → option éventuelle. Ne pas refaire des tirages indépendants susceptibles de contredire le choix initial. Réévaluer le plan si l’état pertinent change.

Ne pas consommer de joker ou de relance uniquement pour satisfaire une préférence, sauf si une stratégie explicite de gestion de ces ressources existe déjà.

**4. Manche active 1 : limiter les dés retirés**

Pour chaque dé sélectionnable, calculer :

`nombreRetires = 1 + nombreDesDisponiblesDeValeurStrictementInferieure`

Le `1` correspond au dé choisi. Les autres dés concernés sont ceux qui seront déplacés dans le carré gris.

Privilégier les coups pour lesquels :

`nombreRetires <= 3`

Utiliser les valeurs physiques des dés, avant application d’un éventuel joker. Ne pas compter les dés déjà choisis ou déjà écartés.

Exemple : choisir un 4 parmi des valeurs `1, 2, 4, 4, 5, 6` retire trois dés : le 4 choisi, le 1 et le 2.

Si aucun coup légal ne satisfait cette limite, poursuivre avec les coups légaux disponibles, conformément au mécanisme de repli.

**5. Manche active 2 : préparer la troisième manche**

Pour chaque choix, déterminer les dés qui resteront disponibles après le retrait du dé choisi et l’élimination des dés strictement inférieurs.

Appliquer successivement :

1. Privilégier les choix laissant au moins un dé disponible.
2. Parmi les choix conservés, privilégier ceux laissant au moins un dé de couleur rose, blanche ou jaune.

Il s’agit de conserver une **identité de dé disponible**, pas de garantir son résultat après le prochain lancer. Ne pas consulter ni anticiper les futurs tirages.

Ces préférences ne s’appliquent ni aux actions passives ni aux utilisations +1.

**6. Marron : éviter trois positions**

Éviter les destinations marron de **positions 4, 5 et 6**, comptées depuis la gauche à partir de 1.

Il s’agit des positions des cases, et non de leurs valeurs imprimées.

Appliquer cette préférence aux dés marron, au blanc utilisé en marron, aux +1 et aux bonus immédiats marron.

Si aucune alternative ne subsiste après les préférences prioritaires, autoriser une destination normalement évitée plutôt que bloquer le jeu.

**7. Bleu : privilégier exclusivement la branche droite**

Parmi les coups conservés, écarter les utilisations de la branche gauche lorsqu’il existe une alternative.

La branche droite correspond aux positions **8 à 13** de la piste à treize cases, le 7 central étant en position 7.

Appliquer cette préférence au dé bleu, au blanc utilisé en bleu et aux bonus immédiats bleus.

Si les seuls coups restants sont des placements à gauche, autoriser ce repli. Ne jamais inscrire une valeur illégale pour forcer un placement à droite.

**8. Préférence probabiliste marron / bleu**

Après application des contraintes précédentes :

* Si des coups marron ou bleus et des coups d’autres couleurs sont disponibles, choisir la famille marron/bleu avec une probabilité de **75 %**, et les autres couleurs avec une probabilité de **25 %**.
* Si seule la famille marron/bleu est disponible, la choisir.
* Si aucun coup marron ou bleu ne reste, choisir parmi les autres couleurs.

Effectuer ce tirage une seule fois par choix d’utilisation de dé ou de couleur, pas à chaque sous-étape.

Dans la branche retenue, appliquer les préférences suivantes puis départager aléatoirement les possibilités restantes. Éviter de favoriser artificiellement un dé simplement parce qu’il possède davantage de destinations : choisir d’abord une utilisation dé/couleur, puis sa destination.

**9. Rose : prendre le bonus**

Lorsqu’une case rose propose le choix entre points et bonus, sélectionner systématiquement **l’option bonus**.

* Inscrire la moitié de la valeur effective, arrondie au supérieur.
* Résoudre la récompense selon les règles du moteur.
* Un renard compte comme une récompense à privilégier.
* Sur la première case, appliquer directement la division par deux obligatoire, sans bonus.
* Si la case ne propose aucun bonus, utiliser l’option autorisée par le moteur.

Appliquer cette règle à tous les contextes, y compris les bonus roses virtuels.

**10. Turquoise : rechercher les valeurs communes**

Privilégier un coup turquoise lorsque le dé utilisé possède au moins **un autre dé de même valeur** dans le groupe pris en compte par les règles de ce contexte.

Utiliser le calcul du moteur, sans le réimplémenter dans la politique :

* Jeu actif : dés précédemment choisis pertinents.
* Jeu passif : dés du carré gris pertinents.
* +1 : groupe déterminé par l’emplacement du dé.
* Recours passif à un dé actif : règle particulière existante du moteur.

Ne pas compter le dé sélectionné comme son propre partenaire.

Si le turquoise n’a pas de partenaire de même valeur et qu’une autre utilisation subsiste à ce niveau de priorité, préférer cette autre utilisation.

Un bonus turquoise immédiat, qui permet une coche sans dé physique, n’est pas soumis à cette préférence et doit être résolu normalement.

Lorsqu’une utilisation turquoise autorise plusieurs coches, prendre le maximum autorisé dans la limite des cases libres, puis choisir aléatoirement parmi les ensembles de destinations légaux de cette taille.

**11. Décisions non couvertes**

Conserver les règles de légalité pour toutes les autres décisions.

* Complément sans effet des dés actifs : choisir aléatoirement parmi les dés autorisés.
* Valeur d’un bonus virtuel : choisir parmi les valeurs permettant un coup légal, en respectant les préférences de couleur et de destination.
* Bonus immédiat obligatoire : le résoudre ; ne pas l’abandonner pour éviter une préférence.
* Ressources facultatives — relance, joker, +1 : réutiliser la stratégie existante et documenter son comportement. Si aucune stratégie n’existe, prévoir une configuration simple indiquant leur probabilité d’utilisation, sans les consommer automatiquement par défaut.
* Passer uniquement lorsque le moteur l’autorise.

Une décision disposant d’un seul choix légal doit être résolue automatiquement.

**12. Logs et vérifications**

En mode debug, journaliser :

* Le contexte et les coups candidats.
* Le nombre de dés retirés et les dés conservés.
* Les filtres appliqués et les préférences relâchées.
* Le tirage marron/bleu à 75 %.
* L’utilisation complète finalement choisie.

Ajouter des tests ciblés couvrant :

* La limite de trois dés retirés à la première manche.
* La conservation d’un dé, puis d’un rose/blanc/jaune à la deuxième.
* La distinction entre position et valeur des cases marron.
* La préférence pour la branche bleue droite.
* Le blanc utilisé comme marron ou bleu.
* Le choix du bonus rose et l’exception de la première case.
* Le calcul turquoise selon le contexte.
* Les replis lorsqu’une préférence est impossible.
* La reproductibilité avec une même graine.
* Des parties automatiques complètes sans action illégale ni attente de validation manuelle.

Vérifier le seuil probabiliste avec un générateur contrôlé ; la règle signifie une probabilité de 75 %, pas exactement trois occurrences dans chaque groupe de quatre décisions.

Effectuer les modifications dans le code, puis résumer les fichiers modifiés, les comportements de repli et les vérifications réalisées.
