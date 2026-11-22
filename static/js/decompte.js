// Compte à rebours vers l'ouverture du calendrier (accueil public et accueil du jeu).
// Le bloc `.countdown[data-open-at]` porte l'heure d'ouverture avec son décalage (« +01:00 ») : le décompte ne dépend pas
// du fuseau du navigateur. Ses chiffres sont les `[data-unit="days|hours|minutes|seconds"]`.
// Rien ne bouge si le navigateur demande moins d'animations (prefers-reduced-motion) ; le décompte, lui, tourne toujours.
(function () {
  "use strict";

  var boite = document.querySelector(".countdown[data-open-at]");
  if (!boite) return;

  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ouverture = Date.parse(boite.dataset.openAt);
  var compteur = boite.querySelector(".countdown__body");
  var invitation = boite.querySelector(".countdown__open");
  var nombres = ["days", "hours", "minutes", "seconds"].map(function (k) { return boite.querySelector('[data-unit="' + k + '"]'); });
  var phrase = boite.querySelector(".countdown__quip");
  var precedent = [];
  var phraseCourante = null;
  var minuteur = null;
  var fini = false;

  // Une phrase par étape de l'attente, de la plus lointaine à la plus proche.
  var PHRASES = [
    [14 * 864e5, "Les lutins vérifient les guirlandes une par une."],
    [7 * 864e5, "Le village retient son souffle sous la neige."],
    [2 * 864e5, "Les ampoules chauffent. Prépare tes meilleures devinettes."],
    [864e5, "Demain, tout s'allume !"],
    [36e5, "Cette nuit, le village se rallume."],
    [0, "Les lutins sont en position. Presque…"]
  ];

  var pad = function (n) { return String(n).padStart(2, "0"); };

  var afficherOuvert = function () {
    boite.hidden = false;
    compteur.hidden = true;
    invitation.hidden = false;
    fini = true;
    if (minuteur) clearInterval(minuteur);
  };

  var maj = function () {
    var reste = ouverture - Date.now();
    if (isNaN(ouverture) || reste <= 0) { afficherOuvert(); return; }
    boite.hidden = false;
    var valeurs = [
      Math.floor(reste / 864e5), Math.floor(reste % 864e5 / 36e5),
      Math.floor(reste % 36e5 / 6e4), Math.floor(reste % 6e4 / 1e3)
    ];
    nombres.forEach(function (el, i) {
      if (!el) return;
      var texte = pad(valeurs[i]);
      if (el.textContent === texte) return;
      el.textContent = texte;
      if (precedent.length && !calme) {  // pas d'animation au premier affichage
        el.classList.remove("est-change");
        void el.offsetWidth;  // relance l'animation
        el.classList.add("est-change");
      }
    });
    precedent = valeurs;
    var etape = PHRASES.find(function (p) { return reste > p[0]; }) || PHRASES[PHRASES.length - 1];
    if (phrase && etape !== phraseCourante) { phraseCourante = etape; phrase.textContent = etape[1]; }
  };

  maj();
  if (!fini) minuteur = setInterval(maj, 1000);

  // Étincelles au clic sur le panneau (la gerbe elle-même est dans etincelles.js, sans effet si mouvements réduits).
  if (!calme) {
    boite.addEventListener("pointerdown", function (event) {
      if (window.aventEtincelles) window.aventEtincelles(event.clientX, event.clientY);
    });
  }
})();
