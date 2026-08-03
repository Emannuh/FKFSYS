/**
 * FKF Meru County League — app.js
 * Global JS for public & dashboard layouts.
 */

document.addEventListener('DOMContentLoaded', function () {

  // ── Bootstrap tooltips ──────────────────────────────────────────
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el, { trigger: 'hover' });
  });

  // ── Scroll-to-top button ─────────────────────────────────────────
  var scrollBtn = document.getElementById('scroll-top');
  if (scrollBtn) {
    window.addEventListener('scroll', function () {
      scrollBtn.classList.toggle('visible', window.scrollY > 280);
    }, { passive: true });
    scrollBtn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ── Navbar scroll effect (public layout) ────────────────────────
  var navbar = document.querySelector('.navbar-custom');
  if (navbar) {
    window.addEventListener('scroll', function () {
      navbar.classList.toggle('scrolled', window.scrollY > 50);
    }, { passive: true });
  }

  // ── Active nav link highlight ────────────────────────────────────
  var currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(function (link) {
    var href = link.getAttribute('href');
    if (href && href !== '/' && currentPath.startsWith(href)) {
      link.classList.add('active');
    }
  });

  // ── Auto-dismiss alerts after 6 s ───────────────────────────────
  document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(function (alert) {
    setTimeout(function () {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 6000);
  });

  // ── Countdown timers ─────────────────────────────────────────────
  document.querySelectorAll('[data-deadline]').forEach(function (el) {
    var deadline = el.getAttribute('data-deadline');
    if (!deadline) return;
    var target = Date.parse(deadline);
    if (Number.isNaN(target)) return;
    function update() {
      var diff = target - Date.now();
      if (diff <= 0) { el.textContent = 'Deadline passed'; return; }
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var s = Math.floor((diff % 60000) / 1000);
      el.textContent = d + 'd ' + h + 'h ' + m + 'm ' + s + 's';
    }
    update();
    setInterval(update, 1000);
  });

  // ── NProgress on link clicks / form submits ───────────────────────
  if (typeof NProgress !== 'undefined') {
    NProgress.configure({ showSpinner: false, speed: 380, minimum: 0.15 });
    document.addEventListener('click', function (e) {
      var link = e.target.closest('a[href]');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript')
          || href.startsWith('http') || href.startsWith('//')
          || href.startsWith('mailto') || link.target === '_blank'
          || link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-dismiss')) return;
      NProgress.start();
    });
    document.addEventListener('submit', function () { NProgress.start(); });
    window.addEventListener('load', function () { NProgress.done(); });
  }

  // ── Page loader hide ─────────────────────────────────────────────
  window.addEventListener('load', function () {
    setTimeout(function () {
      var loader = document.getElementById('page-loader');
      if (loader) loader.classList.add('loaded');
    }, 250);
  });

  // ── AOS init ─────────────────────────────────────────────────────
  if (typeof AOS !== 'undefined') {
    AOS.init({ duration: 580, easing: 'ease-out-cubic', once: true, offset: 50 });
  }

  // ── Dashboard sidebar (if present) ───────────────────────────────
  var sidebar  = document.getElementById('dbSidebar');
  var main     = document.getElementById('dbMain');
  var overlay  = document.getElementById('sbOverlay');
  var sbToggle = document.getElementById('sbToggleBtn');
  var tbToggle = document.getElementById('topbarToggle');

  if (sidebar && main) {
    function isDesktop() { return window.innerWidth >= 992; }

    function toggleDesktop() {
      sidebar.classList.toggle('collapsed');
      main.classList.toggle('expanded');
      localStorage.setItem('sbCollapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
    }
    function openMobile()  { sidebar.classList.add('mobile-open');    if (overlay) overlay.classList.add('active'); }
    function closeMobile() { sidebar.classList.remove('mobile-open'); if (overlay) overlay.classList.remove('active'); }
    function toggle()      { if (isDesktop()) toggleDesktop(); else (sidebar.classList.contains('mobile-open') ? closeMobile() : openMobile()); }

    if (sbToggle) sbToggle.addEventListener('click', toggle);
    if (tbToggle) tbToggle.addEventListener('click', toggle);
    if (overlay)  overlay.addEventListener('click', closeMobile);

    // Restore desktop state
    if (isDesktop() && localStorage.getItem('sbCollapsed') === '1') {
      sidebar.classList.add('collapsed');
      main.classList.add('expanded');
    }

    // Auto-highlight sidebar active item
    document.querySelectorAll('.sb-nav-item[href]').forEach(function (item) {
      var href = item.getAttribute('href');
      if (href && href !== '/' && window.location.pathname.startsWith(href)) {
        item.classList.add('active');
      }
    });

    // Date in topbar
    var dateEl = document.getElementById('topbarDate');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString('en-US', {
        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
      });
    }
  }

});
