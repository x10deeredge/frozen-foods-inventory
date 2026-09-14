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
