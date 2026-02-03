from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.orders import Customer, SalesOrder

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/')
@login_required
def customer_list():
    """List all customers"""
    search = request.args.get('search', '').strip()

    query = Customer.query.filter_by(is_active=True)

    if search:
        query = query.filter(db.or_(
            Customer.customer_code.ilike(f'%{search}%'),
            Customer.name.ilike(f'%{search}%'),
            Customer.contact_name.ilike(f'%{search}%')
        ))

    customers = query.order_by(Customer.name).all()
    return render_template('customers/list.html', customers=customers, search=search)


@customers_bp.route('/new', methods=['GET', 'POST'])
@login_required
def customer_create():
    """Create new customer"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()

        if not name:
            flash('Customer name is required', 'error')
            return render_template('customers/form.html', customer=None)

        customer = Customer(
            customer_code=Customer.generate_customer_code(),
            name=name,
            contact_name=request.form.get('contact_name', '').strip(),
            email=request.form.get('email', '').strip(),
            phone=request.form.get('phone', '').strip(),
            address_line1=request.form.get('address_line1', '').strip(),
            address_line2=request.form.get('address_line2', '').strip(),
            city=request.form.get('city', '').strip(),
            county=request.form.get('county', '').strip(),
            postcode=request.form.get('postcode', '').strip(),
            country=request.form.get('country', 'United Kingdom').strip(),
            credit_terms=request.form.get('credit_terms', 30, type=int),
            credit_limit=request.form.get('credit_limit', type=float),
            tax_number=request.form.get('tax_number', '').strip(),
            special_requirements=request.form.get('special_requirements', '').strip(),
            is_jit=request.form.get('is_jit') == 'on'
        )

        # Billing address (if different)
        if request.form.get('different_billing'):
            customer.billing_address_line1 = request.form.get('billing_address_line1', '').strip()
            customer.billing_address_line2 = request.form.get('billing_address_line2', '').strip()
            customer.billing_city = request.form.get('billing_city', '').strip()
            customer.billing_county = request.form.get('billing_county', '').strip()
            customer.billing_postcode = request.form.get('billing_postcode', '').strip()
            customer.billing_country = request.form.get('billing_country', '').strip()

        db.session.add(customer)
        db.session.commit()

        flash(f'Customer {customer.name} created successfully', 'success')
        return redirect(url_for('customers.customer_detail', customer_id=customer.id))

    return render_template('customers/form.html', customer=None)


@customers_bp.route('/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    """View customer details"""
    customer = Customer.query.get_or_404(customer_id)
    recent_orders = customer.orders.order_by(SalesOrder.created_at.desc()).limit(10).all()
    order_stats = {
        'total_orders': customer.orders.count(),
        'pending_orders': customer.orders.filter(
            SalesOrder.status.in_(['new', 'in_production', 'ready_to_ship'])
        ).count()
    }

    return render_template('customers/detail.html',
                           customer=customer,
                           recent_orders=recent_orders,
                           order_stats=order_stats)


@customers_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def customer_edit(customer_id):
    """Edit customer"""
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip()
        customer.contact_name = request.form.get('contact_name', '').strip()
        customer.email = request.form.get('email', '').strip()
        customer.phone = request.form.get('phone', '').strip()
        customer.address_line1 = request.form.get('address_line1', '').strip()
        customer.address_line2 = request.form.get('address_line2', '').strip()
        customer.city = request.form.get('city', '').strip()
        customer.county = request.form.get('county', '').strip()
        customer.postcode = request.form.get('postcode', '').strip()
        customer.country = request.form.get('country', 'United Kingdom').strip()
        customer.credit_terms = request.form.get('credit_terms', 30, type=int)
        customer.credit_limit = request.form.get('credit_limit', type=float)
        customer.tax_number = request.form.get('tax_number', '').strip()
        customer.special_requirements = request.form.get('special_requirements', '').strip()
        customer.is_jit = request.form.get('is_jit') == 'on'

        # Billing address
        if request.form.get('different_billing'):
            customer.billing_address_line1 = request.form.get('billing_address_line1', '').strip()
            customer.billing_address_line2 = request.form.get('billing_address_line2', '').strip()
            customer.billing_city = request.form.get('billing_city', '').strip()
            customer.billing_county = request.form.get('billing_county', '').strip()
            customer.billing_postcode = request.form.get('billing_postcode', '').strip()
            customer.billing_country = request.form.get('billing_country', '').strip()

        db.session.commit()
        flash(f'Customer {customer.name} updated successfully', 'success')
        return redirect(url_for('customers.customer_detail', customer_id=customer.id))

    return render_template('customers/form.html', customer=customer)


@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
@login_required
def customer_delete(customer_id):
    """Delete (deactivate) customer"""
    if not current_user.is_admin():
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('customers.customer_list'))

    customer = Customer.query.get_or_404(customer_id)

    # Check for open orders
    open_orders = customer.orders.filter(
        SalesOrder.status.in_(['new', 'in_production', 'ready_to_ship'])
    ).count()

    if open_orders > 0:
        flash(f'Cannot delete customer with {open_orders} open orders', 'error')
        return redirect(url_for('customers.customer_detail', customer_id=customer.id))

    customer.is_active = False
    db.session.commit()

    flash(f'Customer {customer.name} has been deactivated', 'success')
    return redirect(url_for('customers.customer_list'))


# API endpoints
@customers_bp.route('/api/search')
@login_required
def api_search():
    """Search customers via API"""
    query = request.args.get('q', '').strip()

    customers = Customer.query.filter(
        Customer.is_active == True,
        db.or_(
            Customer.customer_code.ilike(f'%{query}%'),
            Customer.name.ilike(f'%{query}%')
        )
    ).limit(20).all()

    return jsonify([{
        'id': c.id,
        'customer_code': c.customer_code,
        'name': c.name,
        'is_jit': c.is_jit
    } for c in customers])


@customers_bp.route('/api/<int:customer_id>')
@login_required
def api_customer_detail(customer_id):
    """Get customer details via API"""
    customer = Customer.query.get_or_404(customer_id)

    return jsonify({
        'id': customer.id,
        'customer_code': customer.customer_code,
        'name': customer.name,
        'contact_name': customer.contact_name,
        'email': customer.email,
        'phone': customer.phone,
        'address': {
            'line1': customer.address_line1,
            'line2': customer.address_line2,
            'city': customer.city,
            'county': customer.county,
            'postcode': customer.postcode,
            'country': customer.country
        },
        'is_jit': customer.is_jit,
        'credit_terms': customer.credit_terms
    })
