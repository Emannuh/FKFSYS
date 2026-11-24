/* Public pages: small progressive enhancements, no globals.
   Loaded with {% block extra_js %}<script src="{% static 'js/pages/public.js' %}" defer></script>.

   data-busy-label="Saving…"   on a <form>: on submit, disable its submit button and show a spinner + label.
   data-auto-reload="15000"    on any element: reload the page after N ms (payment status polling).
   data-countdown="<ISO date>" on any element: live "Xd Xh Xm Xs remaining" text.
   data-copy="<text>"          on a button: copy text to the clipboard, confirm in the button label. */
(function () {
  'use strict';

  function busy(form) {
    var btn = form.querySelector('[type="submit"]');
    if (!btn) return;
    var label = form.getAttribute('data-busy-label') || 'Working…';
    var icon = document.createElement('i');
    icon.className = 'fas fa-spinner fa-spin me-2';
    icon.setAttribute('aria-hidden', 'true');
    btn.textContent = '';
    btn.appendChild(icon);
    btn.appendChild(document.createTextNode(label));
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
  }

  document.querySelectorAll('form[data-busy-label]').forEach(function (form) {
    form.addEventListener('submit', function () {
      // Let the browser start the submission first so the disabled button's value isn't lost.
      window.setTimeout(function () { busy(form); }, 0);
    });
  });

  var reloadEl = document.querySelector('[data-auto-reload]');
  if (reloadEl) {
    var ms = parseInt(reloadEl.getAttribute('data-auto-reload'), 10);
    if (ms > 0) window.setTimeout(function () { window.location.reload(); }, ms);
  }

  document.querySelectorAll('[data-countdown]').forEach(function (el) {
    var target = Date.parse(el.getAttribute('data-countdown'));
    if (Number.isNaN(target)) return;
    var timer;
    function tick() {
      var diff = target - Date.now();
      if (diff <= 0) {
        el.textContent = 'Window closed';
        window.clearInterval(timer);
        return;
      }
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var s = Math.floor((diff % 60000) / 1000);
      el.textContent = d + 'd ' + h + 'h ' + m + 'm ' + s + 's remaining';
    }
    tick();
    timer = window.setInterval(tick, 1000);
  });

  document.querySelectorAll('button[data-copy]').forEach(function (btn) {
    if (!navigator.clipboard) { btn.hidden = true; return; }
    var label = btn.querySelector('.copy-label');
    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () {
        if (label) label.textContent = 'Copied';
        window.setTimeout(function () { if (label) label.textContent = 'Copy'; }, 2000);
      });
    });
  });
})();
