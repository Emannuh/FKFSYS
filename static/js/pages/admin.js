/* Admin area page script: FKF charts, deadline countdowns, Referees Manager live tables.
   Loaded with defer from {% block extra_js %}. Exposes no globals. */
(function () {
  'use strict';

  // Canvas cannot read CSS variables, so the FKF chart palette lives here.
  var FKF = {
    red: '#c8102e', green: '#00843d', black: '#0a0a0b',
    graphite: '#6e6e73', grey: '#c5c7cc', amber: '#f2b01e'
  };
  var charts = {};

  function isDark() {
    var main = document.getElementById('main-content');
    var el = main && main.getAttribute('data-bs-theme') ? main : document.documentElement;
    return el.getAttribute('data-bs-theme') === 'dark';
  }

  function colour(name) {
    // Black disappears on the dark surface: swap it for near-white.
    if (name === 'black' && isDark()) return '#e9ebee';
    if (name === 'grey' && isDark()) return '#38383d';
    return FKF[name] || name;
  }

  function themeInk() {
    return {
      text: isDark() ? '#a4acb5' : '#59616a',
      grid: isDark() ? 'rgba(255,255,255,0.08)' : 'rgba(10,10,11,0.08)'
    };
  }

  function parseJSON(value, fallback) {
    try { return JSON.parse(value); } catch (e) { return fallback; }
  }

  function buildConfig(canvas) {
    var type = canvas.getAttribute('data-chart');
    var labels = parseJSON(canvas.getAttribute('data-labels'), []);
    var values = parseJSON(canvas.getAttribute('data-values'), []);
    var total = parseInt(canvas.getAttribute('data-total') || '', 10);
    if (!Number.isNaN(total) && values.length < labels.length) {
      // e.g. squad places: "remaining" is total minus what is used.
      var used = values.reduce(function (a, b) { return a + b; }, 0);
      values.push(Math.max(0, total - used));
    }
    var names = (canvas.getAttribute('data-colors') || 'red,green,black,graphite,grey').split(',');
    var colours = labels.map(function (_, i) { return colour(names[i % names.length].trim()); });
    var ink = themeInk();
    var horizontal = type === 'hbar';
    var openClosed = canvas.getAttribute('data-format') === 'open-closed';

    if (type === 'doughnut') {
      var datasets = [{ data: values, backgroundColor: colours, borderWidth: 0, hoverOffset: 6 }];
      var empty = values.reduce(function (a, b) { return a + (Number(b) || 0); }, 0) === 0;
      if (empty) {
        // All zero: draw a neutral track ring so the panel does not look broken.
        datasets.push({ data: [1], backgroundColor: [colour('grey')], borderWidth: 0, hoverOffset: 0 });
      }
      return {
        type: 'doughnut',
        data: { labels: labels, datasets: datasets },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: '68%',
          plugins: {
            legend: { position: 'bottom', labels: { color: ink.text, boxWidth: 10, boxHeight: 10, padding: 14, font: { size: 11 } } },
            tooltip: { filter: function (item) { return item.datasetIndex === 0; } }
          }
        }
      };
    }
    var valueAxis = {
      beginAtZero: true, grid: { color: ink.grid }, border: { display: false },
      ticks: { color: ink.text, precision: 0 }
    };
    if (openClosed) {
      valueAxis.max = 1;
      valueAxis.ticks = { color: ink.text, stepSize: 1, callback: function (v) { return v ? 'Open' : 'Closed'; } };
    }
    var catAxis = { grid: { display: false }, border: { display: false }, ticks: { color: ink.text } };
    return {
      type: 'bar',
      data: { labels: labels, datasets: [{ label: canvas.getAttribute('aria-label') || 'Count', data: values, backgroundColor: colours, borderRadius: 6, borderSkipped: false, maxBarThickness: 44 }] },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? 'y' : 'x',
        plugins: {
          legend: { display: false },
          tooltip: openClosed ? { callbacks: { label: function (c) { return c.raw ? 'Open' : 'Closed'; } } } : {}
        },
        scales: horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis }
      }
    };
  }

  function renderChart(canvas) {
    if (typeof window.Chart === 'undefined') return;
    if (charts[canvas.id]) {
      // Keep live values pushed by JS when re-rendering for a theme change.
      canvas.setAttribute('data-values', JSON.stringify(charts[canvas.id].data.datasets[0].data));
      charts[canvas.id].destroy();
    }
    charts[canvas.id] = new window.Chart(canvas, buildConfig(canvas));
  }

  function renderAllCharts() {
    document.querySelectorAll('canvas[data-chart]').forEach(renderChart);
  }

  function setChartValue(id, index, value) {
    var chart = charts[id];
    if (!chart) return;
    chart.data.datasets[0].data[index] = value;
    var sum = chart.data.datasets[0].data.reduce(function (a, b) { return a + (Number(b) || 0); }, 0);
    if (sum > 0 && chart.data.datasets.length > 1) chart.data.datasets.length = 1;  // drop the empty track
    chart.update();
  }

  // Re-render charts when the theme toggles (html or main data-bs-theme changes).
  function watchTheme() {
    var targets = [document.documentElement, document.getElementById('main-content')].filter(Boolean);
    var obs = new MutationObserver(function () { renderAllCharts(); });
    targets.forEach(function (t) { obs.observe(t, { attributes: true, attributeFilter: ['data-bs-theme'] }); });
  }

  // --- Deadline countdowns (partials/_reg_window_card.html) ---------------
  function startCountdowns() {
    document.querySelectorAll('.countdown-timer[data-deadline]').forEach(function (el) {
      var target = Date.parse(el.getAttribute('data-deadline'));
      if (Number.isNaN(target)) return;
      function update() {
        var diff = target - Date.now();
        if (diff <= 0) { el.textContent = 'Deadline reached. Refresh the page.'; return false; }
        var d = Math.floor(diff / 86400000);
        var h = Math.floor((diff % 86400000) / 3600000);
        var m = Math.floor((diff % 3600000) / 60000);
        var s = Math.floor((diff % 60000) / 1000);
        el.textContent = d + 'd ' + h + 'h ' + m + 'm ' + s + 's remaining';
        return true;
      }
      if (update()) {
        var timer = setInterval(function () { if (!update()) clearInterval(timer); }, 1000);
      }
    });
  }

  // --- Referees Manager dashboard ------------------------------------------
  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function urlFor(template, id) {
    // Templates are {% url ... 0 %}; swap the /0/ placeholder segment for the real id.
    return template.replace('/0/', '/' + encodeURIComponent(id) + '/');
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function emptyRow(cols, text, icon) {
    return '<tr><td colspan="' + cols + '" class="table-loading">' +
      (icon ? '<i class="fas fa-' + icon + ' me-2" aria-hidden="true"></i>' : '') + esc(text) + '</td></tr>';
  }

  function getJSON(url) {
    return fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  function daysBadge(days) {
    if (days === undefined || days === null) return '<span class="text-body-secondary">&mdash;</span>';
    var tone = days <= 1 ? 'accent' : (days <= 3 ? 'warning' : 'neutral');
    return '<span class="badge status-badge status-' + tone + '">' + esc(days) + (days === 1 ? ' day' : ' days') + '</span>';
  }

  function initRefManager() {
    var root = document.getElementById('refManager');
    if (!root) return;
    var ds = root.dataset;
    var stats = { pending: parseInt(ds.pendingApprovals || '0', 10) || 0, needs: 0, confirm: 0, available: 0 };

    function pushStats() {
      setChartValue('refOverviewChart', 0, stats.pending);
      setChartValue('refOverviewChart', 1, stats.needs);
      setChartValue('refOverviewChart', 2, stats.confirm);
      setChartValue('refOverviewChart', 3, stats.available);
    }

    getJSON(ds.urgentUrl).then(function (data) {
      var matches = data.matches || [];
      stats.needs = matches.length;
      setText('needsOfficialsCount', matches.length);
      setText('urgentMatchesCount', matches.length);
      var tbody = document.getElementById('urgentMatchesBody');
      if (!matches.length) {
        tbody.innerHTML = emptyRow(6, 'All matches in the appointment window have officials.', 'circle-check');
      } else {
        tbody.innerHTML = matches.map(function (m) {
          return '<tr>' +
            '<td><span class="fw-semibold">' + esc(m.match_date) + '</span><span class="cell-sub">' + esc(m.kickoff_time || 'TBD') + '</span></td>' +
            '<td class="match-cell">' + esc(m.home_team) + '<span class="vs">vs</span>' + esc(m.away_team) + '</td>' +
            '<td class="hide-sm">' + esc(m.zone || '—') + '</td>' +
            '<td>' + daysBadge(m.days_left) + '</td>' +
            '<td class="hide-sm"><span class="badge status-badge status-warning">' + esc(m.status || 'Needs Officials') + '</span></td>' +
            '<td class="actions"><a href="' + esc(urlFor(ds.appointUrl, m.id)) + '" class="btn btn-sm btn-primary"><i class="fas fa-user-plus me-1" aria-hidden="true"></i>Appoint</a></td>' +
            '</tr>';
        }).join('');
      }
      pushStats();
    }).catch(function () {
      document.getElementById('urgentMatchesBody').innerHTML = emptyRow(6, 'Could not load data.');
    });

    getJSON(ds.appointedUrl).then(function (data) {
      var matches = data.matches || [];
      stats.confirm = matches.filter(function (m) { return m.status_display !== 'Confirmed'; }).length;
      setText('appointedMatchesCount', matches.length);
      setText('pendingConfirmationCount', stats.confirm);
      var tbody = document.getElementById('appointedMatchesBody');
      if (!matches.length) {
        tbody.innerHTML = emptyRow(5, 'No appointed matches in the appointment window.');
      } else {
        tbody.innerHTML = matches.map(function (m) {
          var confirmed = m.status_display === 'Confirmed';
          return '<tr>' +
            '<td><span class="fw-semibold">' + esc(m.match_date) + '</span><span class="cell-sub">' + esc(m.kickoff_time || 'TBD') + '</span></td>' +
            '<td class="match-cell">' + esc(m.home_team) + '<span class="vs">vs</span>' + esc(m.away_team) + '</td>' +
            '<td class="hide-sm">' + (m.main_referee ? esc(m.main_referee) : '<span class="text-body-secondary">&mdash;</span>') + '</td>' +
            '<td><span class="badge status-badge status-' + (confirmed ? 'success' : 'warning') + '">' + esc(m.status_display || 'Appointed') + '</span></td>' +
            '<td class="actions">' +
              '<a href="' + esc(urlFor(ds.matchUrl, m.id)) + '" class="btn btn-sm btn-outline-secondary"><i class="fas fa-eye me-1" aria-hidden="true"></i>View</a>' +
              '<a href="' + esc(urlFor(ds.appointUrl, m.id)) + '" class="btn btn-sm btn-outline-primary"><i class="fas fa-pen me-1" aria-hidden="true"></i>Edit</a>' +
            '</td></tr>';
        }).join('');
      }
      pushStats();
    }).catch(function () {
      document.getElementById('appointedMatchesBody').innerHTML = emptyRow(5, 'Could not load data.');
    });

    getJSON(ds.availableUrl).then(function (data) {
      var refs = data.referees || [];
      stats.available = refs.length;
      setText('availableRefereesCount', refs.length);
      setText('availableRefCountBadge', refs.length);
      var list = document.getElementById('availableRefBody');
      if (!refs.length) {
        list.innerHTML = '<li class="table-loading">No available referees today.</li>';
      } else {
        list.innerHTML = refs.map(function (r) {
          return '<li><span class="team-crest" aria-hidden="true">' + esc(r.initials) + '</span>' +
            '<span class="who"><strong>' + esc(r.full_name) + '</strong><span>' + esc(r.grade || 'Grade not set') +
            (r.specialization ? ' &middot; ' + esc(r.specialization) : '') + '</span></span></li>';
        }).join('');
      }
      pushStats();
    }).catch(function () {
      document.getElementById('availableRefBody').innerHTML = '<li class="table-loading">Could not load data.</li>';
    });
  }

  // --- Small behaviours that replace inline handlers ------------------------
  // <a|button data-confirm="Message">: ask before following / submitting.
  // <select data-autosubmit>: submit the parent form on change.
  function wireBehaviours() {
    document.addEventListener('click', function (e) {
      var el = e.target.closest('[data-confirm]');
      if (el && !el.matches('form') && !window.confirm(el.getAttribute('data-confirm'))) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    });
    document.addEventListener('submit', function (e) {
      var form = e.target;
      if (form.matches('form[data-confirm]') && !window.confirm(form.getAttribute('data-confirm'))) e.preventDefault();
    });
    document.addEventListener('change', function (e) {
      var el = e.target;
      if (el.matches('[data-autosubmit]') && el.form) el.form.submit();
    });
  }

  // --- Match create/edit form (admin_dashboard/create_match.html, edit_match.html) ---
  function initMatchForm() {
    var form = document.querySelector('form[data-match-form]');
    if (!form) return;
    var zone = document.getElementById('zone');
    var home = document.getElementById('home_team');
    var away = document.getElementById('away_team');
    var status = document.getElementById('status');
    var scores = document.getElementById('scoresSection');

    function filter(select, zoneId) {
      if (!select) return;
      for (var i = 1; i < select.options.length; i++) {
        var opt = select.options[i];
        var show = !zoneId || opt.getAttribute('data-zone') === zoneId;
        opt.hidden = !show;
      }
      var cur = select.options[select.selectedIndex];
      if (select.selectedIndex > 0 && cur.hidden) select.selectedIndex = 0;
    }
    if (zone) zone.addEventListener('change', function () { filter(home, zone.value); filter(away, zone.value); });
    if (status && scores) {
      status.addEventListener('change', function () { scores.classList.toggle('d-none', status.value !== 'completed'); });
    }
    if (form.hasAttribute('data-same-team-check')) {
      form.addEventListener('submit', function (e) {
        if (home && away && home.value && home.value === away.value) {
          e.preventDefault();
          window.alert('Home team and away team cannot be the same!');
        }
      });
    }
  }

  function init() {
    wireBehaviours();
    initMatchForm();
    renderAllCharts();
    watchTheme();
    startCountdowns();
    initRefManager();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
