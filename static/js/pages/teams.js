/* Teams area page scripts. Each block runs only when its page's markup is present. */
(function () {
  'use strict';

  /* ---- Kit editor (teams/select_kit.html + includes/_kit_card.html) ---------------- */
  function initKitForm() {
    var form = document.getElementById('kitForm');
    if (!form) return;

    var submitBtn = document.getElementById('submitBtn');
    var validationAlert = document.getElementById('validationAlert');
    var validationMessage = document.getElementById('validationMessage');
    var MAX_SIZE = 5 * 1024 * 1024;
    var VALID_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];

    function brightness(hex) {
      var r = parseInt(hex.slice(1, 3), 16);
      var g = parseInt(hex.slice(3, 5), 16);
      var b = parseInt(hex.slice(5, 7), 16);
      return (r * 299 + g * 587 + b * 114) / 1000;
    }

    // Colour preview: <input name="home_jersey_color"> -> #homeJerseyPreview
    function updatePreview(input) {
      var card = input.closest('.kit-card');
      var part = input.name.replace(/_color$/, '').split('_').pop();
      var el = card && card.querySelector('.kit-figure__' + part);
      if (!el) return;
      el.style.backgroundColor = input.value;
      el.style.color = brightness(input.value) > 128 ? 'black' : 'white';
    }

    form.querySelectorAll('input[type="color"]').forEach(function (input) {
      updatePreview(input);
      input.addEventListener('input', function () { updatePreview(input); });
    });

    function hideAlert() { if (validationAlert) validationAlert.hidden = true; }

    // New-image preview with size/type checks
    form.querySelectorAll('input[type="file"]').forEach(function (input) {
      var preview = document.getElementById(input.id.replace(/KitImage$/, 'KitPreview'));
      var previewImg = document.getElementById(input.id.replace(/KitImage$/, 'KitPreviewImg'));
      input.addEventListener('change', function () {
        hideAlert();
        if (!preview || !previewImg) return;
        var file = this.files && this.files[0];
        if (!file) { preview.classList.add('d-none'); return; }
        if (file.size > MAX_SIZE) {
          alert('File size too large! Maximum size is 5MB.');
          this.value = '';
          preview.classList.add('d-none');
          return;
        }
        if (VALID_TYPES.indexOf(file.type.toLowerCase()) === -1) {
          alert('Invalid file type! Please upload JPEG, JPG, PNG, GIF, or WebP images.');
          this.value = '';
          preview.classList.add('d-none');
          return;
        }
        var reader = new FileReader();
        reader.onload = function (e) {
          previewImg.src = e.target.result;
          preview.classList.remove('d-none');
        };
        reader.readAsDataURL(file);
      });
    });

    // "Change" on an existing image: require a new upload for that kit
    form.querySelectorAll('[data-change-image]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var input = document.getElementById(btn.getAttribute('data-change-image'));
        if (!input) return;
        input.value = '';
        input.required = true;
        input.removeAttribute('data-has-image');
        var current = form.querySelector('[data-current-image-for="' + input.id + '"]');
        if (current) current.hidden = true;
        var help = document.getElementById(input.id + 'Help');
        if (help) help.textContent = 'Please upload a new image for this kit.';
        input.scrollIntoView({ behavior: 'smooth', block: 'center' });
        input.focus();
      });
    });

    function isMissing(input) {
      return input.hasAttribute('data-kit-required') && !input.hasAttribute('data-has-image') &&
        !(input.files && input.files.length);
    }

    form.addEventListener('submit', function (e) {
      var missing = Array.prototype.filter.call(form.querySelectorAll('input[type="file"]'), isMissing);
      if (missing.length) {
        e.preventDefault();
        validationMessage.textContent = 'Please upload all required images: ' + missing.map(function (i) {
          return i.getAttribute('data-kit-label') + ' image is required';
        }).join(', ');
        validationAlert.hidden = false;
        validationAlert.scrollIntoView({ behavior: 'smooth' });
        missing[0].focus();
        return;
      }
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1" aria-hidden="true"></i>Saving...';
      }
    });
  }

  function init() {
    initKitForm();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
