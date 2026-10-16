"""
Synthetic document generator for automated tests and live demos.
Generates genuine digital PDFs, images, and non-invoice document types.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymupdf


def create_sample_documents(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Standard Digital Invoice PDF
    inv_pdf_path = output_dir / "sample_invoice.pdf"
    doc_inv = pymupdf.open()
    page_inv = doc_inv.new_page(width=595, height=842)  # A4 size

    invoice_text = (
        "ACME Solutions Inc.\n"
        "123 Innovation Way, Tech Park, CA 94016\n"
        "info@acmesolutions.com | (555) 019-2834\n\n"
        "TAX INVOICE\n\n"
        "Invoice Number: INV-2024-0042\n"
        "Invoice Date: 2024-03-15\n"
        "Due Date: 2024-04-14\n"
        "Payment Terms: Net 30\n"
        "Purchase Order Number: PO-89211\n\n"
        "BILL TO:\n"
        "Global Logistics Enterprises\n"
        "742 Industrial Parkway\n"
        "Chicago, IL 60607\n\n"
        "---------------------------------------------------------------------------------------\n"
        "Description                       Qty      Unit Price (USD)         Line Total (USD)\n"
        "---------------------------------------------------------------------------------------\n"
        "Enterprise Cloud Hosting            2                250.00                   500.00\n"
        "Database Optimization Service       1                750.00                   750.00\n"
        "API Security Audit Retainer         1                450.00                   450.00\n"
        "---------------------------------------------------------------------------------------\n\n"
        "Subtotal: $1,700.00\n"
        "Tax: $170.00\n"
        "Discount: $0.00\n"
        "Total Amount: $1,870.00\n\n"
        "Payment Terms: Net 30\n"
        "Thank you for your business!\n"
    )
    page_inv.insert_text((50, 70), invoice_text, fontsize=10, fontname="helv")
    doc_inv.save(str(inv_pdf_path))
    doc_inv.close()

    # 2. Sample Receipt PDF
    receipt_pdf_path = output_dir / "sample_receipt.pdf"
    doc_rec = pymupdf.open()
    page_rec = doc_rec.new_page(width=300, height=500)
    receipt_text = (
        "CORNER CAFE & BAKERY\n"
        "STORE #1042 - POS REGISTER 03\n"
        "CASHIER: SARAH M.\n"
        "================================\n"
        "RECEIPT\n"
        "DATE: 2024-04-10 14:22\n"
        "================================\n"
        "2x ESPRESSO ROAST         $8.00\n"
        "1x CROISSANT              $4.50\n"
        "1x BLUEBERRY MUFFIN       $3.75\n"
        "--------------------------------\n"
        "SUBTOTAL:                $16.25\n"
        "TAX:                      $1.30\n"
        "TOTAL:                   $17.55\n"
        "CASH TENDERED:           $20.00\n"
        "CHANGE DUE:               $2.45\n"
        "ITEMS SOLD: 4\n"
        "THANK YOU FOR YOUR VISIT!\n"
    )
    page_rec.insert_text((20, 40), receipt_text, fontsize=9, fontname="helv")
    doc_rec.save(str(receipt_pdf_path))
    doc_rec.close()

    # 3. Sample Purchase Order PDF
    po_pdf_path = output_dir / "sample_po.pdf"
    doc_po = pymupdf.open()
    page_po = doc_po.new_page(width=595, height=842)
    po_text = (
        "GLOBAL LOGISTICS ENTERPRISES\n"
        "742 Industrial Parkway, Chicago, IL 60607\n\n"
        "PURCHASE ORDER\n\n"
        "PO Number: PO-89211\n"
        "Order Date: 2024-03-01\n"
        "Vendor Order: ACME Solutions Inc.\n"
        "Ship To: Chicago Central Warehouse, Dock 4\n"
        "Requisition No: REQ-4491\n"
        "Order Placed By: Supply Chain Procurement Division\n\n"
        "Item               Qty     Unit Price     Total\n"
        "Cloud Hosting        2         250.00    500.00\n"
        "Database Audit       1         750.00    750.00\n"
        "Security Retainer    1         450.00    450.00\n\n"
        "Total Authorized: $1,870.00\n"
    )
    page_po.insert_text((50, 70), po_text, fontsize=10, fontname="helv")
    doc_po.save(str(po_pdf_path))
    doc_po.close()

    # 4. Sample Contract PDF
    contract_pdf_path = output_dir / "sample_contract.pdf"
    doc_con = pymupdf.open()
    page_con = doc_con.new_page(width=595, height=842)
    contract_text = (
        "MASTER SERVICES AGREEMENT\n\n"
        "THIS AGREEMENT is entered into as of January 15, 2024 by and between ACME Corp and Global Logistics.\n\n"
        "WHEREAS, Client desires to retain Contractor to perform technical consultancy;\n"
        "WHEREAS, Contractor possesses the requisite skills and experience;\n\n"
        "NOW, THEREFORE, the parties hereto agree as follows:\n"
        "1. Scope of Work and Deliverables.\n"
        "2. Terms and Conditions.\n"
        "3. Indemnification and Limitation of Liability.\n"
        "4. Governing Law: This Agreement shall be construed under the laws of the State of California.\n\n"
        "IN WITNESS WHEREOF, the parties hereto have executed this Agreement.\n"
    )
    page_con.insert_text((50, 70), contract_text, fontsize=10, fontname="helv")
    doc_con.save(str(contract_pdf_path))
    doc_con.close()

    # 5. Sample Business Report PDF
    report_pdf_path = output_dir / "sample_report.pdf"
    doc_rep = pymupdf.open()
    page_rep = doc_rep.new_page(width=595, height=842)
    report_text = (
        "ANNUAL REPORT 2024 - STRATEGIC OVERVIEW\n\n"
        "TABLE OF CONTENTS\n"
        "1. Executive Summary\n"
        "2. Market Dynamics & Key Findings\n"
        "3. Research Methodology\n"
        "4. Financial Highlights\n"
        "5. Conclusion and Recommendations\n\n"
        "EXECUTIVE SUMMARY\n"
        "During fiscal year 2024, our enterprise achieved significant growth across cloud services.\n"
        "Key findings indicate recurring revenue increased by 34% year-over-year.\n"
        "Our methodology combines quantitative operational metrics with customer telemetry.\n"
    )
    page_rep.insert_text((50, 70), report_text, fontsize=10, fontname="helv")
    doc_rep.save(str(report_pdf_path))
    doc_rep.close()

    # 6. Sample PNG image invoice
    img_path = output_dir / "sample_invoice.png"
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 590, 390], outline=(180, 180, 180), width=2)
    draw.text((30, 30), "TAX INVOICE - QUICK SERVICES", fill=(0, 0, 0))
    draw.text((30, 60), "Invoice #: INV-9901 | Date: 2024-05-01", fill=(0, 0, 0))
    draw.text((30, 90), "Bill To: Apex Retail Corp", fill=(0, 0, 0))
    draw.text((30, 130), "Consulting Service    1    $500.00    $500.00", fill=(0, 0, 0))
    draw.text((30, 170), "Subtotal: $500.00 | Tax: $50.00 | Total: $550.00", fill=(0, 0, 0))
    img.save(img_path)

    # 7. Sample Corrupt PDF (invalid header/bytes)
    corrupt_pdf_path = output_dir / "sample_corrupt.pdf"
    with open(corrupt_pdf_path, "wb") as f:
        f.write(b"NOT_A_VALID_PDF_FILE_HEADER_TRUNCATED")


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "fixtures" / "samples"
    create_sample_documents(target)
    print(f"Generated synthetic documents in: {target}")
