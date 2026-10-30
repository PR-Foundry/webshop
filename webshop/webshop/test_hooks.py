# A second module-level `doc_events = {...}` replaced the first and silently dropped
# every Item, Quotation, Price List and Tax Rule hook (PR-Foundry/framework#343).
import ast
import unittest
from pathlib import Path

import webshop

HOOKS = Path(webshop.__file__).with_name("hooks.py")


class TestHooks(unittest.TestCase):
	def test_every_hook_is_assigned_once(self):
		names = [
			target.id
			for node in ast.parse(HOOKS.read_text()).body
			if isinstance(node, ast.Assign)
			for target in node.targets
			if isinstance(target, ast.Name)
		]
		self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [])

	def test_document_hooks_survive_the_whole_module(self):
		from webshop import hooks

		self.assertIn(
			"webshop.webshop.crud_events.item.update_website_item.execute",
			hooks.doc_events["Item"]["on_update"],
		)
		self.assertIn(
			"webshop.webshop.crud_events.quotation.validate_shopping_cart_items.execute",
			hooks.doc_events["Quotation"]["validate"],
		)
		self.assertEqual(
			hooks.doc_events["Webshop Settings"]["validate"],
			"webshop.webshop.setup.address_search.validate_country_limit",
		)
