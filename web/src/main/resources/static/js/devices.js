// Devices: Copy puts the new device key (shown once) on the clipboard. A file of its own: the site's
// Content-Security-Policy refuses inline scripts (security hardening spec, 5).
(function () {
  var button = document.getElementById("copy-key");
  if (!button) {
    return;
  }
  button.addEventListener("click", function () {
    var key = document.getElementById("new-key").textContent;
    navigator.clipboard.writeText(key).then(function () {
      button.textContent = "Copied";
    });
  });
})();
