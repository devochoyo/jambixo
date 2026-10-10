(function () {
  // ----- bar chart -----
  var chart = document.getElementById('chart');
  if (chart) {
    var series = [];
    try { series = JSON.parse(chart.getAttribute('data-series')); } catch (e) {}
    var max = 1;
    series.forEach(function (s) { if (s.visits > max) max = s.visits; });
    var every = series.length > 14 ? Math.ceil(series.length / 7) : 1;
    var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    series.forEach(function (s, i) {
      var col = document.createElement('div');
      col.className = 'col' + (s.visits === 0 ? ' zero' : '');
      col.title = s.day + ': ' + s.visits + ' visits, ' + s.unique + ' unique';

      if (s.visits > 0 && series.length <= 14) {
        var n = document.createElement('em');
        n.textContent = s.visits;
        col.appendChild(n);
      }
      var bar = document.createElement('i');
      bar.style.height = Math.max(2, Math.round((s.visits / max) * 100)) + '%';
      col.appendChild(bar);

      var lab = document.createElement('small');
      if (i % every === 0 || i === series.length - 1) {
        var p = s.day.split('-');
        lab.textContent = parseInt(p[2], 10) + ' ' + months[parseInt(p[1], 10) - 1];
      }
      col.appendChild(lab);
      chart.appendChild(col);
    });
  }

  // ----- copy link -----
  var copy = document.getElementById('copy');
  var link = document.getElementById('link');
  if (copy && link) {
    copy.addEventListener('click', function () {
      function done() {
        copy.textContent = 'Copied!';
        setTimeout(function () { copy.textContent = 'Copy link'; }, 1600);
      }
      link.select();
      link.setSelectionRange(0, 999);
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(link.value).then(done, function () { document.execCommand('copy'); done(); });
      } else {
        document.execCommand('copy');
        done();
      }
    });
  }

  // ----- refresh numbers every 2 minutes -----
  setTimeout(function () { window.location.reload(); }, 120000);
})();
