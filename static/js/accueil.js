// Accueil public : neige, étincelles (diptyque) et apparitions au défilement. Le compte à rebours est dans decompte.js.
// Rien ne bouge si le navigateur demande moins d'animations (prefers-reduced-motion) ; le compte à rebours, lui, tourne
// toujours. Sans JavaScript, la page reste complète (le compte à rebours est simplement absent).
(function () {
  "use strict";

  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Étincelles au clic sur le diptyque (la gerbe elle-même est dans etincelles.js) ---------------
  if (!calme) {
    document.addEventListener("pointerdown", function (event) {
      if (!event.target.closest(".diptyque__cadre")) return;
      if (window.aventEtincelles) window.aventEtincelles(event.clientX, event.clientY);
      var cadre = event.target.closest(".diptyque__cadre");
      if (cadre) {  // la chaîne se secoue aussi au toucher
        cadre.classList.remove("est-secoue");
        void cadre.offsetWidth;
        cadre.classList.add("est-secoue");
      }
    });
  }

  // ---- Neige ---------------------------------------------------------------------------------------------------------
  var bouton = document.getElementById("neige-toggle");
  var toile = null;
  var actif = false;
  var relancer = null;  // reprend l'animation après une pause (posé par demarrerNeige)

  var lireChoix = function () {
    try { return window.localStorage.getItem("avent-neige") !== "non"; } catch (e) { return true; }
  };
  var ecrireChoix = function (oui) {
    try { window.localStorage.setItem("avent-neige", oui ? "oui" : "non"); } catch (e) { /* mode privé : tant pis */ }
  };

  var demarrerNeige = function () {
    toile = document.createElement("canvas");
    toile.className = "neige";
    toile.setAttribute("aria-hidden", "true");
    document.body.appendChild(toile);
    var ctx = toile.getContext("2d");
    var flocons = [];
    var largeur = 0, hauteur = 0;

    var dimensionner = function () {
      var ratio = Math.min(window.devicePixelRatio || 1, 2);
      largeur = window.innerWidth;
      hauteur = window.innerHeight;
      toile.width = largeur * ratio;
      toile.height = hauteur * ratio;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      var voulus = Math.max(18, Math.min(55, Math.round(largeur / 26)));
      while (flocons.length < voulus) flocons.push(nouveau(true));
      flocons.length = voulus;
    };

    var nouveau = function (partout) {
      var taille = 1 + Math.random() * 2.4;
      return {
        x: Math.random() * (largeur || window.innerWidth),
        y: partout ? Math.random() * (hauteur || window.innerHeight) : -6,
        r: taille, vy: 0.25 + taille * 0.22, phase: Math.random() * 6.28, amp: 8 + Math.random() * 18
      };
    };

    var dernier = 0;
    var image = 0;  // identifiant de la prochaine image demandée : évite deux boucles si on coupe puis rallume vite
    var boucle = function (t) {
      if (!actif) return;
      var dt = Math.min(50, t - dernier || 16) / 16;
      dernier = t;
      ctx.clearRect(0, 0, largeur, hauteur);
      for (var i = 0; i < flocons.length; i++) {
        var f = flocons[i];
        f.y += f.vy * dt;
        f.phase += 0.012 * dt;
        var x = f.x + Math.sin(f.phase) * f.amp;
        if (f.y > hauteur + 6) { flocons[i] = nouveau(false); continue; }
        // Bleu glacé : visible sur le fond clair de la page comme sur le ciel du compte à rebours
        ctx.fillStyle = "rgba(150, 185, 228, " + (0.45 + f.r * 0.16) + ")";
        ctx.beginPath();
        ctx.arc(x, f.y, f.r, 0, 6.2832);
        ctx.fill();
      }
      image = window.requestAnimationFrame(boucle);
    };

    relancer = function () { window.cancelAnimationFrame(image); dernier = 0; image = window.requestAnimationFrame(boucle); };
    dimensionner();
    window.addEventListener("resize", dimensionner);
    relancer();
  };

  var reglerNeige = function (oui) {
    actif = oui;
    if (oui) {
      if (!toile) demarrerNeige();
      else { toile.hidden = false; relancer(); }
    } else if (toile) {
      toile.hidden = true;
    }
    if (bouton) {
      bouton.setAttribute("aria-pressed", String(oui));
      bouton.textContent = oui ? "Neige : oui" : "Neige : non";
    }
  };

  if (!calme) {
    if (bouton) {
      bouton.hidden = false;
      bouton.addEventListener("click", function () { var oui = !actif; ecrireChoix(oui); reglerNeige(oui); });
    }
    reglerNeige(lireChoix());
  }

  // ---- Apparition au défilement --------------------------------------------------------------------------------------
  // Seuls les blocs encore hors écran sont masqués, puis révélés dès que leur haut entre dans l'écran. Un bloc déjà
  // dépassé (saut vers une ancre, défilement rapide, page rechargée plus bas) est révélé aussi : rien ne reste invisible.
  if (!calme) {
    var attente = [];
    document.querySelectorAll(".section h2, .steps > *, .closing").forEach(function (el) {
      if (el.getBoundingClientRect().top < window.innerHeight) return;
      el.classList.add("apparait");
      attente.push(el);
    });
    var verifier = function () {
      attente = attente.filter(function (el) {
        if (el.getBoundingClientRect().top > window.innerHeight - 40) return true;
        el.classList.add("est-la");
        return false;
      });
      if (!attente.length) window.removeEventListener("scroll", planifier);
    };
    var planifie = false;
    var planifier = function () {
      if (planifie) return;
      planifie = true;
      window.requestAnimationFrame(function () { planifie = false; verifier(); });
    };
    if (attente.length) window.addEventListener("scroll", planifier, { passive: true });
  }
})();
