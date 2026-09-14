import os
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm


def get_pdf_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'InvTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#0f172a')
    )
    sub_title = ParagraphStyle(
        'InvSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#64748b'),
        textTransform='uppercase'
    )
    body_muted = ParagraphStyle(
        'InvMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#475569')
    )
    tbl_hdr = ParagraphStyle(
        'TblHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    tbl_hdr_r = ParagraphStyle('TblHdrR', parent=tbl_hdr, alignment=2)
    tbl_body = ParagraphStyle(
        'TblBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )
    tbl_body_r = ParagraphStyle('TblBodyR', parent=tbl_body, alignment=2)
    tbl_body_br = ParagraphStyle('TblBodyBR', parent=tbl_body_r, fontName='Helvetica-Bold')

    return {
        'title': title_style,
        'sub': sub_title,
        'muted': body_muted,
        'tbl_hdr': tbl_hdr,
        'tbl_hdr_r': tbl_hdr_r,
        'tbl_body': tbl_body,
        'tbl_body_r': tbl_body_r,
        'tbl_body_br': tbl_body_br
    }


def build_invoice_pdf(inv, logo_path='static/logo.jpg'):
    """Generates an A4 commercial vector PDF for wholesale distribution invoices."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    S = get_pdf_styles()
    story = []

    # 1. Header (Logo + Business Info + Invoice Meta Box)
    logo_elem = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_elem = Image(logo_path, width=22 * mm, height=22 * mm)
        except Exception:
            logo_elem = None

    biz_name = inv.get('business_name') or inv.get('full_name') or "Commercial Wholesale Store"
    biz_addr = inv.get('business_address') or ""
    biz_phone = inv.get('business_phone') or ""
    biz_tax = inv.get('tax_id') or ""
    currency = inv.get('currency') or "PKR"

    contact_parts = []
    if biz_phone: contact_parts.append(f"<b>Phone:</b> {biz_phone}")
    if biz_tax: contact_parts.append(f"<b>NTN / Tax ID:</b> {biz_tax}")
    contact_str = " &bull; ".join(contact_parts)

    biz_info = [
        Paragraph(biz_name.upper(), S['title']),
        Paragraph("COMMERCIAL SALES &amp; DELIVERY INVOICE", S['sub']),
    ]
    if biz_addr:
        biz_info.append(Paragraph(biz_addr, S['muted']))
    if contact_str:
        biz_info.append(Paragraph(contact_str, S['muted']))

    status = (inv.get('payment_status') or 'Paid').upper()
    status_fg = '#065f46' if status == 'PAID' else '#92400e'

    meta_table = Table([
        [Paragraph("<b>INVOICE NUMBER:</b>", ParagraphStyle('m1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#64748b'), alignment=2))],
        [Paragraph(f"<b>{inv.get('invoice_no', 'PND-INV-1001')}</b>", ParagraphStyle('m2', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=2, textColor=colors.HexColor('#0f172a')))],
        [Paragraph(f"Issue Date: <b>{inv.get('sale_date', '')}</b>", ParagraphStyle('m3', fontName='Helvetica', fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#475569')))],
        [Spacer(1, 1.5 * mm)],
        [Paragraph(f'<font color="{status_fg}"><b>● PAYMENT: {status}</b></font>', ParagraphStyle('m4', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=2))]
    ], colWidths=[55 * mm])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))

    if logo_elem:
        hdr_table = Table([[logo_elem, biz_info, meta_table]], colWidths=[26 * mm, 101 * mm, 55 * mm])
    else:
        hdr_table = Table([[biz_info, meta_table]], colWidths=[127 * mm, 55 * mm])

    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f172a'), spaceAfter=10))

    # 2. Billed To / Client Box + Shipping Info in 2 Columns
    client_name = inv.get('client_name') or "Valued Client"
    notes = inv.get('notes') or "Standard Wholesale Fulfillment"

    cust_box = Table([
        [
            [
                Paragraph("<b>CUSTOMER / BILLED TO:</b>", ParagraphStyle('cb1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#64748b'))),
                Paragraph(f"<b>{client_name.upper()}</b>", ParagraphStyle('cb2', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor('#0f172a'))),
            ],
            [
                Paragraph("<b>DELIVERY &amp; DISPATCH DETAILS:</b>", ParagraphStyle('cb3', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#64748b'))),
                Paragraph(f"<b>Notes / Terms:</b> {notes}" if notes else "Standard Wholesale Delivery", S['muted']),
            ]
        ]
    ], colWidths=[90 * mm, 92 * mm])
    cust_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(cust_box)
    story.append(Spacer(1, 5 * mm))

    # 3. Itemized Products Table
    headers = [
        Paragraph("<b>#</b>", S['tbl_hdr']),
        Paragraph("<b>PRODUCT DESCRIPTION &amp; SPECIFICATIONS</b>", S['tbl_hdr']),
        Paragraph("<b>QUANTITY &amp; UNIT</b>", S['tbl_hdr_r']),
        Paragraph(f"<b>UNIT RATE ({currency})</b>", S['tbl_hdr_r']),
        Paragraph(f"<b>TOTAL AMOUNT ({currency})</b>", S['tbl_hdr_r'])
    ]
    tbl_data = [headers]

    items = inv.get('items') or []
    for idx, it in enumerate(items, 1):
        desc_parts = [f"<b>{it.get('product_name', 'Item')}</b>"]
        extra = []
        if it.get('sku'): extra.append(f"SKU: {it['sku']}")
        if it.get('batch_no'): extra.append(f"Batch: {it['batch_no']}")
        if it.get('expiry_date'): extra.append(f"Best Before: {it['expiry_date']}")
        if extra:
            desc_parts.append(f"<font size=7.5 color='#64748b'>{' &bull; '.join(extra)}</font>")

        desc_p = Paragraph("<br/>".join(desc_parts), S['tbl_body'])
        qty_str = f"{it.get('quantity_sold', 0):,.2f} {it.get('unit', '')}"
        rate_str = f"{it.get('unit_price', 0):,.2f}"
        amt_str = f"<b>{it.get('total_amount', 0):,.2f}</b>"

        tbl_data.append([
            Paragraph(str(idx), S['tbl_body']),
            desc_p,
            Paragraph(qty_str, S['tbl_body_r']),
            Paragraph(rate_str, S['tbl_body_r']),
            Paragraph(amt_str, S['tbl_body_br'])
        ])

    items_table = Table(tbl_data, colWidths=[10 * mm, 88 * mm, 28 * mm, 26 * mm, 30 * mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0f172a')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # 4. Financial Calculation Block (Subtotal, Tax, Grand Total)
    grand_total = inv.get('grand_total') or sum(it.get('total_amount', 0) for it in items)
    total_items = len(items)
    total_qty = sum(it.get('quantity_sold', 0) for it in items)

    summary_table = Table([
        [
            [
                Paragraph("<b>PAYMENT TERMS &amp; SETTLEMENT:</b>", ParagraphStyle('p1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#1e293b'))),
                Paragraph(f"<b>Settlement:</b> {inv.get('bank_details')}" if inv.get('bank_details') else "Payment is accepted via <b>Cash, Direct Bank Transfer, or Authorized Cheque</b> payable to the seller.", S['muted']),
                Paragraph(f"<b>Terms / Notes:</b> {inv.get('invoice_notes')}" if inv.get('invoice_notes') else "Please quote invoice number on electronic remittances. Payment due per agreed terms.", S['muted']),
                Spacer(1, 1.5 * mm),
                Paragraph("<b>Commercial Policy:</b> Please verify goods, quantities, and packaging upon delivery.", ParagraphStyle('cc', parent=S['muted'], fontSize=7.5, textColor=colors.HexColor('#64748b')))
            ],
            Table([
                [Paragraph("Total Items / Lines:", S['tbl_body']), Paragraph(f"<b>{total_items} items ({total_qty:,.2f} units)</b>", S['tbl_body_r'])],
                [Paragraph(f"Subtotal Amount:", S['tbl_body']), Paragraph(f"{currency} {grand_total:,.2f}", S['tbl_body_r'])],
                [Paragraph(f"Sales Tax / GST (0%):", S['tbl_body']), Paragraph(f"{currency} 0.00", S['tbl_body_r'])],
                [
                    Paragraph("<b>GRAND TOTAL:</b>", ParagraphStyle('gt1', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0f172a'))),
                    Paragraph(f"<b>{currency} {grand_total:,.2f}</b>", ParagraphStyle('gt2', fontName='Helvetica-Bold', fontSize=13, alignment=2, textColor=colors.HexColor('#047857')))
                ]
            ], colWidths=[38 * mm, 34 * mm])
        ]
    ], colWidths=[110 * mm, 72 * mm])

    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 0), (-1, -1), 1, colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(KeepTogether(summary_table))

    # 5. Signatures Block (2 columns: Customer acknowledgment & Authorized Signatory)
    story.append(Spacer(1, 10 * mm))
    sig_table = Table([
        [
            [
                Paragraph("___________________________________", S['muted']),
                Paragraph("<b>Received By / Customer Signature &amp; Stamp</b>", ParagraphStyle('s1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#475569'))),
                Paragraph("Date: ________________________", S['muted']),
            ],
            [
                Paragraph("___________________________________", ParagraphStyle('s2', parent=S['muted'], alignment=2)),
                Paragraph("<b>Authorized Signatory / Store Officer</b>", ParagraphStyle('s3', fontName='Helvetica-Bold', fontSize=8, alignment=2, textColor=colors.HexColor('#475569'))),
                Paragraph(biz_name, ParagraphStyle('s4', parent=S['muted'], alignment=2)),
            ]
        ]
    ], colWidths=[90 * mm, 92 * mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(sig_table))

    # 6. Clean Corporate Footer
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=6))
    story.append(Paragraph(
        "Thank you for your business! &bull; Computer-Generated Commercial Invoice &bull; Systems Architect: Habib Naseer &bull; Support: x10deeredge@gmail.com",
        ParagraphStyle('Foot', fontName='Helvetica', fontSize=7.5, alignment=1, textColor=colors.HexColor('#94a3b8'))
    ))

    doc.build(story)
    return buffer.getvalue()


def build_audit_report_pdf(rep, logo_path='static/logo.jpg'):
    """Generates an executive vector PDF for period financial audit statements."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    S = get_pdf_styles()
    story = []

    logo_elem = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_elem = Image(logo_path, width=20 * mm, height=20 * mm)
        except Exception:
            logo_elem = None

    biz_name = rep.get('business_name') or "PANDA'S Wholesale Distribution System"
    currency = rep.get('currency') or "PKR"
    kpi = rep.get('kpi') or {}

    hdr_left = [
        Paragraph(biz_name.upper(), S['title']),
        Paragraph("EXECUTIVE FINANCIAL AUDIT &amp; PERIOD STATEMENT", S['sub']),
        Paragraph(f"Reporting Timeframe: <b>{rep.get('start_date')}</b> to <b>{rep.get('end_date')}</b>", S['muted'])
    ]

    hdr_right = [
        Paragraph(f"Statement ID: <b>AUD-{rep.get('start_date', '')[:7] or '2026'}</b>", ParagraphStyle('a1', fontName='Helvetica-Bold', fontSize=11, alignment=2, textColor=colors.HexColor('#0f172a'))),
        Paragraph(f"Generated: {rep.get('generated_at', '')}", ParagraphStyle('a2', fontName='Helvetica', fontSize=8, alignment=2, textColor=colors.HexColor('#64748b'))),
        Paragraph("Classification: <b>CONFIDENTIAL &bull; EXECUTIVE</b>", ParagraphStyle('a3', fontName='Helvetica-Bold', fontSize=8, alignment=2, textColor=colors.HexColor('#dc2626')))
    ]

    if logo_elem:
        hdr = Table([[logo_elem, hdr_left, hdr_right]], colWidths=[24 * mm, 104 * mm, 54 * mm])
    else:
        hdr = Table([[hdr_left, hdr_right]], colWidths=[128 * mm, 54 * mm])

    hdr.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f172a'), spaceAfter=10))

    # KPI Financial Highlights Table (Executive Summary)
    sales_rev = kpi.get('sales_revenue', 0)
    stock_pur = kpi.get('stock_purchases', 0)
    gross_prof = kpi.get('gross_profit', 0)
    op_exp = kpi.get('operating_expenses', 0)
    net_prof = kpi.get('net_profit', 0)

    kpi_table = Table([
        [
            Paragraph("<b>TOTAL REVENUE</b>", S['tbl_hdr']),
            Paragraph("<b>STOCK PURCHASES</b>", S['tbl_hdr']),
            Paragraph("<b>GROSS PROFIT</b>", S['tbl_hdr']),
            Paragraph("<b>OPERATING EXP.</b>", S['tbl_hdr']),
            Paragraph("<b>NET CASHFLOW</b>", S['tbl_hdr'])
        ],
        [
            Paragraph(f"<b>{currency} {sales_rev:,.0f}</b>", ParagraphStyle('k1', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0f172a'))),
            Paragraph(f"{currency} {stock_pur:,.0f}", ParagraphStyle('k2', fontName='Helvetica', fontSize=9.5, textColor=colors.HexColor('#475569'))),
            Paragraph(f"<b>{currency} {gross_prof:,.0f}</b>", ParagraphStyle('k3', fontName='Helvetica-Bold', fontSize=9.5, textColor=colors.HexColor('#059669') if gross_prof >= 0 else colors.HexColor('#dc2626'))),
            Paragraph(f"{currency} {op_exp:,.0f}", ParagraphStyle('k4', fontName='Helvetica', fontSize=9.5, textColor=colors.HexColor('#dc2626'))),
            Paragraph(f"<b>{currency} {net_prof:,.0f}</b>", ParagraphStyle('k5', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#047857') if net_prof >= 0 else colors.HexColor('#dc2626')))
        ]
    ], colWidths=[36 * mm, 36 * mm, 36 * mm, 36 * mm, 38 * mm])

    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6 * mm))

    # Section 1: Sales by Product
    story.append(Paragraph("<b>1. SALES REVENUE &amp; DISPATCH BREAKDOWN BY PRODUCT</b>", ParagraphStyle('sec1', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0f172a'), spaceAfter=4)))

    prod_rows = [
        [
            Paragraph("<b>#</b>", S['tbl_hdr']),
            Paragraph("<b>PRODUCT NAME</b>", S['tbl_hdr']),
            Paragraph("<b>CATEGORY</b>", S['tbl_hdr']),
            Paragraph("<b>UNITS SOLD</b>", S['tbl_hdr_r']),
            Paragraph(f"<b>TOTAL REVENUE ({currency})</b>", S['tbl_hdr_r'])
        ]
    ]

    prod_breakdown = rep.get('product_breakdown') or []
    for idx, p in enumerate(prod_breakdown, 1):
        prod_rows.append([
            Paragraph(str(idx), S['tbl_body']),
            Paragraph(f"<b>{p.get('product_name', '')}</b>", S['tbl_body']),
            Paragraph(p.get('category', ''), S['tbl_body']),
            Paragraph(f"{p.get('units_sold', 0):,.2f} {p.get('unit', '')}", S['tbl_body_r']),
            Paragraph(f"<b>{p.get('revenue', 0):,.2f}</b>", S['tbl_body_br'])
        ])

    if len(prod_rows) == 1:
        prod_rows.append([Paragraph("—", S['tbl_body']), Paragraph("No sales recorded in selected period", S['tbl_body']), Paragraph("—", S['tbl_body']), Paragraph("0.00", S['tbl_body_r']), Paragraph("0.00", S['tbl_body_r'])])

    ptable = Table(prod_rows, colWidths=[10 * mm, 75 * mm, 35 * mm, 32 * mm, 30 * mm])
    ptable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(ptable)
    story.append(Spacer(1, 6 * mm))

    # Section 2: Operational Expenses
    story.append(Paragraph("<b>2. OPERATIONAL EXPENSES LOG (OVERHEADS &amp; LOGISTICS)</b>", ParagraphStyle('sec2', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0f172a'), spaceAfter=4)))

    exp_rows = [
        [
            Paragraph("<b>#</b>", S['tbl_hdr']),
            Paragraph("<b>EXPENSE TITLE / VENDOR</b>", S['tbl_hdr']),
            Paragraph("<b>CATEGORY</b>", S['tbl_hdr']),
            Paragraph("<b>DATE</b>", S['tbl_hdr']),
            Paragraph(f"<b>AMOUNT ({currency})</b>", S['tbl_hdr_r'])
        ]
    ]
    expenses_log = rep.get('expenses_log') or []
    for idx, ex in enumerate(expenses_log[:15], 1):
        exp_rows.append([
            Paragraph(str(idx), S['tbl_body']),
            Paragraph(f"<b>{ex.get('title', '')}</b>", S['tbl_body']),
            Paragraph(ex.get('category', 'General'), S['tbl_body']),
            Paragraph(str(ex.get('expense_date', '')), S['tbl_body']),
            Paragraph(f"<b>{ex.get('amount', 0):,.2f}</b>", S['tbl_body_br'])
        ])

    if len(exp_rows) == 1:
        exp_rows.append([Paragraph("—", S['tbl_body']), Paragraph("No operational expenses logged in selected period", S['tbl_body']), Paragraph("—", S['tbl_body']), Paragraph("—", S['tbl_body']), Paragraph("0.00", S['tbl_body_r'])])

    etable = Table(exp_rows, colWidths=[10 * mm, 80 * mm, 32 * mm, 28 * mm, 32 * mm])
    etable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(etable)

    # Certification Signatures
    story.append(Spacer(1, 10 * mm))
    cert_table = Table([
        [
            [
                Paragraph("___________________________________", S['muted']),
                Paragraph("<b>Internal Auditor / Accountant</b>", ParagraphStyle('ca1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#475569'))),
                Paragraph("Financial records cross-verified with ledger", S['muted']),
            ],
            [
                Paragraph("___________________________________", ParagraphStyle('ca2', parent=S['muted'], alignment=2)),
                Paragraph("<b>Executive Director / Managing Partner</b>", ParagraphStyle('ca3', fontName='Helvetica-Bold', fontSize=8, alignment=2, textColor=colors.HexColor('#475569'))),
                Paragraph(biz_name, ParagraphStyle('ca4', parent=S['muted'], alignment=2)),
            ]
        ]
    ], colWidths=[90 * mm, 92 * mm])
    cert_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(cert_table))

    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=6))
    story.append(Paragraph(
        "Executive Financial Audit Statement &bull; Confidential &bull; Powered by PANDA'S Wholesale ERP",
        ParagraphStyle('Foot', fontName='Helvetica', fontSize=7.5, alignment=1, textColor=colors.HexColor('#94a3b8'))
    ))

    doc.build(story)
    return buffer.getvalue()


def build_user_backup_pdf(user, products, stock_entries, sales, expenses, logo_path='static/logo.jpg'):
    """
    Generates an executive, multi-page vector PDF containing a complete,
    human-readable store statement and verified database audit for the user's account.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0f172a')
    )
    sub_title = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#65a30d'),
        textTransform='uppercase'
    )
    body_muted = ParagraphStyle(
        'DocMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    tbl_hdr = ParagraphStyle(
        'TblHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )
    tbl_hdr_r = ParagraphStyle('TblHdrR', parent=tbl_hdr, alignment=2)
    tbl_body = ParagraphStyle(
        'TblBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0f172a')
    )
    tbl_body_r = ParagraphStyle('TblBodyR', parent=tbl_body, alignment=2)
    tbl_body_b = ParagraphStyle('TblBodyB', parent=tbl_body, fontName='Helvetica-Bold')
    tbl_body_br = ParagraphStyle('TblBodyBR', parent=tbl_body_r, fontName='Helvetica-Bold')

    sec_hdr = ParagraphStyle(
        'SecHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=3,
        spaceBefore=8
    )

    story = []

    # 1. Header Banner
    logo_elem = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo_elem = Image(logo_path, width=20 * mm, height=20 * mm)
        except Exception:
            logo_elem = None

    biz_name = user.get('business_name') or "PANDA Wholesale & Retail Traders"
    username = user.get('username') or "admin"
    gen_time = datetime.now().strftime('%d-%b-%Y %I:%M %p') if 'datetime' in globals() else ""
    if not gen_time:
        from datetime import datetime as dt_cls
        gen_time = dt_cls.now().strftime('%d-%b-%Y %I:%M %p')
    currency = user.get('currency') or "PKR"

    hdr_left = [
        Paragraph(biz_name.upper(), title_style),
        Paragraph("OFFICIAL STORE AUDIT &amp; COMPLETE ACCOUNT BACKUP STATEMENT", sub_title),
        Paragraph(f"Account Holder: <b>{username}</b> &bull; User ID: #{user.get('id', 1)} &bull; Currency: <b>{currency}</b>", body_muted),
        Paragraph(f"Contact &amp; Architecture: <b>Habib Naseer</b> &bull; x10deeredge@gmail.com", body_muted)
    ]

    hdr_right = [
        Paragraph("CLASSIFICATION: <b>CONFIDENTIAL &bull; VERIFIED</b>", ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=8, alignment=2, textColor=colors.HexColor('#65a30d'))),
        Paragraph(f"Export Date: <b>{gen_time}</b>", ParagraphStyle('h2', fontName='Helvetica', fontSize=8, alignment=2, textColor=colors.HexColor('#0f172a'))),
        Paragraph("Authorization: <b>Password-Protected Cryptographic Release</b>", ParagraphStyle('h3', fontName='Helvetica', fontSize=7.5, alignment=2, textColor=colors.HexColor('#64748b'))),
        Paragraph("System Engine: <b>PANDA Enterprise Suite v2.5</b>", ParagraphStyle('h4', fontName='Helvetica', fontSize=7.5, alignment=2, textColor=colors.HexColor('#64748b')))
    ]

    if logo_elem:
        hdr_table = Table([[logo_elem, hdr_left, hdr_right]], colWidths=[24 * mm, 95 * mm, 67 * mm])
    else:
        hdr_table = Table([[hdr_left, hdr_right]], colWidths=[118 * mm, 68 * mm])

    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#65a30d'), spaceAfter=5, spaceBefore=4))

    # 2. Executive KPI Financial Snapshot
    tot_sales = sum(float(s.get('total_amount') or 0) for s in sales)
    tot_stock_cost = sum(float(st.get('total_cost') or 0) for st in stock_entries)
    tot_expenses = sum(float(e.get('amount') or 0) for e in expenses)
    net_profit = tot_sales - tot_stock_cost - tot_expenses
    tot_valuation = sum(float(p.get('effective_cost') or p.get('purchase_price') or 0) * max(0.0, float(p.get('available') or 0)) for p in products)

    kpi_card_data = [
        [
            Paragraph("TOTAL SALES REVENUE", ParagraphStyle('kp_l1', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#64748b'))),
            Paragraph("STOCK PURCHASES", ParagraphStyle('kp_l2', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#64748b'))),
            Paragraph("STORE EXPENSES", ParagraphStyle('kp_l3', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#64748b'))),
            Paragraph("NET OPERATING PROFIT", ParagraphStyle('kp_l4', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#64748b'))),
            Paragraph("INVENTORY VALUATION", ParagraphStyle('kp_l5', fontName='Helvetica-Bold', fontSize=7, textColor=colors.HexColor('#64748b'))),
        ],
        [
            Paragraph(f"<b>{currency} {tot_sales:,.2f}</b>", ParagraphStyle('kv_s', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#15803d'))),
            Paragraph(f"<b>{currency} {tot_stock_cost:,.2f}</b>", ParagraphStyle('kv_p', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0369a1'))),
            Paragraph(f"<b>{currency} {tot_expenses:,.2f}</b>", ParagraphStyle('kv_e', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#b91c1c'))),
            Paragraph(f"<b>{currency} {net_profit:,.2f}</b>", ParagraphStyle('kv_np', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#15803d') if net_profit >= 0 else colors.HexColor('#b91c1c'))),
            Paragraph(f"<b>{currency} {tot_valuation:,.2f}</b>", ParagraphStyle('kv_iv', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0f172a'))),
        ],
        [
            Paragraph(f"Ledger Invoices: <b>{len(sales)}</b>", body_muted),
            Paragraph(f"Stock Purchases: <b>{len(stock_entries)}</b>", body_muted),
            Paragraph(f"Expenses Logged: <b>{len(expenses)}</b>", body_muted),
            Paragraph("Sales - Stock - Expenses", body_muted),
            Paragraph(f"Active Products: <b>{len(products)}</b>", body_muted),
        ]
    ]
    kpi_table = Table(kpi_card_data, colWidths=[37.2 * mm, 37.2 * mm, 37.2 * mm, 37.2 * mm, 37.2 * mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 4 * mm))

    # 3. Section 1: Complete Product Catalog & Inventory Valuation
    story.append(Paragraph("<b>1. REGISTERED PRODUCT CATALOG &amp; CURRENT INVENTORY VALUATION</b>", sec_hdr))

    prod_rows = [
        [
            Paragraph("<b>#</b>", tbl_hdr),
            Paragraph("<b>ITEM NAME &amp; DETAILS</b>", tbl_hdr),
            Paragraph("<b>CATEGORY</b>", tbl_hdr),
            Paragraph("<b>ACTION DATE</b>", tbl_hdr),
            Paragraph("<b>UNIT</b>", tbl_hdr),
            Paragraph(f"<b>COST ({currency})</b>", tbl_hdr_r),
            Paragraph(f"<b>SALE ({currency})</b>", tbl_hdr_r),
            Paragraph("<b>STOCK</b>", tbl_hdr_r),
            Paragraph(f"<b>VALUATION ({currency})</b>", tbl_hdr_r),
            Paragraph("<b>STATUS</b>", tbl_hdr)
        ]
    ]

    for idx, p in enumerate(products, 1):
        avail = float(p.get('available') or 0)
        c_price = float(p.get('effective_cost') or p.get('purchase_price') or 0)
        s_price = float(p.get('effective_sale_price') or p.get('selling_price') or 0)
        act_date = str(p.get('last_action_date') or p.get('created_at') or '')[:10]
        val = c_price * max(0.0, avail)
        status_txt = "In Stock"
        status_color = "#15803d"
        thresh = float(p.get('low_stock_threshold') or 0)
        if avail <= 0:
            status_txt = "OUT OF STOCK"
            status_color = "#b91c1c"
        elif thresh > 0 and avail <= thresh:
            status_txt = "LOW STOCK"
            status_color = "#d97706"

        prod_rows.append([
            Paragraph(str(idx), tbl_body),
            Paragraph(f"<b>{p.get('name', '')}</b>", tbl_body),
            Paragraph(p.get('category', '') or 'General', tbl_body),
            Paragraph(act_date or '—', tbl_body),
            Paragraph(p.get('unit', '') or 'unit', tbl_body),
            Paragraph(f"{c_price:,.2f}", tbl_body_r),
            Paragraph(f"{s_price:,.2f}", tbl_body_r),
            Paragraph(f"<b>{avail:,.2f}</b>", tbl_body_br),
            Paragraph(f"<b>{val:,.2f}</b>", tbl_body_br),
            Paragraph(f"<font color='{status_color}'><b>{status_txt}</b></font>", tbl_body)
        ])

    if len(prod_rows) == 1:
        prod_rows.append([Paragraph("—", tbl_body), Paragraph("No products registered in this account", tbl_body), Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("0.00", tbl_body_r), Paragraph("0.00", tbl_body_r), Paragraph("0.00", tbl_body_r), Paragraph("0.00", tbl_body_r), Paragraph("—", tbl_body)])
    else:
        # Total Row
        prod_rows.append([
            Paragraph("", tbl_body),
            Paragraph("<b>TOTAL PORTFOLIO VALUATION</b>", tbl_body_b),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph(f"<b>{tot_valuation:,.2f}</b>", tbl_body_br),
            Paragraph("", tbl_body)
        ])

    ptable = Table(prod_rows, colWidths=[6 * mm, 40 * mm, 18 * mm, 20 * mm, 10 * mm, 18 * mm, 18 * mm, 16 * mm, 24 * mm, 16 * mm])
    ptable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
    ]))
    story.append(ptable)
    story.append(Spacer(1, 4 * mm))

    # 4. Section 2: Sales Invoices Ledger
    story.append(Paragraph("<b>2. SALES INVOICES &amp; CLIENT TRANSACTIONS LEDGER</b>", sec_hdr))
    sales_rows = [
        [
            Paragraph("<b>#</b>", tbl_hdr),
            Paragraph("<b>INVOICE #</b>", tbl_hdr),
            Paragraph("<b>TRANSACTION DATE</b>", tbl_hdr),
            Paragraph("<b>CLIENT / STORE</b>", tbl_hdr),
            Paragraph("<b>PRODUCT SOLD</b>", tbl_hdr),
            Paragraph("<b>QTY</b>", tbl_hdr_r),
            Paragraph("<b>PAYMENT STATUS</b>", tbl_hdr),
            Paragraph(f"<b>TOTAL ({currency})</b>", tbl_hdr_r)
        ]
    ]

    for idx, s in enumerate(sales, 1):
        st_color = "#15803d" if str(s.get('payment_status', '')).lower() == 'paid' else ("#d97706" if str(s.get('payment_status', '')).lower() == 'partial' else "#b91c1c")
        inv_title = s.get('invoice_no') or f"INV-{s.get('id', '')}"
        s_date = str(s.get('sale_date', ''))[:10]
        sales_rows.append([
            Paragraph(str(idx), tbl_body),
            Paragraph(f"<b>{inv_title}</b>", tbl_body),
            Paragraph(s_date or '—', tbl_body),
            Paragraph(f"<b>{s.get('client_name', '')}</b>", tbl_body),
            Paragraph(s.get('product_name', '') or '—', tbl_body),
            Paragraph(f"{float(s.get('quantity_sold') or 0):,.2f} {s.get('unit', '')}", tbl_body_r),
            Paragraph(f"<font color='{st_color}'><b>{(s.get('payment_status') or 'unpaid').upper()}</b></font>", tbl_body),
            Paragraph(f"<b>{float(s.get('total_amount') or 0):,.2f}</b>", tbl_body_br)
        ])

    if len(sales_rows) == 1:
        sales_rows.append([Paragraph("—", tbl_body), Paragraph("No sales recorded", tbl_body), Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("0.00", tbl_body_r), Paragraph("—", tbl_body), Paragraph("0.00", tbl_body_r)])
    else:
        sales_rows.append([
            Paragraph("", tbl_body),
            Paragraph("<b>TOTAL RECORDED REVENUE</b>", tbl_body_b),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph(f"<b>{tot_sales:,.2f}</b>", tbl_body_br)
        ])

    stable = Table(sales_rows, colWidths=[7 * mm, 24 * mm, 22 * mm, 41 * mm, 37 * mm, 18 * mm, 17 * mm, 20 * mm])
    stable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
    ]))
    story.append(stable)
    story.append(Spacer(1, 4 * mm))

    # 5. Section 3: Stock Purchase History
    story.append(Paragraph("<b>3. STOCK INWARD &amp; PURCHASES AUDIT LOG</b>", sec_hdr))
    stock_rows = [
        [
            Paragraph("<b>#</b>", tbl_hdr),
            Paragraph("<b>PURCHASE DATE</b>", tbl_hdr),
            Paragraph("<b>PRODUCT PURCHASED</b>", tbl_hdr),
            Paragraph("<b>SUPPLIER / VENDOR</b>", tbl_hdr),
            Paragraph("<b>QTY ADDED</b>", tbl_hdr_r),
            Paragraph(f"<b>UNIT COST</b>", tbl_hdr_r),
            Paragraph(f"<b>TOTAL COST ({currency})</b>", tbl_hdr_r)
        ]
    ]
    for idx, st in enumerate(stock_entries, 1):
        q = float(st.get('quantity') or 0)
        tc = float(st.get('total_cost') or 0)
        uc = tc / q if q > 0 else 0.0
        stock_rows.append([
            Paragraph(str(idx), tbl_body),
            Paragraph(str(st.get('purchase_date', ''))[:10] or '—', tbl_body),
            Paragraph(f"<b>{st.get('product_name', '')}</b>", tbl_body),
            Paragraph(st.get('supplier', '') or 'Standard Supplier', tbl_body),
            Paragraph(f"{q:,.2f} {st.get('unit', '')}", tbl_body_r),
            Paragraph(f"{uc:,.2f}", tbl_body_r),
            Paragraph(f"<b>{tc:,.2f}</b>", tbl_body_br)
        ])

    if len(stock_rows) == 1:
        stock_rows.append([Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("No stock purchases recorded", tbl_body), Paragraph("—", tbl_body), Paragraph("0.00", tbl_body_r), Paragraph("0.00", tbl_body_r), Paragraph("0.00", tbl_body_r)])
    else:
        stock_rows.append([
            Paragraph("", tbl_body),
            Paragraph("<b>TOTAL STOCK PURCHASES VALUE</b>", tbl_body_b),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph(f"<b>{tot_stock_cost:,.2f}</b>", tbl_body_br)
        ])

    sktable = Table(stock_rows, colWidths=[7 * mm, 24 * mm, 48 * mm, 38 * mm, 22 * mm, 20 * mm, 27 * mm])
    sktable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
    ]))
    story.append(sktable)
    story.append(Spacer(1, 4 * mm))

    # 6. Section 4: Operational Expenses
    story.append(Paragraph("<b>4. STORE OPERATING EXPENSES LOG</b>", sec_hdr))
    exp_rows = [
        [
            Paragraph("<b>#</b>", tbl_hdr),
            Paragraph("<b>EXPENSE DATE</b>", tbl_hdr),
            Paragraph("<b>EXPENSE TITLE / REASON</b>", tbl_hdr),
            Paragraph("<b>CATEGORY</b>", tbl_hdr),
            Paragraph("<b>PAYMENT MODE</b>", tbl_hdr),
            Paragraph(f"<b>AMOUNT ({currency})</b>", tbl_hdr_r)
        ]
    ]
    for idx, e in enumerate(expenses, 1):
        exp_rows.append([
            Paragraph(str(idx), tbl_body),
            Paragraph(str(e.get('expense_date', ''))[:10] or '—', tbl_body),
            Paragraph(f"<b>{e.get('title', '')}</b>", tbl_body),
            Paragraph(e.get('category', 'General'), tbl_body),
            Paragraph(e.get('payment_method', 'Cash') or 'Cash', tbl_body),
            Paragraph(f"<b>{float(e.get('amount') or 0):,.2f}</b>", tbl_body_br)
        ])

    if len(exp_rows) == 1:
        exp_rows.append([Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("No operational expenses logged", tbl_body), Paragraph("—", tbl_body), Paragraph("—", tbl_body), Paragraph("0.00", tbl_body_r)])
    else:
        exp_rows.append([
            Paragraph("", tbl_body),
            Paragraph("<b>TOTAL OPERATIONAL EXPENSES</b>", tbl_body_b),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph("", tbl_body),
            Paragraph(f"<b>{tot_expenses:,.2f}</b>", tbl_body_br)
        ])

    etable = Table(exp_rows, colWidths=[7 * mm, 24 * mm, 62 * mm, 33 * mm, 25 * mm, 35 * mm])
    etable.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#0f172a')),
    ]))
    story.append(etable)

    # 7. Verification & Certification Signatures
    story.append(Spacer(1, 8 * mm))
    cert_table = Table([
        [
            [
                Paragraph("____________________________________________", body_muted),
                Paragraph("<b>Authorized Store Owner / Account Holder</b>", ParagraphStyle('ca1', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#475569'))),
                Paragraph(f"Account: <b>{username}</b> &bull; {biz_name}", body_muted),
                Paragraph("Certified that the store records above are true &amp; accurate.", body_muted)
            ],
            [
                Paragraph("____________________________________________", ParagraphStyle('ca2', parent=body_muted, alignment=2)),
                Paragraph("<b>PANDA ERP Core System &bull; Lead Engineer</b>", ParagraphStyle('ca3', fontName='Helvetica-Bold', fontSize=8, alignment=2, textColor=colors.HexColor('#475569'))),
                Paragraph("<b>Habib Naseer</b> &bull; x10deeredge@gmail.com", ParagraphStyle('ca4', parent=body_muted, alignment=2)),
                Paragraph("Digitally verified with cryptographic password release.", ParagraphStyle('ca5', parent=body_muted, alignment=2))
            ]
        ]
    ], colWidths=[93 * mm, 93 * mm])
    cert_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(cert_table))

    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=4))
    story.append(Paragraph(
        "PANDA Enterprise Wholesale ERP &bull; Official Account Data Backup &bull; All Rights Reserved &bull; Confidential Store Statement",
        ParagraphStyle('Foot', fontName='Helvetica', fontSize=7, alignment=1, textColor=colors.HexColor('#94a3b8'))
    ))

    doc.build(story)
    return buffer.getvalue()
