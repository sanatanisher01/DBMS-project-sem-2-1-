// HostelMate Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Add animation classes to elements
    addAnimations();

    // Initialize dark mode
    initDarkMode();

    // Initialize loading indicators
    initLoadingIndicators();

    // Add responsive behavior
    handleResponsiveLayout();

    // Form validation
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Toggle password visibility
    var togglePasswordButtons = document.querySelectorAll('.toggle-password');
    togglePasswordButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var input = document.querySelector(button.getAttribute('data-target'));
            if (input.type === 'password') {
                input.type = 'text';
                button.innerHTML = '<i class="fas fa-eye-slash"></i>';
            } else {
                input.type = 'password';
                button.innerHTML = '<i class="fas fa-eye"></i>';
            }
        });
    });

    // Confirm delete modals
    var deleteButtons = document.querySelectorAll('[data-confirm]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm(button.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    // Dynamic form fields based on selection
    var conditionalFields = document.querySelectorAll('[data-condition-field]');
    conditionalFields.forEach(function(field) {
        var targetField = document.getElementById(field.getAttribute('data-condition-field'));
        var targetValue = field.getAttribute('data-condition-value');

        function toggleVisibility() {
            if (targetField.value === targetValue) {
                field.style.display = 'block';
                // Enable required fields
                var requiredFields = field.querySelectorAll('[data-required-if-shown]');
                requiredFields.forEach(function(reqField) {
                    reqField.required = true;
                });
            } else {
                field.style.display = 'none';
                // Disable required fields
                var requiredFields = field.querySelectorAll('[data-required-if-shown]');
                requiredFields.forEach(function(reqField) {
                    reqField.required = false;
                });
            }
        }

        // Initial check
        toggleVisibility();

        // Add event listener
        targetField.addEventListener('change', toggleVisibility);
    });

    // Date range picker initialization
    var dateRangePickers = document.querySelectorAll('.date-range-picker');
    dateRangePickers.forEach(function(picker) {
        if (typeof daterangepicker !== 'undefined') {
            $(picker).daterangepicker({
                opens: 'left',
                autoUpdateInput: false,
                locale: {
                    cancelLabel: 'Clear',
                    format: 'YYYY-MM-DD'
                }
            });

            $(picker).on('apply.daterangepicker', function(ev, picker) {
                $(this).val(picker.startDate.format('YYYY-MM-DD') + ' to ' + picker.endDate.format('YYYY-MM-DD'));
            });

            $(picker).on('cancel.daterangepicker', function(ev, picker) {
                $(this).val('');
            });
        }
    });

    // Table sorting
    var sortableTables = document.querySelectorAll('.sortable');
    sortableTables.forEach(function(table) {
        var headers = table.querySelectorAll('th[data-sort]');
        headers.forEach(function(header) {
            header.addEventListener('click', function() {
                var column = header.getAttribute('data-sort');
                var order = header.getAttribute('data-order') === 'asc' ? 'desc' : 'asc';

                // Reset all headers
                headers.forEach(function(h) {
                    h.setAttribute('data-order', '');
                    h.classList.remove('sorting-asc', 'sorting-desc');
                });

                // Set current header
                header.setAttribute('data-order', order);
                header.classList.add(order === 'asc' ? 'sorting-asc' : 'sorting-desc');

                // Sort the table
                sortTable(table, column, order);
            });
        });
    });

    function sortTable(table, column, order) {
        var tbody = table.querySelector('tbody');
        var rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort(function(a, b) {
            var aValue = a.querySelector(`td[data-column="${column}"]`).textContent.trim();
            var bValue = b.querySelector(`td[data-column="${column}"]`).textContent.trim();

            if (!isNaN(aValue) && !isNaN(bValue)) {
                aValue = parseFloat(aValue);
                bValue = parseFloat(bValue);
            }

            if (order === 'asc') {
                return aValue > bValue ? 1 : -1;
            } else {
                return aValue < bValue ? 1 : -1;
            }
        });

        // Clear the table
        while (tbody.firstChild) {
            tbody.removeChild(tbody.firstChild);
        }

        // Add sorted rows
        rows.forEach(function(row) {
            tbody.appendChild(row);
        });
    }

    // Search functionality
    var searchInputs = document.querySelectorAll('.table-search');
    searchInputs.forEach(function(input) {
        input.addEventListener('keyup', function() {
            var tableId = input.getAttribute('data-table');
            var table = document.getElementById(tableId);
            var searchText = input.value.toLowerCase();

            var rows = table.querySelectorAll('tbody tr');
            rows.forEach(function(row) {
                var text = row.textContent.toLowerCase();
                if (text.indexOf(searchText) === -1) {
                    row.style.display = 'none';
                } else {
                    row.style.display = '';
                }
            });
        });
    });
});

