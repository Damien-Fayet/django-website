#!/usr/bin/env python
"""
Script d'initialisation des définitions pour le jeu Max Challenge
Lance ce script avec : python init_definitions.py
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from max_challenge.models import Definition

# 150 définitions : 50 faciles, 50 moyennes, 50 difficiles
DEFINITIONS = [
    # ==================== FACILE (1-50) ====================
    {
        'word': 'Soleil',
        'definition': 'Étoile lumineuse située au centre de notre système planétaire qui nous apporte chaleur et lumière chaque jour',
        'difficulty': 1
    },
    {
        'word': 'Paris',
        'definition': 'Ville principale de la France où se trouvent la tour Eiffel, le musée du Louvre et l\'Arc de Triomphe',
        'difficulty': 1
    },
    {
        'word': 'Chat',
        'definition': 'Animal domestique à quatre pattes couvert de poils qui miaule, ronronne et aime chasser les souris',
        'difficulty': 1
    },
    {
        'word': 'Piano',
        'definition': 'Grand instrument de musique avec des touches noires et blanches sur lesquelles on appuie pour créer des mélodies',
        'difficulty': 1
    },
    {
        'word': 'Océan',
        'definition': 'Immense étendue d\'eau salée qui couvre plus de la moitié de notre planète et abrite baleines, requins et dauphins',
        'difficulty': 1
    },
    {
        'word': 'Livre',
        'definition': 'Objet composé de nombreuses pages reliées ensemble qu\'on peut lire pour découvrir des histoires ou apprendre de nouvelles choses',
        'difficulty': 1
    },
    {
        'word': 'Ballon',
        'definition': 'Objet sphérique gonflé d\'air qu\'on utilise pour pratiquer le football, le basketball ou le volleyball',
        'difficulty': 1
    },
    {
        'word': 'Maison',
        'definition': 'Bâtiment avec des murs, un toit et des fenêtres où une famille habite et se protège du froid et de la pluie',
        'difficulty': 1
    },
    {
        'word': 'Fleur',
        'definition': 'Partie colorée et parfumée d\'une plante qui attire les abeilles et les papillons pour la pollinisation',
        'difficulty': 1
    },
    {
        'word': 'Vélo',
        'definition': 'Moyen de transport écologique à deux roues qu\'on fait avancer en appuyant sur des pédales avec ses pieds',
        'difficulty': 1
    },
    {
        'word': 'Pomme',
        'definition': 'Fruit rond et croquant qui pousse dans les pommiers et peut être rouge, vert ou jaune selon la variété',
        'difficulty': 1
    },
    {
        'word': 'Lune',
        'definition': 'Satellite naturel qui tourne autour de notre planète et qu\'on voit briller dans le ciel pendant la nuit',
        'difficulty': 1
    },
    {
        'word': 'Arc-en-ciel',
        'definition': 'Magnifique phénomène naturel aux sept couleurs qui apparaît dans le ciel après une averse quand le soleil revient',
        'difficulty': 1
    },
    {
        'word': 'Oiseau',
        'definition': 'Animal vertébré couvert de plumes qui possède des ailes pour voler et pond des œufs dans un nid',
        'difficulty': 1
    },
    {
        'word': 'Peinture',
        'definition': 'Art qui consiste à créer des images et des tableaux en appliquant des couleurs sur une toile avec un pinceau',
        'difficulty': 1
    },
    {
        'word': 'Montagne',
        'definition': 'Relief naturel très élevé avec des sommets rocheux souvent recouverts de neige où on peut faire du ski ou de la randonnée',
        'difficulty': 1
    },
    {
        'word': 'Chocolat',
        'definition': 'Aliment sucré et délicieux fabriqué à partir des fèves de cacao que les enfants et les adultes adorent manger',
        'difficulty': 1
    },
    {
        'word': 'Téléphone',
        'definition': 'Appareil électronique qui permet de parler avec quelqu\'un situé très loin ou d\'envoyer des messages instantanés',
        'difficulty': 1
    },
    {
        'word': 'Jardin',
        'definition': 'Espace extérieur aménagé autour d\'une maison où poussent des fleurs, des arbres et parfois des légumes',
        'difficulty': 1
    },
    {
        'word': 'Étoile',
        'definition': 'Point lumineux qu\'on observe dans le ciel nocturne et qui est en réalité une boule de gaz brûlant très loin de nous',
        'difficulty': 1
    },
    {
        'word': 'École',
        'definition': 'Établissement où les enfants vont chaque jour pour apprendre à lire, écrire, compter et acquérir des connaissances',
        'difficulty': 1
    },
    {
        'word': 'Plage',
        'definition': 'Étendue de sable fin au bord de la mer où les gens vont se baigner, construire des châteaux et bronzer',
        'difficulty': 1
    },
    {
        'word': 'Gâteau',
        'definition': 'Pâtisserie sucrée et moelleuse qu\'on sert lors des anniversaires et des fêtes, souvent décorée avec des bougies',
        'difficulty': 1
    },
    {
        'word': 'Neige',
        'definition': 'Précipitation blanche et froide formée de cristaux de glace qui tombe du ciel en hiver et recouvre le sol',
        'difficulty': 1
    },
    {
        'word': 'Forêt',
        'definition': 'Vaste territoire couvert de nombreux arbres serrés les uns contre les autres où vivent écureuils, cerfs et sangliers',
        'difficulty': 1
    },
    {
        'word': 'Train',
        'definition': 'Long véhicule composé de plusieurs wagons qui roule sur des rails pour transporter des voyageurs entre les villes',
        'difficulty': 1
    },
    {
        'word': 'Nuage',
        'definition': 'Masse vaporeuse blanche ou grise formée de minuscules gouttelettes d\'eau qui flotte dans le ciel',
        'difficulty': 1
    },
    {
        'word': 'Papillon',
        'definition': 'Insecte léger aux ailes colorées qui vole de fleur en fleur pour butiner le nectar avec sa trompe',
        'difficulty': 1
    },
    {
        'word': 'Fromage',
        'definition': 'Aliment fabriqué à partir du lait de vache, de chèvre ou de brebis dont la France possède des centaines de variétés',
        'difficulty': 1
    },
    {
        'word': 'Avion',
        'definition': 'Appareil volant motorisé plus lourd que l\'air qui peut transporter des passagers très haut dans le ciel',
        'difficulty': 1
    },
    {
        'word': 'Pluie',
        'definition': 'Eau qui tombe du ciel sous forme de gouttes lorsque les nuages deviennent trop lourds et saturés d\'humidité',
        'difficulty': 1
    },
    {
        'word': 'Chien',
        'definition': 'Animal de compagnie fidèle et affectueux qui aboie, remue la queue et adore jouer à rapporter la balle',
        'difficulty': 1
    },
    {
        'word': 'Guitare',
        'definition': 'Instrument de musique à cordes qu\'on fait vibrer en les pinçant ou en les grattant avec les doigts ou un médiator',
        'difficulty': 1
    },
    {
        'word': 'Mer',
        'definition': 'Grande étendue d\'eau salée moins vaste qu\'un océan où vivent poissons, méduses et crustacés',
        'difficulty': 1
    },
    {
        'word': 'Soleil',
        'definition': 'Astre lumineux et chaud visible le jour qui se lève à l\'est le matin et se couche à l\'ouest le soir',
        'difficulty': 1
    },
    {
        'word': 'Voiture',
        'definition': 'Véhicule automobile à quatre roues équipé d\'un moteur qui permet de se déplacer rapidement sur les routes',
        'difficulty': 1
    },
    {
        'word': 'Arbre',
        'definition': 'Grande plante vivace avec un tronc en bois, des branches et des feuilles qui produit de l\'oxygène',
        'difficulty': 1
    },
    {
        'word': 'Pain',
        'definition': 'Aliment de base fabriqué avec de la farine, de l\'eau et de la levure puis cuit au four par le boulanger',
        'difficulty': 1
    },
    {
        'word': 'Eau',
        'definition': 'Liquide transparent et incolore absolument essentiel à la vie de tous les êtres vivants sur notre planète',
        'difficulty': 1
    },
    {
        'word': 'Feu',
        'definition': 'Réaction chimique qui produit des flammes chaudes, de la lumière et de la fumée en brûlant du bois ou d\'autres matières',
        'difficulty': 1
    },
    {
        'word': 'Vent',
        'definition': 'Déplacement naturel de l\'air qu\'on sent sur notre peau et qui peut être doux comme une brise ou violent comme une tempête',
        'difficulty': 1
    },
    {
        'word': 'Poisson',
        'definition': 'Animal vertébré qui vit sous l\'eau et respire grâce à ses branchies en filtrant l\'oxygène dissous',
        'difficulty': 1
    },
    {
        'word': 'Banane',
        'definition': 'Fruit tropical allongé à la peau jaune qu\'il faut éplucher avant de manger sa chair douce et sucrée',
        'difficulty': 1
    },
    {
        'word': 'Carotte',
        'definition': 'Légume orange qui pousse sous la terre et qu\'on dit excellent pour avoir une bonne vue',
        'difficulty': 1
    },
    {
        'word': 'Éléphant',
        'definition': 'Plus gros mammifère terrestre reconnaissable à sa longue trompe mobile et ses grandes oreilles',
        'difficulty': 1
    },
    {
        'word': 'Lunettes',
        'definition': 'Paire de verres correcteurs montés dans une monture qu\'on porte sur le nez pour améliorer sa vision',
        'difficulty': 1
    },
    {
        'word': 'Chapeau',
        'definition': 'Accessoire vestimentaire qu\'on place sur sa tête pour se protéger du soleil, du froid ou simplement comme décoration',
        'difficulty': 1
    },
    {
        'word': 'Chaussure',
        'definition': 'Protection rigide qu\'on enfile à chaque pied pour marcher confortablement et éviter de se blesser',
        'difficulty': 1
    },
    {
        'word': 'Porte',
        'definition': 'Panneau mobile fixé sur des gonds qui permet d\'entrer dans une pièce ou un bâtiment et qu\'on peut fermer à clé',
        'difficulty': 1
    },
    {
        'word': 'Fenêtre',
        'definition': 'Ouverture dans un mur équipée de vitres transparentes qui laisse entrer la lumière naturelle tout en protégeant du froid',
        'difficulty': 1
    },
    
    # ==================== MOYEN (51-100) ====================
    {
        'word': 'Pyramide',
        'definition': 'Monument funéraire égyptien de forme géométrique à base carrée et quatre faces triangulaires servant de tombeau aux pharaons de l\'Antiquité. Les plus célèbres se trouvent sur le plateau de Gizeh près du Caire',
        'difficulty': 2
    },
    {
        'word': 'Renaissance',
        'definition': 'Période historique européenne des quinzième et seizième siècles marquée par un renouveau des arts, des sciences et de la pensée humaniste inspiré de l\'Antiquité gréco-romaine',
        'difficulty': 2
    },
    {
        'word': 'Équateur',
        'definition': 'Ligne imaginaire tracée autour du globe terrestre à égale distance des deux pôles qui divise notre planète en deux hémisphères nord et sud',
        'difficulty': 2
    },
    {
        'word': 'Photosynthèse',
        'definition': 'Processus biologique par lequel les plantes vertes captent l\'énergie lumineuse du soleil pour transformer le dioxyde de carbone et l\'eau en sucres et en oxygène',
        'difficulty': 2
    },
    {
        'word': 'Démocratie',
        'definition': 'Système politique où le pouvoir appartient au peuple qui choisit librement ses représentants par le vote et où les libertés fondamentales sont garanties',
        'difficulty': 2
    },
    {
        'word': 'Volcan',
        'definition': 'Montagne issue de l\'ouverture de la croûte terrestre par laquelle remontent du magma et des gaz en fusion qui peuvent créer des éruptions spectaculaires de lave',
        'difficulty': 2
    },
    {
        'word': 'Mozart',
        'definition': 'Compositeur autrichien prodige du dix-huitième siècle qui a créé plus de six cents œuvres musicales dont des opéras, symphonies et concertos qui sont encore joués aujourd\'hui',
        'difficulty': 2
    },
    {
        'word': 'Amazonie',
        'definition': 'Immense forêt tropicale d\'Amérique du Sud considérée comme le poumon vert de la planète qui abrite une biodiversité exceptionnelle mais menacée par la déforestation',
        'difficulty': 2
    },
    {
        'word': 'Squelette',
        'definition': 'Structure interne rigide composée de deux cent six os chez l\'adulte qui soutient le corps humain, protège les organes vitaux et permet les mouvements',
        'difficulty': 2
    },
    {
        'word': 'Olympiades',
        'definition': 'Grande compétition sportive internationale organisée tous les quatre ans où des athlètes du monde entier s\'affrontent dans de nombreuses disciplines pour remporter des médailles',
        'difficulty': 2
    },
    {
        'word': 'Révolution',
        'definition': 'Changement brusque et profond dans l\'organisation politique, sociale ou économique d\'une société, souvent accompagné de mouvements populaires et parfois de violence',
        'difficulty': 2
    },
    {
        'word': 'Constellation',
        'definition': 'Ensemble d\'étoiles formant une figure imaginaire dans le ciel nocturne auquel les civilisations anciennes ont donné des noms d\'animaux ou de personnages mythologiques',
        'difficulty': 2
    },
    {
        'word': 'Fresque',
        'definition': 'Technique de peinture murale où les pigments sont appliqués sur un enduit frais encore humide ce qui permet une excellente conservation des couleurs au fil des siècles',
        'difficulty': 2
    },
    {
        'word': 'Opéra',
        'definition': 'Spectacle théâtral musical où les acteurs chantent leurs dialogues accompagnés par un grand orchestre dans des décors somptueux',
        'difficulty': 2
    },
    {
        'word': 'Tsunami',
        'definition': 'Vague océanique géante et dévastatrice provoquée par un séisme sous-marin ou une éruption volcanique qui peut atteindre plusieurs dizaines de mètres de hauteur',
        'difficulty': 2
    },
    {
        'word': 'Métamorphose',
        'definition': 'Transformation complète et progressive de la forme d\'un être vivant au cours de son développement comme la chenille qui devient papillon',
        'difficulty': 2
    },
    {
        'word': 'Stalactite',
        'definition': 'Colonne de calcaire qui pend du plafond d\'une grotte et qui se forme lentement goutte après goutte par le dépôt de minéraux dissous dans l\'eau',
        'difficulty': 2
    },
    {
        'word': 'Caravelle',
        'definition': 'Type de navire à voiles léger et maniable utilisé par les grands explorateurs comme Christophe Colomb lors de leurs expéditions vers le Nouveau Monde',
        'difficulty': 2
    },
    {
        'word': 'Haïku',
        'definition': 'Forme poétique japonaise traditionnelle composée de seulement trois vers courts évoquant la nature et les saisons avec simplicité et profondeur',
        'difficulty': 2
    },
    {
        'word': 'Fjord',
        'definition': 'Vallée profonde creusée par un ancien glacier puis envahie par les eaux de la mer formant un bras étroit bordé de falaises vertigineuses typique de la Norvège',
        'difficulty': 2
    },
    {
        'word': 'Équinoxe',
        'definition': 'Moment astronomique se produisant deux fois par an où la durée du jour est exactement égale à celle de la nuit sur toute la planète',
        'difficulty': 2
    },
    {
        'word': 'Sonnet',
        'definition': 'Poème structuré de quatorze vers répartis en deux quatrains et deux tercets très utilisé dans la poésie classique française et italienne',
        'difficulty': 2
    },
    {
        'word': 'Métronome',
        'definition': 'Petit appareil mécanique ou électronique utilisé par les musiciens qui produit des battements réguliers pour maintenir un tempo constant pendant l\'apprentissage',
        'difficulty': 2
    },
    {
        'word': 'Mammouth',
        'definition': 'Cousin préhistorique de l\'éléphant recouvert d\'une épaisse fourrure et doté de longues défenses courbes qui a disparu il y a environ dix mille ans',
        'difficulty': 2
    },
    {
        'word': 'Acropole',
        'definition': 'Citadelle fortifiée bâtie sur une colline dominant les cités grecques antiques où se trouvaient les temples et bâtiments les plus importants',
        'difficulty': 2
    },
    {
        'word': 'Stalactite',
        'definition': 'Formation minérale calcaire descendant du plafond des grottes comme des chandelles de pierre qui met des milliers d\'années à se développer',
        'difficulty': 2
    },
    {
        'word': 'Aurore boréale',
        'definition': 'Phénomène lumineux magnifique aux couleurs chatoyantes vertes et violettes visible dans le ciel des régions polaires causé par des particules solaires',
        'difficulty': 2
    },
    {
        'word': 'Latitude',
        'definition': 'Coordonnée géographique qui mesure la distance angulaire d\'un point sur Terre par rapport à l\'équateur exprimée en degrés nord ou sud',
        'difficulty': 2
    },
    {
        'word': 'Hibernation',
        'definition': 'État de sommeil profond et prolongé adopté par certains animaux pendant la saison froide pour économiser leur énergie en ralentissant leur métabolisme',
        'difficulty': 2
    },
    {
        'word': 'Colonie',
        'definition': 'Territoire lointain occupé, administré et exploité économiquement par une nation étrangère plus puissante généralement pour ses ressources naturelles',
        'difficulty': 2
    },
    {
        'word': 'Sénat',
        'definition': 'Assemblée parlementaire formant la chambre haute du pouvoir législatif qui vote les lois en collaboration avec l\'Assemblée nationale',
        'difficulty': 2
    },
    {
        'word': 'Ballade',
        'definition': 'Forme poétique narrative médiévale composée de trois strophes et d\'un envoi ou chanson populaire racontant une histoire souvent mélancolique',
        'difficulty': 2
    },
    {
        'word': 'Éclipse',
        'definition': 'Phénomène astronomique spectaculaire durant lequel un astre en cache temporairement un autre comme lorsque la Lune passe devant le Soleil',
        'difficulty': 2
    },
    {
        'word': 'Vignoble',
        'definition': 'Terrain agricole spécialement aménagé et planté de rangées de vignes cultivées pour produire différentes variétés de raisin destinées à la fabrication du vin',
        'difficulty': 2
    },
    {
        'word': 'Citadelle',
        'definition': 'Forteresse militaire puissamment fortifiée construite sur une hauteur pour dominer et protéger une ville des attaques ennemies',
        'difficulty': 2
    },
    {
        'word': 'Manuscrit',
        'definition': 'Texte entièrement écrit à la main sur du parchemin ou du papier avant l\'invention de l\'imprimerie souvent richement décoré d\'enluminures',
        'difficulty': 2
    },
    {
        'word': 'Aqueduc',
        'definition': 'Ouvrage d\'ingénierie romaine composé d\'arches de pierre permettant de transporter l\'eau potable sur de longues distances depuis sa source jusqu\'aux villes',
        'difficulty': 2
    },
    {
        'word': 'Fossile',
        'definition': 'Reste minéralisé ou trace d\'un organisme vivant ancien conservé dans les couches rocheuses qui permet aux scientifiques d\'étudier la vie préhistorique',
        'difficulty': 2
    },
    {
        'word': 'Chœur',
        'definition': 'Groupe organisé de chanteurs qui interprètent ensemble des œuvres vocales à plusieurs voix dans un esprit d\'harmonie et de coordination',
        'difficulty': 2
    },
    {
        'word': 'Archipel',
        'definition': 'Ensemble géographique formé par un groupe d\'îles plus ou moins rapprochées les unes des autres dans une même zone maritime',
        'difficulty': 2
    },
    {
        'word': 'Glacier',
        'definition': 'Masse imposante de glace accumulée en haute montagne qui descend très lentement en sculptant les vallées sous l\'effet de son propre poids',
        'difficulty': 2
    },
    {
        'word': 'Sismographe',
        'definition': 'Instrument scientifique sensible qui détecte et enregistre les mouvements du sol lors des tremblements de terre en traçant des courbes sur un graphique',
        'difficulty': 2
    },
    {
        'word': 'Rosace',
        'definition': 'Grande fenêtre circulaire ornementale garnie de vitraux colorés disposés en motifs rayonnants caractéristique de l\'architecture des cathédrales gothiques',
        'difficulty': 2
    },
    {
        'word': 'Oasis',
        'definition': 'Zone fertile et verdoyante au milieu du désert aride où la présence d\'eau souterraine permet aux plantes de pousser et aux populations de s\'installer',
        'difficulty': 2
    },
    {
        'word': 'Nébuleuse',
        'definition': 'Immense nuage cosmique composé de gaz et de poussières stellaires dans l\'espace où naissent de nouvelles étoiles par condensation de la matière',
        'difficulty': 2
    },
    {
        'word': 'Cromlechs',
        'definition': 'Monument mégalithique préhistorique formé d\'un ensemble de pierres levées disposées en cercle ou en demi-cercle utilisé pour des rituels anciens',
        'difficulty': 2
    },
    {
        'word': 'Vigile',
        'definition': 'Personne employée pour assurer la surveillance et la sécurité d\'un lieu en effectuant des rondes régulières de jour comme de nuit',
        'difficulty': 2
    },
    {
        'word': 'Tanière',
        'definition': 'Abri naturel creusé dans le sol ou aménagé dans une cavité rocheuse où certains animaux sauvages se réfugient et élèvent leurs petits',
        'difficulty': 2
    },
    {
        'word': 'Torrent',
        'definition': 'Cours d\'eau de montagne au débit rapide et tumultueux qui dévale les pentes raides en créant des cascades et en charriant des rochers',
        'difficulty': 2
    },
    {
        'word': 'Symbiose',
        'definition': 'Relation biologique durable entre deux organismes vivants différents qui cohabitent de manière bénéfique pour chacun en s\'apportant mutuellement des avantages',
        'difficulty': 2
    },
    
    # ==================== DIFFICILE (101-150) ====================
    {
        'word': 'Miroir',
        'definition': 'Surface réfléchissante où l\'on peut observer son propre reflet inversé qui a longtemps été un objet de fascination et de superstition dans de nombreuses cultures',
        'difficulty': 3
    },
    {
        'word': 'Ombre',
        'definition': 'Zone sombre créée par l\'interception de la lumière par un corps opaque utilisée depuis l\'Antiquité pour mesurer le temps avec les cadrans solaires',
        'difficulty': 3
    },
    {
        'word': 'Boussole',
        'definition': 'Instrument d\'orientation dont l\'aiguille aimantée pointe toujours vers le nord magnétique terrestre permettant aux navigateurs de trouver leur chemin',
        'difficulty': 3
    },
    {
        'word': 'Pendule',
        'definition': 'Masse suspendue qui oscille régulièrement de part et d\'autre d\'une position d\'équilibre dont Galilée découvrit les propriétés pour mesurer le temps',
        'difficulty': 3
    },
    {
        'word': 'Horloge',
        'definition': 'Mécanisme ingénieux inventé au Moyen Âge qui divise la journée en heures, minutes et secondes grâce à un système complexe d\'engrenages',
        'difficulty': 3
    },
    {
        'word': 'Racine',
        'definition': 'Organe végétal souterrain qui ancre solidement la plante dans le sol tout en puisant l\'eau et les nutriments nécessaires à sa croissance',
        'difficulty': 3
    },
    {
        'word': 'Horizon',
        'definition': 'Ligne imaginaire apparente où le ciel semble toucher la terre ou la mer qui recule constamment à mesure qu\'on avance vers elle',
        'difficulty': 3
    },
    {
        'word': 'Empreinte',
        'definition': 'Marque en creux ou en relief laissée par la pression d\'un objet sur une surface molle utilisée depuis toujours pour identifier et authentifier',
        'difficulty': 3
    },
    {
        'word': 'Labyrinthe',
        'definition': 'Réseau complexe de chemins entrelacés conçu pour égarer celui qui s\'y aventure dont le plus célèbre de la mythologie grecque abritait le Minotaure',
        'difficulty': 3
    },
    {
        'word': 'Énigme',
        'definition': 'Question formulée de manière obscure ou ambiguë qui nécessite réflexion et perspicacité pour en découvrir la réponse cachée',
        'difficulty': 3
    },
    {
        'word': 'Momie',
        'definition': 'Corps humain ou animal préservé de la décomposition par dessiccation naturelle ou par des techniques d\'embaumement pratiquées notamment en Égypte ancienne',
        'difficulty': 3
    },
    {
        'word': 'Parchemin',
        'definition': 'Support d\'écriture fabriqué à partir de peau animale soigneusement préparée qui a précédé le papier pendant des siècles en Europe médiévale',
        'difficulty': 3
    },
    {
        'word': 'Horloge',
        'definition': 'Dispositif mécanique ou électronique qui découpe le temps qui passe en unités mesurables et affiche l\'heure du jour',
        'difficulty': 3
    },
    {
        'word': 'Clepsydre',
        'definition': 'Instrument antique qui mesure l\'écoulement du temps grâce à un filet d\'eau s\'écoulant régulièrement d\'un récipient vers un autre',
        'difficulty': 3
    },
    {
        'word': 'Écho',
        'definition': 'Phénomène acoustique de répétition d\'un son causé par la réflexion des ondes sonores sur une paroi qui les renvoie vers leur source',
        'difficulty': 3
    },
    {
        'word': 'Sphinx',
        'definition': 'Créature légendaire au corps de lion et tête humaine qui dans la mythologie grecque posait des devinettes mortelles aux voyageurs',
        'difficulty': 3
    },
    {
        'word': 'Mosaïque',
        'definition': 'Art décoratif antique consistant à assembler minutieusement de petits cubes de pierre ou de verre colorés pour former des images ou des motifs',
        'difficulty': 3
    },
    {
        'word': 'Relique',
        'definition': 'Objet ou fragment corporel ayant appartenu à un saint vénéré par les fidèles et conservé précieusement comme témoignage sacré',
        'difficulty': 3
    },
    {
        'word': 'Cascade',
        'definition': 'Chute spectaculaire d\'un cours d\'eau qui dégringole verticalement ou en gradins depuis une hauteur en produisant un bruit caractéristique',
        'difficulty': 3
    },
    {
        'word': 'Cloche',
        'definition': 'Instrument de bronze en forme de coupe renversée qui résonne quand on le frappe avec un battant utilisé pour rythmer la vie religieuse',
        'difficulty': 3
    },
    {
        'word': 'Comète',
        'definition': 'Astre glacé du système solaire qui développe une longue traînée lumineuse visible quand il s\'approche du soleil et dont l\'apparition a longtemps été vue comme un présage',
        'difficulty': 3
    },
    {
        'word': 'Vitrail',
        'definition': 'Panneau décoratif composé de morceaux de verre coloré assemblés par des baguettes de plomb qui filtre magnifiquement la lumière dans les églises',
        'difficulty': 3
    },
    {
        'word': 'Ancre',
        'definition': 'Lourde pièce métallique reliée au navire par une chaîne qu\'on jette au fond de l\'eau pour immobiliser le bateau',
        'difficulty': 3
    },
    {
        'word': 'Marée',
        'definition': 'Mouvement périodique montant et descendant du niveau de la mer causé par l\'attraction gravitationnelle conjuguée de la Lune et du Soleil',
        'difficulty': 3
    },
    {
        'word': 'Navire',
        'definition': 'Grand bâtiment de mer conçu pour naviguer sur les océans et transporter marchandises ou passagers sur de longues distances',
        'difficulty': 3
    },
    {
        'word': 'Cadran',
        'definition': 'Surface plane graduée d\'un instrument de mesure sur laquelle une aiguille mobile indique une valeur comme l\'heure ou la vitesse',
        'difficulty': 3
    },
    {
        'word': 'Compas',
        'definition': 'Instrument formé de deux branches articulées utilisé pour tracer des cercles parfaits ou reporter des distances sur un plan',
        'difficulty': 3
    },
    {
        'word': 'Sablier',
        'definition': 'Dispositif de mesure du temps composé de deux bulbes de verre reliés par un col étroit où le sable s\'écoule à vitesse constante',
        'difficulty': 3
    },
    {
        'word': 'Prisme',
        'definition': 'Solide transparent de forme géométrique qui décompose la lumière blanche en un spectre de couleurs arc-en-ciel par réfraction',
        'difficulty': 3
    },
    {
        'word': 'Lentille',
        'definition': 'Pièce de verre ou matière transparente aux surfaces courbes qui fait converger ou diverger les rayons lumineux qui la traversent',
        'difficulty': 3
    },
    {
        'word': 'Télescope',
        'definition': 'Instrument optique inventé au dix-septième siècle qui grossit les objets célestes lointains permettant d\'observer les astres en détail',
        'difficulty': 3
    },
    {
        'word': 'Écluse',
        'definition': 'Ouvrage hydraulique formé de deux portes qui permet aux bateaux de franchir une dénivellation en faisant varier le niveau de l\'eau',
        'difficulty': 3
    },
    {
        'word': 'Moulin',
        'definition': 'Construction équipée de meules tournantes actionnées par le vent ou l\'eau servant traditionnellement à moudre le grain en farine',
        'difficulty': 3
    },
    {
        'word': 'Balance',
        'definition': 'Instrument de pesée à deux plateaux suspendus en équilibre qui permet de comparer la masse de différents objets',
        'difficulty': 3
    },
    {
        'word': 'Éolienne',
        'definition': 'Machine moderne dotée de grandes pales qui tournent sous l\'action du vent pour produire de l\'électricité renouvelable',
        'difficulty': 3
    },
    {
        'word': 'Phare',
        'definition': 'Tour élevée construite sur les côtes rocheuses qui émet un puissant faisceau lumineux pour guider les navires la nuit',
        'difficulty': 3
    },
    {
        'word': 'Pont',
        'definition': 'Construction architecturale enjambant un obstacle naturel comme une rivière pour permettre le passage de véhicules et piétons',
        'difficulty': 3
    },
    {
        'word': 'Tunnel',
        'definition': 'Galerie souterraine creusée à travers une montagne ou sous un cours d\'eau pour créer une voie de communication directe',
        'difficulty': 3
    },
    {
        'word': 'Barrage',
        'definition': 'Gigantesque mur de béton construit en travers d\'une vallée pour retenir l\'eau d\'un fleuve et créer un lac artificiel',
        'difficulty': 3
    },
    {
        'word': 'Rempart',
        'definition': 'Muraille fortifiée très épaisse entourant une ville médiévale pour la protéger des assauts ennemis lors des sièges',
        'difficulty': 3
    },
    {
        'word': 'Donjon',
        'definition': 'Tour maîtresse massive située au cœur d\'un château fort servant de dernier refuge défensif et de résidence seigneuriale',
        'difficulty': 3
    },
    {
        'word': 'Beffroi',
        'definition': 'Tour civile médiévale abritant les cloches municipales symbole des libertés urbaines et servant de poste de guet',
        'difficulty': 3
    },
    {
        'word': 'Portail',
        'definition': 'Entrée monumentale richement sculptée d\'un édifice religieux souvent ornée de statues de saints et de scènes bibliques',
        'difficulty': 3
    },
    {
        'word': 'Arcade',
        'definition': 'Ouverture en forme d\'arc soutenue par des piliers caractéristique de l\'architecture romane et gothique',
        'difficulty': 3
    },
    {
        'word': 'Voûte',
        'definition': 'Plafond de pierre courbe en forme d\'arc qui permet de couvrir un espace en répartissant les charges sur les murs latéraux',
        'difficulty': 3
    },
    {
        'word': 'Colonnade',
        'definition': 'Rangée de colonnes régulièrement espacées soutenant une toiture caractéristique des temples antiques et des palais',
        'difficulty': 3
    },
    {
        'word': 'Fronton',
        'definition': 'Couronnement triangulaire au-dessus de l\'entrée d\'un temple grec ou romain souvent décoré de sculptures en relief',
        'difficulty': 3
    },
    {
        'word': 'Coupole',
        'definition': 'Toit hémisphérique de forme arrondie qui surmonte majestueusement certains édifices religieux ou palais prestigieux',
        'difficulty': 3
    },
    {
        'word': 'Flèche',
        'definition': 'Construction pyramidale très élancée couronnant le clocher d\'une église qui s\'élève vers le ciel comme pour toucher les nuages',
        'difficulty': 3
    },
    {
        'word': 'Cloître',
        'definition': 'Galerie couverte à arcades entourant un jardin carré dans un monastère où les moines méditent en marchant',
        'difficulty': 3
    },
]

def init_definitions():
    """Initialise la base de données avec les définitions"""
    print("🎯 Initialisation des définitions pour Max Challenge...")
    print(f"📝 Nombre de définitions à créer : {len(DEFINITIONS)}")
    
    # Vérifier si des définitions existent déjà
    existing_count = Definition.objects.count()
    if existing_count > 0:
        response = input(f"\n⚠️  {existing_count} définition(s) existe(nt) déjà. Voulez-vous les supprimer ? (oui/non) : ")
        if response.lower() in ['oui', 'o', 'yes', 'y']:
            Definition.objects.all().delete()
            print("✅ Anciennes définitions supprimées")
        else:
            print("❌ Annulation de l'initialisation")
            return
    
    # Créer les définitions
    created = 0
    for def_data in DEFINITIONS:
        Definition.objects.create(**def_data)
        created += 1
        print(f"  ✓ [{created}/{len(DEFINITIONS)}] {def_data['word']} ajouté")
    
    print(f"\n🎉 {created} définitions créées avec succès !")
    print("\n📊 Répartition par difficulté :")
    print(f"   • Facile : {Definition.objects.filter(difficulty=1).count()} définitions")
    print(f"   • Moyen : {Definition.objects.filter(difficulty=2).count()} définitions")
    print(f"   • Difficile : {Definition.objects.filter(difficulty=3).count()} définitions")
    print("\n🚀 Le jeu est prêt à être lancé !")

if __name__ == '__main__':
    init_definitions()
