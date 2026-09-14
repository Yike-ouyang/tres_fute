Applique les corrections et fonctionnalités suivantes au jeu React + TypeScript existant. Ces instructions remplacent les règles précédentes lorsqu’elles les contredisent. Conserve les autres mécanismes, les identifiants et les logs de débogage.

**1. Corriger les cases foncées turquoise**

Le bloc turquoise conserve **5 lignes et 6 colonnes**. Les cases foncées commencent toujours à gauche :

| Ligne depuis le haut | Nombre de cases foncées | Colonnes concernées |
| -------------------- | ----------------------- | ------------------- |
| 1                    | 6                       | 1 à 6               |
| 2                    | 5                       | 1 à 5               |
| 3                    | 3                       | 1 à 3               |
| 4                    | 2                       | 1 et 2              |
| 5                    | 1                       | 1                   |

Toutes les autres cases sont claires et restent jouables.

Mettre à jour simultanément :

* L’apparence des cases.
* Les conditions de déclenchement des bonus de ligne et de colonne, qui dépendent des cases foncées.
* Les données utilisées pour vérifier ces conditions.

Le score turquoise continue de compter toutes les cases cochées, claires comme foncées.

**2. Corriger les deux derniers bonus jaunes**

Ici, « première ligne » et « deuxième ligne » désignent les **rangées de bonus entre les lignes de cases**, pas les lignes de cases elles-mêmes.

* Première rangée de bonus, colonne 6, entre les lignes de cases 1 et 2 : **renard**.
* Deuxième rangée de bonus, colonne 6, entre les lignes de cases 2 et 3 : **+1**.

Chaque bonus se déclenche lorsque les deux cases qui l’encadrent sont cochées.

Corriger à la fois leur affichage et leur logique. Supprimer l’ancien déclencheur du renard jaune pour empêcher un double déblocage. Ne pas modifier les autres bonus jaunes.

**3. Présélectionner une destination unique**

Lorsqu’un dé ou un bonus ne possède qu’une seule destination légale, présélectionner automatiquement cette case.

* La présélection reste provisoire.
* Afficher clairement la case sélectionnée.
* Le joueur doit encore cliquer sur **« Valider »**.
* Ne pas inscrire de valeur, cocher définitivement de case ou consommer de ressource avant validation.
* Permettre l’annulation selon les règles existantes.

Appliquer ce comportement aux actions actives, passives, +1 et bonus immédiats.

**Une seule destination ne signifie pas nécessairement un seul choix complet.** Si un choix de valeur, de couleur ou d’option rose reste nécessaire, le demander avant d’activer la validation. Ne jamais choisir automatiquement entre les points et le bonus rose.

Si plusieurs destinations sont légales, conserver la sélection manuelle.

**4. Compléter les emplacements actifs lorsqu’il ne reste aucun dé disponible**

Remplacer la fin anticipée automatique dans le cas suivant : le joueur actif a encore des manches à jouer, mais aucun dé disponible.

Ouvrir alors une phase intitulée **« Compléter les dés actifs — sans effet »** :

1. Le joueur choisit un dé du carré gris.
2. Le dé est déplacé dans le prochain emplacement actif vide.
3. Répéter jusqu’à ce que les trois emplacements actifs soient occupés.

Ces déplacements servent uniquement à répartir les six dés :

* Aucun effet sur le plateau.
* Aucun bonus déclenché.
* Aucun lancer.
* Aucune élimination supplémentaire.
* Aucune consommation de joker ou de +1.
* Les valeurs physiques des dés restent inchangées.

Afficher explicitement que ces choix ne produisent aucun coup.

À la fin de chaque séquence active, avant l’action passive, il doit toujours y avoir **3 dés dans les emplacements actifs et 3 dés dans le carré gris**.

Si la séquence active se termine parce qu’aucun dé disponible n’est jouable, transférer d’abord les dés disponibles dans le carré gris, puis utiliser la même phase de complément pour remplir les emplacements actifs manquants.

Pour les actions ultérieures, notamment les +1 et les calculs turquoise, ces dés appartiennent au groupe dans lequel ils ont été placés.

**5. Autoriser un dé actif si aucun dé passif n’est jouable**

Pendant l’action passive normale :

* Vérifier d’abord les coups possibles avec les trois dés du carré gris.
* Si au moins un de ces dés permet un coup légal, seuls les dés du carré gris sont accessibles.
* Si aucun ne permet de coup légal, autoriser le joueur passif à choisir l’un des trois dés actifs.
* Si aucun des six dés n’est jouable, permettre de passer.

