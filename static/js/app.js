/**
 * FKF Meru County League — app.js
 * Global behaviour for the public and dashboard layouts. Loaded with `defer`;
 * everything is scoped inside this IIFE so no globals leak. Optional libraries
 * (bootstrap, AOS, NProgress) are feature-detected, so pages that do not load
 * them (e.g. the login page) still work.
 *
 * Theme (light/dark) is applied before first paint by static/js/theme.js;
 * this file only wires up the toggle buttons.
 */
(() => {
  'use strict';

  const storage = {
    get(key) { try { return window.localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { window.localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
  };

  const hasBootstrap = typeof window.bootstrap !== 'undefined';
  const nprogress = typeof window.NProgress !== 'undefined' ? window.NProgress : null;

  // Start the progress bar as early as possible; finished on window load.
  if (nprogress) {
    nprogress.configure({ showSpinner: false, speed: 380, minimum: 0.15 });
    nprogress.start();
  }

  function initTooltips() {
    if (!hasBootstrap) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
      window.bootstrap.Tooltip.getOrCreateInstance(el, { trigger: 'hover focus' });
    });
  }

  function initScrollEffects() {
    const scrollBtn = document.getElementById('scroll-top');
    const navbar = document.querySelector('.navbar-custom, .site-nav');
    const onScroll = () => {
      if (scrollBtn) scrollBtn.classList.toggle('visible', window.scrollY > 280);
      if (navbar) navbar.classList.toggle('scrolled', window.scrollY > 8);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    if (scrollBtn) {
      scrollBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    }
  }

  function highlightActiveLinks() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-link[href], .sb-nav-item[href]').forEach((link) => {
      const href = link.getAttribute('href');
      if (href && href !== '/' && href.startsWith('/') && path.startsWith(href)) {
        link.classList.add('active');
      }
    });
  }

  function autoDismissAlerts() {
    if (!hasBootstrap) return;
    document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach((alert) => {
      if (!alert.querySelector('[data-bs-dismiss="alert"]')) return;
      window.setTimeout(() => window.bootstrap.Alert.getOrCreateInstance(alert).close(), 6000);
    });
  }

  function initCountdowns() {
    document.querySelectorAll('[data-deadline]').forEach((el) => {
      const target = Date.parse(el.getAttribute('data-deadline') || '');
      if (Number.isNaN(target)) return;
      let timer = null;
      const update = () => {
        const diff = target - Date.now();
        if (diff <= 0) {
          el.textContent = 'Deadline passed';
          if (timer) window.clearInterval(timer);
          return;
        }
        const d = Math.floor(diff / 86400000);
        const h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        el.textContent = `${d}d ${h}h ${m}m ${s}s`;
      };
      update();
      timer = window.setInterval(update, 1000);
    });
  }

  function initProgressBar() {
    if (!nprogress) return;
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a[href]');
      if (!link || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const href = link.getAttribute('href') || '';
      const skip = !href || href.startsWith('#') || href.startsWith('javascript')
        || /^(https?:)?\/\//.test(href) || href.startsWith('mailto') || href.startsWith('tel')
        || link.target === '_blank' || link.hasAttribute('download')
        || link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-dismiss');
      if (!skip) nprogress.start();
    });
    document.addEventListener('submit', (e) => { if (!e.defaultPrevented) nprogress.start(); });
    // Pages restored from the back/forward cache never fire `load` again.
    window.addEventListener('pageshow', () => nprogress.done());
  }

  function initPageLoader() {
    const hide = () => {
      const loader = document.getElementById('page-loader');
      if (loader) window.setTimeout(() => loader.classList.add('loaded'), 150);
      if (nprogress) nprogress.done();
    };
    if (document.readyState === 'complete') hide();
    else window.addEventListener('load', hide);
  }

  function initAnimations() {
    if (typeof window.AOS === 'undefined') return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.AOS.init({ duration: 480, easing: 'ease-out-cubic', once: true, offset: 40, disable: reduce });
  }

  function initPasswordToggles() {
    // <button type="button" data-toggle-password="id_password"><i class="fas fa-eye"></i></button>
    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
      const input = document.getElementById(btn.getAttribute('data-toggle-password'));
      if (!input) return;
      btn.addEventListener('click', () => {
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.setAttribute('aria-pressed', String(show));
        btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        const icon = btn.querySelector('i');
        if (icon) icon.className = show ? 'fas fa-eye-slash' : 'fas fa-eye';
      });
    });
  }

  function initThemeToggle() {
    // <button type="button" data-theme-toggle aria-label="Toggle dark mode">…</button>
    const root = document.documentElement;
    const buttons = document.querySelectorAll('[data-theme-toggle]');
    const sync = () => {
      const dark = root.getAttribute('data-bs-theme') === 'dark';
      buttons.forEach((btn) => {
        btn.setAttribute('aria-pressed', String(dark));
        btn.setAttribute('title', dark ? 'Switch to light mode' : 'Switch to dark mode');
      });
    };
    buttons.forEach((btn) => btn.addEventListener('click', () => {
      const next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-bs-theme', next);
      storage.set('fkf-theme', next);
      sync();
    }));
    sync();
  }

  function initTabsFromHash() {
    // Lets links such as /#zone-b open the matching Bootstrap tab.
    if (!hasBootstrap || !window.location.hash) return;
    const trigger = document.querySelector(`[data-bs-toggle="tab"][data-bs-target="${CSS.escape(window.location.hash)}"]`);
    if (trigger) window.bootstrap.Tab.getOrCreateInstance(trigger).show();
  }

  function initDashboardSidebar() {
    const sidebar = document.getElementById('dbSidebar');
    const main = document.getElementById('dbMain');
    if (!sidebar || !main) return;
    const overlay = document.getElementById('sbOverlay');
    const toggles = [document.getElementById('sbToggleBtn'), document.getElementById('topbarToggle')].filter(Boolean);
    const isDesktop = () => window.matchMedia('(min-width: 992px)').matches;

    const setExpanded = (expanded) => toggles.forEach((t) => t.setAttribute('aria-expanded', String(expanded)));
    const openMobile = () => {
      sidebar.classList.add('mobile-open');
      if (overlay) overlay.classList.add('active');
      setExpanded(true);
      const first = sidebar.querySelector('a, button');
      if (first) first.focus();
    };
    const closeMobile = () => {
      sidebar.classList.remove('mobile-open');
      if (overlay) overlay.classList.remove('active');
      setExpanded(false);
    };
    const toggleDesktop = () => {
      const collapsed = sidebar.classList.toggle('collapsed');
      main.classList.toggle('expanded', collapsed);
      storage.set('sbCollapsed', collapsed ? '1' : '0');
      setExpanded(!collapsed);
    };
    const toggle = () => {
      if (isDesktop()) toggleDesktop();
      else if (sidebar.classList.contains('mobile-open')) closeMobile();
      else openMobile();
    };

    toggles.forEach((t) => t.addEventListener('click', toggle));
    if (overlay) overlay.addEventListener('click', closeMobile);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
        closeMobile();
        const tb = document.getElementById('topbarToggle');
        if (tb) tb.focus();
      }
    });

    if (isDesktop() && storage.get('sbCollapsed') === '1') {
      sidebar.classList.add('collapsed');
      main.classList.add('expanded');
      setExpanded(false);
    } else {
      setExpanded(isDesktop());
    }

    const dateEl = document.getElementById('topbarDate');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString('en-GB', {
        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
      });
    }
  }

  function init() {
    initThemeToggle();
    initTooltips();
    initScrollEffects();
    highlightActiveLinks();
    autoDismissAlerts();
    initCountdowns();
    initProgressBar();
    initPageLoader();
    initAnimations();
    initPasswordToggles();
    initTabsFromHash();
    initDashboardSidebar();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
