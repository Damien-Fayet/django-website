// Gerbe d'étincelles (petites étoiles) : window.aventEtincelles(x, y[, nombre]) avec x, y en pixels d'écran.
// Ne fait rien si le navigateur demande moins d'animations ou ne sait pas animer.
(function () {
  "use strict";
  var COULEURS = ["#d9a441", "#ffe6a8", "#ff6b78", "#52c79b", "#ffffff"];
  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  window.aventEtincelles = function (x, y, nombre) {
    if (calme || !document.body.animate) return;
    nombre = nombre || 12;
    for (var i = 0; i < nombre; i++) {
      var e = document.createElement("span");
      e.className = "etincelle";
      e.style.left = x + "px";
      e.style.top = y + "px";
      e.style.background = COULEURS[i % COULEURS.length];
      document.body.appendChild(e);
      var angle = (Math.PI * 2 * i) / nombre + Math.random() * 0.5;
      var distance = 40 + Math.random() * 60;
      var anim = e.animate([
        { transform: "translate(0, 0) scale(.4) rotate(0deg)", opacity: 1 },
        { transform: "translate(" + Math.cos(angle) * distance + "px, " + (Math.sin(angle) * distance + 24) + "px) scale(1.1) rotate(" + (Math.random() * 180) + "deg)", opacity: 0 }
      ], { duration: 700 + Math.random() * 300, easing: "cubic-bezier(.2,.7,.3,1)" });
      anim.onfinish = (function (el) { return function () { el.remove(); }; })(e);
    }
  };
})();
