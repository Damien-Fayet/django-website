// Accueil public : compte à rebours, neige, étincelles et apparitions au défilement.
// Rien ne bouge si le navigateur demande moins d'animations (prefers-reduced-motion) ; le compte à rebours, lui, tourne
// toujours. Sans JavaScript, la page reste complète (le compte à rebours est simplement absent).
(function () {
  "use strict";

  var calme = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- Compte à rebours ---------------------------------------------------------------------------------------
  // L'heure d'ouverture porte son décalage (« +01:00 ») : le décompte ne dépend pas du fuseau du navigateur.
  var boite = document.getElementById("countdown");
  if (boite) {
    var ouverture = Date.parse(boite.dataset.openAt);
    var compteur = boite.querySelector(".countdown__body");
    var invitation = boite.querySelector(".countdown__open");
    var nombres = ["days", "hours", "minutes", "seconds"].map(function (k) { return document.getElementById(k + "-welcome"); });
    var phrase = document.getElementById("countdown-quip");
    var precedent = [];
    var palier = null;
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
      if (phrase && etape !== palier) { palier = etape; phrase.textContent = etape[1]; }
    };

    maj();
    if (!fini) minuteur = setInterval(maj, 1000);
  }

  // ---- Étincelles au clic (compte à rebours et diptyque) --------------------------------------------------------
  var COULEURS = ["#d9a441", "#ffe6a8", "#ff6b78", "#52c79b", "#ffffff"];

  var etincelles = function (x, y) {
    for (var i = 0; i < 12; i++) {
      var e = document.createElement("span");
      e.className = "etincelle";
      e.style.left = x + "px";
      e.style.top = y + "px";
      e.style.background = COULEURS[i % COULEURS.length];
      document.body.appendChild(e);
      var angle = (Math.PI * 2 * i) / 12 + Math.random() * 0.5;
      var distance = 40 + Math.random() * 60;
      var anim = e.animate([
        { transform: "translate(0, 0) scale(.4) rotate(0deg)", opacity: 1 },
        { transform: "translate(" + Math.cos(angle) * distance + "px, " + (Math.sin(angle) * distance + 24) + "px) scale(1.1) rotate(" + (Math.random() * 180) + "deg)", opacity: 0 }
      ], { duration: 700 + Math.random() * 300, easing: "cubic-bezier(.2,.7,.3,1)" });
      anim.onfinish = (function (el) { return function () { el.remove(); }; })(e);
    }
  };

  if (!calme && document.body.animate) {
    document.addEventListener("pointerdown", function (event) {
      if (!event.target.closest(".countdown, .diptyque__cadre")) return;
      etincelles(event.clientX, event.clientY);
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
