// Place for small project-wide JS. Bootstrap bundle is already included.
// Example: enable tooltips globally if used.

document.addEventListener('DOMContentLoaded', () => {
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
  document.addEventListener('DOMContentLoaded', function() {
      // Defensive: remove any page loader overlays that might hide content
      try {
          var loader = document.getElementById('page-loader');
          if (loader) loader.style.display = 'none';
          var overlay = document.getElementById('sbOverlay');
          if (overlay) overlay.style.display = 'none';
          var dbMain = document.getElementById('dbMain');
          if (dbMain) dbMain.style.minHeight = 'auto';
      } catch (e) {
          console.warn('Debug JS: overlay removal failed', e);
      }
  });
});
