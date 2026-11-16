// Mauvaise réponse : la phrase drôle s'ouvre dans une fenêtre, à la place de la bande rouge.
// Sans JavaScript (ou sans <dialog>), la bande rouge reste affichée avec la même phrase.
(function () {
  "use strict";
  var fenetre = document.querySelector("dialog[data-oups]");
  if (!fenetre || typeof fenetre.showModal !== "function") return;
  var bande = fenetre.closest(".notice");

  fenetre.addEventListener("close", function () {
    // Retour au champ de réponse, mais seulement avec une souris : sur mobile, le clavier cacherait l'énoncé.
    var champ = document.getElementById("answer");
    if (champ && window.matchMedia("(hover: hover) and (pointer: fine)").matches) champ.focus({preventScroll: true});
  });
  // Un clic en dehors de la fenêtre (sur le fond assombri) la ferme.
  fenetre.addEventListener("click", function (event) {
    if (event.target === fenetre) fenetre.close();
  });

  try {
    // La fenêtre sort de la bande rouge : un élément dans un parent en display:none ne s'affiche pas, même en modale.
    document.body.appendChild(fenetre);
    fenetre.showModal();
    if (bande) bande.classList.add("a-popup");
  } catch (e) {
    // La fenêtre n'a pas pu s'ouvrir : la bande rouge reste visible.
    if (bande) bande.appendChild(fenetre);
  }
})();
