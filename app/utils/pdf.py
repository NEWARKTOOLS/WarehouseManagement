from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Brand / theme colours used throughout the packing list
# ---------------------------------------------------------------------------
_PRIMARY = colors.HexColor('#1a3e5c')       # Dark navy header bar
_PRIMARY_LIGHT = colors.HexColor('#e8edf2')  # Very light blue tint
_ACCENT = colors.HexColor('#2980b9')         # Accent blue for highlights
_ROW_ALT = colors.HexColor('#f5f7fa')        # Alternating row background
_BORDER = colors.HexColor('#c0c8d1')         # Subtle table borders
_TEXT_DARK = colors.HexColor('#1a1a1a')       # Primary text colour
_TEXT_MID = colors.HexColor('#555555')        # Secondary text colour
_WARNING_BG = colors.HexColor('#fff8e1')      # Yellow tint for warnings
_WARNING_BORDER = colors.HexColor('#f9a825')  # Yellow border for warnings
_SUCCESS = colors.HexColor('#27ae60')         # Green for checkbox header


def _load_image_safe(path, width, height):
    """Attempt to load an image; return None on failure."""
    import os
    if path and os.path.exists(path):
        try:
            img = Image(path, width=width, height=height)
            img.hAlign = 'LEFT'
            return img
        except Exception:
            pass
    return None


