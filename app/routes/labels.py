from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from app import db
from app.models.inventory import Item
from app.models.settings import CompanySettings

labels_bp = Blueprint('labels', __name__)


@labels_bp.route('/')
@login_required
def label_list():
    """Label printing page - select items to print labels"""
    items = Item.query.filter_by(is_active=True).order_by(Item.sku).all()
    company = CompanySettings.get_settings()

    return render_template('labels/index.html', items=items, company=company)


@labels_bp.route('/preview', methods=['POST'])
@login_required
def label_preview():
    """Preview labels before printing"""
    item_ids = request.form.getlist('item_ids')
    quantities = {}

    # Get quantities for each item (empty/0 = blank for write-in)
    for item_id in item_ids:
        qty_key = f'qty_{item_id}'
        qty_str = request.form.get(qty_key, '').strip()
        # Empty or 0 means blank label for manual entry
        qty = int(qty_str) if qty_str and qty_str != '0' else None
        quantities[int(item_id)] = qty

    if not item_ids:
        flash('Please select at least one item', 'error')
        return redirect(url_for('labels.label_list'))

    items = Item.query.filter(Item.id.in_([int(i) for i in item_ids])).all()
    company = CompanySettings.get_settings()

    # Get label format settings
    label_format = {
        'show_company': company.label_show_company if company else True,
        'show_sku': company.label_show_sku if company else True,
        'show_name': company.label_show_name if company else True,
        'show_barcode': company.label_show_barcode if company else True,
        'show_quantity': company.label_show_quantity if company else True,
        'show_image': company.label_show_image if company else False,
        'label_width': company.label_width if company else 89,
        'label_height': company.label_height if company else 36,
    }

    return render_template('labels/preview.html',
                           items=items,
                           quantities=quantities,
                           company=company,
                           label_format=label_format)


@labels_bp.route('/print', methods=['POST'])
@login_required
def label_print():
    """Generate printable label page"""
    item_ids = request.form.getlist('item_ids')
    quantities = {}
    copies = {}

    for item_id in item_ids:
        qty_key = f'qty_{item_id}'
        copies_key = f'copies_{item_id}'
        qty_str = request.form.get(qty_key, '').strip()
        # Empty or 0 means blank label for manual entry
        quantities[int(item_id)] = int(qty_str) if qty_str and qty_str != '0' else None
        copies[int(item_id)] = request.form.get(copies_key, 1, type=int)

    if not item_ids:
        flash('Please select at least one item', 'error')
        return redirect(url_for('labels.label_list'))

    items = Item.query.filter(Item.id.in_([int(i) for i in item_ids])).all()
    company = CompanySettings.get_settings()

    label_format = {
        'show_company': company.label_show_company if company else True,
        'show_sku': company.label_show_sku if company else True,
        'show_name': company.label_show_name if company else True,
        'show_barcode': company.label_show_barcode if company else True,
        'show_quantity': company.label_show_quantity if company else True,
        'show_image': company.label_show_image if company else False,
        'label_width': company.label_width if company else 89,
        'label_height': company.label_height if company else 36,
    }

    return render_template('labels/print.html',
                           items=items,
                           quantities=quantities,
                           copies=copies,
                           company=company,
                           label_format=label_format)


@labels_bp.route('/quick/<int:item_id>')
@login_required
def quick_label(item_id):
    """Quick print single label for an item"""
    item = Item.query.get_or_404(item_id)
    company = CompanySettings.get_settings()
    quantity = request.args.get('qty', 1, type=int)
    copies = request.args.get('copies', 1, type=int)

    label_format = {
        'show_company': company.label_show_company if company else True,
        'show_sku': company.label_show_sku if company else True,
        'show_name': company.label_show_name if company else True,
        'show_barcode': company.label_show_barcode if company else True,
        'show_quantity': company.label_show_quantity if company else True,
        'show_image': company.label_show_image if company else False,
        'label_width': company.label_width if company else 89,
        'label_height': company.label_height if company else 36,
    }

    return render_template('labels/print.html',
                           items=[item],
                           quantities={item.id: quantity},
                           copies={item.id: copies},
                           company=company,
                           label_format=label_format)


# API endpoint for barcode data
@labels_bp.route('/api/barcode/<int:item_id>')
@login_required
def api_barcode(item_id):
    """Get barcode data URL for an item"""
    from app.utils.barcode import get_barcode_data_url

    item = Item.query.get_or_404(item_id)
    barcode_code = item.barcode or item.sku

    data_url = get_barcode_data_url(barcode_code)

    return jsonify({
        'item_id': item.id,
        'sku': item.sku,
        'barcode': barcode_code,
        'data_url': data_url
    })
