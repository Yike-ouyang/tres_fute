Ajoute des logs dans la **console du navigateur** pour faciliter le débogage du jeu React + TypeScript, puis identifie et corrige le bug suivant.

**Bug à résoudre**

Lorsque je clique sur un dé de couleur, les cases autorisées sont mises en évidence, mais cliquer dessus ne permet pas de les sélectionner. Je ne peux donc pas terminer le coup ni le valider.

Le comportement attendu est le suivant :

* Cliquer sur un dé sélectionne provisoirement ce dé et affiche ses destinations légales.
* Cliquer sur une destination légale enregistre le choix.
* Pour les actions à destination unique, ce clic valide le coup selon le fonctionnement existant.
* Pour le turquoise, les clics permettent de sélectionner ou désélectionner les cases provisoires, puis le bouton « Valider » confirme le coup.
* Les cases non autorisées restent inactives.

**1. Ajouter des logs structurés**

Prévoir un mode debug activable et désactivable facilement. Utiliser un préfixe commun, par exemple `[GameDebug]`, et `console.groupCollapsed` pour regrouper les informations liées à une même interaction.

Journaliser les étapes suivantes :

* Clic sur un dé.
* Sélection ou annulation d’un dé.
* Choix de couleur pour le blanc.
* Calcul des destinations légales et du nombre de cases sélectionnables.
* Clic sur une case.
* Acceptation ou refus de cette sélection, avec la raison précise.
* Mise à jour de la sélection provisoire.
* Tentative de validation, validation réussie ou refus motivé.
* Application du coup au plateau.
* Déplacement des dés et changement de manche, de phase ou de tour.
* Réinitialisation de la partie.

Inclure les informations pertinentes : tour, manche, phase active ou passive, joueur actif, joueur qui doit agir, identité et valeur du dé, couleur effective, ID de la case, destinations légales et sélection provisoire.

Pour les transitions importantes, afficher un résumé de l’état avant et après. Utiliser des instantanés de données pour éviter que la console affiche ultérieurement des objets modifiés. Ne pas présenter comme nouvel état une valeur React encore ancienne juste après un appel à son setter.

Éviter les logs à chaque rendu : privilégier les interactions et les transitions utiles.

**2. Rechercher la cause du blocage**

Reproduire le problème et suivre toute la chaîne :

**clic sur le dé → destinations légales → clic sur la case → sélection provisoire → validation.**

Vérifier notamment :

* Que les cases proposées possèdent bien un gestionnaire de clic.
* Qu’aucun attribut `disabled`, style `pointer-events`, élément superposé ou problème de propagation ne bloque le clic.
* Que les identifiants des cases correspondent exactement à ceux utilisés par le calcul des destinations, y compris les préfixes `p1-` et `p2-`.
* Que l’autorisation dépend du joueur qui doit agir, notamment en phase passive.
* Que la sélection du dé est conservée jusqu’à la fin du coup.
* Que les gestionnaires utilisent un état React à jour.
* Que la condition rendant une case cliquable correspond à celle qui la met en évidence.
* Que la sélection provisoire et la condition d’activation du bouton « Valider » sont cohérentes.

Si un clic ne parvient pas au gestionnaire de la case, inspecter le DOM et les styles pour identifier ce qui l’intercepte.

Ces points sont des pistes de diagnostic : identifier la cause à partir du code et des observations, sans la supposer à l’avance.

**3. Corriger et vérifier**

Corriger la cause du bug en conservant les règles existantes. Ne pas contourner le problème en rendant toutes les cases modifiables ou en supprimant les contrôles de légalité.

Vérifier de manière ciblée :

* Une sélection de destination avec un dé de couleur.
* Une sélection turquoise de plusieurs cases, suivie de sa validation.
* Une utilisation du dé blanc après choix de couleur.
* Une action active et une action passive, sur les deux plateaux.
* Le refus d’une case illégale.
* L’absence de double application d’un coup.

Si l’environnement ne permet pas de tester les interactions dans un navigateur, préciser cette limite et fournir les étapes exactes de reproduction et de vérification manuelle.

**Résultat attendu**

Effectuer les modifications dans le code, puis expliquer brièvement :

* La cause identifiée et les éléments qui la démontrent.
* La correction apportée.
* Comment activer les logs et les consulter dans la console du navigateur.
* Les vérifications effectuées et leurs résultats.

L’ajout de logs seul ne suffit pas : l’objectif est de rétablir la sélection des cases et la validation des coups.