def generate_packing_list(order):
    """
    Generate a professional packing list PDF for a sales order.

    Args:
        order: SalesOrder object

    Returns:
        BytesIO buffer containing the PDF
    """
    from flask import current_app
    from app.models.settings import CompanySettings
    import os

    buffer = BytesIO()
    page_w, page_h = A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    usable_width = page_w - doc.leftMargin - doc.rightMargin

    styles = getSampleStyleSheet()
    story = []

    # Get company settings
    settings = CompanySettings.get_settings()

    # ------------------------------------------------------------------
    # Custom paragraph styles
    # ------------------------------------------------------------------
    style_body = ParagraphStyle(
        'PLBody', parent=styles['Normal'], fontSize=9,
        textColor=_TEXT_DARK, leading=13,
    )
    style_body_small = ParagraphStyle(
        'PLBodySmall', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_MID, leading=11,
    )
    style_label = ParagraphStyle(
        'PLLabel', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_MID, leading=11,
    )
    style_value = ParagraphStyle(
        'PLValue', parent=styles['Normal'], fontSize=9,
        textColor=_TEXT_DARK, fontName='Helvetica-Bold', leading=13,
    )
    style_section = ParagraphStyle(
        'PLSection', parent=styles['Normal'], fontSize=10,
        textColor=_PRIMARY, fontName='Helvetica-Bold',
        spaceBefore=6, spaceAfter=4,
    )
    style_table_header = ParagraphStyle(
        'PLTableHeader', parent=styles['Normal'], fontSize=8,
        textColor=colors.white, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=11,
    )
    style_table_cell = ParagraphStyle(
        'PLTableCell', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_DARK, leading=11,
    )
    style_table_cell_center = ParagraphStyle(
        'PLTableCellCenter', parent=style_table_cell, alignment=TA_CENTER,
    )
    style_table_cell_right = ParagraphStyle(
        'PLTableCellRight', parent=style_table_cell, alignment=TA_RIGHT,
    )

    # ==================================================================
    # 1. HEADER BAR  --  company name in coloured band
    # ==================================================================
    company_name = settings.company_name or ''
    header_bar_data = [[Paragraph(
        f"<font color='white' size='14'><b>{company_name}</b></font>",
        ParagraphStyle('HeaderBar', parent=styles['Normal'],
                       alignment=TA_LEFT, textColor=colors.white),
    )]]
    header_bar = Table(header_bar_data, colWidths=[usable_width])
    header_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_bar)
    story.append(Spacer(1, 10))

    # ==================================================================
    # 2. LOGOS ROW  --  company logo (left) + customer logo (right)
    # ==================================================================
    company_logo = None
    if settings.logo_filename:
        logo_path = os.path.join(
            current_app.root_path, 'static', 'img', settings.logo_filename)
        company_logo = _load_image_safe(logo_path, 4 * cm, 2 * cm)

    customer = order.customer
    customer_logo = None
    if getattr(customer, 'logo_filename', None):
        cust_logo_path = os.path.join(
            current_app.root_path, 'static', 'img', 'customers',
            customer.logo_filename)
        customer_logo = _load_image_safe(cust_logo_path, 4 * cm, 2 * cm)

    if company_logo or customer_logo:
        logo_row = [[
            company_logo or '',
            customer_logo or '',
        ]]
        logo_table = Table(logo_row, colWidths=[usable_width / 2] * 2)
        logo_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(logo_table)
        story.append(Spacer(1, 6))

    # ==================================================================
    # 3. COMPANY DETAILS  --  small text under logo
    # ==================================================================
    company_text_parts = []
    if settings.address_line1:
        company_text_parts.append(settings.address_line1)
    if settings.address_line2:
        company_text_parts.append(settings.address_line2)
    city_line = ' '.join(filter(None, [settings.city, settings.postcode]))
    if city_line:
        company_text_parts.append(city_line)
    contact_parts = []
    if settings.phone:
        contact_parts.append(f"Tel: {settings.phone}")
    if settings.email:
        contact_parts.append(settings.email)
    if contact_parts:
        company_text_parts.append(' | '.join(contact_parts))
    if settings.vat_number:
        company_text_parts.append(f"VAT: {settings.vat_number}")

    if company_text_parts:
        story.append(Paragraph(
            '<br/>'.join(company_text_parts), style_body_small))
        story.append(Spacer(1, 6))

    # Thin rule
    story.append(HRFlowable(
        width='100%', thickness=0.5, color=_BORDER,
        spaceAfter=10, spaceBefore=4))

    # ==================================================================
    # 4. "PACKING LIST" TITLE  --  watermark-style large header
    # ==================================================================
    title_text = settings.packing_list_title if settings.packing_list_title else 'PACKING LIST'
    title_style = ParagraphStyle(
        'PLTitle', parent=styles['Heading1'],
        fontSize=26, fontName='Helvetica-Bold',
        textColor=_PRIMARY, alignment=TA_CENTER,
        spaceAfter=4, spaceBefore=2,
        borderWidth=0,
    )
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 6))

    # ==================================================================
    # 5. ORDER INFORMATION  --  three-column key/value grid
    # ==================================================================
    info_label_style = style_label
    info_value_style = style_value

    info_data = [[
        Paragraph('Order Number', info_label_style),
        Paragraph(order.order_number or '-', info_value_style),
        Paragraph('Date', info_label_style),
        Paragraph(datetime.now().strftime('%d/%m/%Y'), info_value_style),
        Paragraph('Customer PO', info_label_style),
        Paragraph(order.customer_po or '-', info_value_style),
    ]]
    info_col_w = usable_width / 6
    info_table = Table(info_data, colWidths=[info_col_w] * 6)
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY_LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, _BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # ==================================================================
    # 6. CUSTOMER / DELIVERY ADDRESS  --  side-by-side boxes
    # ==================================================================
    addr_half = usable_width / 2 - 3 * mm

    # Build customer address paragraphs
    cust_parts = [Paragraph('<b>CUSTOMER</b>', style_section)]
    cust_parts.append(Paragraph(f'<b>{customer.name}</b>', style_body))
    if customer.address_line1:
        cust_parts.append(Paragraph(customer.address_line1, style_body))
    if customer.address_line2:
        cust_parts.append(Paragraph(customer.address_line2, style_body))
    city_pc = ' '.join(filter(None, [customer.city, customer.postcode]))
    if city_pc:
        cust_parts.append(Paragraph(city_pc, style_body))
    if customer.country and customer.country != 'United Kingdom':
        cust_parts.append(Paragraph(customer.country, style_body))

    # Build delivery address paragraphs
    del_parts = [Paragraph('<b>DELIVERY ADDRESS</b>', style_section)]
    del_line1 = order.delivery_address_line1 or customer.address_line1 or ''
    if del_line1:
        del_parts.append(Paragraph(del_line1, style_body))
    if order.delivery_address_line2:
        del_parts.append(Paragraph(order.delivery_address_line2, style_body))
    del_city_pc = ' '.join(filter(None, [
        order.delivery_city or '', order.delivery_postcode or '']))
    if del_city_pc.strip():
        del_parts.append(Paragraph(del_city_pc, style_body))
    del_country = order.delivery_country or ''
    if del_country and del_country != 'United Kingdom':
        del_parts.append(Paragraph(del_country, style_body))

    addr_data = [[cust_parts, del_parts]]
    addr_table = Table(addr_data, colWidths=[addr_half, addr_half],
                       hAlign='LEFT')
    addr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (0, 0), 0.5, _BORDER),
        ('BOX', (1, 0), (1, 0), 0.5, _BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 14))

    # ==================================================================
    # 7. LINE ITEMS TABLE  --  with tick-box, line#, alternating rows
    # ==================================================================
    story.append(Paragraph('<b>ITEMS</b>', style_section))
    story.append(Spacer(1, 4))

    show_prices = getattr(settings, 'packing_list_show_prices', False)

    # Unicode ballot box for the checkbox column
    tick_box = '\u2610'  # empty checkbox character

    # Build header row
    if show_prices:
        header_labels = [tick_box, '#', 'SKU', 'Description', 'Qty', 'Unit',
                         'Price', 'Total']
    else:
        header_labels = [tick_box, '#', 'SKU', 'Description', 'Qty', 'Unit']

    header_row = [Paragraph(h, style_table_header) for h in header_labels]
    items_data = [header_row]

    # Track total quantity
    total_qty = 0

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

        qty = line.quantity_ordered or 0
        total_qty += qty

        row = [
            Paragraph(tick_box, style_table_cell_center),
            Paragraph(str(line.line_number), style_table_cell_center),
            Paragraph(sku, style_table_cell),
            Paragraph(description, style_table_cell),
            Paragraph(str(int(qty)), style_table_cell_center),
            Paragraph(unit, style_table_cell_center),
        ]
        if show_prices:
            unit_price = line.unit_price or 0
            line_total = line.line_total or (qty * unit_price)
            row.extend([
                Paragraph(f'\u00a3{unit_price:.2f}', style_table_cell_right),
                Paragraph(f'\u00a3{line_total:.2f}', style_table_cell_right),
            ])
        items_data.append(row)

    # Total quantity footer row
    if show_prices:
        total_row = [
            '', '', '', Paragraph('<b>TOTAL QTY</b>', style_table_cell_right),
            Paragraph(f'<b>{int(total_qty)}</b>', style_table_cell_center),
            '', '', '',
        ]
    else:
        total_row = [
            '', '', '',
            Paragraph('<b>TOTAL QTY</b>', style_table_cell_right),
            Paragraph(f'<b>{int(total_qty)}</b>', style_table_cell_center),
            '',
        ]
    items_data.append(total_row)

    # Column widths
    if show_prices:
        col_widths = [
            0.9 * cm,   # tick
            0.8 * cm,   # line#
            2.2 * cm,   # SKU
            5.1 * cm,   # description
            1.3 * cm,   # qty
            1.5 * cm,   # unit
            1.9 * cm,   # price
            2.3 * cm,   # total
        ]
    else:
        col_widths = [
            0.9 * cm,   # tick
            0.8 * cm,   # line#
            2.8 * cm,   # SKU
            7.5 * cm,   # description
            1.8 * cm,   # qty
            2.2 * cm,   # unit
        ]

    num_data_rows = len(items_data) - 2  # exclude header and total row
    last_data_row = num_data_rows  # 1-indexed (row 0 is header)
    total_row_idx = len(items_data) - 1

    table_style_cmds = [
        # -- Header row --
        ('BACKGROUND', (0, 0), (-1, 0), _PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),

        # -- Body rows --
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),

        # -- Grid lines --
        ('LINEBELOW', (0, 0), (-1, 0), 1, _PRIMARY),         # under header
        ('LINEBELOW', (0, 1), (-1, -2), 0.25, _BORDER),       # between rows
        ('LINEABOVE', (0, total_row_idx), (-1, total_row_idx),
         1, _PRIMARY),                                         # above total
        ('LINEBELOW', (0, total_row_idx), (-1, total_row_idx),
         1, _PRIMARY),                                         # below total
        ('LINEBEFORE', (0, 0), (0, -1), 0.5, _BORDER),        # left edge
        ('LINEAFTER', (-1, 0), (-1, -1), 0.5, _BORDER),       # right edge

        # -- Total row styling --
        ('BACKGROUND', (0, total_row_idx), (-1, total_row_idx),
         _PRIMARY_LIGHT),
        ('FONTNAME', (0, total_row_idx), (-1, total_row_idx),
         'Helvetica-Bold'),
    ]

    # Alternating row backgrounds for data rows
    for i in range(1, total_row_idx):
        if i % 2 == 0:
            table_style_cmds.append(
                ('BACKGROUND', (0, i), (-1, i), _ROW_ALT))

    items_table = Table(items_data, colWidths=col_widths, hAlign='LEFT',
                        repeatRows=1)
    items_table.setStyle(TableStyle(table_style_cmds))
    story.append(items_table)

    # ==================================================================
    # 8. PRICE TOTALS  (only when show_prices is enabled)
    # ==================================================================
    if show_prices:
        story.append(Spacer(1, 8))
        total_style = ParagraphStyle(
            'PLTotal', parent=styles['Normal'], fontSize=10,
            alignment=TA_RIGHT, textColor=_TEXT_DARK,
        )
        total_bold_style = ParagraphStyle(
            'PLTotalBold', parent=total_style, fontSize=12,
            fontName='Helvetica-Bold',
        )

        subtotal = order.subtotal or 0
        story.append(Paragraph(
            f'Subtotal: \u00a3{subtotal:.2f}', total_style))

        shipping = order.shipping_cost or 0
        if shipping > 0:
            story.append(Paragraph(
                f'Shipping: \u00a3{shipping:.2f}', total_style))

        tax_amount = order.tax_amount or 0
        if tax_amount > 0:
            tax_rate = order.tax_rate or 20
            story.append(Paragraph(
                f'VAT ({int(tax_rate)}%): \u00a3{tax_amount:.2f}',
                total_style))

        total = order.total or 0
        story.append(Paragraph(
            f'<b>Total: \u00a3{total:.2f}</b>', total_bold_style))

    story.append(Spacer(1, 14))

    # ==================================================================
    # 9. DELIVERY NOTES / SPECIAL HANDLING SECTION
    # ==================================================================
    delivery_notes_elements = []

    # Special handling instructions in highlighted box
    if order.delivery_instructions:
        delivery_notes_elements.append(
            Paragraph('<b>SPECIAL HANDLING INSTRUCTIONS</b>', style_section))
        delivery_notes_elements.append(Spacer(1, 3))

        warn_data = [[Paragraph(
            f'\u26a0  {order.delivery_instructions}',
            ParagraphStyle(
                'PLWarning', parent=style_body, fontSize=9,
                textColor=colors.HexColor('#6d4c00'),
            ),
        )]]
        warn_table = Table(warn_data, colWidths=[usable_width - 6 * mm])
        warn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), _WARNING_BG),
            ('BOX', (0, 0), (-1, -1), 1, _WARNING_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        delivery_notes_elements.append(warn_table)
        delivery_notes_elements.append(Spacer(1, 10))

    # Number of boxes/pallets and weight placeholders
    delivery_notes_elements.append(
        Paragraph('<b>SHIPMENT DETAILS</b>', style_section))
    delivery_notes_elements.append(Spacer(1, 3))

    shipment_data = [
        [Paragraph('Number of Boxes:', style_label),
         Paragraph('____________', style_body),
         Paragraph('Number of Pallets:', style_label),
         Paragraph('____________', style_body)],
        [Paragraph('Total Weight (kg):', style_label),
         Paragraph('____________', style_body),
         Paragraph('Delivery Method:', style_label),
         Paragraph(order.delivery_method or '____________', style_body)],
    ]
    ship_col_w = usable_width / 4
    ship_table = Table(shipment_data, colWidths=[ship_col_w] * 4)
    ship_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, _BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 0.25, _BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY_LIGHT),
    ]))
    delivery_notes_elements.append(ship_table)

    story.append(KeepTogether(delivery_notes_elements))
    story.append(Spacer(1, 14))

    # ==================================================================
    # 10. SIGNATURE SECTION  --  Packed by / Checked by (two columns)
    # ==================================================================
    show_signature = getattr(settings, 'packing_list_show_signature', True)
    if show_signature:
        story.append(HRFlowable(
            width='100%', thickness=0.5, color=_BORDER,
            spaceAfter=6, spaceBefore=4))
        story.append(Paragraph('<b>WAREHOUSE USE</b>', style_section))
        story.append(Spacer(1, 4))

        sig_half = usable_width / 2 - 2 * mm
        sig_line = '_' * 28
        date_line = '_' * 16

        packed_col = [
            Paragraph('<b>Packed by</b>', style_label),
            Spacer(1, 4),
            Paragraph(f'Name: {sig_line}', style_body),
            Spacer(1, 10),
            Paragraph(f'Signature: {sig_line}', style_body),
            Spacer(1, 10),
            Paragraph(f'Date: {date_line}', style_body),
        ]
        checked_col = [
            Paragraph('<b>Checked by</b>', style_label),
            Spacer(1, 4),
            Paragraph(f'Name: {sig_line}', style_body),
            Spacer(1, 10),
            Paragraph(f'Signature: {sig_line}', style_body),
            Spacer(1, 10),
            Paragraph(f'Date: {date_line}', style_body),
        ]

        sig_data = [[packed_col, checked_col]]
        sig_table = Table(sig_data, colWidths=[sig_half, sig_half])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (0, 0), 0.5, _BORDER),
            ('BOX', (1, 0), (1, 0), 0.5, _BORDER),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 14))

    # ==================================================================
    # 11. GOODS RECEIVED CONFIRMATION  --  customer signs on delivery
    # ==================================================================
    recv_elements = []
    recv_elements.append(HRFlowable(
        width='100%', thickness=0.5, color=_BORDER,
        spaceAfter=6, spaceBefore=4))
    recv_elements.append(
        Paragraph('<b>GOODS RECEIVED IN GOOD CONDITION</b>', style_section))
    recv_elements.append(Spacer(1, 4))

    recv_text = (
        'I confirm that the goods listed above have been received '
        'in good condition and the quantities are correct.'
    )
    recv_elements.append(Paragraph(recv_text, style_body))
    recv_elements.append(Spacer(1, 10))

    recv_sig_line = '_' * 35
    recv_date_line = '_' * 20

    recv_data = [
        [Paragraph(f'Name: {recv_sig_line}', style_body),
         Paragraph(f'Date: {recv_date_line}', style_body)],
        [Paragraph(f'Signature: {recv_sig_line}', style_body),
         Paragraph('', style_body)],
    ]
    recv_table = Table(recv_data, colWidths=[usable_width / 2] * 2)
    recv_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    recv_elements.append(recv_table)

    story.append(KeepTogether(recv_elements))
    story.append(Spacer(1, 14))

    # ==================================================================
    # 12. BANK DETAILS  (optional)
    # ==================================================================
    show_bank = getattr(settings, 'packing_list_show_bank_details', False)
    if show_bank and settings.bank_name and settings.account_number:
        story.append(HRFlowable(
            width='100%', thickness=0.5, color=_BORDER,
            spaceAfter=6, spaceBefore=2))
        story.append(Paragraph('<b>BANK DETAILS</b>', style_section))
        bank_text = []
        if settings.bank_name:
            bank_text.append(f'Bank: {settings.bank_name}')
        if settings.account_name:
            bank_text.append(f'Account Name: {settings.account_name}')
        if settings.sort_code:
            bank_text.append(f'Sort Code: {settings.sort_code}')
        if settings.account_number:
            bank_text.append(f'Account No: {settings.account_number}')
        story.append(Paragraph('<br/>'.join(bank_text), style_body_small))

    # ==================================================================
    # 13. FOOTER TEXT
    # ==================================================================
    if settings.packing_list_footer:
        story.append(Spacer(1, 14))
        story.append(HRFlowable(
            width='100%', thickness=0.5, color=_BORDER,
            spaceAfter=6, spaceBefore=2))
        story.append(Paragraph(settings.packing_list_footer, style_body))

    # ==================================================================
    # 14. TERMS & CONDITIONS
    # ==================================================================
    if settings.packing_list_terms:
        story.append(Spacer(1, 6))
        terms_style = ParagraphStyle(
            'PLTerms', parent=styles['Normal'], fontSize=7,
            textColor=_TEXT_MID, leading=9,
        )
        story.append(Paragraph(
            f'<i>{settings.packing_list_terms}</i>', terms_style))

    # ==================================================================
    # Build PDF
    # ==================================================================
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_delivery_note(order):
    """
    Generate a customer-facing delivery note PDF for signing on delivery.

    Similar layout to packing list but titled "DELIVERY NOTE", excludes
    warehouse-use signature section, and has a prominent customer signature
    section for proof of delivery.
    """
    from flask import current_app
    from app.models.settings import CompanySettings
    import os

    buffer = BytesIO()
    page_w, page_h = A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    usable_width = page_w - doc.leftMargin - doc.rightMargin

    styles = getSampleStyleSheet()
    story = []

    settings = CompanySettings.get_settings()

    # Styles (reuse same style definitions as packing list)
    style_body = ParagraphStyle(
        'DNBody', parent=styles['Normal'], fontSize=9,
        textColor=_TEXT_DARK, leading=13,
    )
    style_body_small = ParagraphStyle(
        'DNBodySmall', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_MID, leading=11,
    )
    style_label = ParagraphStyle(
        'DNLabel', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_MID, leading=11,
    )
    style_value = ParagraphStyle(
        'DNValue', parent=styles['Normal'], fontSize=9,
        textColor=_TEXT_DARK, fontName='Helvetica-Bold', leading=13,
    )
    style_section = ParagraphStyle(
        'DNSection', parent=styles['Normal'], fontSize=10,
        textColor=_PRIMARY, fontName='Helvetica-Bold',
        spaceBefore=6, spaceAfter=4,
    )
    style_table_header = ParagraphStyle(
        'DNTableHeader', parent=styles['Normal'], fontSize=8,
        textColor=colors.white, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=11,
    )
    style_table_cell = ParagraphStyle(
        'DNTableCell', parent=styles['Normal'], fontSize=8,
        textColor=_TEXT_DARK, leading=11,
    )
    style_table_cell_center = ParagraphStyle(
        'DNTableCellCenter', parent=style_table_cell, alignment=TA_CENTER,
    )

    # ==================================================================
    # 1. HEADER BAR
    # ==================================================================
    company_name = settings.company_name or ''
    header_bar_data = [[Paragraph(
        f"<font color='white' size='14'><b>{company_name}</b></font>",
        ParagraphStyle('HeaderBar', parent=styles['Normal'],
                       alignment=TA_LEFT, textColor=colors.white),
    )]]
    header_bar = Table(header_bar_data, colWidths=[usable_width])
    header_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(header_bar)
    story.append(Spacer(1, 10))

    # ==================================================================
    # 2. LOGOS
    # ==================================================================
    company_logo = None
    if settings.logo_filename:
        logo_path = os.path.join(
            current_app.root_path, 'static', 'img', settings.logo_filename)
        company_logo = _load_image_safe(logo_path, 4 * cm, 2 * cm)

    customer = order.customer
    customer_logo = None
    if getattr(customer, 'logo_filename', None):
        cust_logo_path = os.path.join(
            current_app.root_path, 'static', 'img', 'customers',
            customer.logo_filename)
        customer_logo = _load_image_safe(cust_logo_path, 4 * cm, 2 * cm)

    if company_logo or customer_logo:
        logo_row = [[company_logo or '', customer_logo or '']]
        logo_table = Table(logo_row, colWidths=[usable_width / 2] * 2)
        logo_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(logo_table)
        story.append(Spacer(1, 6))

    # ==================================================================
    # 3. COMPANY DETAILS
    # ==================================================================
    company_text_parts = []
    if settings.address_line1:
        company_text_parts.append(settings.address_line1)
    if settings.address_line2:
        company_text_parts.append(settings.address_line2)
    city_line = ' '.join(filter(None, [settings.city, settings.postcode]))
    if city_line:
        company_text_parts.append(city_line)
    contact_parts = []
    if settings.phone:
        contact_parts.append(f"Tel: {settings.phone}")
    if settings.email:
        contact_parts.append(settings.email)
    if contact_parts:
        company_text_parts.append(' | '.join(contact_parts))
    if settings.vat_number:
        company_text_parts.append(f"VAT: {settings.vat_number}")

    if company_text_parts:
        story.append(Paragraph(
            '<br/>'.join(company_text_parts), style_body_small))
        story.append(Spacer(1, 6))

    story.append(HRFlowable(
        width='100%', thickness=0.5, color=_BORDER,
        spaceAfter=10, spaceBefore=4))

    # ==================================================================
    # 4. "DELIVERY NOTE" TITLE
    # ==================================================================
    title_style = ParagraphStyle(
        'DNTitle', parent=styles['Heading1'],
        fontSize=26, fontName='Helvetica-Bold',
        textColor=_PRIMARY, alignment=TA_CENTER,
        spaceAfter=4, spaceBefore=2, borderWidth=0,
    )
    story.append(Paragraph('DELIVERY NOTE', title_style))
    story.append(Spacer(1, 6))

    # ==================================================================
    # 5. ORDER INFORMATION
    # ==================================================================
    info_data = [[
        Paragraph('Order Number', style_label),
        Paragraph(order.order_number or '-', style_value),
        Paragraph('Date', style_label),
        Paragraph(datetime.now().strftime('%d/%m/%Y'), style_value),
        Paragraph('Customer PO', style_label),
        Paragraph(order.customer_po or '-', style_value),
    ]]
    info_col_w = usable_width / 6
    info_table = Table(info_data, colWidths=[info_col_w] * 6)
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY_LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, _BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # ==================================================================
    # 6. CUSTOMER / DELIVERY ADDRESS
    # ==================================================================
    addr_half = usable_width / 2 - 3 * mm

    cust_parts = [Paragraph('<b>CUSTOMER</b>', style_section)]
    cust_parts.append(Paragraph(f'<b>{customer.name}</b>', style_body))
    if customer.address_line1:
        cust_parts.append(Paragraph(customer.address_line1, style_body))
    if customer.address_line2:
        cust_parts.append(Paragraph(customer.address_line2, style_body))
    city_pc = ' '.join(filter(None, [customer.city, customer.postcode]))
    if city_pc:
        cust_parts.append(Paragraph(city_pc, style_body))
    if customer.country and customer.country != 'United Kingdom':
        cust_parts.append(Paragraph(customer.country, style_body))

    del_parts = [Paragraph('<b>DELIVERY ADDRESS</b>', style_section)]
    del_line1 = order.delivery_address_line1 or customer.address_line1 or ''
    if del_line1:
        del_parts.append(Paragraph(del_line1, style_body))
    if order.delivery_address_line2:
        del_parts.append(Paragraph(order.delivery_address_line2, style_body))
    del_city_pc = ' '.join(filter(None, [
        order.delivery_city or '', order.delivery_postcode or '']))
    if del_city_pc.strip():
        del_parts.append(Paragraph(del_city_pc, style_body))
    del_country = order.delivery_country or ''
    if del_country and del_country != 'United Kingdom':
        del_parts.append(Paragraph(del_country, style_body))

    addr_data = [[cust_parts, del_parts]]
    addr_table = Table(addr_data, colWidths=[addr_half, addr_half], hAlign='LEFT')
    addr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (0, 0), 0.5, _BORDER),
        ('BOX', (1, 0), (1, 0), 0.5, _BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 14))

    # ==================================================================
    # 7. LINE ITEMS TABLE (no prices — delivery note is quantity only)
    # ==================================================================
    story.append(Paragraph('<b>ITEMS</b>', style_section))
    story.append(Spacer(1, 4))

    tick_box = '\u2610'
    header_labels = [tick_box, '#', 'SKU', 'Description', 'Qty', 'Unit']
    header_row = [Paragraph(h, style_table_header) for h in header_labels]
    items_data = [header_row]

    total_qty = 0
    for line in order.lines:
        if line.is_custom_item:
            sku = line.custom_sku or 'CUSTOM'
            description = line.custom_description or ''
            unit = 'each'
        else:
            sku = line.item.sku if line.item else '-'
            description = line.item.name if line.item else '-'
            unit = line.item.unit_of_measure if line.item else 'each'

        qty = line.quantity_ordered or 0
        total_qty += qty

        row = [
            Paragraph(tick_box, style_table_cell_center),
            Paragraph(str(line.line_number), style_table_cell_center),
            Paragraph(sku, style_table_cell),
            Paragraph(description, style_table_cell),
            Paragraph(str(int(qty)), style_table_cell_center),
            Paragraph(unit, style_table_cell_center),
        ]
        items_data.append(row)

    total_row = [
        '', '', '',
        Paragraph('<b>TOTAL QTY</b>', ParagraphStyle(
            'TotalRight', parent=style_table_cell, alignment=TA_RIGHT)),
        Paragraph(f'<b>{int(total_qty)}</b>', style_table_cell_center),
        '',
    ]
    items_data.append(total_row)

    col_widths = [
        0.9 * cm, 0.8 * cm, 2.8 * cm, 7.5 * cm, 1.8 * cm, 2.2 * cm,
    ]

    total_row_idx = len(items_data) - 1

    table_style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), _PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, 0), 1, _PRIMARY),
        ('LINEBELOW', (0, 1), (-1, -2), 0.25, _BORDER),
        ('LINEABOVE', (0, total_row_idx), (-1, total_row_idx), 1, _PRIMARY),
        ('LINEBELOW', (0, total_row_idx), (-1, total_row_idx), 1, _PRIMARY),
        ('LINEBEFORE', (0, 0), (0, -1), 0.5, _BORDER),
        ('LINEAFTER', (-1, 0), (-1, -1), 0.5, _BORDER),
        ('BACKGROUND', (0, total_row_idx), (-1, total_row_idx), _PRIMARY_LIGHT),
        ('FONTNAME', (0, total_row_idx), (-1, total_row_idx), 'Helvetica-Bold'),
    ]

    for i in range(1, total_row_idx):
        if i % 2 == 0:
            table_style_cmds.append(
                ('BACKGROUND', (0, i), (-1, i), _ROW_ALT))

    items_table = Table(items_data, colWidths=col_widths, hAlign='LEFT',
                        repeatRows=1)
    items_table.setStyle(TableStyle(table_style_cmds))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # ==================================================================
    # 8. DELIVERY INSTRUCTIONS
    # ==================================================================
    if order.delivery_instructions:
        warn_data = [[Paragraph(
            f'\u26a0  <b>DELIVERY INSTRUCTIONS:</b> {order.delivery_instructions}',
            ParagraphStyle(
                'DNWarning', parent=style_body, fontSize=9,
                textColor=colors.HexColor('#6d4c00'),
            ),
        )]]
        warn_table = Table(warn_data, colWidths=[usable_width - 6 * mm])
        warn_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), _WARNING_BG),
            ('BOX', (0, 0), (-1, -1), 1, _WARNING_BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(warn_table)
        story.append(Spacer(1, 14))

    # ==================================================================
    # 9. CUSTOMER SIGNATURE — PROOF OF DELIVERY
    # ==================================================================
    story.append(HRFlowable(
        width='100%', thickness=1, color=_PRIMARY,
        spaceAfter=6, spaceBefore=4))

    story.append(Paragraph(
        '<b>PROOF OF DELIVERY</b>', ParagraphStyle(
            'DNProof', parent=styles['Heading2'],
            fontSize=14, fontName='Helvetica-Bold',
            textColor=_PRIMARY, alignment=TA_CENTER,
            spaceAfter=6,
        )))

    story.append(Paragraph(
        'I confirm that the goods listed above have been received '
        'in good condition and the quantities are correct.',
        style_body))
    story.append(Spacer(1, 12))

    sig_line = '_' * 35
    date_line = '_' * 20

    sig_data = [
        [Paragraph(f'<b>Print Name:</b>  {sig_line}', style_body),
         Paragraph(f'<b>Date:</b>  {date_line}', style_body)],
        [Paragraph(f'<b>Signature:</b>  {sig_line}', style_body),
         Paragraph(f'<b>Time:</b>  {date_line}', style_body)],
    ]
    sig_table = Table(sig_data, colWidths=[usable_width / 2] * 2)
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, _PRIMARY),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, _BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), _PRIMARY_LIGHT),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 10))

    # Any items damaged or missing?
    story.append(Paragraph('<b>DISCREPANCIES / DAMAGE NOTES:</b>', style_section))
    story.append(Spacer(1, 4))
    notes_box_data = [['']]
    notes_box = Table(notes_box_data, colWidths=[usable_width],
                      rowHeights=[3 * cm])
    notes_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, _BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    story.append(notes_box)

    # ==================================================================
    # 10. FOOTER
    # ==================================================================
    if settings.packing_list_footer:
        story.append(Spacer(1, 10))
        story.append(HRFlowable(
            width='100%', thickness=0.5, color=_BORDER,
            spaceAfter=6, spaceBefore=2))
        story.append(Paragraph(settings.packing_list_footer, style_body))

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
