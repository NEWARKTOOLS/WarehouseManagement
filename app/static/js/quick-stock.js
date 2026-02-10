/**
 * Quick Stock - Barcode scanning workflow for fast stock receipt
 * Flow: Scan Location → Scan Item (with auto qty) → Confirm & Add
 *
 * Uses html5-qrcode library (ZXing-based) which reliably handles:
 * - QR codes on iOS Safari
 * - CODE128, EAN, UPC barcodes
 * - Camera permissions on all platforms
 */
(function() {
    'use strict';

    // State
    let currentStep = 1;
    let selectedLocation = null;
    let selectedItem = null;
    let suggestedQty = 0;
    let sessionHistory = [];
    let lastScannedCode = '';
    let lastScanTime = 0;

    // Scanner instance
    let html5QrScanner = null;
    let currentScannerId = null;

    // DOM elements
    let modal, steps;

    function init() {
        modal = document.getElementById('quickStockModal');
        if (!modal) return;

        steps = {
            1: document.getElementById('qs-step1'),
            2: document.getElementById('qs-step2'),
            3: document.getElementById('qs-step3')
        };

        document.getElementById('qs-close')?.addEventListener('click', closeModal);
        document.getElementById('qs-manual-location')?.addEventListener('click', showLocationDropdown);
        document.getElementById('qs-manual-item')?.addEventListener('click', showItemSearch);
        document.getElementById('qs-change-location')?.addEventListener('click', () => goToStep(1));
        document.getElementById('qs-add-stock')?.addEventListener('click', addStock);
        document.getElementById('qs-add-more')?.addEventListener('click', addAndContinue);
        document.getElementById('qs-multiplier')?.addEventListener('input', updateTotal);
        document.getElementById('qs-qty-per-unit')?.addEventListener('input', updateTotal);

        document.getElementById('qs-location-select')?.addEventListener('change', function() {
            if (this.value) selectLocationById(this.value);
        });

        document.getElementById('qs-item-search')?.addEventListener('input', debounce(searchItems, 300));

        // Manual barcode entry (location - step 1)
        document.getElementById('qs-manual-barcode-btn')?.addEventListener('click', submitManualBarcode);
        document.getElementById('qs-manual-barcode')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') submitManualBarcode();
        });

        // Manual barcode entry (item - step 2)
        document.getElementById('qs-manual-barcode-item-btn')?.addEventListener('click', submitManualBarcodeItem);
        document.getElementById('qs-manual-barcode-item')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') submitManualBarcodeItem();
        });

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

        Object.values(steps).forEach(s => { if (s) s.style.display = 'none'; });
        if (steps[step]) steps[step].style.display = '';

        document.querySelectorAll('.qs-step-indicator').forEach(el => {
            const s = parseInt(el.dataset.step);
            el.classList.remove('active', 'completed');
            if (s === step) el.classList.add('active');
            if (s < step) el.classList.add('completed');
        });

        if (step === 1) {
            setTimeout(() => startScanner('qs-scanner-1'), 400);
            hideEl('qs-location-dropdown');
        }
        if (step === 2) {
            setTimeout(() => startScanner('qs-scanner-2'), 400);
            hideEl('qs-item-search-area');
            updateLocationDisplay();
        }
        if (step === 3) {
            updateConfirmDisplay();
        }
    }

    // ===== Scanner using html5-qrcode =====

    async function startScanner(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (typeof Html5Qrcode === 'undefined') {
            container.innerHTML = `<div class="text-center text-muted p-4">
                <i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>
                Scanner library not loaded<br><small>Use manual entry below</small>
            </div>`;
            return;
        }

        if (!window.isSecureContext) {
            container.innerHTML = `<div class="text-center text-muted p-4">
                <i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>
                Camera requires HTTPS<br><small>Use manual entry below</small>
            </div>`;
            return;
        }

        // Create a unique reader div inside the container
        const readerId = `qs-reader-${containerId}`;
        container.innerHTML = `<div id="${readerId}" style="width:100%;border-radius:8px;overflow:hidden;"></div>
            <div id="qs-status-${containerId}" class="text-center mt-2 small text-muted">Starting camera...</div>`;

        currentScannerId = readerId;

        try {
            html5QrScanner = new Html5Qrcode(readerId);

            const config = {
                fps: 10,
                qrbox: function(viewfinderWidth, viewfinderHeight) {
                    const minDim = Math.min(viewfinderWidth, viewfinderHeight);
                    return { width: Math.floor(minDim * 0.8), height: Math.floor(minDim * 0.6) };
                },
                aspectRatio: 1.333,
                formatsToSupport: [
                    Html5QrcodeSupportedFormats.QR_CODE,
                    Html5QrcodeSupportedFormats.CODE_128,
                    Html5QrcodeSupportedFormats.EAN_13,
                    Html5QrcodeSupportedFormats.EAN_8,
                    Html5QrcodeSupportedFormats.CODE_39,
                    Html5QrcodeSupportedFormats.UPC_A,
                    Html5QrcodeSupportedFormats.UPC_E
                ]
            };

            await html5QrScanner.start(
                { facingMode: "environment" },
                config,
                onScanSuccess,
                onScanFailure
            );

            const statusEl = document.getElementById(`qs-status-${containerId}`);
            if (statusEl) statusEl.textContent = 'Scanning for QR codes & barcodes...';

        } catch (err) {
            console.error('Scanner start error:', err);
            const statusEl = document.getElementById(`qs-status-${containerId}`);
            let msg = 'Camera not available';
            if (typeof err === 'string') {
                if (err.includes('NotAllowedError') || err.includes('Permission')) {
                    msg = 'Camera permission denied. Check Settings > Safari > Camera.';
                } else if (err.includes('NotFoundError')) {
                    msg = 'No camera found.';
                } else {
                    msg = err;
                }
            }
            container.innerHTML = `<div class="text-center text-muted p-4">
                <i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>
                ${msg}<br><small>Use manual entry below</small>
            </div>`;
        }
    }

    function onScanSuccess(decodedText, decodedResult) {
        const now = Date.now();
        // Debounce: ignore same code within 3 seconds
        if (decodedText === lastScannedCode && (now - lastScanTime) < 3000) return;
        lastScannedCode = decodedText;
        lastScanTime = now;

        if (navigator.vibrate) navigator.vibrate(100);
        processScannedCode(decodedText);
    }

    function onScanFailure(error) {
        // Ignore - this fires on every frame without a detection
    }

    function submitManualBarcode() {
        const input = document.getElementById('qs-manual-barcode');
        if (!input) return;
        const code = input.value.trim();
        if (!code) return;
        input.value = '';
        processScannedCode(code);
    }

    function submitManualBarcodeItem() {
        const input = document.getElementById('qs-manual-barcode-item');
        if (!input) return;
        const code = input.value.trim();
        if (!code) return;
        input.value = '';
        processScannedCode(code);
    }

    async function stopScanner() {
        if (html5QrScanner) {
            try {
                const state = html5QrScanner.getState();
                if (state === Html5QrcodeScannerState.SCANNING || state === Html5QrcodeScannerState.PAUSED) {
                    await html5QrScanner.stop();
                }
            } catch (e) {
                // May already be stopped
            }
            try {
                html5QrScanner.clear();
            } catch (e) {}
            html5QrScanner = null;
        }
        currentScannerId = null;
    }

    // ===== Process scanned code =====
    function processScannedCode(code) {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = csrfMeta ? csrfMeta.content : '';

        fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ barcode: code, context: 'receive' })
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(`Not found: ${code}`, 'warning');
                return;
            }

            if (currentStep === 1 && data.type === 'location') {
                selectLocation(data);
            } else if (currentStep === 1 && data.type === 'item') {
                showToast('That\'s an item barcode. Please scan a location first.', 'warning');
            } else if (currentStep === 2 && data.type === 'item') {
                selectItem(data);
            } else if (currentStep === 2 && data.type === 'location') {
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
            .catch(() => showToast('Failed to load location', 'error'));
    }

    function showLocationDropdown() {
        const area = document.getElementById('qs-location-dropdown');
        area.style.display = '';

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

        fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ barcode: query, context: 'receive' })
        })
        .then(r => { if (!r.ok) return { error: true }; return r.json(); })
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
        .catch(() => { results.innerHTML = '<div class="text-muted p-2">Search failed.</div>'; });
    }

    // ===== Display updates =====
    function updateLocationDisplay() {
        if (!selectedLocation) return;
        const el = document.getElementById('qs-selected-location');
        if (el) el.innerHTML = `<i class="bi bi-geo-alt me-1"></i> <strong>${selectedLocation.code}</strong> - ${selectedLocation.name || ''}`;
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

        document.getElementById('qs-total-qty').textContent = total.toLocaleString();
        document.getElementById('qs-total-unit').textContent = selectedItem?.unit || 'parts';

        const addBtn = document.getElementById('qs-add-stock');
        const addMoreBtn = document.getElementById('qs-add-more');
        if (addBtn) addBtn.disabled = total <= 0;
        if (addMoreBtn) addMoreBtn.disabled = total <= 0;
    }

    // ===== Add stock =====
    function addStock() { doAddStock(false); }
    function addAndContinue() { doAddStock(true); }

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
        const addBtn = document.getElementById('qs-add-stock');
        const addMoreBtn = document.getElementById('qs-add-more');
        if (addBtn) addBtn.disabled = true;
        if (addMoreBtn) addMoreBtn.disabled = true;

        fetch('/api/quick-receive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ item_id: selectedItem.id, location_id: selectedLocation.id, quantity: total })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                sessionHistory.unshift({
                    sku: selectedItem.sku, name: selectedItem.name,
                    qty: total, unit: selectedItem.unit,
                    location: selectedLocation.code, time: new Date().toLocaleTimeString()
                });
                updateHistoryDisplay();
                if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
                showToast(data.message, 'success');

                if (continueScanning) {
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
        .catch(() => {
            showToast('Network error. Try again.', 'error');
            if (addBtn) addBtn.disabled = false;
            if (addMoreBtn) addMoreBtn.disabled = false;
        });
    }

    // ===== History =====
    function updateHistoryDisplay() {
        const container = document.getElementById('qs-history');
        if (!container) return;
        if (sessionHistory.length === 0) { container.style.display = 'none'; return; }

        container.style.display = '';
        const list = document.getElementById('qs-history-list');
        list.innerHTML = '';
        sessionHistory.slice(0, 10).forEach(entry => {
            const li = document.createElement('li');
            li.className = 'list-group-item py-1 px-2 d-flex justify-content-between align-items-center';
            li.innerHTML = `<span><strong>${entry.sku}</strong> <small class="text-muted">${entry.name}</small></span>
                <span><span class="badge bg-success">${entry.qty.toLocaleString()} ${entry.unit}</span>
                <small class="text-muted ms-1">${entry.location}</small></span>`;
            list.appendChild(li);
        });
    }

    // ===== Helpers =====
    function hideEl(id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; }

    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 99999; min-width: 280px; max-width: 90vw; box-shadow: 0 4px 12px rgba(0,0,0,0.3);';
        toast.innerHTML = `${message}<button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function debounce(fn, delay) {
        let timer;
        return function(e) { clearTimeout(timer); timer = setTimeout(() => fn(e), delay); };
    }

    window.QuickStock = { open: openModal, init: init };
    document.addEventListener('DOMContentLoaded', init);
})();
