"""Petites phrases drôles pour les réponses : une citation ou une moquerie gentille quand on se trompe,
un compliment à l'humour des lutins quand on réussit.

Le ton reste bienveillant : se tromper ne coûte que quelques points (scoring.ERROR_PENALTY) et on rit avec le
joueur, pas à ses dépens.
`{nom}` est remplacé par le nom du joueur. Les citations dont l'attribution est douteuse le disent.
"""
import random

# Mauvaise réponse : affichée dans une fenêtre « Raté ! » (voir _messages.html et static/avent2026/js/popup.js).
ECHECS = (
    # Citations sur l'échec
    "« Toujours essayé. Toujours échoué. Peu importe. Essaie encore. Échoue encore. Échoue mieux. » Samuel Beckett",
    "« Je n'ai pas échoué. J'ai simplement trouvé dix mille solutions qui ne fonctionnent pas. » Thomas Edison, paraît-il",
    "« L'expérience est le nom que chacun donne à ses erreurs. » Oscar Wilde",
    "« Le succès, c'est d'aller d'échec en échec sans perdre son enthousiasme. » Winston Churchill, selon Internet (sans preuve)",
    "« La folie, c'est de refaire la même chose en espérant un résultat différent. » Albert Einstein, qui ne l'a jamais dit",
    "« J'ai raté plus de neuf mille tirs dans ma carrière. C'est pour ça que je réussis. » Michael Jordan",
    "« Essayer, il ne faut pas. Faire, ou ne pas faire. Il n'y a pas d'essai. » Maître Yoda, qui ne rate jamais, lui",
    "« Je ne perds jamais : soit je gagne, soit j'apprends. » Nelson Mandela, attribué",
    # Moqueries gentilles
    "Cette réponse a été examinée avec le plus grand sérieux, puis jetée dans la neige.",
    "Cinq points de moins, et une légère déception collective chez les lutins.",
    "Même les rennes ont secoué la tête, et ils ont pourtant très peu d'opinions.",
    "Le Père Noël, dans sa cellule, vient de pousser un long soupir de vapeur.",
    "Erreur 404 : bonne réponse introuvable. Elle doit être quelque part dans le village.",
    "Les lutins ont noté ça dans leur carnet : « Idées originales, mais fausses ».",
    "C'est faux, mais avec beaucoup de conviction. On aime ça.",
    "{nom}, respire. Relis l'énoncé. Puis relis-le encore, plus lentement.",
    "On ne te juge pas. Les lutins, un petit peu, mais ils sont payés en chocolat.",
    "Même la chaîne du Père Noël a levé un maillon d'un air dubitatif.",
    "Bonne nouvelle : tu peux réessayer autant que tu veux. Mauvaise nouvelle : chaque erreur coûte 5 points.",
    "Le hasard aurait peut-être fait mieux. Mais le hasard n'a pas d'amour-propre, lui.",
    "Ce n'est pas la bonne réponse, mais c'est une réponse. Les grandes découvertes commencent ainsi. Les petites aussi.",
    "Un lampion de plus qui reste éteint. Il fait semblant de dormir.",
    "{nom}, tu chauffes. Enfin, pas du tout, mais l'intention est là.",
    "Cette réponse a un charme fou. Elle n'a juste aucune chance d'être juste.",
)

# Bonne réponse : en tête du message vert, suivi de « +N points. ».
REUSSITES = (
    "Bravo ! Les lutins sont impressionnés (et un peu jaloux).",
    "Exact ! On a bien cru que tu avais triché, mais non.",
    "Bien joué ! Le village applaudit et les rennes aussi.",
    "Gagné ! Raconte-le à ta famille, ils ne te croiront pas.",
    "Eurêka ! Archimède aurait sorti la serviette de bain.",
    "Bonne réponse. Les lutins ont écrit « il l'a fait » sur le grand tableau.",
    "Oui ! Même le Père Noël a levé un sourcil, c'est dire.",
    "Parfait. Tu peux te la raconter dix minutes, on te les accorde.",
    "Validé ! Il y a eu un petit suspense chez les lutins, mais tu l'as dissipé.",
    "Excellent ! Ton cerveau mérite une bûche.",
    "Bingo ! On cherchait quelqu'un pour ça, et c'est toi.",
    "{nom} a frappé : les lutins en sont encore sous le choc.",
    "Réponse juste ! Un verrou de moins, un sourire de plus.",
    "Brillant ! Il va falloir rallonger les guirlandes pour fêter ça.",
)


def _pick(phrases, nom):
    # `replace` plutôt que `format` : un nom d'utilisateur ou une citation avec des accolades ne casserait rien.
    return random.choice(phrases).replace("{nom}", nom)


def echec(nom=""):
    """Une phrase pour une mauvaise réponse."""
    return _pick(ECHECS, nom or "Allumeur")


def reussite(nom=""):
    """Une phrase pour une bonne réponse."""
    return _pick(REUSSITES, nom or "Allumeur")
