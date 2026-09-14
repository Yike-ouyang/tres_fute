Corrige l’avance rapide dans le jeu React + TypeScript existant.

**1. Automatiser toutes les validations**

Actuellement, l’avance rapide s’arrête à chaque manche parce qu’elle attend un clic sur « Valider ». Elle doit exécuter entièrement le nombre de tours demandé **sans intervention humaine**.

Pendant l’avance rapide, effectuer automatiquement :

* La sélection du dé et de sa destination.
* Les choix supplémentaires : couleur du blanc, valeur d’un bonus, option rose, cases turquoise.
* La validation du coup.
* La résolution des bonus et de leurs enchaînements.
* Les confirmations et transitions : manche suivante, tour suivant, fin des fenêtres +1, passage autorisé et complément des dés actifs.

Réutiliser les mêmes fonctions de validation et de transition que le jeu manuel. Ne pas simuler des clics sur les boutons du DOM et ne pas contourner les contrôles de légalité.

Chaque action doit être entièrement résolue avant la suivante, à partir de l’état actualisé. Empêcher les doubles validations et les boucles infinies.

**Le mode manuel conserve ses confirmations habituelles.**

**2. Éviter le dé le plus élevé aux deux premières manches**

Appliquer cette restriction uniquement aux **choix normaux de dés pendant les manches actives 1 et 2**, pour les deux joueurs, pendant l’avance rapide.

Procédure :

1. Relever la valeur physique maximale parmi tous les dés encore disponibles.
2. Déterminer les dés permettant au moins un coup légal.
3. S’il existe un dé jouable de valeur **strictement inférieure à ce maximum**, exclure tous les dés ayant la valeur maximale.
4. Choisir aléatoirement parmi les dés jouables restants.
5. Si aucun dé de valeur inférieure n’est jouable, autoriser les dés de valeur maximale qui permettent un coup légal.

Comparer les **valeurs physiques issues du lancer**, avant tout joker, et non les valeurs effectives ou la somme bleu + blanc.

Pour déterminer si une alternative est jouable, prendre en compte toutes les couleurs possibles du blanc. Ne pas imposer la consommation d’un joker uniquement pour créer une alternative de valeur inférieure. Si aucun coup n’est possible sans joker, utiliser les règles existantes de gestion des bonus et des situations bloquées.

Exemples :

* Dés disponibles `1, 3, 4, 6` : si le 3 ou le 4 est jouable, ne pas choisir le 6.
* Dés disponibles `2, 5, 5` : si le 2 est jouable, exclure les deux 5.
* Dés disponibles `2, 5, 5` : si seul un 5 est jouable, autoriser ce choix.
* Tous les dés disponibles ont la même valeur : choisir parmi ceux qui sont jouables.

Ne pas appliquer cette restriction à la troisième manche, aux actions passives, aux +1, aux bonus immédiats ni aux déplacements sans effet servant à compléter les emplacements actifs.

**3. Vérifier le comportement**

Ajouter aux logs debug :

* La manche et la phase.
* Les dés disponibles et leurs valeurs physiques.
* Les dés jouables, ceux exclus par la restriction et le dé finalement choisi.
* La raison d’une éventuelle autorisation de la valeur maximale.
* Les validations automatiques et les transitions.

Vérifier qu’une avance de plusieurs tours se termine sans clic, y compris avec des choix roses et des bonus en chaîne, et qu’elle s’arrête exactement à la limite demandée ou à la fin de partie.

Effectuer les corrections dans le code, puis résumer la cause du blocage et les vérifications réalisées.
