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

    function init() {
        initDashboardChart();
        initAvailability();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
