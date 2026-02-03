from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas


def generate_packing_list(order):
    """
    Generate a packing list PDF for a sales order

    Args:
        order: SalesOrder object

    Returns:
        BytesIO buffer containing the PDF
    """
    from flask import current_app
    from app.models.settings import CompanySettings
    import os

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    story = []

    # Get company settings
    settings = CompanySettings.get_settings()

    # Company header with logo
    company_info = []

    # Try to add logo if exists
    if settings.logo_filename:
        logo_path = os.path.join(current_app.root_path, 'static', 'img', settings.logo_filename)
        if os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=4*cm, height=2*cm)
                logo.hAlign = 'LEFT'
                company_info.append(logo)
            except Exception:
                pass

    # Company details
    company_text = []
    if settings.company_name:
        company_text.append(f"<b>{settings.company_name}</b>")
    if settings.address_line1:
        company_text.append(settings.address_line1)
    if settings.address_line2:
        company_text.append(settings.address_line2)
    city_line = ' '.join(filter(None, [settings.city, settings.postcode]))
    if city_line:
        company_text.append(city_line)
    if settings.phone:
        company_text.append(f"Tel: {settings.phone}")
    if settings.email:
        company_text.append(settings.email)
    if settings.vat_number:
        company_text.append(f"VAT: {settings.vat_number}")

    if company_text:
        company_para = Paragraph("<br/>".join(company_text), styles['Normal'])
        story.append(company_para)
        story.append(Spacer(1, 15))

    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=1,  # Center
        spaceAfter=20
    )
    title_text = settings.packing_list_title if settings.packing_list_title else 'PACKING LIST'
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 10))

    # Order info
    info_style = styles['Normal']
    info_data = [
        ['Order Number:', order.order_number],
        ['Date:', datetime.now().strftime('%d/%m/%Y')],
        ['Customer PO:', order.customer_po or '-'],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 8*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Customer and delivery info side by side
    customer = order.customer
    customer_info = [
        Paragraph("<b>CUSTOMER</b>", styles['Normal']),
        Paragraph(customer.name, styles['Normal']),
        Paragraph(customer.address_line1 or '', styles['Normal']),
        Paragraph(customer.address_line2 or '', styles['Normal']) if customer.address_line2 else None,
        Paragraph(f"{customer.city or ''} {customer.postcode or ''}", styles['Normal']),
    ]
    customer_info = [p for p in customer_info if p is not None]

    delivery_info = [
        Paragraph("<b>DELIVERY ADDRESS</b>", styles['Normal']),
        Paragraph(order.delivery_address_line1 or customer.address_line1 or '', styles['Normal']),
        Paragraph(order.delivery_address_line2 or '', styles['Normal']) if order.delivery_address_line2 else None,
        Paragraph(f"{order.delivery_city or ''} {order.delivery_postcode or ''}", styles['Normal']),
    ]
    delivery_info = [p for p in delivery_info if p is not None]

    address_data = [[customer_info, delivery_info]]
    address_table = Table(address_data, colWidths=[8*cm, 8*cm])
    address_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(address_table)
    story.append(Spacer(1, 20))

    # Line items
    story.append(Paragraph("<b>ITEMS</b>", styles['Normal']))
    story.append(Spacer(1, 10))

    # Check if we should show prices
    show_prices = getattr(settings, 'packing_list_show_prices', False)

    # Table header
    if show_prices:
        items_data = [['Line', 'SKU', 'Description', 'Qty', 'Unit', 'Price', 'Total']]
    else:
        items_data = [['Line', 'SKU', 'Description', 'Qty', 'Unit']]

    # Add line items
    for line in order.lines:
        # Handle custom items vs stock items
        if line.is_custom_item:
            sku = line.custom_sku or 'CUSTOM'
            description = line.custom_description or ''
            unit = 'each'
        else:
            sku = line.item.sku if line.item else '-'
            description = line.item.name if line.item else '-'
            unit = line.item.unit_of_measure if line.item else 'each'

        row = [
            str(line.line_number),
            sku,
            Paragraph(description, styles['Normal']),
            str(int(line.quantity_ordered)),
            unit
        ]
        if show_prices:
            unit_price = line.unit_price or 0
            line_total = line.line_total or (line.quantity_ordered * unit_price)
            row.extend([
                f"£{unit_price:.2f}",
                f"£{line_total:.2f}"
            ])
        items_data.append(row)

    # Set column widths based on whether prices are shown
    if show_prices:
        col_widths = [1*cm, 2.5*cm, 5.5*cm, 1.5*cm, 2*cm, 2*cm, 2.5*cm]
    else:
        col_widths = [1.5*cm, 3*cm, 7*cm, 2*cm, 2.5*cm]

    items_table = Table(items_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Line number
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Quantity
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),  # Unit
        ('ALIGN', (5, 1), (-1, -1), 'RIGHT') if show_prices else ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # Price columns

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(items_table)

    # Show order totals if prices are enabled
    if show_prices:
        story.append(Spacer(1, 10))
        total_style = ParagraphStyle('Total', parent=styles['Normal'], fontSize=10, alignment=2)

        # Subtotal
        subtotal = order.subtotal or 0
        story.append(Paragraph(f"Subtotal: £{subtotal:.2f}", total_style))

        # Shipping cost
        shipping = order.shipping_cost or 0
        if shipping > 0:
            story.append(Paragraph(f"Shipping: £{shipping:.2f}", total_style))

        # VAT
        tax_amount = order.tax_amount or 0
        if tax_amount > 0:
            tax_rate = order.tax_rate or 20
            story.append(Paragraph(f"VAT ({int(tax_rate)}%): £{tax_amount:.2f}", total_style))

        # Grand total
        total = order.total or 0
        total_bold_style = ParagraphStyle('TotalBold', parent=styles['Normal'], fontSize=12, alignment=2)
        story.append(Paragraph(f"<b>Total: £{total:.2f}</b>", total_bold_style))

    story.append(Spacer(1, 20))

    # Delivery instructions
    if order.delivery_instructions:
        story.append(Paragraph("<b>DELIVERY INSTRUCTIONS</b>", styles['Normal']))
        story.append(Spacer(1, 5))
        story.append(Paragraph(order.delivery_instructions, styles['Normal']))
        story.append(Spacer(1, 20))

    # Signature section (optional)
    show_signature = getattr(settings, 'packing_list_show_signature', True)
    if show_signature:
        story.append(Spacer(1, 30))
        sig_data = [
            ['Packed by:', '_' * 30, 'Date:', '_' * 20],
            ['', '', '', ''],
            ['Received by:', '_' * 30, 'Date:', '_' * 20],
        ]
        sig_table = Table(sig_data, colWidths=[3*cm, 5*cm, 2*cm, 4*cm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        story.append(sig_table)

    # Bank details (optional)
    show_bank = getattr(settings, 'packing_list_show_bank_details', False)
    if show_bank and settings.bank_name and settings.account_number:
        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>BANK DETAILS</b>", styles['Normal']))
        bank_text = []
        if settings.bank_name:
            bank_text.append(f"Bank: {settings.bank_name}")
        if settings.account_name:
            bank_text.append(f"Account Name: {settings.account_name}")
        if settings.sort_code:
            bank_text.append(f"Sort Code: {settings.sort_code}")
        if settings.account_number:
            bank_text.append(f"Account No: {settings.account_number}")
        story.append(Paragraph("<br/>".join(bank_text), styles['Normal']))

    # Footer text
    if settings.packing_list_footer:
        story.append(Spacer(1, 20))
        story.append(Paragraph(settings.packing_list_footer, styles['Normal']))

    # Terms
    if settings.packing_list_terms:
        story.append(Spacer(1, 10))
        terms_style = ParagraphStyle('Terms', parent=styles['Normal'], fontSize=8)
        story.append(Paragraph(f"<i>{settings.packing_list_terms}</i>", terms_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_labels_pdf(items_data, label_size='avery_l7163'):
    """
    Generate a PDF with labels (Avery compatible)

    Args:
        items_data: List of dicts with 'sku', 'name', 'barcode', 'location'
        label_size: Label format (default: Avery L7163 - 14 labels per sheet)

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()

    # Avery L7163 dimensions (14 labels per A4 sheet)
    # 2 columns, 7 rows
    label_width = 99.1 * mm
    label_height = 38.1 * mm
    margin_left = 4.65 * mm
    margin_top = 15 * mm
    col_gap = 2.5 * mm

    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    label_index = 0
    labels_per_page = 14

    for item in items_data:
        # Calculate position
        page_label = label_index % labels_per_page
        col = page_label % 2
        row = page_label // 2

        x = margin_left + col * (label_width + col_gap)
        y = page_height - margin_top - (row + 1) * label_height

        # Draw label content
        c.setFont('Helvetica-Bold', 12)
        c.drawString(x + 3*mm, y + label_height - 8*mm, item.get('sku', ''))

        c.setFont('Helvetica', 9)
        name = item.get('name', '')
        if len(name) > 40:
            name = name[:37] + '...'
        c.drawString(x + 3*mm, y + label_height - 14*mm, name)

        # Location
        c.setFont('Helvetica', 10)
        c.drawString(x + 3*mm, y + 5*mm, f"Location: {item.get('location', '-')}")

        # Barcode placeholder (you would integrate actual barcode here)
        c.setFont('Helvetica', 8)
        c.drawString(x + label_width - 35*mm, y + 5*mm, item.get('barcode', item.get('sku', '')))

        label_index += 1

        # New page if needed
        if label_index % labels_per_page == 0 and label_index < len(items_data):
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer
