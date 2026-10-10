(function () {
  var page = document.querySelector('.page');
  if (!page) return;
  var url = page.getAttribute('data-play');
  var id = page.getAttribute('data-visit');
  var delay = parseInt(page.getAttribute('data-delay'), 10) || 1800;
  var started = false;
  var timer;

  function mark() {
    if (!id) return;
    try {
      var body = new Blob([JSON.stringify({ id: id })], { type: 'application/json' });
      if (!(navigator.sendBeacon && navigator.sendBeacon('/api/redirected', body))) {
        fetch('/api/redirected', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id }),
          keepalive: true
        });
      }
    } catch (e) {}
  }

  function go() {
    if (started) return;
    started = true;
    mark();
    setTimeout(function () { window.location.href = url; }, 150);
  }

  timer = setTimeout(go, delay);

  // Tapping the Play Store button counts too (the browser does the navigation).
  var btn = document.querySelector('a.play');
  if (btn) {
    btn.addEventListener('click', function () {
      if (started) return;
      started = true;
      clearTimeout(timer);
      mark();
    });
  }

  // If the user comes back with the back button, do not bounce them again.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) {
      started = true;
      clearTimeout(timer);
      var note = document.querySelector('.redirect span');
      if (note) note.textContent = 'Tap the button to open Google Play';
    }
  });
})();
