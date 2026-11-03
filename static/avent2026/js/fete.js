// Touches de fête du jeu : chiffres qui montent, réactions à une réponse ou à un indice.
// Les chiffres sont déjà dans la page : sans JavaScript, ou si le navigateur demande moins d'animations, rien ne change.
(function () {
  "use strict";
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // ---- Compteurs de l'accueil : de 0 à la valeur, une fois au chargement --------------------------------------
  document.querySelectorAll("[data-compte]").forEach(function (el) {
    var cible = parseInt(el.dataset.compte, 10);
    if (!(cible > 0)) return;
    var duree = 800 + Math.min(cible, 60) * 8;
    var debut = null;
    el.textContent = "0";
    var pas = function (t) {
      if (debut === null) debut = t;
      var k = Math.min(1, (t - debut) / duree);
      el.textContent = String(Math.round(cible * (1 - Math.pow(1 - k, 3))));
      if (k < 1) window.requestAnimationFrame(pas); else el.textContent = String(cible);
    };
    window.requestAnimationFrame(pas);
  });

  // ---- Page d'un puzzle : le bloc réagit au message qui vient d'arriver ---------------------------------------
  var bloc = document.querySelector("#resultat .aside-block");
  if (!bloc) return;
  var message = function (type) { return document.querySelector("#resultat .notice--" + type); };

  if (message("error")) bloc.classList.add("secoue");  // mauvaise réponse : le bloc se secoue

  if (message("info")) {  // indice révélé : le dernier apparaît avec un éclat
    var indices = document.querySelectorAll(".hint");
    if (indices.length) indices[indices.length - 1].classList.add("est-nouveau");
  }

  if (message("success")) {  // bonne réponse : gerbes d'étincelles au-dessus du bloc
    bloc.classList.add("bravo");
    window.addEventListener("load", function () {
      // Après le saut vers #resultat : on lit la position une fois la page calée
      window.setTimeout(function () {
        var r = bloc.getBoundingClientRect();
        var y = Math.max(80, Math.min(window.innerHeight - 80, r.top + 70));
        [[0.5, 0], [0.2, 220], [0.8, 420]].forEach(function (p) {
          window.setTimeout(function () { if (window.aventEtincelles) window.aventEtincelles(r.left + r.width * p[0], y, 16); }, p[1]);
        });
      }, 200);
    });
  }
})();
