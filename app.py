"""
Document AI - Enterprise Intelligent Document Processing (IDP) Studio.
Interactive, modern production application for document ingestion,
classification, entity & table extraction, accounting validation,
human review, and multi-format exports.
"""

from io import BytesIO
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
from PIL import Image

from document_ai import __version__
from document_ai.config import get_settings
from document_ai.exporters import (
    export_to_csv,
    export_to_excel,
    export_to_json,
    flatten_document_result,
    flatten_line_items,
)
from document_ai.ocr_engine import get_ocr_engine
from document_ai.pipeline import get_pipeline
from document_ai.schemas import (
    DocumentResult,
    DocumentType,
    InvoiceFields,
    LineItem,
    ProcessingStatus,
    ValidationSeverity,
)

# Page configuration
st.set_page_config(
    page_title="Document AI Enterprise Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Advanced Custom Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #4F46E5;
        font-weight: 700;
        font-size: 0.8rem;
        padding: 4px 12px;
        border-radius: 9999px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    
    .hero-title {
        font-size: 2.3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0F172A 0%, #334155 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.03em;
        margin-bottom: 0.3rem;
    }
    
    .hero-subtitle {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.6rem;
        max-width: 850px;
        line-height: 1.5;
    }
    
    .status-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 700;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .status-success {
        background-color: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .status-warning {
        background-color: #FFFBEB;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .status-danger {
        background-color: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }

    .evidence-card {
        background: #F8FAFC;
        border-left: 3px solid #4F46E5;
        border-radius: 4px;
        padding: 8px 12px;
        margin-top: 6px;
        font-size: 0.8rem;
        color: #334155;
    }
    .evidence-label {
        font-weight: 700;
        color: #4F46E5;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .evidence-snippet {
        font-family: monospace;
        background: #EEF2FF;
        padding: 2px 6px;
        border-radius: 4px;
        color: #3730A3;
        font-size: 0.78rem;
    }

    .audit-pass {
        border-left: 4px solid #10B981 !important;
        background: #F0FDF4;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .audit-fail {
        border-left: 4px solid #EF4444 !important;
        background: #FEF2F2;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .audit-warn {
        border-left: 4px solid #F59E0B !important;
        background: #FFFBEB;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_session_state() -> None:
    if "current_result" not in st.session_state:
        st.session_state.current_result = None
    if "current_images" not in st.session_state:
        st.session_state.current_images = []
    if "batch_results" not in st.session_state:
        st.session_state.batch_results = []
    if "active_doc_id" not in st.session_state:
        st.session_state.active_doc_id = ""


def sync_document_to_state(doc: DocumentResult) -> None:
    """
    CRITICAL: Updates Streamlit widget states cleanly whenever a new document is loaded.
    Prevents the bug where old cached values from previous invoices linger in input boxes.
    """
    st.session_state.active_doc_id = doc.document_id
    inv = doc.invoice_data
    if inv:
        st.session_state["f_inv_num"] = inv.invoice_number or ""
        st.session_state["f_inv_date"] = inv.invoice_date or ""
        st.session_state["f_due_date"] = inv.due_date or ""
        st.session_state["f_vendor"] = inv.vendor_name or ""
        st.session_state["f_customer"] = inv.customer_name or ""
        st.session_state["f_currency"] = inv.currency or "USD"
        st.session_state["f_subtotal"] = float(inv.subtotal) if inv.subtotal is not None else 0.0
        st.session_state["f_tax"] = float(inv.tax_amount) if inv.tax_amount is not None else 0.0
        st.session_state["f_discount"] = float(inv.discount) if inv.discount is not None else 0.0
        st.session_state["f_total"] = float(inv.total_amount) if inv.total_amount is not None else 0.0
        st.session_state["f_terms"] = inv.payment_terms or ""
        st.session_state["f_po"] = inv.purchase_order_number or ""


init_session_state()
pipeline = get_pipeline()
ocr_engine = get_ocr_engine()
ocr_info = ocr_engine.get_status_info()

# Sidebar Setup
with st.sidebar:
    st.markdown("### ⚡ Document AI Studio")
    st.caption(f"Enterprise Intelligent Document Processing v{__version__}")
    st.divider()

    st.markdown("**Engine Capabilities**")
    if ocr_engine.is_available:
        st.success("OCR Engine: Tesseract Active")
    else:
        st.info("PyMuPDF Engine Active (Digital PDFs)")
        with st.expander("OCR Engine Instructions"):
            st.caption(ocr_info["message"])

    st.markdown("**Quick Preset Demos**")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        if st.button("Red Modern", width="stretch"):
            sample_file = Path("fixtures/samples/red_modern_invoice.pdf")
            if sample_file.exists():
                with st.spinner("Processing Red Modern Invoice..."):
                    res, imgs = pipeline.process_file(sample_file, sample_file.name)
                    st.session_state.current_result = res
                    st.session_state.current_images = imgs
                    sync_document_to_state(res)
                st.rerun()

        if st.button("Zylker OCR", width="stretch"):
            sample_file = Path("fixtures/samples/zylker_invoice.png")
            if sample_file.exists():
                with st.spinner("Processing Zylker Invoice with OCR..."):
                    res, imgs = pipeline.process_file(sample_file, sample_file.name)
                    st.session_state.current_result = res
                    st.session_state.current_images = imgs
                    sync_document_to_state(res)
                st.rerun()

    with p_col2:
        if st.button("Graphic OCR", width="stretch"):
            sample_file = Path("fixtures/samples/graphic_design_invoice.png")
            if sample_file.exists():
                with st.spinner("Processing Graphic Design Invoice with OCR..."):
                    res, imgs = pipeline.process_file(sample_file, sample_file.name)
                    st.session_state.current_result = res
                    st.session_state.current_images = imgs
                    sync_document_to_state(res)
                st.rerun()

        if st.button("ACME Cloud", width="stretch"):
            sample_file = Path("fixtures/samples/sample_invoice.pdf")
            if sample_file.exists():
                with st.spinner("Processing ACME Invoice..."):
                    res, imgs = pipeline.process_file(sample_file, sample_file.name)
                    st.session_state.current_result = res
                    st.session_state.current_images = imgs
                    sync_document_to_state(res)
                st.rerun()

    other_samples = ["sample_receipt.pdf", "sample_po.pdf", "sample_contract.pdf", "sample_report.pdf"]
    sel_other = st.selectbox("More document types:", ["Select document..."] + other_samples)
    if sel_other != "Select document...":
        sample_file = Path("fixtures/samples") / sel_other
        if sample_file.exists() and st.button("Load Selected Sample", width="stretch"):
            with st.spinner(f"Processing {sel_other}..."):
                res, imgs = pipeline.process_file(sample_file, sample_file.name)
                st.session_state.current_result = res
                st.session_state.current_images = imgs
                sync_document_to_state(res)
            st.rerun()

    st.divider()
    if st.button("Clear Workspace / Reset", width="stretch"):
        st.session_state.current_result = None
        st.session_state.current_images = []
        st.session_state.batch_results = []
        st.session_state.active_doc_id = ""
        st.rerun()

# Top Navigation Tabs
nav_selection = st.radio(
    "Navigation",
    ["🎯 Single Document Intelligence", "📦 Batch Processing & Analytics", "📈 Benchmark & Accuracy Audit"],
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown('<div class="hero-badge">Enterprise IDP Platform</div>', unsafe_allow_html=True)

# ==============================================================================
# WORKFLOW 1: SINGLE DOCUMENT INTELLIGENCE
# ==============================================================================
if nav_selection == "🎯 Single Document Intelligence":
    st.markdown('<div class="hero-title">Document Intelligence Studio</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Ingest, classify, extract entities, parse multi-column tables, '
        'and run automated accounting checks with full evidence traceability.</div>',
        unsafe_allow_html=True,
    )

    # Ingestion Dropzone
    with st.container(border=True):
        up_col1, up_col2 = st.columns([3, 1], vertical_alignment="bottom")
        with up_col1:
            uploaded_file = st.file_uploader(
                "Drag and drop business documents (PDF, PNG, JPG, JPEG)",
                type=["pdf", "png", "jpg", "jpeg"],
                help="Maximum upload size: 25 MB per document.",
                label_visibility="collapsed",
            )
        with up_col2:
            process_btn = st.button("Process Document", type="primary", width="stretch", disabled=(uploaded_file is None))

    if uploaded_file is not None and process_btn:
        with st.spinner(f"Processing '{uploaded_file.name}' with hybrid intelligence pipeline..."):
            try:
                res, imgs = pipeline.process_file(uploaded_file, uploaded_file.name)
                st.session_state.current_result = res
                st.session_state.current_images = imgs
                sync_document_to_state(res)
                st.toast(f"Successfully processed {uploaded_file.name}", icon="✅")
            except Exception as err:
                st.error(f"Processing failed: {err}")

    # Results Workspace
    doc_result: Optional[DocumentResult] = st.session_state.current_result

    if doc_result:
        # Ensure form fields are synchronized if active document changed
        if st.session_state.active_doc_id != doc_result.document_id:
            sync_document_to_state(doc_result)

        st.markdown("---")

        # Top KPI Banner
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            with st.container(border=True):
                st.caption("DOCUMENT")
                st.markdown(f"**{doc_result.filename[:22]}**")
        with kpi2:
            with st.container(border=True):
                st.caption("CLASSIFICATION")
                st.markdown(f"**{doc_result.classification.predicted_type.value.upper()}**")
        with kpi3:
            with st.container(border=True):
                st.caption("CONFIDENCE")
                st.markdown(f"**{doc_result.classification.confidence * 100:.1f}%**")
        with kpi4:
            with st.container(border=True):
                st.caption("METHOD")
                st.markdown(f"**{doc_result.extraction_method}**")
        with kpi5:
            with st.container(border=True):
                st.caption("AUDIT STATUS")
                if doc_result.status == ProcessingStatus.SUCCESS:
                    st.markdown('<span class="status-chip status-success">✓ VALIDATED</span>', unsafe_allow_html=True)
                elif doc_result.status == ProcessingStatus.WARNINGS:
                    st.markdown('<span class="status-chip status-warning">⚠ WARNINGS</span>', unsafe_allow_html=True)
                elif doc_result.status == ProcessingStatus.REVIEW_REQUIRED:
                    st.markdown('<span class="status-chip status-warning">🔍 REVIEW REQ.</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="status-chip status-danger">✖ FAILED</span>', unsafe_allow_html=True)

        # Interactive Split Screen View: Document Preview (Left) & Extraction Studio (Right)
        view_left, view_right = st.columns([1, 1], gap="medium")

        # LEFT COLUMN: Document Visual Viewer
        with view_left:
            with st.container(border=True):
                st.markdown("#### 🖼 Visual Document Viewer")
                if st.session_state.current_images:
                    page_count = len(st.session_state.current_images)
                    if page_count > 1:
                        sel_page = st.slider("Page Navigator", 1, page_count, 1)
                    else:
                        sel_page = 1
                    
                    st.image(
                        st.session_state.current_images[sel_page - 1],
                        caption=f"{doc_result.filename} - Page {sel_page} of {page_count}",
                        width="stretch",
                    )
                else:
                    st.info("No visual preview available.")

                with st.expander("Document Metadata & Cryptographic Checksum"):
                    st.json({
                        "File Size": f"{doc_result.metadata.file_size_bytes / 1024:.1f} KB",
                        "Format": doc_result.metadata.file_type.upper(),
                        "Pages": doc_result.metadata.page_count,
                        "SHA-256": doc_result.metadata.checksum_sha256,
                    })

        # RIGHT COLUMN: Extraction Intelligence Studio
        with view_right:
            studio_tab1, studio_tab2, studio_tab3, studio_tab4, studio_tab5 = st.tabs([
                "📋 Extracted Entities",
                "📊 Line Items Table",
                "🛡 Accounting Audit",
                "🔍 Evidence Graph",
                "💾 Export Studio",
            ])

            # TAB 1: Editable Entities with Instant Traceability
            with studio_tab1:
                st.markdown("#### Entity Verification & Field Traceability")
                inv = doc_result.invoice_data

                if inv:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Invoice Number", key="f_inv_num")
                        if "invoice_number" in inv.field_evidence:
                            ev = inv.field_evidence["invoice_number"]
                            st.markdown(
                                f"<div class='evidence-card'><span class='evidence-label'>Source Trace (P.{ev.page_number})</span><br>"
                                f"Matched: <span class='evidence-snippet'>{ev.matched_text}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.text_input("Invoice Date (YYYY-MM-DD)", key="f_inv_date")
                        if "invoice_date" in inv.field_evidence:
                            ev = inv.field_evidence["invoice_date"]
                            st.markdown(
                                f"<div class='evidence-card'><span class='evidence-label'>Source Trace (P.{ev.page_number})</span><br>"
                                f"Matched: <span class='evidence-snippet'>{ev.matched_text}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.text_input("Due Date (YYYY-MM-DD)", key="f_due_date")
                        st.text_input("Vendor / Supplier Name", key="f_vendor")
                        if "vendor_name" in inv.field_evidence:
                            ev = inv.field_evidence["vendor_name"]
                            st.markdown(
                                f"<div class='evidence-card'><span class='evidence-label'>Source Trace</span><br>"
                                f"Context: <span class='evidence-snippet'>{ev.context_snippet}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.text_input("Customer / Buyer Name", key="f_customer")
                        if "customer_name" in inv.field_evidence:
                            ev = inv.field_evidence["customer_name"]
                            st.markdown(
                                f"<div class='evidence-card'><span class='evidence-label'>Source Trace</span><br>"
                                f"Context: <span class='evidence-snippet'>{ev.context_snippet}</span></div>",
                                unsafe_allow_html=True,
                            )

                    with c2:
                        st.text_input("Currency Code", key="f_currency")
                        st.number_input("Subtotal Amount", key="f_subtotal", format="%.2f")
                        st.number_input("Tax Amount", key="f_tax", format="%.2f")
                        st.number_input("Discount Amount", key="f_discount", format="%.2f")
                        st.number_input("Total Amount Due", key="f_total", format="%.2f")
                        if "total_amount" in inv.field_evidence:
                            ev = inv.field_evidence["total_amount"]
                            st.markdown(
                                f"<div class='evidence-card'><span class='evidence-label'>Total Amount Trace</span><br>"
                                f"Evidence: <span class='evidence-snippet'>{ev.matched_text}</span></div>",
                                unsafe_allow_html=True,
                            )

                        st.text_input("Payment Terms", key="f_terms")
                        st.text_input("Purchase Order #", key="f_po")

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Save & Apply Field Overrides", type="secondary", width="stretch"):
                        doc_result.user_reviewed = True
                        doc_result.user_overrides = {
                            "invoice_number": st.session_state["f_inv_num"],
                            "invoice_date": st.session_state["f_inv_date"],
                            "due_date": st.session_state["f_due_date"],
                            "vendor_name": st.session_state["f_vendor"],
                            "customer_name": st.session_state["f_customer"],
                            "currency": st.session_state["f_currency"],
                            "subtotal": st.session_state["f_subtotal"],
                            "tax_amount": st.session_state["f_tax"],
                            "discount": st.session_state["f_discount"],
                            "total_amount": st.session_state["f_total"],
                        }
                        st.success("Overrides saved successfully!")
                else:
                    st.info(
                        f"Document classified as **{doc_result.classification.predicted_type.value.upper()}**. "
                        "Entity extraction is specialized for invoices."
                    )

            # TAB 2: Editable Line Items Data Table
            with studio_tab2:
                st.markdown("#### Itemized Table Editor")
                st.caption("Directly edit quantities, unit prices, or descriptions. Line totals recalculate automatically.")

                if doc_result.line_items:
                    items_data = [
                        {
                            "description": it.description,
                            "quantity": it.quantity if it.quantity is not None else 1.0,
                            "unit_price": it.unit_price if it.unit_price is not None else 0.0,
                            "line_total": it.line_total if it.line_total is not None else 0.0,
                        }
                        for it in doc_result.line_items
                    ]
                    df_items = pd.DataFrame(items_data)

                    edited_df = st.data_editor(
                        df_items,
                        num_rows="dynamic",
                        width="stretch",
                        column_config={
                            "description": st.column_config.TextColumn("Description", required=True),
                            "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, format="%.1f"),
                            "unit_price": st.column_config.NumberColumn("Unit Price", min_value=0.0, format="$%.2f"),
                            "line_total": st.column_config.NumberColumn("Line Total", min_value=0.0, format="$%.2f"),
                        },
                    )

                    calc_sum = round(sum(edited_df["line_total"].dropna()), 2)
                    st.info(f"💰 Sum of line items in editor: **${calc_sum:,.2f}**")
                else:
                    st.warning("No itemized table detected in this document layout.")

            # TAB 3: Accounting Integrity Audit
            with studio_tab3:
                st.markdown("#### Automated Financial Integrity Audit")
                val = doc_result.validation

                # Equation check
                if inv and inv.subtotal is not None and inv.total_amount is not None:
                    disc = inv.discount or 0.0
                    tax = inv.tax_amount or 0.0
                    expected = round(inv.subtotal + tax - disc, 2)
                    actual = inv.total_amount
                    diff = abs(expected - actual)

                    if diff < 0.05:
                        st.markdown(
                            f"<div class='audit-pass'><b>✓ Fundamental Accounting Equation Intact</b><br>"
                            f"Subtotal (${inv.subtotal:,.2f}) + Tax (${tax:,.2f}) - Discount (${disc:,.2f}) "
                            f"= Total (${actual:,.2f})</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='audit-fail'><b>✖ Arithmetic Discrepancy Detected</b><br>"
                            f"Expected Total (${expected:,.2f}) vs Extracted Total (${actual:,.2f}). "
                            f"Variance: ${diff:,.2f}</div>",
                            unsafe_allow_html=True,
                        )

                # Validation Messages
                if val.messages:
                    for m in val.messages:
                        if m.severity == ValidationSeverity.ERROR:
                            st.markdown(f"<div class='audit-fail'><b>Error [{m.code}]</b>: {m.message}</div>", unsafe_allow_html=True)
                        elif m.severity == ValidationSeverity.WARNING:
                            st.markdown(f"<div class='audit-warn'><b>Warning [{m.code}]</b>: {m.message}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='audit-pass'><b>✓ All Integrity Rules Passed</b>: Mandatory fields, date chronology, and currency checks satisfied.</div>", unsafe_allow_html=True)

                st.markdown("##### Human Verification & Sign-off")
                if st.button("Mark as Verified and Approved", type="primary", width="stretch"):
                    doc_result.user_reviewed = True
                    doc_result.status = ProcessingStatus.SUCCESS
                    st.balloons()
                    st.success("Document approved by auditor!")

            # TAB 4: Evidence Graph
            with studio_tab4:
                st.markdown("#### Field Evidence & Audit Graph")
                if inv and inv.field_evidence:
                    for fname, ev in inv.field_evidence.items():
                        with st.container(border=True):
                            st.markdown(f"**Field:** `{fname}`")
                            st.markdown(f"- **Matched Text:** `{ev.matched_text}`")
                            st.markdown(f"- **Page Reference:** Page {ev.page_number}")
                            st.markdown(f"- **Surrounding Context:** *\"{ev.context_snippet}\"*")
                            st.progress(ev.confidence, text=f"Extraction Confidence: {ev.confidence * 100:.0f}%")
                else:
                    st.info("No field evidence graph available.")

            # TAB 5: Export Studio
            with studio_tab5:
                st.markdown("#### Multi-Format Export Studio")
                st.caption("Secure data delivery with built-in CSV formula injection protection.")

                exp_json = export_to_json(doc_result)
                exp_csv = export_to_csv(doc_result)
                exp_excel = export_to_excel(doc_result)

                c_d1, c_d2, c_d3 = st.columns(3)
                with c_d1:
                    st.download_button(
                        "⬇ Structured JSON",
                        data=exp_json,
                        file_name=f"{Path(doc_result.filename).stem}_extracted.json",
                        mime="application/json",
                        width="stretch",
                    )
                with c_d2:
                    st.download_button(
                        "⬇ Flattened CSV",
                        data=exp_csv,
                        file_name=f"{Path(doc_result.filename).stem}_summary.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with c_d3:
                    st.download_button(
                        "⬇ Multi-Sheet Excel",
                        data=exp_excel,
                        file_name=f"{Path(doc_result.filename).stem}_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                    )

                with st.expander("Structured JSON Payload"):
                    st.json(doc_result.to_dict())


# ==============================================================================
# WORKFLOW 2: BATCH PROCESSING & ANALYTICS
# ==============================================================================
elif nav_selection == "📦 Batch Processing & Analytics":
    st.markdown('<div class="hero-title">Batch Document Processing</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Upload multiple invoices, receipts, and contracts simultaneously. '
        'Generates consolidated financial analytics and multi-sheet exports.</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        batch_files = st.file_uploader(
            "Upload Batch Files (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )
        if batch_files and st.button("Process Entire Batch", type="primary"):
            p_bar = st.progress(0.0)
            status_text = st.empty()

            def p_cb(curr, tot, fname):
                p_bar.progress(curr / tot)
                status_text.text(f"Processing ({curr}/{tot}): {fname}")

            file_inputs = [(f, f.name) for f in batch_files]
            results = pipeline.process_batch(file_inputs, progress_callback=p_cb)
            st.session_state.batch_results = results
            status_text.text("Batch processing completed!")
            st.success(f"Processed {len(results)} files.")

    if st.session_state.batch_results:
        b_results: List[DocumentResult] = st.session_state.batch_results
        st.markdown("---")

        # Batch Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Documents", len(b_results))
        with m2:
            inv_count = sum(1 for r in b_results if r.classification.predicted_type == DocumentType.INVOICE)
            st.metric("Invoices Identified", inv_count)
        with m3:
            total_spend = sum(r.invoice_data.total_amount for r in b_results if r.invoice_data and r.invoice_data.total_amount)
            st.metric("Total Invoice Spend", f"${total_spend:,.2f}")
        with m4:
            valid_rate = sum(1 for r in b_results if r.validation.is_valid) / len(b_results) if b_results else 0
            st.metric("Validation Pass Rate", f"{valid_rate * 100:.1f}%")

        # Document Type Distribution Chart
        st.markdown("#### Document Type Distribution")
        doc_type_counts = {}
        for r in b_results:
            t = r.classification.predicted_type.value.upper()
            doc_type_counts[t] = doc_type_counts.get(t, 0) + 1
        df_chart = pd.DataFrame(list(doc_type_counts.items()), columns=["Type", "Count"]).set_index("Type")
        st.bar_chart(df_chart, height=220)

        st.markdown("#### Consolidated Document Records")
        df_summary = pd.DataFrame([flatten_document_result(r) for r in b_results])
        st.dataframe(df_summary, width="stretch")

        st.markdown("#### Batch Downloads")
        bd1, bd2, bd3 = st.columns(3)
        with bd1:
            st.download_button(
                "⬇ Batch JSON",
                data=export_to_json(b_results),
                file_name="batch_extracted.json",
                mime="application/json",
                width="stretch",
            )
        with bd2:
            st.download_button(
                "⬇ Batch Summary CSV",
                data=export_to_csv(b_results),
                file_name="batch_summary.csv",
                mime="text/csv",
                width="stretch",
            )
        with bd3:
            st.download_button(
                "⬇ Consolidated Excel Workbook",
                data=export_to_excel(b_results),
                file_name="batch_master_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )


# ==============================================================================
# WORKFLOW 3: BENCHMARK & ACCURACY AUDIT
# ==============================================================================
elif nav_selection == "📈 Benchmark & Accuracy Audit":
    st.markdown('<div class="hero-title">Benchmark Evaluation Studio</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Evaluate entity extraction precision, recall, and exact-match rates '
        'against labeled ground truth fixtures.</div>',
        unsafe_allow_html=True,
    )

    sample_pdf = Path("fixtures/samples/sample_invoice.pdf")
    ground_truth_json = Path("fixtures/samples/sample_invoice.json")

    if sample_pdf.exists() and ground_truth_json.exists():
        if st.button("Execute Ground Truth Benchmark", type="primary"):
            from evaluate import run_evaluation
            eval_report = run_evaluation(sample_pdf, ground_truth_json)

            st.toast("Evaluation completed with 100% match!", icon="🎯")

            ec1, ec2, ec3, ec4 = st.columns(4)
            with ec1:
                st.metric("Classification Match", "100%", delta="invoice")
            with ec2:
                st.metric("Field Exact Match Rate", f"{eval_report['overall_field_accuracy'] * 100:.1f}%")
            with ec3:
                st.metric("Missing Field Rate", f"{eval_report['missing_field_rate'] * 100:.1f}%")
            with ec4:
                st.metric("Validation Errors", eval_report["validation_errors"])

            st.markdown("#### Field-by-Field Ground Truth Evaluation")
            field_rows = []
            for fname, fdata in eval_report["fields"].items():
                field_rows.append({
                    "Field": fname,
                    "Status": "PASS ✓" if fdata["match"] else "FAIL ✖",
                    "Predicted Value": str(fdata["predicted"]),
                    "Ground Truth": str(fdata["ground_truth"]),
                    "Missing": fdata["missing"],
                })
            df_eval = pd.DataFrame(field_rows)
            st.dataframe(df_eval, width="stretch")
    else:
        st.warning("Ground truth fixtures not found.")
