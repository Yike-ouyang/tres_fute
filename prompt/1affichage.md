Construis une interface de plateau de jeu de dés en **React + TypeScript** dans le dossier frontend.

L’objectif est de créer un **plateau interactif manipulable manuellement**, sans logique de jeu : aucun calcul de score, aucune validation des coups, aucun déclenchement de bonus et aucun lancer automatique de dés. Les compteurs de bonus sont uniquement des cases à cocher.

Respecte les dimensions décrites ci-dessous, même si elles diffèrent de celles du jeu original.

**Disposition**

Le plateau occupe une seule page web :

* En haut : une barre de suivi des 6 tours.
* En dessous : trois emplacements de dés à gauche et trois compteurs de bonus empilés à droite.
* Au milieu : une zone jaune à gauche et une zone turquoise à droite.
* En bas : trois pistes horizontales empilées, dans l’ordre bleu foncé, marron, puis rose.

Sur ordinateur, vise un affichage compact permettant de voir tout le plateau sur un écran standard. Sur mobile, adapte la disposition et autorise le défilement vertical pour conserver des cases lisibles.

**Interactions communes**

Chaque case appartient à l’un des types suivants :

* **Case à cocher** : un clic la coche, un second clic la décoche. Si elle porte un nombre, celui-ci reste visible et ne peut pas être modifié.
* **Case de saisie numérique** : l’utilisateur peut saisir, modifier ou effacer un nombre entier. Une case vide reste vide ; elle ne devient pas automatiquement zéro.
* **Case fixe** : elle affiche une valeur non modifiable.

Toutes les cases à cocher sont indépendantes. Aucune action sur une case ne modifie automatiquement une autre case.

**1. Barre de suivi des tours**

Afficher 6 cases à cocher portant les numéros 1 à 6.

Identifiants, de gauche à droite : `turn-1` à `turn-6`.

**2. Compteurs de bonus**

Afficher 3 barres horizontales de 7 cases à cocher chacune, avec les libellés neutres « Compteur 1 », « Compteur 2 » et « Compteur 3 ».

Ne leur associer aucun effet.

Format des identifiants : `bonus-{barre}-cell-{position}`.

* Barre : de 1 à 3, de haut en bas.
* Position : de 1 à 7, de gauche à droite.
* Exemples : `bonus-1-cell-1`, `bonus-3-cell-7`.

**3. Emplacements de dés**

Afficher 3 emplacements, repérés I, II et III.

Chaque emplacement permet de choisir manuellement :

* Une valeur entière de 1 à 6, ou aucune valeur.
* Une couleur parmi jaune, turquoise, bleu foncé, marron, rose et blanc, ou aucune couleur.

La couleur choisie devient le fond du dé, avec un chiffre suffisamment contrasté pour rester lisible.

Identifiants des emplacements : `die-1`, `die-2`, `die-3`.

Identifiants des contrôles associés :

* Valeur : `die-{position}-value`.
* Couleur : `die-{position}-color`.

**4. Zone jaune**

Afficher une grille de **3 lignes et 6 colonnes**, soit 18 cases à cocher.

Chaque ligne affiche les nombres fixes suivants, de gauche à droite : **1, 2, 3, 4, 5, 6**.

Format des identifiants : `yellow-r{ligne}-c{colonne}`.

* Lignes de 1 à 3, de haut en bas.
* Colonnes de 1 à 6, de gauche à droite.
* Exemples : `yellow-r1-c1`, `yellow-r3-c6`.

**5. Zone turquoise**

Afficher une grille de **6 lignes et 6 colonnes**, soit 36 cases à cocher.

Chaque ligne affiche les nombres fixes suivants, de gauche à droite : **1, 2, 3, 4, 5, 6**.

Format des identifiants : `turquoise-r{ligne}-c{colonne}`.

* Lignes et colonnes de 1 à 6.
* Exemples : `turquoise-r1-c1`, `turquoise-r6-c6`.

**6. Piste bleu foncé**

Afficher une seule ligne de **11 cases** :

* 5 cases de saisie numérique initialement vides.
* 1 case centrale fixe affichant **7**.
* 5 cases de saisie numérique initialement vides.

Identifiants, de gauche à droite : `blue-cell-1` à `blue-cell-11`.

La case centrale est `blue-cell-6`. Elle ne peut être ni modifiée ni cochée.

Les dix autres cases acceptent librement des nombres entiers, sans contrainte de progression.

**7. Piste marron**

Afficher une seule ligne de **12 cases à cocher**, portant les nombres fixes suivants, de gauche à droite :

**1, 5, 3, 4, 2, 6, 4, 5, 2, 1, 6, 3**.

Identifiants, de gauche à droite : `brown-cell-1` à `brown-cell-12`.

Toutes les cases peuvent être cochées et décochées dans n’importe quel ordre.

**8. Piste rose**

Afficher une seule ligne de **12 cases de saisie numérique**, initialement vides.

Identifiants, de gauche à droite : `pink-cell-1` à `pink-cell-12`.

Chaque case accepte librement un nombre entier.

**Exigences techniques et visuelles**

* Utiliser des composants fonctionnels React et des types TypeScript explicites.
* Conserver les valeurs et les états cochés dans l’état React.
* Créer des composants réutilisables pour les cases à cocher, les cases numériques et les emplacements de dés.
* Utiliser les identifiants définis ci-dessus comme identifiants stables dans les données et comme attributs HTML `id`. Ils doivent être uniques et ne pas changer lors d’un rendu.
* Les identifiants n’ont pas besoin d’être affichés sur le plateau.
* Prévoir des libellés accessibles et une utilisation au clavier.
* Distinguer clairement une case cochée par une coche visible, tout en conservant son nombre lisible.
* Donner à chaque zone un titre et sa couleur de fond, avec des cases bien contrastées.
* Initialiser toutes les cases à cocher à « non cochée », toutes les saisies à vide et les dés sans valeur ni couleur. Seuls les nombres préimprimés, dont le 7 central, sont présents au départ.
* Le fonctionnement doit être entièrement local au front-end, sans back-end ni base de données.

**Résultat attendu**

Fournir le code complet de l’interface et les commandes nécessaires pour la lancer. Toutes les interactions décrites doivent fonctionner dès cette première version.
