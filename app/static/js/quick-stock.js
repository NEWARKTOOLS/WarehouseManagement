/**
 * Quick Stock - Barcode scanning workflow for fast stock receipt
 * Flow: Scan Location → Scan Item (with auto qty) → Confirm & Add
 */
(function() {
    'use strict';

    // State
    let currentStep = 1;
    let selectedLocation = null;
    let selectedItem = null;
    let suggestedQty = 0;
    let sessionHistory = [];
    let scannerActive = false;
    let lastScannedCode = '';
    let lastScanTime = 0;

    // DOM elements (populated on init)
    let modal, steps, locationInfo, itemInfo;

    function init() {
        modal = document.getElementById('quickStockModal');
        if (!modal) return;

        steps = {
            1: document.getElementById('qs-step1'),
            2: document.getElementById('qs-step2'),
            3: document.getElementById('qs-step3')
        };

        // Bind events
        document.getElementById('qs-close')?.addEventListener('click', closeModal);
        document.getElementById('qs-manual-location')?.addEventListener('click', showLocationDropdown);
        document.getElementById('qs-manual-item')?.addEventListener('click', showItemSearch);
        document.getElementById('qs-change-location')?.addEventListener('click', () => goToStep(1));
        document.getElementById('qs-add-stock')?.addEventListener('click', addStock);
        document.getElementById('qs-add-more')?.addEventListener('click', addAndContinue);

        // Multiplier calculation
        document.getElementById('qs-multiplier')?.addEventListener('input', updateTotal);
        document.getElementById('qs-qty-per-unit')?.addEventListener('input', updateTotal);

        // Manual location select
        document.getElementById('qs-location-select')?.addEventListener('change', function() {
            if (this.value) {
                selectLocationById(this.value);
            }
        });

        // Manual item search
        document.getElementById('qs-item-search')?.addEventListener('input', debounce(searchItems, 300));

        // Listen for modal show/hide
        modal.addEventListener('shown.bs.modal', onModalShown);
        modal.addEventListener('hidden.bs.modal', onModalHidden);
    }

    function openModal() {
        if (!modal) init();
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    function closeModal() {
        const bsModal = bootstrap.Modal.getInstance(modal);
        if (bsModal) bsModal.hide();
    }

    function onModalShown() {
        resetState();
        goToStep(1);
        startScanner('qs-scanner-1');
    }

    function onModalHidden() {
        stopScanner();
        resetState();
    }

    function resetState() {
        selectedLocation = null;
        selectedItem = null;
        suggestedQty = 0;
        lastScannedCode = '';
    }

    // ===== Step management =====
    function goToStep(step) {
        currentStep = step;
        stopScanner();

        // Hide all steps
        Object.values(steps).forEach(s => { if (s) s.style.display = 'none'; });

        // Show current step
        if (steps[step]) steps[step].style.display = '';

        // Update step indicators
        document.querySelectorAll('.qs-step-indicator').forEach(el => {
            const s = parseInt(el.dataset.step);
            el.classList.remove('active', 'completed');
            if (s === step) el.classList.add('active');
            if (s < step) el.classList.add('completed');
        });

        // Start scanner for the current step
        if (step === 1) {
            setTimeout(() => startScanner('qs-scanner-1'), 300);
            hideEl('qs-location-dropdown');
        }
        if (step === 2) {
            setTimeout(() => startScanner('qs-scanner-2'), 300);
            hideEl('qs-item-search-area');
            updateLocationDisplay();
        }
        if (step === 3) {
            updateConfirmDisplay();
        }
    }

    // ===== Scanner =====
    function startScanner(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        // Check if Quagga is available
        if (typeof Quagga === 'undefined') {
            console.log('QuaggaJS not loaded, manual entry only');
            return;
        }

        scannerActive = true;
        container.innerHTML = '<div id="qs-scanner-viewport" style="width:100%;height:250px;position:relative;overflow:hidden;border-radius:8px;background:#000;"></div>';

        try {
            Quagga.init({
                inputStream: {
                    name: "Live",
                    type: "LiveStream",
                    target: document.getElementById('qs-scanner-viewport'),
                    constraints: {
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        facingMode: "environment"
                    }
                },
                decoder: {
                    readers: ["code_128_reader", "ean_reader", "ean_8_reader", "code_39_reader", "upc_reader", "qr_reader"]
                },
                locate: true,
                frequency: 10
            }, function(err) {
                if (err) {
                    console.log('Scanner init error:', err);
                    container.innerHTML = '<div class="text-center text-muted p-4"><i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>Camera not available<br><small>Use manual entry below</small></div>';
                    return;
                }
                Quagga.start();
            });

            Quagga.onDetected(onBarcodeDetected);
        } catch (e) {
            console.log('Scanner error:', e);
            container.innerHTML = '<div class="text-center text-muted p-4"><i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>Camera not available<br><small>Use manual entry below</small></div>';
        }
    }

    function stopScanner() {
        if (scannerActive && typeof Quagga !== 'undefined') {
            try {
                Quagga.offDetected(onBarcodeDetected);
                Quagga.stop();
            } catch(e) {}
        }
        scannerActive = false;
    }

    function onBarcodeDetected(result) {
        const code = result.codeResult.code;
        const now = Date.now();

        // Debounce: ignore same code within 3 seconds
        if (code === lastScannedCode && (now - lastScanTime) < 3000) return;
        lastScannedCode = code;
        lastScanTime = now;

        // Vibrate on scan
        if (navigator.vibrate) navigator.vibrate(100);

        processScannedCode(code);
    }

    function processScannedCode(code) {
        // Get CSRF token
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.content : '';

        const context = currentStep === 1 ? 'receive' : 'receive';

        fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ barcode: code, context: context })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(`Not found: ${code}`, 'warning');
                return;
            }

            if (currentStep === 1 && data.type === 'location') {
                // Location scanned in step 1 - perfect
                selectLocation(data);
            } else if (currentStep === 1 && data.type === 'item') {
                showToast('That\'s an item barcode. Please scan a location first.', 'warning');
            } else if (currentStep === 2 && data.type === 'item') {
                // Item scanned in step 2 - perfect
                selectItem(data);
            } else if (currentStep === 2 && data.type === 'location') {
                // Location scanned in step 2 - switch location
                selectLocation(data);
                showToast(`Location changed to ${data.code}`, 'info');
            }
        })
        .catch(err => {
            console.error('Scan error:', err);
            showToast('Scan failed. Try again.', 'error');
        });
    }

    // ===== Location selection =====
    function selectLocation(data) {
        selectedLocation = data;
        stopScanner();
        goToStep(2);
    }

    function selectLocationById(locationId) {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.content : '';

        fetch(`/locations/api/${locationId}/contents`)
            .then(r => r.json())
            .then(data => {
                selectedLocation = {
                    type: 'location',
                    id: data.location.id,
                    code: data.location.code,
                    name: data.location.name,
                    contents: data.contents
                };
                goToStep(2);
            })
            .catch(err => {
                showToast('Failed to load location', 'error');
            });
    }

    function showLocationDropdown() {
        const area = document.getElementById('qs-location-dropdown');
        area.style.display = '';

        // Load locations if not already loaded
        const select = document.getElementById('qs-location-select');
        if (select.options.length <= 1) {
            fetch('/locations/api/search?q=')
                .then(r => r.json())
                .then(locations => {
                    locations.forEach(loc => {
                        const opt = document.createElement('option');
                        opt.value = loc.id;
                        opt.textContent = `${loc.code} - ${loc.name}`;
                        select.appendChild(opt);
                    });
                });
        }
    }

    // ===== Item selection =====
    function selectItem(data) {
        selectedItem = data;
        suggestedQty = data.suggested_qty || 0;
        stopScanner();
        goToStep(3);
    }

    function showItemSearch() {
        const area = document.getElementById('qs-item-search-area');
        area.style.display = '';
        document.getElementById('qs-item-search')?.focus();
    }

    function searchItems(e) {
        const query = e.target.value.trim();
        if (query.length < 2) return;

        const results = document.getElementById('qs-item-results');
        results.innerHTML = '<div class="text-muted p-2">Searching...</div>';

        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.content : '';

        // Use the scan endpoint with the search term
        fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ barcode: query, context: 'receive' })
        })
        .then(r => {
            if (!r.ok) {
                // If not found by barcode, try a search
                return { error: true };
            }
            return r.json();
        })
        .then(data => {
            if (data.error) {
                results.innerHTML = '<div class="text-muted p-2">No items found. Try a different search.</div>';
                return;
            }
            if (data.type === 'item') {
                results.innerHTML = '';
                const btn = document.createElement('button');
                btn.className = 'list-group-item list-group-item-action';
                btn.innerHTML = `<strong>${data.sku}</strong> - ${data.name} <span class="text-muted">(Stock: ${data.total_stock})</span>`;
                btn.addEventListener('click', () => selectItem(data));
                results.appendChild(btn);
            }
        })
        .catch(() => {
            results.innerHTML = '<div class="text-muted p-2">Search failed. Try again.</div>';
        });
    }

    // ===== Display updates =====
    function updateLocationDisplay() {
        if (!selectedLocation) return;
        const el = document.getElementById('qs-selected-location');
        if (el) {
            el.innerHTML = `<i class="bi bi-geo-alt me-1"></i> <strong>${selectedLocation.code}</strong> - ${selectedLocation.name || ''}`;
        }
    }

    function updateConfirmDisplay() {
        if (!selectedItem || !selectedLocation) return;

        document.getElementById('qs-confirm-location').textContent = selectedLocation.code;
        document.getElementById('qs-confirm-item').textContent = `${selectedItem.sku} - ${selectedItem.name}`;
        document.getElementById('qs-confirm-unit').textContent = selectedItem.unit || 'parts';

        const qtyInput = document.getElementById('qs-qty-per-unit');
        const multiplierInput = document.getElementById('qs-multiplier');

        if (suggestedQty > 0) {
            qtyInput.value = suggestedQty;
            document.getElementById('qs-qty-source').textContent = '(from label)';
            document.getElementById('qs-qty-source').style.display = '';
        } else {
            qtyInput.value = '';
            qtyInput.focus();
            document.getElementById('qs-qty-source').style.display = 'none';
        }

        multiplierInput.value = 1;
        updateTotal();
    }

    function updateTotal() {
        const qty = parseInt(document.getElementById('qs-qty-per-unit')?.value) || 0;
        const mult = parseInt(document.getElementById('qs-multiplier')?.value) || 1;
        const total = qty * mult;
        const unit = selectedItem?.unit || 'parts';

        document.getElementById('qs-total-qty').textContent = total.toLocaleString();
        document.getElementById('qs-total-unit').textContent = unit;

        // Enable/disable add button
        const addBtn = document.getElementById('qs-add-stock');
        const addMoreBtn = document.getElementById('qs-add-more');
        if (addBtn) addBtn.disabled = total <= 0;
        if (addMoreBtn) addMoreBtn.disabled = total <= 0;
    }

    // ===== Add stock =====
    function addStock() {
        doAddStock(false);
    }

    function addAndContinue() {
        doAddStock(true);
    }

    function doAddStock(continueScanning) {
        const qty = parseInt(document.getElementById('qs-qty-per-unit')?.value) || 0;
        const mult = parseInt(document.getElementById('qs-multiplier')?.value) || 1;
        const total = qty * mult;

        if (total <= 0 || !selectedItem || !selectedLocation) {
            showToast('Invalid quantity', 'error');
            return;
        }

        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.content : '';

        // Disable buttons during request
        const addBtn = document.getElementById('qs-add-stock');
        const addMoreBtn = document.getElementById('qs-add-more');
        if (addBtn) addBtn.disabled = true;
        if (addMoreBtn) addMoreBtn.disabled = true;

        fetch('/api/quick-receive', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                item_id: selectedItem.id,
                location_id: selectedLocation.id,
                quantity: total
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // Add to session history
                sessionHistory.unshift({
                    sku: selectedItem.sku,
                    name: selectedItem.name,
                    qty: total,
                    unit: selectedItem.unit,
                    location: selectedLocation.code,
                    time: new Date().toLocaleTimeString()
                });
                updateHistoryDisplay();

                if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                showToast(data.message, 'success');

                if (continueScanning) {
                    // Reset item but keep location
                    selectedItem = null;
                    suggestedQty = 0;
                    goToStep(2);
                } else {
                    closeModal();
                }
            } else {
                showToast(data.error || 'Failed to add stock', 'error');
                if (addBtn) addBtn.disabled = false;
                if (addMoreBtn) addMoreBtn.disabled = false;
            }
        })
        .catch(err => {
            showToast('Network error. Try again.', 'error');
            if (addBtn) addBtn.disabled = false;
            if (addMoreBtn) addMoreBtn.disabled = false;
        });
    }

    // ===== History display =====
    function updateHistoryDisplay() {
        const container = document.getElementById('qs-history');
        if (!container) return;

        if (sessionHistory.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = '';
        const list = document.getElementById('qs-history-list');
        list.innerHTML = '';

        sessionHistory.slice(0, 10).forEach(entry => {
            const li = document.createElement('li');
            li.className = 'list-group-item py-1 px-2 d-flex justify-content-between align-items-center';
            li.innerHTML = `
                <span><strong>${entry.sku}</strong> <small class="text-muted">${entry.name}</small></span>
                <span>
                    <span class="badge bg-success">${entry.qty.toLocaleString()} ${entry.unit}</span>
                    <small class="text-muted ms-1">${entry.location}</small>
                </span>
            `;
            list.appendChild(li);
        });
    }

    // ===== Helpers =====
    function hideEl(id) {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }

    function showToast(message, type) {
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 99999; min-width: 300px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);';
        toast.innerHTML = `${message}<button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function debounce(fn, delay) {
        let timer;
        return function(e) {
            clearTimeout(timer);
            timer = setTimeout(() => fn(e), delay);
        };
    }

    // Expose globally
    window.QuickStock = {
        open: openModal,
        init: init
    };

    // Init on DOM ready
    document.addEventListener('DOMContentLoaded', init);
})();
