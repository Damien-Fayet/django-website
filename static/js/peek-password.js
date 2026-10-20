// Bouton « Afficher / Masquer » des champs mot de passe. Sans JavaScript, le bouton reste caché (attribut hidden).
document.querySelectorAll("button[data-peek]").forEach(function (button) {
  var input = document.getElementById(button.dataset.peek);
  if (!input) return;
  button.hidden = false;
  button.addEventListener("click", function () {
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    button.textContent = show ? "Masquer" : "Afficher";
    button.setAttribute("aria-pressed", String(show));
  });
});
