from . import __version__ as _version

app_name = "webshop"
app_title = "Webshop"

# PR-Foundry/framework#165 (fork patch) — frappe v16 replaced the Desktop Icon grid
# with the `Apps` screen (`Desktop Settings.desktop_page`, default `Apps`), which is
# drawn ONLY from this hook. webshop declares none upstream, so its public `Webshop`
# workspace lost its only entry point: the Link-type Desktop Icon client_app seeds
# (framework bug-029/#038) still exists and is not hidden, but nothing renders it.
#
# It must live HERE, not in client_app: frappe/boot.py iterates
# `for app_name in frappe.get_active_apps()` and reads each app's OWN hook, so
# declaring it elsewhere would spend that app's tile slot on a tile labelled Webshop.
#
# `/desk/webshop` resolves because the public `Webshop` workspace supplies that slug;
# a `/desk/*` route without a matching workspace is a blank flicker with no Error Log
# row (framework#139 / bug-196). No `logo` key — webshop ships no brand asset, so boot
# falls back to the default rather than borrowing another app's mark.
# Upstream-owned line — re-verify after any webshop sync.
add_to_apps_screen = [
	{
		"name": "webshop",
		"title": app_title,
		"route": "/desk/webshop",
	}
]
app_publisher = "Frappe Technologies Pvt. Ltd."
app_description = "Open Source eCommerce Platform"
app_email = "contact@frappe.io"
app_license = "GNU General Public License (v3)"
app_version = _version

required_apps = ["payments", "erpnext"]

web_include_css = "webshop-web.bundle.css"

# checkout_address.bundle.js replaces the native New Address dialog by rebinding
# .btn-new-address -- see the bundle's own header and
# client_app.tests.test_checkout_address_seam.
web_include_js = ["web.bundle.js", "checkout_address.bundle.js", "portal_shipping.bundle.js"]

after_install = "webshop.setup.install.after_install"
on_logout = "webshop.webshop.shopping_cart.utils.clear_cart_count"
on_session_creation = [
	"webshop.webshop.utils.portal.update_debtors_account",
	"webshop.webshop.shopping_cart.utils.set_cart_count",
]
update_website_context = [
	"webshop.webshop.shopping_cart.utils.update_website_context",
]

website_generators = ["Website Item", "Item Group"]

override_doctype_class = {
	"Payment Request": "webshop.webshop.doctype.override_doctype.payment_request.PaymentRequest",
	"Item Group": "webshop.webshop.doctype.override_doctype.item_group.WebshopItemGroup",
	"Item": "webshop.webshop.doctype.override_doctype.item.WebshopItem",
}

doctype_js = {
	"Item": "public/js/override/item.js",
	"Homepage": "public/js/override/homepage.js",
}

doc_events = {
	"Item": {
		"on_update": [
			"webshop.webshop.crud_events.item.update_website_item.execute",
			"webshop.webshop.crud_events.item.invalidate_item_variants_cache.execute",
		],
		"before_rename": [
			"webshop.webshop.crud_events.item.validate_duplicate_website_item.execute",
		],
		"after_rename": [
			"webshop.webshop.crud_events.item.invalidate_item_variants_cache.execute",
		],
	},
	"Sales Taxes and Charges Template": {
		"on_update": [
			"webshop.webshop.doctype.webshop_settings.webshop_settings.validate_cart_settings",
		],
	},
	"Quotation": {
		"validate": [
			"webshop.webshop.crud_events.quotation.validate_shopping_cart_items.execute",
		],
	},
	"Price List": {
		"validate": ["webshop.webshop.crud_events.price_list.check_impact_on_cart.execute"],
	},
	"Tax Rule": {
		"validate": [
			"webshop.webshop.crud_events.tax_rule.validate_use_for_cart.execute",
		],
	},
	# Added here, not as a second `doc_events =` further down: a second assignment
	# replaces this whole dict and silently drops every hook above (framework#343).
	"Webshop Settings": {
		# Google's includedRegionCodes takes at most 15. Refused at save so the operator
		# finds out while looking at the field, rather than through customers in the
		# silently dropped countries failing to find their address.
		"validate": "webshop.webshop.setup.address_search.validate_country_limit",
	},
}

has_website_permission = {
	"Website Item": "webshop.webshop.doctype.website_item.website_item.has_website_permission_for_website_item",
	"Item Group": "webshop.webshop.doctype.website_item.website_item.has_website_permission_for_item_group",
}


# The checkout address form validates the phone server-side. Registered as an override
# rather than by editing shopping_cart/cart.py: this app is an upstream fork, and the
# override keeps the patch surface in upstream-owned files at zero. Guarded by
# client_app.tests.test_checkout_address_phone.
override_whitelisted_methods = {
	"webshop.webshop.shopping_cart.cart.add_new_address": "webshop.webshop.checkout_address.add_new_address",
	# framework#277 -- upstream returned the whole existing Lead to a guest.
	"webshop.webshop.shopping_cart.cart.create_lead_for_item_inquiry": "webshop.webshop.item_inquiry.create_lead_for_item_inquiry",
	# framework#286 -- upstream loaded any Address name the caller sent.
	"webshop.webshop.shopping_cart.cart.update_cart_address": "webshop.webshop.checkout_address.update_cart_address",
	# framework#284 -- guest coupon endpoints, throttled per IP.
	"webshop.webshop.shopping_cart.cart.apply_coupon_code": "webshop.webshop.cart_guards.apply_coupon_code",
	"webshop.webshop.shopping_cart.cart.remove_coupon_code": "webshop.webshop.cart_guards.remove_coupon_code",
}


# Ensures the checkout address-search country field on every migrate. A Custom Field, so
# upstream's webshop_settings.json is never edited.
after_migrate = "webshop.webshop.setup.address_search.after_migrate"
