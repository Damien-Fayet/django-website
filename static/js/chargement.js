// Signe de chargement : dès qu'on clique sur un lien ou qu'on envoie un formulaire, une barre apparaît en haut
// de l'écran, le bouton validé affiche une roue et, si la réponse tarde, une pastille « Chargement… » s'affiche.
// Un second envoi du même formulaire est ignoré tant que le premier n'a pas abouti.
// Sans JavaScript, le site fonctionne comme avant. Styles : static/css/chargement.css.
// Un lien ou un formulaire peut s'exclure avec data-sans-chargement ; data-chargement="Texte…" change le message.
(function () {
  "use strict";

  var DELAI_PASTILLE = 600;   // ms avant d'afficher la pastille
  var DELAI_SECURITE = 30000; // ms : si la page n'a pas changé (téléchargement, navigation annulée), on rend la main

  var racine = document.documentElement;
  var pastille = null;
  var texte = null;
  var minuteurPastille = null;
  var minuteurSecurite = null;
  var formulaire = null;
  var bouton = null;

  function creerPastille() {
    pastille = document.createElement("div");
    pastille.className = "chargement";
    pastille.setAttribute("role", "status");
    pastille.setAttribute("aria-live", "polite");
    var roue = document.createElement("span");
    roue.className = "chargement__roue";
    roue.setAttribute("aria-hidden", "true");
    texte = document.createElement("span");
    pastille.appendChild(roue);
    pastille.appendChild(texte);
    document.body.appendChild(pastille);
  }

  function demarrer(message, form, submitter) {
    racine.classList.add("charge");
    formulaire = form || null;
    bouton = submitter || null;
    if (formulaire) formulaire.setAttribute("aria-busy", "true");
    if (bouton) bouton.classList.add("is-loading");
    clearTimeout(minuteurPastille);
    clearTimeout(minuteurSecurite);
    minuteurPastille = setTimeout(function () {
      if (!pastille) creerPastille();
      texte.textContent = message;
      // La région « status » n'annonce que les changements : le texte est posé avant d'afficher la pastille.
      pastille.classList.add("visible");
    }, DELAI_PASTILLE);
    minuteurSecurite = setTimeout(arreter, DELAI_SECURITE);
  }

  function arreter() {
    clearTimeout(minuteurPastille);
    clearTimeout(minuteurSecurite);
    racine.classList.remove("charge");
    if (pastille) pastille.classList.remove("visible");
    if (formulaire) formulaire.removeAttribute("aria-busy");
    if (bouton) bouton.classList.remove("is-loading");
    formulaire = null;
    bouton = null;
  }

  // Retour arrière : le navigateur peut réafficher la page telle qu'elle était, chargement compris.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) arreter();
  });

  // Liens. Écouteur au niveau du document (phase de bouillonnement) : les autres scripts ont déjà pu annuler le clic.
  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var lien = event.target.closest ? event.target.closest("a[href]") : null;
    if (!lien || lien.hasAttribute("download") || lien.hasAttribute("data-sans-chargement")) return;
    if (lien.target && lien.target !== "_self") return;
    var url;
    try { url = new URL(lien.href, window.location.href); } catch (e) { return; }
    if (url.protocol !== "http:" && url.protocol !== "https:") return;
    // Simple ancre sur la même page : pas de chargement.
    if (url.origin === window.location.origin && url.pathname === window.location.pathname &&
        url.search === window.location.search) return;
    demarrer(lien.dataset.chargement || "Chargement…");
  });

  // Formulaires.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || !form || form.tagName !== "FORM") return;
    var envoyeur = event.submitter || form.querySelector('button[type="submit"], button:not([type]), input[type="submit"]');
    var cible = (envoyeur && envoyeur.formTarget) || form.target;
    if (cible && cible !== "_self") return;
    if (form.hasAttribute("data-sans-chargement")) return;
    if (form.getAttribute("aria-busy") === "true") {
      // Double clic ou double « Entrée » : le premier envoi est déjà parti.
      event.preventDefault();
      return;
    }
    demarrer(form.dataset.chargement || "Envoi en cours…", form,
             envoyeur && envoyeur.tagName === "BUTTON" ? envoyeur : null);
  });
})();
