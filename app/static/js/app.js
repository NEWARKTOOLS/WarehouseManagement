// Warehouse Management System - Main JavaScript

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
    initializeSearch();
    initializeForms();
});

// Bootstrap tooltips
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
}

// Search functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('[data-search]');
    searchInputs.forEach(input => {
        let debounceTimer;
        input.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const searchType = this.dataset.search;
                performSearch(searchType, this.value);
            }, 300);
        });
    });
}

async function performSearch(type, query) {
    if (query.length < 2) return;

    try {
        const response = await fetch(`/api/${type}/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        displaySearchResults(type, data);
    } catch (error) {
        console.error('Search error:', error);
    }
}

function displaySearchResults(type, results) {
    const container = document.querySelector(`[data-search-results="${type}"]`);
    if (!container) return;

    container.innerHTML = results.map(item => `
        <a href="/${type}/${item.id}" class="list-group-item list-group-item-action">
            <strong>${item.sku || item.code || item.name}</strong>
            ${item.name ? `<br><small class="text-muted">${item.name}</small>` : ''}
        </a>
    `).join('');
}

// Form enhancements
function initializeForms() {
    // Auto-submit on select change
    document.querySelectorAll('select[data-auto-submit]').forEach(select => {
        select.addEventListener('change', function() {
            this.form.submit();
        });
    });

    // Quantity input controls
    document.querySelectorAll('[data-quantity-control]').forEach(container => {
        const input = container.querySelector('input');
        const minusBtn = container.querySelector('[data-minus]');
        const plusBtn = container.querySelector('[data-plus]');

        if (minusBtn) {
            minusBtn.addEventListener('click', () => {
                const min = parseFloat(input.min) || 0;
                const step = parseFloat(input.step) || 1;
                const value = parseFloat(input.value) || 0;
                input.value = Math.max(min, value - step);
                input.dispatchEvent(new Event('change'));
            });
        }

        if (plusBtn) {
            plusBtn.addEventListener('click', () => {
                const max = parseFloat(input.max) || Infinity;
                const step = parseFloat(input.step) || 1;
                const value = parseFloat(input.value) || 0;
                input.value = Math.min(max, value + step);
                input.dispatchEvent(new Event('change'));
            });
        }
    });
}

// Barcode Scanner
class BarcodeScanner {
    constructor(videoElement, onScan) {
        this.video = videoElement;
        this.onScan = onScan;
        this.stream = null;
        this.scanning = false;
    }

    async start() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });
            this.video.srcObject = this.stream;
            await this.video.play();
            this.scanning = true;
            this.scan();
        } catch (error) {
            console.error('Camera error:', error);
            alert('Unable to access camera. Please check permissions.');
        }
    }

    stop() {
        this.scanning = false;
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }

    scan() {
        if (!this.scanning) return;

        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = this.video.videoWidth;
        canvas.height = this.video.videoHeight;
        context.drawImage(this.video, 0, 0);

        // Use jsQR or similar library for barcode detection
        if (window.jsQR) {
            const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height);
            if (code) {
                this.onScan(code.data);
                // Pause briefly before next scan
                setTimeout(() => this.scan(), 1000);
                return;
            }
        }

        // Continue scanning
        requestAnimationFrame(() => this.scan());
    }
}

// API helper functions
const api = {
    async scan(barcode, context = 'lookup') {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ barcode, context })
        });
        return response.json();
    },

    async quickReceive(itemId, locationId, quantity, batchNumber = '') {
        const response = await fetch('/api/quick-receive', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                item_id: itemId,
                location_id: locationId,
                quantity: quantity,
                batch_number: batchNumber
            })
        });
        return response.json();
    },

    async quickMove(itemId, fromLocationId, toLocationId, quantity) {
        const response = await fetch('/api/quick-move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                item_id: itemId,
                from_location_id: fromLocationId,
                to_location_id: toLocationId,
                quantity: quantity
            })
        });
        return response.json();
    },

    async startProduction(orderId, machineId) {
        const response = await fetch('/api/production/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                order_id: orderId,
                machine_id: machineId
            })
        });
        return response.json();
    },

    async updateProduction(orderId, goodQty, rejectedQty) {
        const response = await fetch('/api/production/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                order_id: orderId,
                good_quantity: goodQty,
                rejected_quantity: rejectedQty
            })
        });
        return response.json();
    },

    async getDashboardStats() {
        const response = await fetch('/api/dashboard-stats');
        return response.json();
    }
};

// Get CSRF token from meta tag or cookie
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;

    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') return value;
    }
    return '';
}

// Format number for display
function formatNumber(num, decimals = 0) {
    return new Intl.NumberFormat('en-GB', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(num);
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-GB', {
        style: 'currency',
        currency: 'GBP'
    }).format(amount);
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed bottom-0 start-50 translate-middle-x mb-4`;
    toast.style.zIndex = '9999';
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Confirm dialog
function confirmAction(message) {
    return new Promise(resolve => {
        if (confirm(message)) {
            resolve(true);
        } else {
            resolve(false);
        }
    });
}

// Export for use in other scripts
window.WMS = {
    api,
    BarcodeScanner,
    formatNumber,
    formatCurrency,
    showToast,
    confirmAction
};
