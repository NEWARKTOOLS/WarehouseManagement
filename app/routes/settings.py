import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.settings import CompanySettings

settings_bp = Blueprint('settings', __name__)


def allowed_file(filename):
    """Check if file extension is allowed for logos"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@settings_bp.route('/')
@login_required
def index():
    """Settings overview"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    settings = CompanySettings.get_settings()
    return render_template('settings/index.html', settings=settings)


@settings_bp.route('/company', methods=['GET', 'POST'])
@login_required
def company():
    """Company settings"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    settings = CompanySettings.get_settings()

    if request.method == 'POST':
        settings.company_name = request.form.get('company_name', '').strip()
        settings.trading_name = request.form.get('trading_name', '').strip()
        settings.company_number = request.form.get('company_number', '').strip()
        settings.vat_number = request.form.get('vat_number', '').strip()

        settings.address_line1 = request.form.get('address_line1', '').strip()
        settings.address_line2 = request.form.get('address_line2', '').strip()
        settings.city = request.form.get('city', '').strip()
        settings.county = request.form.get('county', '').strip()
        settings.postcode = request.form.get('postcode', '').strip()
        settings.country = request.form.get('country', '').strip()

        settings.phone = request.form.get('phone', '').strip()
        settings.email = request.form.get('email', '').strip()
        settings.website = request.form.get('website', '').strip()

        settings.bank_name = request.form.get('bank_name', '').strip()
        settings.account_name = request.form.get('account_name', '').strip()
        settings.sort_code = request.form.get('sort_code', '').strip()
        settings.account_number = request.form.get('account_number', '').strip()
        settings.iban = request.form.get('iban', '').strip()
        settings.swift_bic = request.form.get('swift_bic', '').strip()

        settings.packing_list_footer = request.form.get('packing_list_footer', '').strip()
        settings.packing_list_terms = request.form.get('packing_list_terms', '').strip()

        # Handle logo upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Prefix with 'logo_' to identify
                filename = f'logo_{filename}'
                upload_path = os.path.join(current_app.root_path, 'static', 'img', filename)
                file.save(upload_path)
                settings.logo_filename = filename

        db.session.commit()
        flash('Company settings saved successfully', 'success')
        return redirect(url_for('settings.index'))

    return render_template('settings/company.html', settings=settings)


@settings_bp.route('/logo/remove', methods=['POST'])
@login_required
def remove_logo():
    """Remove company logo"""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('settings.index'))

    settings = CompanySettings.get_settings()

    if settings.logo_filename:
        # Try to delete the file
        try:
            logo_path = os.path.join(current_app.root_path, 'static', 'img', settings.logo_filename)
            if os.path.exists(logo_path):
                os.remove(logo_path)
        except Exception:
            pass

        settings.logo_filename = None
        db.session.commit()
        flash('Logo removed', 'success')

    return redirect(url_for('settings.company'))


@settings_bp.route('/packing-list', methods=['GET', 'POST'])
@login_required
def packing_list():
    """Packing list template settings"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    settings = CompanySettings.get_settings()

    if request.method == 'POST':
        settings.packing_list_title = request.form.get('packing_list_title', 'PACKING LIST').strip()
        settings.packing_list_footer = request.form.get('packing_list_footer', '').strip()
        settings.packing_list_terms = request.form.get('packing_list_terms', '').strip()
        settings.packing_list_show_prices = 'packing_list_show_prices' in request.form
        settings.packing_list_show_signature = 'packing_list_show_signature' in request.form
        settings.packing_list_show_bank_details = 'packing_list_show_bank_details' in request.form

        db.session.commit()
        flash('Packing list settings saved successfully', 'success')
        return redirect(url_for('settings.packing_list'))

    return render_template('settings/packing_list.html', settings=settings)


@settings_bp.route('/labels', methods=['GET', 'POST'])
@login_required
def labels():
    """Label format settings"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

    settings = CompanySettings.get_settings()

    if request.method == 'POST':
        # Label content toggles (checkboxes - not present = False)
        # Note: label size is now selected on the print page, not in settings
        settings.label_show_company = 'label_show_company' in request.form
        settings.label_show_sku = 'label_show_sku' in request.form
        settings.label_show_name = 'label_show_name' in request.form
        settings.label_show_barcode = 'label_show_barcode' in request.form
        settings.label_show_quantity = 'label_show_quantity' in request.form
        settings.label_show_image = 'label_show_image' in request.form

        db.session.commit()
        flash('Label settings saved successfully', 'success')
        return redirect(url_for('settings.labels'))

    return render_template('settings/labels.html',
                           settings=settings,
                           company_name=settings.company_name)