// Add animations to elements
function addAnimations() {
    // Add fade-in animation to cards
    document.querySelectorAll('.card').forEach(function(card, index) {
        card.classList.add('fade-in');
        card.style.animationDelay = (index * 0.1) + 's';
    });

    // Add slide-in animations to different sections
    document.querySelectorAll('.row > div:nth-child(odd)').forEach(function(element, index) {
        element.classList.add('slide-in-left');
        element.style.animationDelay = (index * 0.1) + 's';
    });

    document.querySelectorAll('.row > div:nth-child(even)').forEach(function(element, index) {
        element.classList.add('slide-in-right');
        element.style.animationDelay = (index * 0.1) + 's';
    });

    // Add bounce animation to important buttons
    document.querySelectorAll('.btn-primary').forEach(function(button) {
        button.addEventListener('mouseenter', function() {
            this.classList.add('bounce');
        });
        button.addEventListener('animationend', function() {
            this.classList.remove('bounce');
        });
    });
}

// Initialize dark mode
function initDarkMode() {
    // Create dark mode toggle button
    var navbarNav = document.querySelector('.navbar-nav.ms-auto');
    if (navbarNav) {
        var darkModeToggle = document.createElement('li');
        darkModeToggle.className = 'nav-item';
        darkModeToggle.innerHTML = `
            <a class="nav-link dark-mode-toggle" href="#" id="darkModeToggle">
                <i class="fas fa-moon"></i>
            </a>
        `;
        navbarNav.prepend(darkModeToggle);

        // Check for saved dark mode preference
        var darkMode = localStorage.getItem('darkMode') === 'enabled';
        if (darkMode) {
            document.body.classList.add('dark-mode');
            document.getElementById('darkModeToggle').innerHTML = '<i class="fas fa-sun"></i>';
        }

        // Add event listener for dark mode toggle
        document.getElementById('darkModeToggle').addEventListener('click', function(e) {
            e.preventDefault();
            if (document.body.classList.contains('dark-mode')) {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('darkMode', 'disabled');
                this.innerHTML = '<i class="fas fa-moon"></i>';
            } else {
                document.body.classList.add('dark-mode');
                localStorage.setItem('darkMode', 'enabled');
                this.innerHTML = '<i class="fas fa-sun"></i>';
            }
        });
    }
}

// Initialize loading indicators
function initLoadingIndicators() {
    // Create loading overlay
    var loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-container">
            <div class="loading-spinner"></div>
            <div class="spinner-text">Loading...</div>
        </div>
    `;
    document.body.appendChild(loadingOverlay);

    // Add loading indicator to forms
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            // Don't show loading for search forms
            if (!this.classList.contains('search-form')) {
                showLoading('Processing your request...');
            }
        });
    });

    // Add loading indicator to links that are not within the same page
    document.querySelectorAll('a:not([href^="#"])').forEach(function(link) {
        // Skip links with specific classes
        if (!link.classList.contains('dropdown-toggle') &&
            !link.classList.contains('nav-link') &&
            !link.getAttribute('href').startsWith('javascript:')) {
            link.addEventListener('click', function() {
                showLoading();
            });
        }
    });
}

// Show loading overlay
function showLoading(message) {
    var overlay = document.querySelector('.loading-overlay');
    if (message) {
        document.querySelector('.spinner-text').textContent = message;
    } else {
        document.querySelector('.spinner-text').textContent = 'Loading...';
    }
    overlay.classList.add('show');
}

// Hide loading overlay
function hideLoading() {
    var overlay = document.querySelector('.loading-overlay');
    overlay.classList.remove('show');
}

// Handle responsive layout
function handleResponsiveLayout() {
    // Adjust layout based on screen size
    function adjustLayout() {
        if (window.innerWidth < 768) {
            // Mobile layout adjustments
            document.querySelectorAll('.card-body').forEach(function(cardBody) {
                cardBody.style.padding = '1rem';
            });

            document.querySelectorAll('.table').forEach(function(table) {
                table.classList.add('table-sm');
            });
        } else {
            // Desktop layout adjustments
            document.querySelectorAll('.card-body').forEach(function(cardBody) {
                cardBody.style.padding = '';
            });

            document.querySelectorAll('.table').forEach(function(table) {
                table.classList.remove('table-sm');
            });
        }
    }

    // Initial adjustment
    adjustLayout();

    // Adjust on window resize
    window.addEventListener('resize', adjustLayout);
}
