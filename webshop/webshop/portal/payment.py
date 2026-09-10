"""Portal "Pay" endpoint for logged-in webshop customers and suppliers.

PR-Foundry/framework#182 (fork marker).

ERPNext's ``make_payment_request`` gates on **two** doctype permissions, in this order::

    frappe.has_permission("Payment Request", "create", throw=True)   # doctype-INDEPENDENT
    frappe.has_permission(args.dt, "read", args.dn, throw=True)      # per reference doctype

A real portal user's roles are ``['All', 'Customer', 'Guest']`` (``Portal Settings.default_role``
is ``Customer``), and erpnext ships **no** permission row granting ``Customer`` anything on
Payment Request, Sales Invoice or Sales Order. ``frappe.has_permission`` consults role, user and
share permissions only -- never website permission -- so **both** gates fail, for **every**
reference doctype. The native order-page "Pay" link therefore 403s for exactly the customers the
on-account flow exists to serve.

What a portal user *does* hold is ``has_website_permission`` on their own document, backed by a
``Portal User`` row on their Customer (``erpnext.controllers.website_list_for_contact``). This
module gates on that -- the permission they actually have -- and only then elevates so
``make_payment_request``'s own doctype checks pass. The ownership gate always runs *before* any
elevation, so a user can never pay another party's document.

Why this lives in **webshop** and not in a client app: webshop owns the template that calls it and
is forked by every sibling from PR-Foundry, so siblings inherit one implementation. The previous
per-tier wrappers (``client_app.api.portal.pay_invoice`` here,
``client_app.api.guest_checkout.pay_for_order`` at OA-Method) each lived in a *client-specific*
app, which is precisely why the shared template diverged and why a sibling could not resolve the
function the template named.

Known, unclosed: framework#109 -- this endpoint is state-changing but reachable via GET, mirroring
the native ``make_payment_request`` GET pattern.
"""

import frappe
from erpnext.accounts.doctype.payment_request.payment_request import (
    ALLOWED_DOCTYPES_FOR_PAYMENT_REQUEST,
    get_amount,
    make_payment_request,
)
from frappe import _
from frappe.utils import flt

# erpnext decides the Payment Request direction from exactly these two doctypes
# ("payment_request_type = 'Outward' if args.get('dt') in ['Purchase Order', 'Purchase Invoice']").
# The party side is derived the same way rather than classified a second time here.
_SUPPLIER_SIDE_DOCTYPES = ("Purchase Order", "Purchase Invoice")


def amount_due(doc) -> float:
    """Return what erpnext would actually charge for ``doc`` right now, else ``0.0``.

    This delegates to erpnext's own :func:`get_amount` -- the very function
    ``make_payment_request`` uses to set the Payment Request's ``grand_total``. Asking the
    *charging* function whether there is anything to charge is what keeps the affordance and
    the charge from drifting apart: the button is offered exactly when a non-zero amount would
    be requested.

    It also removes the per-doctype hand-rolled conditions this bug came from. ``get_amount``
    already handles both shapes, currency conversion included:

    * Sales/Purchase Order -- ``(rounded_total or grand_total) - flt(advance_paid)``; ``flt``
      maps a ``None`` ``advance_paid`` (its value before any payment) to ``0.0``.
    * Sales/Purchase Invoice -- driven by ``outstanding_amount``.

    Fails **closed** (returns ``0.0``) if erpnext cannot value the document. A hidden Pay button
    costs the customer a phone call; a Pay button shown on a settled document is a real double
    charge (framework#183), so the safe direction is not symmetric.
    """
    if doc.doctype not in ALLOWED_DOCTYPES_FOR_PAYMENT_REQUEST:
        return 0.0

    try:
        return flt(get_amount(doc))
    except Exception:  # noqa: BLE001 -- deliberate: ANY valuation failure must fail closed
        frappe.log_error(
            title="webshop: could not value document for portal payment",
            message=f"{doc.doctype} {doc.name}: {frappe.get_traceback()}",
        )
        return 0.0


def is_payable(doc) -> bool:
    """Return True when ``doc`` still owes money and erpnext can raise a Payment Request for it."""
    return amount_due(doc) > 0


def _party_for(doc) -> tuple[str, str | None]:
    party_type = "Supplier" if doc.doctype in _SUPPLIER_SIDE_DOCTYPES else "Customer"
    return party_type, doc.get(party_type.lower())


@frappe.whitelist()  # login required (NOT allow_guest); Guest is also rejected explicitly below
def pay_for_document(dt: str, dn: str):
    """Create (and redirect to) a gateway Payment Request for the caller's own document.

    Args:
            dt: reference doctype (must be payable per ``ALLOWED_DOCTYPES_FOR_PAYMENT_REQUEST``).
            dn: reference document name; the caller must own it via website permission.

    Returns:
            The ``make_payment_request`` result. With ``order_type="Shopping Cart"`` that call sets
            an HTTP redirect to the gateway checkout, which is the intended "Pay" behaviour.

    Raises:
            frappe.PermissionError: caller is Guest, or does not own ``dn``.
            frappe.ValidationError: ``dt`` is not payable, or nothing is owed.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to pay."), frappe.PermissionError)

    # Imported from erpnext rather than re-declared, so the payable set cannot drift from the
    # one make_payment_request itself enforces.
    if dt not in ALLOWED_DOCTYPES_FOR_PAYMENT_REQUEST:
        frappe.throw(
            _("Payment Requests cannot be created against: {0}").format(
                frappe.bold(dt)
            ),
            frappe.ValidationError,
        )

    # Existence check BEFORE get_doc, raising the SAME error a valid-but-unowned document gets.
    # frappe.get_doc() raises DoesNotExistError for a missing name, which is distinguishable
    # from PermissionError -- that difference would let a logged-in caller enumerate real
    # document names by probing responses.
    if not frappe.db.exists(dt, dn):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    doc = frappe.get_doc(dt, dn)

    # Ownership gate -- MUST run before any elevation. frappe.has_website_permission fails
    # CLOSED (returns False when the doctype has neither a has_website_permission hook nor a
    # controller method), so a payable doctype with no website-permission handler -- POS Invoice,
    # Fees -- is refused by construction rather than by an allowlist someone has to maintain.
    if not frappe.has_website_permission(doc):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    # Server-side twin of the template's gate. The affordance is not the control: this endpoint
    # is directly reachable, and a settled document must not be chargeable from a stale link
    # (framework#183, and the framework#149 lesson that a caller-side gate alone is not enough).
    if not is_payable(doc):
        frappe.throw(
            _("This document has no outstanding balance."), frappe.ValidationError
        )

    party_type, party = _party_for(doc)

    # Elevate ONLY after the ownership gate above passed.
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        return make_payment_request(
            dt=dt,
            dn=dn,
            submit_doc=1,
            order_type="Shopping Cart",
            party_type=party_type,
            party=party,
        )
    finally:
        frappe.set_user(original_user)