Pour détecter les coups possibles, prendre en compte les couleurs utilisables avec le blanc. Ne pas obliger le joueur à dépenser un joker pour éviter ce recours : déterminer l’accès aux dés actifs sans consommation de bonus stockable.

Afficher un message lorsque le recours devient disponible : **« Aucun dé passif n’est jouable : vous pouvez choisir un dé actif. »**

L’utilisation d’un dé actif reste une **action passive** :

* Appliquer les restrictions du jaune passif.
* Pour le turquoise, compter les autres dés de même valeur présents dans le carré gris, même si le dé choisi vient des emplacements actifs.
* Pour le bleu, conserver le calcul avec les valeurs physiques du blanc et du bleu.
* Ne déplacer aucun dé et ne modifier aucune valeur physique.
* Autoriser une seule action passive normale.

Cette règle ne modifie pas le fonctionnement particulier des fenêtres +1.

**6. Ajouter une avance automatique de plusieurs tours**

À côté de « Réinitialiser la partie », ajouter :

* Un champ entier « Nombre de tours à jouer automatiquement ».
* Un bouton **« Avancer »**.

Définir précisément le comportement : avancer de N tours signifie **terminer le tour global en cours, puis N−1 tours supplémentaires**. Si le tour actuel n’a pas commencé, il compte comme le premier tour à simuler.

Limiter la saisie aux tours restants. Ne jamais dépasser la fin de partie.

Pendant cette avance, jouer automatiquement pour les deux joueurs en choisissant aléatoirement parmi les actions légales :

* Lancers et choix de dés.
* Choix des destinations et des couleurs du blanc.
* Choix rose entre points et bonus.
* Sélections turquoise.
* Résolution de tous les bonus immédiats et de leurs enchaînements.
* Utilisation ou conservation des bonus stockables aux moments autorisés.
* Fenêtres +1.
* Complément des emplacements actifs sans effet.
* Recours aux dés actifs pendant une action passive, si nécessaire.

Pour une action facultative, inclure la possibilité de continuer sans dépenser de bonus. Ne jamais passer une action obligatoire lorsqu’un coup légal existe.

**Réutiliser les mêmes fonctions de légalité et de transition que le jeu manuel.** Ne pas modifier directement les cases pour fabriquer un résultat et ne pas créer un second ensemble de règles pour la simulation.

Avant de démarrer, annuler les sélections purement provisoires sans consommer de ressources. Conserver les bonus immédiats déjà obtenus et les résoudre automatiquement.

Pendant l’exécution :

* Désactiver les interactions manuelles incompatibles.
* Afficher la progression.
* Garder l’interface réactive.
* Journaliser les actions en mode debug.
* Prévoir une protection contre les boucles infinies ; en cas de blocage, arrêter avec un diagnostic sans forcer un coup illégal.

S’arrêter à la fin du dernier tour demandé, après toutes ses actions et tous ses bonus, avant d’initialiser le tour suivant. Si la partie est terminée, afficher les résultats.

**7. Afficher les scores en permanence**

Ajouter un panneau de score visible sur chaque plateau, associé à son joueur.

Afficher :

* Les scores jaune, turquoise, bleu foncé, marron et rose.
* Le nombre de renards débloqués.
* La valeur actuelle d’un renard.
* Les points actuellement apportés par les renards.
* Le total actuel.

Utiliser les fonctions de calcul existantes, avec les mêmes barèmes que pour le résultat final.

Mettre à jour les scores après chaque action **validée**, y compris pendant l’avance automatique. Une présélection ou une action annulée ne doit pas modifier le score.

Pendant la partie, présenter ces valeurs comme des **scores provisoires** : la valeur des renards évolue avec le minimum des cinq couleurs.

**8. Vérifications attendues**

Vérifier notamment :

* Le motif turquoise `6, 5, 3, 2, 1` et les déclenchements associés.
* Les emplacements et conditions des deux bonus jaunes corrigés.
* La présélection d’une destination unique sans validation automatique.
* Le maintien du choix rose malgré une destination unique.
* La répartition finale de trois dés actifs et trois dés passifs, sans effet des dés de complément.
* L’accès aux dés actifs uniquement lorsque le recours passif est autorisé.
* Une avance automatique traversant des bonus en chaîne et plusieurs tours.
* L’arrêt exact de l’avance demandée et à la fin de partie.
* La concordance entre scores permanents et résultats finaux.
* La réinitialisation complète des nouvelles données.

Effectuer les modifications, puis résumer les changements et les vérifications réalisées.
