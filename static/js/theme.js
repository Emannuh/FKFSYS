/* Applies the saved/OS colour theme before first paint (loaded synchronously in <head>).
   Kept tiny and external so pages need no inline script (CSP-friendly).
   Toggle buttons are wired up in app.js; preference key: localStorage "fkf-theme". */
(function () {
  'use strict';
  var theme = null;
  try { theme = window.localStorage.getItem('fkf-theme'); } catch (e) { /* storage blocked */ }
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-bs-theme', theme);
})();
