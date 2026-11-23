/* Referees area page scripts. Each block runs only when its page markup is present. */
(function () {
    'use strict';

    var FKF = { red: '#c8102e', green: '#00843d', black: '#0a0a0b', graphite: '#6e6e73', grey: '#c5c7cc' };

    function isDark() {
        return document.documentElement.getAttribute('data-bs-theme') === 'dark';
    }

    function pad(n) { return (n < 10 ? '0' : '') + n; }
    // Local YYYY-MM-DD (toISOString shifts to UTC and lands on the previous day in EAT).
    function ymd(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
    function parseYmd(s) {
        var p = (s || '').split('-');
        return p.length === 3 ? new Date(+p[0], +p[1] - 1, +p[2]) : null;
    }

    /* ---- Referee dashboard: assignments doughnut ------------------------- */
    function initDashboardChart() {
        var canvas = document.getElementById('assignmentsChart');
        if (!canvas || typeof Chart === 'undefined') return;
        var values = (canvas.dataset.values || '').split(',').map(Number);
        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['Pending', 'Today', 'Upcoming', 'Reports due'],
                datasets: [{
                    data: values,
                    backgroundColor: [FKF.red, isDark() ? '#ffffff' : FKF.black, FKF.green, FKF.grey],
                    borderWidth: 0, hoverOffset: 6
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '64%',
                plugins: {
                    legend: { position: 'bottom', labels: { padding: 14, boxWidth: 10, font: { size: 11 }, color: isDark() ? FKF.grey : FKF.graphite } }
                }
            }
        });
    }

    /* ---- Availability page ------------------------------------------------ */
    function initAvailability() {
        var page = document.getElementById('availabilityPage');
        if (!page) return;
        var today = parseYmd(page.dataset.today) || new Date();
        today.setHours(0, 0, 0, 0);
        var currentMonth = today.getMonth();
        var currentYear = today.getFullYear();
        var dateInput = document.getElementById('date');
        var reasonContainer = document.getElementById('reasonContainer');
        var reasonInput = document.getElementById('reason');
        var availableRadio = document.getElementById('available');
        var unavailableRadio = document.getElementById('unavailable');

        function showReason(show) { reasonContainer.hidden = !show; }
        unavailableRadio.addEventListener('change', function () { if (this.checked) showReason(true); });
        availableRadio.addEventListener('change', function () { if (this.checked) showReason(false); });

        function markQuick(value) {
            document.querySelectorAll('.quick-date').forEach(function (btn) {
                var on = btn.dataset.date === value;
                btn.classList.toggle('btn-primary', on);
                btn.classList.toggle('btn-outline-secondary', !on);
                btn.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
        }

        document.querySelectorAll('.quick-date').forEach(function (button) {
            button.addEventListener('click', function () {
                dateInput.value = this.dataset.date;
                markQuick(this.dataset.date);
            });
        });

        document.querySelectorAll('.edit-availability').forEach(function (button) {
            button.addEventListener('click', function () {
                var row = this.closest('tr');
                dateInput.value = this.dataset.date;
                if (row.dataset.status === 'true') {
                    availableRadio.checked = true;
                    reasonInput.value = '';
                    showReason(false);
                } else {
                    unavailableRadio.checked = true;
                    reasonInput.value = row.dataset.reason || '';
                    showReason(true);
                }
                markQuick(this.dataset.date);
                dateInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                dateInput.focus({ preventScroll: true });
            });
        });

        var modalEl = document.getElementById('deleteModal');
        var deleteModal = (modalEl && window.bootstrap) ? new bootstrap.Modal(modalEl) : null;
        document.querySelectorAll('.delete-availability').forEach(function (button) {
            button.addEventListener('click', function () {
                var d = parseYmd(this.dataset.date);
                document.getElementById('deleteDate').textContent = d ? d.toLocaleDateString('en-GB', {
                    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
                }) : this.dataset.date;
                document.getElementById('deleteDateInput').value = this.dataset.date;
                if (deleteModal) deleteModal.show();
            });
        });

        var monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];

        function selectDate(cell) {
            dateInput.value = cell.dataset.date;
            document.querySelectorAll('.calendar-day').forEach(function (d) { d.classList.remove('selected'); });
            cell.classList.add('selected');
            markQuick(cell.dataset.date);
        }

        function renderCalendar() {
            document.getElementById('currentMonth').textContent = monthNames[currentMonth] + ' ' + currentYear;
            var grid = document.getElementById('calendarDays');
            grid.innerHTML = '';
            var first = new Date(currentYear, currentMonth, 1);
            var daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
            var lead = (first.getDay() + 6) % 7; // Monday-first, matching the header
            var i;
            for (i = 0; i < lead; i++) {
                var blank = document.createElement('span');
                blank.className = 'calendar-day other-month';
                grid.appendChild(blank);
            }
            for (var day = 1; day <= daysInMonth; day++) {
                var date = new Date(currentYear, currentMonth, day);
                var dateStr = ymd(date);
                var isPast = date < today;
                var cell = document.createElement(isPast ? 'span' : 'button');
                cell.className = 'calendar-day';
                cell.textContent = day;
                cell.dataset.date = dateStr;
                if (date.getTime() === today.getTime()) cell.classList.add('today');
                if (isPast) cell.classList.add('past-day');
                var row = document.querySelector('#availabilityTable tr[data-date="' + dateStr + '"]');
                if (row) cell.classList.add(row.dataset.status === 'true' ? 'available' : 'unavailable');
                if (dateInput.value === dateStr) cell.classList.add('selected');
                if (!isPast) {
                    cell.type = 'button';
                    cell.setAttribute('aria-label', date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' }));
                    cell.addEventListener('click', function () { selectDate(this); });
                }
                grid.appendChild(cell);
            }
            var total = lead + daysInMonth;
            for (i = total; i % 7 !== 0; i++) {
                var tail = document.createElement('span');
                tail.className = 'calendar-day other-month';
                grid.appendChild(tail);
            }
        }

        document.getElementById('prevMonth').addEventListener('click', function () {
            currentMonth--;
            if (currentMonth < 0) { currentMonth = 11; currentYear--; }
            renderCalendar();
        });
        document.getElementById('nextMonth').addEventListener('click', function () {
            currentMonth++;
            if (currentMonth > 11) { currentMonth = 0; currentYear++; }
            renderCalendar();
        });

        // Bulk helpers are not wired to the server yet; keep the original notices.
        document.getElementById('setAvailableWeek').addEventListener('click', function () {
            alert('This feature would set all dates in the next week as available');
        });
        document.getElementById('setUnavailableWeek').addEventListener('click', function () {
            alert('This feature would set all dates in the next week as unavailable');
        });
        document.getElementById('clearAll').addEventListener('click', function () {
            if (confirm('Are you sure you want to clear all availability settings?')) {
                alert('All availability settings would be cleared');
            }
        });

        document.querySelectorAll('[data-filter]').forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                var filter = this.dataset.filter;
                document.querySelectorAll('#availabilityTable tbody tr').forEach(function (row) {
                    var isAvailable = row.dataset.status === 'true';
                    var d = parseYmd(row.dataset.date);
                    var show = true;
                    if (filter === 'available') show = isAvailable;
                    else if (filter === 'unavailable') show = !isAvailable;
                    else if (filter === 'future') show = d && d >= today;
                    row.hidden = !show;
                });
            });
        });

        function updateStats() {
            var avail = document.querySelectorAll('#availabilityTable tr.is-available').length;
            var unavail = document.querySelectorAll('#availabilityTable tr.is-unavailable').length;
            var total = avail + unavail;
            document.getElementById('availableCount').textContent = avail;
            document.getElementById('unavailableCount').textContent = unavail;
            var a = total ? Math.round((avail / total) * 100) : 100;
            document.getElementById('availableProgress').style.width = a + '%';
            document.getElementById('unavailableProgress').style.width = (100 - a) + '%';
            document.getElementById('availablePercent').textContent = a + '% available';
            document.getElementById('unavailablePercent').textContent = (100 - a) + '% unavailable';
        }

        renderCalendar();
        updateStats();
    }

    /* ---- Report formsets (comprehensive + flash) -------------------------
       Same contract as the original inline scripts: clone the empty form, swap
       __prefix__ for the next index, bump <prefix>-TOTAL_FORMS. */
    function totalInput(prefix) { return document.getElementById('id_' + prefix + '-TOTAL_FORMS'); }

    function insertForm(prefix, container, html) {
        var total = totalInput(prefix);
        if (!total || !container || !html) return null;
        var idx = parseInt(total.value, 10) || 0;
        container.insertAdjacentHTML('beforeend', html.replace(/__prefix__/g, idx));
        total.value = idx + 1;
        return container.lastElementChild;
    }

    function rowIndex(row, prefix) {
        var field = row.querySelector('[name^="' + prefix + '-"]');
        var m = field && field.name.match(new RegExp('^' + prefix + '-(\\d+)-'));
        return m ? parseInt(m[1], 10) : -1;
    }

    // Existing rows: tick DELETE and hide. New rows: drop the last one outright, or
    // blank a middle one (unchanged extra forms are ignored by Django) so indices stay contiguous.
    function removeRow(row, prefix) {
        if (!row) return;
        var idInput = row.querySelector('input[name$="-id"]');
        var del = row.querySelector('input[name$="-DELETE"]');
        if (idInput && idInput.value) {
            if (del) del.checked = true;
            row.hidden = true;
            return;
        }
        var total = totalInput(prefix);
        var idx = rowIndex(row, prefix);
        if (total && idx === parseInt(total.value, 10) - 1) {
            total.value = idx;
            row.remove();
        } else {
            row.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(function (el) {
                if (el.type === 'checkbox' || el.type === 'radio') el.checked = false;
                else el.value = '';
            });
            row.hidden = true;
        }
    }

    function initReportFormsets() {
        var report = document.getElementById('matchReportForm');
        var flash = document.getElementById('flashReportForm');
        if (!report && !flash) return;

        function wireSimple(kind) { // goal | card
            var btn = document.getElementById('add-' + kind + '-form');
            var container = document.getElementById(kind + '-formset');
            var tpl = document.querySelector('#empty-' + kind + ' .formset-form');
            if (!btn || !container) return;
            var prefix = container.dataset.prefix || kind;
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                var el = tpl && insertForm(prefix, container, tpl.outerHTML);
                if (!el) { alert('Could not add a row. Please reload the page and try again.'); return; }
                var first = el.querySelector('select, input:not([type="hidden"])');
                if (first) first.focus();
                if (flash) filterPlayersForRow(el);
            });
            container.addEventListener('click', function (e) {
                var rm = e.target.closest('.remove-' + kind + '-form');
                if (!rm) return;
                e.preventDefault();
                if (flash && !confirm('Remove this ' + (kind === 'goal' ? 'goal' : 'card') + ' entry?')) return;
                removeRow(rm.closest('.formset-form'), prefix);
            });
        }
        wireSimple('goal');
        wireSimple('card');

        if (report) {
            var homeTeam = report.dataset.homeTeam;
            var awayTeam = report.dataset.awayTeam;
            [['add-home-starting', 'starting', 'home-starting-lineup', 'empty-starting-home', homeTeam],
             ['add-away-starting', 'starting', 'away-starting-lineup', 'empty-starting-away', awayTeam],
             ['add-home-reserves', 'reserve', 'home-reserves', 'empty-reserve-home', homeTeam],
             ['add-away-reserves', 'reserve', 'away-reserves', 'empty-reserve-away', awayTeam]
            ].forEach(function (cfg) {
                var btn = document.getElementById(cfg[0]);
                if (!btn) return;
                btn.addEventListener('click', function (e) {
                    e.preventDefault();
                    var tpl = document.getElementById(cfg[3]);
                    var el = tpl && insertForm(cfg[1], document.getElementById(cfg[2]), tpl.innerHTML);
                    if (!el) return;
                    var idx = parseInt(totalInput(cfg[1]).value, 10) - 1;
                    var team = document.getElementById('id_' + cfg[1] + '-' + idx + '-team');
                    if (team) team.value = cfg[4];
                    var jersey = document.getElementById('id_' + cfg[1] + '-' + idx + '-jersey_number');
                    if (jersey) { jersey.focus(); jersey.select(); }
                });
            });
            report.addEventListener('click', function (e) {
                var s = e.target.closest('.remove-starting-form');
                var r = e.target.closest('.remove-reserve-form');
                if (s) { e.preventDefault(); removeRow(s.closest('tr'), 'starting'); }
                if (r) { e.preventDefault(); removeRow(r.closest('.formset-form'), 'reserve'); }
            });
            [['add-host-official', 'host-officials'], ['add-away-official', 'away-officials']].forEach(function (cfg) {
                var btn = document.getElementById(cfg[0]);
                var tpl = document.getElementById('empty-team_officials');
                if (!btn || !tpl) return;
                btn.addEventListener('click', function (e) {
                    e.preventDefault();
                    insertForm('team_officials', document.getElementById(cfg[1]), tpl.innerHTML);
                });
            });
        }

        // Flash report: limit player / assist choices to the selected team.
        var playerTpl = document.getElementById('flashPlayers');
        var players = playerTpl ? Array.prototype.slice.call(playerTpl.content.querySelectorAll('option')) : [];
        function fillSelect(select, teamId) {
            if (!select) return;
            var current = select.value;
            select.innerHTML = '<option value="">---------</option>';
            players.forEach(function (opt) {
                if (opt.dataset.team === teamId) {
                    var o = opt.cloneNode(true);
                    if (o.value === current) o.selected = true;
                    select.appendChild(o);
                }
            });
        }
        function filterPlayersForRow(row, teamSelect) {
            if (!players.length || !row) return;
            teamSelect = teamSelect || row.querySelector('select[id*="team"]');
            if (!teamSelect || !teamSelect.value) return;
            var player = Array.prototype.find.call(row.querySelectorAll('select[id*="player"]'), function (s) { return s.id.indexOf('assist') === -1; });
            fillSelect(player, teamSelect.value);
            fillSelect(row.querySelector('select[id*="assist"]'), teamSelect.value);
        }
        if (flash) {
            flash.addEventListener('change', function (e) {
                if (e.target.matches('select[id*="team"]')) filterPlayersForRow(e.target.closest('.formset-form'), e.target);
            });
            flash.querySelectorAll('.formset-form').forEach(function (row) { filterPlayersForRow(row); });
        }
    }

    function init() {
        initDashboardChart();
        initAvailability();
        initReportFormsets();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
