from decimal import Decimal, ROUND_HALF_UP

from apps.inventory.models import InventoryAdjustment
from apps.reports.pdf import PAGE_SIZES, _escape, render_pdf

LEFT = 50
RIGHT = 50
TOP = 60
BOTTOM = 60
LINE_HEIGHT = 16
WRAP_CHARS = 90


def _number(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:,.2f}"


def _wrap(text, limit=WRAP_CHARS):
    words = str(text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def build_adjustment_pdf(adjustment):
    width, height = PAGE_SIZES["A4"]
    pages = []
    state = {"commands": [], "y": height - TOP}

    def new_page():
        pages.append(state["commands"])
        state["commands"] = []
        state["y"] = height - TOP

    def ensure_space(required=LINE_HEIGHT):
        if state["y"] - required < BOTTOM:
            new_page()

    def text(x, value, size=10):
        state["commands"].extend(
            [
                "BT",
                f"/F1 {size} Tf",
                f"1 0 0 1 {x:.2f} {state['y']:.2f} Tm",
                f"({_escape(value)}) Tj",
                "ET",
            ]
        )

    def rule():
        state["commands"].append(
            f"0.5 w {LEFT:.2f} {state['y']:.2f} m {width - RIGHT:.2f} {state['y']:.2f} l S"
        )

    def advance(amount=LINE_HEIGHT):
        state["y"] -= amount

    organization = adjustment.organization
    currency = (organization.currency if organization and organization.currency else "INR")
    is_value = adjustment.adjustment_type == InventoryAdjustment.AdjustmentType.VALUE

    if organization and organization.name:
        text(LEFT, organization.name, size=14)
        advance(22)
    text(LEFT, "INVENTORY ADJUSTMENT", size=16)
    text(width - RIGHT - 80, adjustment.get_status_display(), size=11)
    advance(24)
    rule()
    advance(20)

    details = [
        ("Date", adjustment.date.strftime("%d %b %Y") if adjustment.date else ""),
        ("Reason", adjustment.reason),
        ("Account", adjustment.account),
        ("Reference#", adjustment.reference_number),
        ("Adjusted By", adjustment.adjusted_by_name),
        ("Adjustment Type", "Value" if is_value else "Quantity"),
    ]
    for label, value in details:
        ensure_space()
        text(LEFT, f"{label}:")
        text(LEFT + 120, value or "-")
        advance()

    advance(10)
    ensure_space(LINE_HEIGHT * 3)
    text(LEFT, "ADJUSTED ITEMS", size=12)
    advance(20)
    item_x, sku_x = LEFT, LEFT + 200
    qty_x, rate_x, value_x = LEFT + 300, LEFT + 370, LEFT + 440
    headers = [(item_x, "ITEM"), (sku_x, "SKU"), (qty_x, "QTY")]
    headers += [(rate_x, "RATE"), (value_x, f"VALUE ({currency})")]
    for x, label in headers:
        text(x, label, size=9)
    advance(6)
    rule()
    advance(14)

    lines = list(adjustment.lines.select_related("item"))
    if not lines:
        text(LEFT, "No items adjusted.")
        advance()
    for line in lines:
        ensure_space()
        name = line.item.name if line.item else "-"
        if len(name) > 34:
            name = name[:31] + "..."
        sku = (line.item.sku if line.item else "") or "-"
        text(item_x, name)
        text(sku_x, sku[:16])
        text(qty_x, _number(line.quantity_adjusted))
        text(rate_x, _number(line.rate))
        text(value_x, _number(line.value))
        advance()

    advance(4)
    rule()
    advance(16)
    ensure_space()
    if is_value:
        text(LEFT, f"Total Adjustment Value: {currency} {_number(adjustment.adjustment_value)}", size=11)
    else:
        text(LEFT, f"Total Quantity Adjusted: {_number(adjustment.quantity_change)}", size=11)
    advance(28)

    description_lines = _wrap(adjustment.description)
    if description_lines:
        ensure_space(LINE_HEIGHT * 2)
        text(LEFT, "MORE INFORMATION", size=12)
        advance(20)
        text(LEFT, "Description:", size=10)
        advance()
        for chunk in description_lines:
            ensure_space()
            text(LEFT, chunk)
            advance()

    pages.append(state["commands"])
    streams = []
    for number, page_commands in enumerate(pages, start=1):
        stream = "\n".join(page_commands)
        stream += (
            f"\nBT\n/F1 8 Tf\n1 0 0 1 {width / 2:.2f} {BOTTOM / 2:.2f} Tm\n"
            f"(Page {number} of {len(pages)}) Tj\nET"
        )
        streams.append(stream)
    return render_pdf(streams, width, height)
