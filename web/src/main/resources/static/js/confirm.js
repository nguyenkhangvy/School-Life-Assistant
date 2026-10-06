// A form with data-confirm="Remove Lan from your friends?" asks before it is sent. The question is read as plain
// text, so a name in it can never run as code (an onsubmit="confirm('…')" with a name inside could).
document.addEventListener("submit", function (event) {
  var question = event.target.getAttribute("data-confirm");
  if (question && !window.confirm(question)) {
    event.preventDefault();
  }
});
