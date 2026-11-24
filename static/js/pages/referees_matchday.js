// Matchday squad submission: live counts, no player in both lists, submit gated on a valid XI.
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('squadForm');
    if (!form) return;
    const startingCount = document.getElementById('startingCount');
    const subsCount = document.getElementById('subsCount');
    const submitBtn = document.getElementById('submitBtn');

    function setTone(el, tone) {
        if (!el) return;
        el.classList.remove('status-success', 'status-warning', 'status-danger', 'status-neutral');
        el.classList.add('status-' + tone);
    }

    function update() {
        const starting = form.querySelectorAll('.starting-checkbox:checked').length;
        const subs = form.querySelectorAll('.sub-checkbox:checked').length;
        const gks = form.querySelectorAll('.starting-checkbox:checked[data-position="GK"]').length;
        if (startingCount) startingCount.textContent = starting + '/11';
        if (subsCount) subsCount.textContent = subs + '/14';
        const startingOk = starting >= 7 && starting <= 11;
        setTone(startingCount, startingOk ? 'success' : 'warning');
        setTone(subsCount, subs <= 14 ? 'neutral' : 'danger');
        if (submitBtn) {
            const valid = startingOk && subs <= 14 && gks >= 1;
            submitBtn.disabled = !valid;
            submitBtn.title = valid ? '' : 'Pick 7–11 starters including a goalkeeper, and at most 14 substitutes';
        }
    }

    form.addEventListener('change', function (e) {
        const cb = e.target;
        if (!(cb instanceof HTMLInputElement) || cb.type !== 'checkbox') return;
        if (cb.checked) {
            const otherId = cb.classList.contains('starting-checkbox') ? 'sub_' + cb.value : 'starting_' + cb.value;
            const other = document.getElementById(otherId);
            if (other) other.checked = false;
        }
        update();
    });

    update();
});
