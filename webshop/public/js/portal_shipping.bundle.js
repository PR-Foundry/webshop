// Renders shipping panels on a portal order page (PR-Foundry/framework#229).
//
// THE SEAM. Mounts by finding an anchor in the rendered page, NOT by editing
// templates/pages/order.html. webshop is an upstream fork here, so a template we patch is a
// line the next sync resets and a re-verify grep has to watch. This way upstream-owned
// lines stay at zero — the same choice made for the checkout address form.
//
// Panels come from `webshop.webshop.portal.shipping_panels.get_shipping_panels`, which
// aggregates every app that registered the `webshop_shipping_panels` hook. This file knows
// nothing about any carrier: a second shipping app appears here by registering, with no
// change to this bundle.
//
// EVERY contributed value is written with textContent, never innerHTML. A carrier's
// tracking string is attacker-influenced data arriving through a third-party app, and this
// page is a public storefront.

frappe.provide("webshop.portal_shipping");

webshop.portal_shipping = {
	// The order page renders one of these; both carry the doctype and name we need.
	REFERENCE_SELECTOR: "[data-doctype][data-docname]",

	reference() {
		const el = document.querySelector(webshop.portal_shipping.REFERENCE_SELECTOR);
		if (el) {
			return { doctype: el.getAttribute("data-doctype"), name: el.getAttribute("data-docname") };
		}
		// Fall back to the route: /orders/<name> and /shipments/<name> are webshop's own
		// portal list routes.
		const match = window.location.pathname.match(/^\/(orders|shipments)\/([^/?#]+)/);
		if (!match) return null;
		return {
			doctype: match[1] === "orders" ? "Sales Order" : "Delivery Note",
			name: decodeURIComponent(match[2]),
		};
	},

	host() {
		const existing = document.querySelector(".webshop-shipping-panels");
		if (existing) return existing;
		// Sits after the page's main card, before the footer, so it reads as part of the
		// order rather than as a floating box.
		const anchor =
			document.querySelector(".page_content .frappe-card:last-of-type") ||
			document.querySelector(".page_content") ||
			document.querySelector("main");
		if (!anchor) return null;
		const host = document.createElement("div");
		host.className = "webshop-shipping-panels mt-4";
		anchor.parentNode.insertBefore(host, anchor.nextSibling);
		return host;
	},

	render(host, panels) {
		host.textContent = "";
		panels.forEach((panel) => {
			const card = document.createElement("div");
			card.className = "mb-3 frappe-card p-5";

			const head = document.createElement("div");
			head.className = "d-flex justify-content-between align-items-center";
			const title = document.createElement("h6");
			title.className = "mb-0";
			title.textContent = panel.title || "";
			head.appendChild(title);
			if (panel.status) {
				const badge = document.createElement("span");
				badge.className = "small text-muted";
				badge.textContent = panel.status;
				head.appendChild(badge);
			}
			card.appendChild(head);
			card.appendChild(document.createElement("hr"));

			(panel.rows || []).forEach((row) => {
				const line = document.createElement("div");
				line.className = "d-flex justify-content-between small mb-1";
				const label = document.createElement("span");
				label.className = "text-muted";
				label.textContent = row.label || "";
				const value = document.createElement("span");
				value.className = "text-right";
				// textContent, never innerHTML. See the header.
				value.textContent = row.value || "";
				line.append(label, value);
				card.appendChild(line);
			});

			if (panel.note) {
				const note = document.createElement("div");
				note.className = "small text-muted mt-2";
				note.textContent = panel.note;
				card.appendChild(note);
			}
			(panel.timelines || []).forEach((tl) => {
				// One bad timeline costs that timeline, never the card: an exception here would
				// otherwise skip host.appendChild below and blank every panel after this one.
				// renderTimeline appends to the card only as its last step, so a throw leaves no
				// half-drawn timeline behind.
				try {
					webshop.portal_shipping.renderTimeline(card, tl);
				} catch (e) {
					console.error("shipping panel: could not draw a timeline", e);
				}
			});
			host.appendChild(card);
		});
	},

	STYLE_ID: "webshop-timeline-style",

	ensureStyles() {
		if (document.getElementById(webshop.portal_shipping.STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = webshop.portal_shipping.STYLE_ID;
		style.textContent = [
			".wst-bar{display:flex;gap:4px;margin:1rem 0 .5rem}",
			".wst-seg{flex:1;height:6px;border-radius:3px;background:#e2e6ea}",
			".wst-seg.on{background:var(--primary,#2490ef)}",
			".wst-stopped .wst-seg.on{background:#adb5bd}",
			".wst-steps{display:flex;gap:4px;font-size:.8rem;color:#6c757d}",
			".wst-steps span{flex:1;text-align:center}",
			".wst-steps span.now{color:inherit;font-weight:600;color:#1f272e}",
			".wst-events{list-style:none;padding:0;margin:1rem 0 0;border-left:2px solid #e2e6ea}",
			".wst-events li{position:relative;padding:0 0 .75rem 1rem}",
			".wst-events li::before{content:'';position:absolute;left:-6px;top:.35rem;width:10px;height:10px;border-radius:50%;background:var(--primary,#2490ef)}",
			".wst-time{font-size:.75rem;color:#6c757d}",
			// One row at every width: each label must stay under its own segment, so on a phone the
			// labels shrink and wrap inside their column rather than wrapping the row.
			"@media (max-width:576px){.wst-steps{font-size:.7rem}.wst-steps span{min-width:0;overflow-wrap:anywhere}}",
		].join("");
		document.head.appendChild(style);
	},

	renderTimeline(card, tl) {
		// textContent only, like every other value on this page -- see the header.
		webshop.portal_shipping.ensureStyles();
		const wrap = document.createElement("div");
		wrap.className = "mt-3" + (tl.stopped ? " wst-stopped" : "");

		const head = document.createElement("div");
		head.className = "d-flex justify-content-between small font-weight-bold";
		const title = document.createElement("span");
		title.textContent = tl.title || "";
		head.appendChild(title);
		if (tl.stopped) {
			const badge = document.createElement("span");
			badge.className = "text-muted";
			badge.textContent = __("Cancelled");
			head.appendChild(badge);
		}
		wrap.appendChild(head);

		const steps = tl.steps || [];
		const bar = document.createElement("div");
		bar.className = "wst-bar";
		const labels = document.createElement("div");
		labels.className = "wst-steps";
		steps.forEach((label, i) => {
			const seg = document.createElement("div");
			seg.className = "wst-seg" + (i <= tl.reached ? " on" : "");
			bar.appendChild(seg);
			const name = document.createElement("span");
			name.className = i === tl.reached ? "now" : "";
			name.textContent = label;
			labels.appendChild(name);
		});
		wrap.append(bar, labels);

		const list = document.createElement("ul");
		list.className = "wst-events";
		(tl.events || []).forEach((ev) => {
			const item = document.createElement("li");
			const label = document.createElement("div");
			label.textContent = ev.location ? `${ev.label || ""} — ${ev.location}` : ev.label || "";
			const time = document.createElement("div");
			time.className = "wst-time";
			time.textContent = ev.time || "";
			item.append(label, time);
			list.appendChild(item);
		});
		wrap.appendChild(list);
		card.appendChild(wrap);
	},

	mount() {
		const reference = webshop.portal_shipping.reference();
		if (!reference) return;
		frappe.call({
			method: "webshop.webshop.portal.shipping_panels.get_shipping_panels",
			args: reference,
			callback: (r) => {
				const panels = (r && r.message) || [];
				// No panel is the common case -- most orders are not shipped by an app that
				// registered one -- so nothing is inserted at all rather than an empty box.
				if (!panels.length) return;
				const host = webshop.portal_shipping.host();
				if (host) webshop.portal_shipping.render(host, panels);
			},
			// A failure here must leave the order page exactly as it was: the customer came
			// to read their order, not their parcel.
			error: () => {},
		});
	},
};

frappe.ready(() => {
	if (!/^\/(orders|shipments)\//.test(window.location.pathname)) return;
	webshop.portal_shipping.mount();
});
