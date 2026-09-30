from decimal import Decimal, ROUND_HALF_UP

from apps.payments_received.models import PaymentReceived
from apps.payments_received.services import customer_display_name
from apps.reports.pdf import PAGE_SIZES, _escape, render_pdf

LEFT = 50
RIGHT = 50
TOP = 60
BOTTOM = 60
LINE_HEIGHT = 16


def _number(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}"


def _date(value):
    return value.strftime("%d %b %Y") if value else ""


def build_receipt_pdf(payment):
    width, height = PAGE_SIZES["A4"]
    commands = []
    state = {"y": height - TOP}
    template = payment.template or PaymentReceived.Template.STANDARD

    def text(x, value, size=10):
        commands.extend(
            [
                "BT",
                f"/F1 {size} Tf",
                f"1 0 0 1 {x:.2f} {state['y']:.2f} Tm",
                f"({_escape(value)}) Tj",
                "ET",
            ]
        )

    def text_right(x_right, value, size=10):
        approx_width = len(str(value or "")) * size * 0.5
        text(x_right - approx_width, value, size=size)

    def rule():
        commands.append(
            f"0.5 w {LEFT:.2f} {state['y']:.2f} m {width - RIGHT:.2f} {state['y']:.2f} l S"
        )

    def advance(amount=LINE_HEIGHT):
        state["y"] -= amount

    organization = payment.organization
    currency = payment.currency or (organization.currency if organization else "") or "INR"

    if template == PaymentReceived.Template.CLASSIC:
        commands.append(
            f"1 w {LEFT - 20:.2f} {BOTTOM - 20:.2f} "
            f"{width - LEFT - RIGHT + 40:.2f} {height - TOP - BOTTOM + 50:.2f} re S"
        )

    if organization:
        text(LEFT, organization.name, size=14)
        advance(16)
        address = ", ".join(
            part
            for part in (
                organization.address_line1,
                organization.address_line2,
                organization.city,
                organization.state,
                organization.postal_code,
            )
            if part
        )
        if address:
            text(LEFT, address, size=9)
            advance(12)
        if organization.country:
            text(LEFT, organization.country, size=9)
            advance(12)
    advance(20)

    if template == PaymentReceived.Template.ELITE:
        band_y = state["y"] - 8
        commands.append(f"0.9 g {LEFT:.2f} {band_y:.2f} {width - LEFT - RIGHT:.2f} 28 re f 0 g")
        text(width / 2 - 70, "PAYMENT RECEIPT", size=16)
    else:
        text(LEFT, "PAYMENT RECEIPT", size=16)
    if payment.is_void:
        text_right(width - RIGHT, "VOID", size=14)
    advance(30)
    rule()
    advance(22)

    details = [
        ("Payment Date", _date(payment.payment_date)),
        ("Reference Number", payment.reference_number or "-"),
        ("Payment Mode", payment.get_payment_mode_display() or "-"),
        ("Payment#", payment.payment_number),
    ]
    for label, value in details:
        text(LEFT, label, size=10)
        text(LEFT + 130, value, size=10)
        advance()

    summary_y = state["y"] + LINE_HEIGHT * len(details)
    box_x = width - RIGHT - 170
    commands.append(f"0.3 0.6 0.3 rg {box_x:.2f} {summary_y - 44:.2f} 170 52 re f 0 g")
    saved_y = state["y"]
    state["y"] = summary_y - 12
    commands.append("1 g")
    text(box_x + 12, "Amount Received", size=10)
    state["y"] -= 22
    text(box_x + 12, f"{currency} {_number(payment.amount)}", size=14)
    commands.append("0 g")
    state["y"] = saved_y

    advance(14)
    text(LEFT, "Received From", size=10)
    advance(LINE_HEIGHT)
    text(LEFT, customer_display_name(payment.customer) or "-", size=12)
    advance(28)

    if Decimal(payment.bank_charges or 0) > 0:
        text(LEFT, f"Bank Charges: {currency} {_number(payment.bank_charges)}", size=10)
        advance(22)

    text(LEFT, "Payment for", size=12)
    advance(20)
    number_x, date_x = LEFT, LEFT + 150
    invoice_amount_right, payment_amount_right = LEFT + 390, width - RIGHT
    text(number_x, "Invoice Number", size=9)
    text(date_x, "Invoice Date", size=9)
    text_right(invoice_amount_right, "Invoice Amount", size=9)
    text_right(payment_amount_right, "Payment Amount", size=9)
    advance(6)
    rule()
    advance(14)

    applications = list(payment.applications.select_related("invoice"))
    if not applications:
        text(LEFT, "No invoices were paid with this payment.", size=10)
        advance()
    for application in applications:
        if state["y"] < BOTTOM + 40:
            break
        invoice = application.invoice
        text(number_x, invoice.invoice_number, size=10)
        text(date_x, _date(invoice.invoice_date), size=10)
        text_right(invoice_amount_right, _number(invoice.total_amount), size=10)
        text_right(payment_amount_right, _number(application.amount), size=10)
        advance()

    advance(4)
    rule()
    advance(18)
    if payment.unused_amount > 0:
        text(LEFT, f"Amount in Excess: {currency} {_number(payment.unused_amount)}", size=10)
        advance()
    if payment.is_void and payment.void_reason:
        text(LEFT, f"Void Reason: {payment.void_reason[:90]}", size=10)
        advance()

    stream = "\n".join(commands)
    stream += (
        f"\nBT\n/F1 8 Tf\n1 0 0 1 {width / 2 - 20:.2f} {BOTTOM / 2:.2f} Tm\n"
        f"(Page 1 of 1) Tj\nET"
    )
    return render_pdf([stream], width, height)


def receipt_filename(payment):
    number = payment.payment_number or str(payment.id)[:8]
    digits = number.split("-")[-1].lstrip("0") or number
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in digits)
    return f"Payment-{safe}.pdf"
