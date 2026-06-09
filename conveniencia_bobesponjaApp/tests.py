import json
from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Categorys, Customers, Products, Sales, Salesitems
from .views import is_overnight_period


class OvernightPeriodTests(TestCase):
	def test_overnight_period_boundaries(self):
		tz = timezone.get_current_timezone()

		before_midnight = timezone.make_aware(datetime(2026, 4, 26, 23, 59), tz)
		start_overnight = timezone.make_aware(datetime(2026, 4, 27, 0, 0), tz)
		end_overnight = timezone.make_aware(datetime(2026, 4, 27, 5, 59), tz)
		after_overnight = timezone.make_aware(datetime(2026, 4, 27, 6, 0), tz)

		self.assertFalse(is_overnight_period(before_midnight))
		self.assertTrue(is_overnight_period(start_overnight))
		self.assertTrue(is_overnight_period(end_overnight))
		self.assertFalse(is_overnight_period(after_overnight))


class ProductManagementTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser(
			username='admin_produto',
			email='admin_produto@example.com',
			password='123456',
		)
		self.category = Categorys.objects.create(
			name='Categoria Teste',
			description='Categoria para teste de edicao',
			status=1,
		)
		self.product = Products.objects.create(
			code='7891000999000',
			category_id=self.category,
			name='Produto Original',
			description='Descricao original',
			price=8.5,
			overnight_price=10.0,
			quantity=5,
			status=1,
		)

	def test_save_product_allows_edit_with_same_code(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('save-product-page'),
			{
				'id': str(self.product.id),
				'code': self.product.code,
				'category_id': str(self.category.id),
				'name': 'Produto Editado',
				'description': 'Descricao editada',
				'price': '9.90',
				'overnight_price': '12.50',
				'quantity': '11',
				'status': '1',
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(self.product.name, 'Produto Editado')
		self.assertEqual(self.product.quantity, 11)
		self.assertEqual(self.product.price, 9.9)
		self.assertEqual(self.product.overnight_price, 12.5)

	def test_manage_product_edit_keeps_current_category_selected(self):
		self.client.force_login(self.admin)

		response = self.client.get(
			reverse('manage_product-page'),
			{'id': str(self.product.id)},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(
			response,
			f'<option value="{self.category.id}" selected>{self.category.name}</option>',
			html=True,
		)

	def test_save_product_generates_internal_code_for_product_without_barcode(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('save-product-page'),
			{
				'id': '',
				'code': '',
				'product_without_barcode': '1',
				'category_id': str(self.category.id),
				'name': 'Dose de Whisky',
				'description': 'Produto sem codigo de barras',
				'price': '12.00',
				'overnight_price': '15.00',
				'quantity': '0',
				'infinite_stock': '1',
				'status': '1',
			},
		)

		payload = json.loads(response.content)
		created_product = Products.objects.exclude(id=self.product.id).get(name='Dose de Whisky')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertTrue(created_product.code.startswith('29'))
		self.assertEqual(len(created_product.code), 13)
		self.assertTrue(created_product.infinite_stock)


class PosBarcodeFlowTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='caixa', password='123456')
		self.category = Categorys.objects.create(
			name='Bebidas',
			description='Categoria de teste',
			status=1,
		)
		self.product = Products.objects.create(
			code='7891000100103',
			category_id=self.category,
			name='Refrigerante 2L',
			description='Produto de teste',
			price=10.5,
			overnight_price=13.5,
			quantity=8,
			status=1,
		)

	def test_pos_page_exposes_barcode_in_product_payload(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('pos-page'))

		self.assertEqual(response.status_code, 200)
		self.assertIn('7891000100103', response.context['product_json'])

	def test_save_pos_creates_sale_and_decrements_stock(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '21.0',
				'grand_total': '21.0',
				'tendered_amount': '25.0',
				'amount_change': '4.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(Sales.objects.count(), 1)
		self.assertEqual(Salesitems.objects.count(), 1)
		self.assertEqual(self.product.quantity, 6)
		self.assertEqual(Sales.objects.get().grand_total, 21.0)

	def test_save_pos_recalculates_total_from_changed_quantity(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '10.5',
				'grand_total': '10.5',
				'tendered_amount': '25.0',
				'amount_change': '4.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(sale.sub_total, 21.0)
		self.assertEqual(sale.grand_total, 21.0)

	def test_save_pos_blocks_sale_when_stock_is_insufficient(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '105.0',
				'grand_total': '105.0',
				'tendered_amount': '110.0',
				'amount_change': '5.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['10'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'failed')
		self.assertIn('Estoque insuficiente', payload['msg'])
		self.assertEqual(Sales.objects.count(), 0)
		self.assertEqual(Salesitems.objects.count(), 0)
		self.assertEqual(self.product.quantity, 8)

	@patch('conveniencia_bobesponjaApp.views.is_overnight_period', return_value=True)
	def test_pos_page_uses_overnight_price_during_overnight_period(self, _mocked_period):
		self.client.force_login(self.user)

		response = self.client.get(reverse('pos-page'))
		payload = json.loads(response.context['product_json'])

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context['overnight_mode'])
		self.assertEqual(payload[0]['price'], 13.5)
		self.assertEqual(payload[0]['base_price'], 10.5)
		self.assertEqual(payload[0]['overnight_price'], 13.5)

	@patch('conveniencia_bobesponjaApp.views.is_overnight_period', return_value=True)
	def test_save_pos_uses_server_side_overnight_price(self, _mocked_period):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '27.0',
				'grand_total': '27.0',
				'tendered_amount': '30.0',
				'amount_change': '3.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['13.5'],
			},
		)

		payload = json.loads(response.content)
		item = Salesitems.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(item.price, 13.5)
		self.assertEqual(item.total_price, 27.0)

	@patch('conveniencia_bobesponjaApp.views.is_overnight_period', return_value=True)
	def test_save_pos_allows_discounted_price_below_overnight_price(self, _mocked_period):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '21.0',
				'grand_total': '21.0',
				'tendered_amount': '25.0',
				'amount_change': '4.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		item = Salesitems.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(item.price, 10.5)
		self.assertEqual(item.total_price, 21.0)

	def test_save_pos_allows_price_above_current_product_price(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '24.0',
				'grand_total': '24.0',
				'tendered_amount': '25.0',
				'amount_change': '1.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['12.0'],
			},
		)

		payload = json.loads(response.content)
		item = Salesitems.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(item.price, 12.0)
		self.assertEqual(item.total_price, 24.0)

	def test_save_pos_keeps_infinite_stock_without_decrement(self):
		self.client.force_login(self.user)
		self.product.infinite_stock = True
		self.product.quantity = 0
		self.product.save(update_fields=['infinite_stock', 'quantity'])

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '21.0',
				'grand_total': '21.0',
				'tendered_amount': '25.0',
				'amount_change': '4.0',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()
		item = Salesitems.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(item.qty, 2)
		self.assertEqual(item.total_price, 21.0)
		self.assertEqual(self.product.quantity, 0)

	def test_save_pos_rejects_fractional_quantity_even_for_infinite_stock_product(self):
		self.client.force_login(self.user)
		self.product.infinite_stock = True
		self.product.quantity = 0
		self.product.save(update_fields=['infinite_stock', 'quantity'])

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '5.25',
				'grand_total': '5.25',
				'tendered_amount': '10.0',
				'amount_change': '4.75',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['0.5'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'failed')
		self.assertIn('nao permite quantidade fracionada', payload['msg'])
		self.assertEqual(Sales.objects.count(), 0)
		self.assertEqual(Salesitems.objects.count(), 0)

	def test_save_pos_opens_comanda_without_decrementing_stock(self):
		self.client.force_login(self.user)
		customer = Customers.objects.create(name='Cliente Teste', phone='123456789')

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'comanda_code': '12',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_id': str(customer.id),
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertEqual(sale.comanda_code, '12')
		self.assertEqual(sale.sub_total, 21.0)
		self.assertEqual(sale.grand_total, 21.0)
		self.assertEqual(sale.customer_id, customer.id)
		self.assertEqual(Salesitems.objects.get().qty, 2)
		self.assertEqual(self.product.quantity, 8)

	def test_save_pos_repeated_open_comanda_save_keeps_stock_unchanged(self):
		self.client.force_login(self.user)
		customer = Customers.objects.create(name='Cliente Repetido', phone='123456789')

		first_response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'comanda_code': 'JANSEN-01',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_id': str(customer.id),
			},
		)
		first_payload = json.loads(first_response.content)
		sale = Sales.objects.get(id=first_payload['sale_id'])

		second_response = self.client.post(
			reverse('save-pos'),
			{
				'sale_id': str(sale.id),
				'sale_action': 'open_comanda',
				'comanda_code': 'JANSEN-01',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['5'],
				'price[]': ['10.5'],
				'customer_id': str(customer.id),
			},
		)

		second_payload = json.loads(second_response.content)
		sale.refresh_from_db()
		self.product.refresh_from_db()

		self.assertEqual(first_payload['status'], 'success')
		self.assertEqual(second_payload['status'], 'success')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertEqual(sale.sub_total, 52.5)
		self.assertEqual(sale.grand_total, 52.5)
		self.assertEqual(Salesitems.objects.filter(sale_id=sale).count(), 1)
		self.assertEqual(Salesitems.objects.get(sale_id=sale).qty, 5)
		self.assertEqual(self.product.quantity, 8)

	def test_save_pos_converts_partial_payment_to_open_comanda_with_outro(self):
		self.client.force_login(self.user)
		customer = Customers.objects.create(name='Cliente Teste', phone='123456789')

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'checkout',
				'comanda_code': '12',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_id': str(customer.id),
				'tendered_amount': '10.0',
				'amount_change': '-10.0',
				'payment_methods': 'outro',
				'payment_other_detail': 'Fiado',
			},
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertEqual(sale.comanda_code, '12')
		self.assertEqual(sale.tendered, 10.0)
		self.assertEqual(sale.grand_total, 21.0)
		self.assertEqual(sale.amount_change, -11.0)
		self.assertEqual(sale.payment_methods, 'OUTRO')

	def test_save_pos_converts_partial_payment_to_open_comanda_without_customer(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'checkout',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'tendered_amount': '10.0',
				'amount_change': '-10.0',
				'payment_methods': 'outro',
				'payment_other_detail': 'Fiado',
			},
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertIsNone(sale.customer_id)
		self.assertTrue(sale.comanda_code.startswith('COMANDA-'))
		self.assertEqual(sale.tendered, 10.0)
		self.assertEqual(sale.grand_total, 21.0)
		self.assertEqual(sale.payment_methods, 'OUTRO')

	def test_save_pos_allows_open_comanda_without_customer(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertEqual(sale.customer, None)
		self.assertTrue(sale.comanda_code.startswith('COMANDA-'))
		self.assertEqual(Salesitems.objects.get().qty, 2)

	def test_save_pos_opens_comanda_with_customer_name_only(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'comanda_code': '12',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_name': 'Cliente Nome Teste',
			},
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.status, Sales.STATUS_OPEN)
		self.assertEqual(sale.comanda_code, '12')
		self.assertEqual(sale.sub_total, 21.0)
		self.assertEqual(sale.grand_total, 21.0)
		self.assertTrue(sale.customer_id > 0)
		self.assertEqual(sale.customer.name, 'Cliente Nome Teste')
		self.assertEqual(Salesitems.objects.get().qty, 2)

	def test_save_pos_opens_comanda_with_existing_customer_name_case_insensitive(self):
		self.client.force_login(self.user)
		Customers.objects.create(name='cliente teste', phone='999999999')

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'comanda_code': '12',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_name': 'Cliente Teste',
			}
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.customer_id, 1)
		self.assertEqual(sale.customer.name.lower(), 'cliente teste')
		self.assertEqual(Salesitems.objects.get().qty, 2)

	def test_save_pos_resolves_existing_customer_name_with_extra_spaces(self):
		self.client.force_login(self.user)
		Customers.objects.create(name='Cliente Teste', phone='999999999')

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_action': 'open_comanda',
				'comanda_code': '12',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
				'customer_name': '  Cliente   Teste  ',
			}
		)

		payload = json.loads(response.content)
		sale = Sales.objects.get()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_action'], 'open_comanda')
		self.assertEqual(sale.customer_id, 1)
		self.assertEqual(sale.customer.name, 'Cliente Teste')
		self.assertEqual(Salesitems.objects.get().qty, 2)

	def test_save_pos_finalizes_existing_open_comanda_with_discount(self):
		self.client.force_login(self.user)
		open_sale = Sales.objects.create(
			user=self.user,
			code='2026202600099',
			status=Sales.STATUS_OPEN,
			comanda_code='15',
			sub_total=0,
			grand_total=0,
		)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sale_id': str(open_sale.id),
				'sale_action': 'checkout',
				'comanda_code': '15',
				'sub_total': '21.0',
				'grand_total': '18.9',
				'tendered_amount': '20.0',
				'amount_change': '1.1',
				'discount_type': 'PERCENT',
				'discount_value': '10',
				'payment_methods': 'dinheiro',
				'product_id[]': [str(self.product.id)],
				'qty[]': ['2'],
				'price[]': ['10.5'],
			},
		)

		payload = json.loads(response.content)
		self.product.refresh_from_db()
		open_sale.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(payload['sale_id'], open_sale.id)
		self.assertEqual(open_sale.status, Sales.STATUS_CLOSED)
		self.assertEqual(open_sale.discount_type, Sales.DISCOUNT_TYPE_PERCENT)
		self.assertEqual(open_sale.discount_value, 10.0)
		self.assertEqual(open_sale.discount_amount, 2.1)
		self.assertEqual(open_sale.grand_total, 18.9)
		self.assertEqual(open_sale.tendered, 20.0)
		self.assertEqual(open_sale.amount_change, 1.1)
		self.assertEqual(Salesitems.objects.filter(sale_id=open_sale).count(), 1)
		self.assertEqual(self.product.quantity, 6)


class SalesPresentationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='operador', password='123456')
		self.category = Categorys.objects.create(
			name='Bebidas',
			description='Categoria de teste',
			status=1,
		)
		self.product = Products.objects.create(
			code='7891000100104',
			category_id=self.category,
			name='Suco 1L',
			description='Produto do recibo',
			price=12.0,
			quantity=10,
			status=1,
		)
		self.sale = Sales.objects.create(
			user=self.user,
			code='2026202600001',
			sub_total=24.0,
			grand_total=24.0,
			tendered=30.0,
			amount_change=6.0,
		)
		Salesitems.objects.create(
			sale_id=self.sale,
			product_id=self.product,
			price=12.0,
			qty=2,
			total_price=24.0,
		)

	def test_sales_page_does_not_show_tax_column(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('sales-page'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Imposto Incluso')
		self.assertNotContains(response, 'Imposto')

	def test_receipt_does_not_show_tax_information(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('receipt-modal'), {'id': self.sale.id})

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Imposto')
		self.assertNotContains(response, '2.40')


class HomePresentationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='caixa_home', password='123456')
		Sales.objects.create(
			user=self.user,
			code='2026202600099',
			sub_total=42.5,
			grand_total=42.5,
			tendered=50.0,
			amount_change=7.5,
		)

	def test_home_page_shows_total_sales_in_brl_format(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('home-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'R$ 42,50')


class UsersPresentationTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='Marcos', password='123456', is_superuser=True, is_staff=True)
		self.seller = User.objects.create_user(username='vendedor_teste', password='123456')
		Sales.objects.create(
			user=self.seller,
			code='2026202600101',
			sub_total=77.3,
			grand_total=77.3,
			tendered=80.0,
			amount_change=2.7,
		)

	def test_users_page_shows_total_sales_in_brl_format(self):
		self.client.force_login(self.admin)

		response = self.client.get(reverse('users-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'R$ 77,30')

	def test_users_page_shows_action_buttons_for_current_admin_row(self):
		self.client.force_login(self.admin)

		response = self.client.get(reverse('users-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'data-id="{self.admin.id}"')
		self.assertContains(response, 'class="btn btn-sm btn-primary edit-user"')
		self.assertContains(response, 'class="btn btn-sm btn-warning toggle-status"')
		self.assertContains(response, 'class="btn btn-sm btn-danger delete-user"')


class ProductListingTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='Marcos', password='123456', is_superuser=True, is_staff=True)
		self.category = Categorys.objects.create(
			name='Destilados',
			description='Categoria de teste',
			status=1,
		)
		Products.objects.create(
			code='7891000100998',
			category_id=self.category,
			name='Whisky',
			description='Produto com preço de madrugada',
			price=25.0,
			overnight_price=30.0,
			quantity=4,
			status=1,
		)

	def test_products_page_shows_normal_and_overnight_prices(self):
		self.client.force_login(self.admin)

		response = self.client.get(reverse('product-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Preço Madrugada')
		self.assertContains(response, 'R$ 25,00')
		self.assertContains(response, 'R$ 30,00')


class ProductSaveTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='Marcos', password='123456', is_superuser=True, is_staff=True)
		self.category = Categorys.objects.create(
			name='Cervejas',
			description='Categoria de teste',
			status=1,
		)

	def test_save_product_accepts_brazilian_currency_format(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('save-product-page'),
			{
				'id': '',
				'code': '7891234567890',
				'category_id': str(self.category.id),
				'name': 'Cerveja Lata',
				'description': 'Produto de teste',
				'price': 'R$ 12,50',
				'overnight_price': 'R$ 14,75',
				'quantity': '10',
				'status': '1',
			},
		)

		payload = json.loads(response.content)
		product = Products.objects.get(code='7891234567890')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(product.price, 12.5)
		self.assertEqual(product.overnight_price, 14.75)


class RegisterUserRoleTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='Marcos', password='123456', is_superuser=True, is_staff=True)
		self.seller = User.objects.create_user(username='vendedor_base', password='123456')
		self.other_admin = User.objects.create_user(username='gerente_base', password='123456', is_superuser=True, is_staff=True)

	def test_non_admin_cannot_create_user(self):
		response = self.client.post(
			reverse('register-user'),
			{
				'username': 'bloqueado',
				'email': 'bloqueado@example.com',
				'password': 'SenhaForte123',
				'confirm_password': 'SenhaForte123',
			},
		)

		self.assertEqual(response.status_code, 403)
		self.assertFalse(User.objects.filter(username='bloqueado').exists())

	def test_admin_can_create_new_user_as_seller(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('register-user'),
			{
				'username': 'vendedor1',
				'email': 'vendedor1@example.com',
				'password': 'SenhaForte123',
				'confirm_password': 'SenhaForte123',
			},
		)

		payload = json.loads(response.content)
		user = User.objects.get(username='vendedor1')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertFalse(user.is_superuser)
		self.assertFalse(user.is_staff)
		self.assertTrue(user.is_active)

	def test_admin_can_create_new_user_as_admin(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('register-user'),
			{
				'username': 'gerente1',
				'email': 'gerente1@example.com',
				'password': 'SenhaForte123',
				'confirm_password': 'SenhaForte123',
				'is_admin': 'on',
			},
		)

		payload = json.loads(response.content)
		user = User.objects.get(username='gerente1')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertTrue(user.is_superuser)
		self.assertTrue(user.is_staff)

	def test_admin_can_toggle_user_role(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('toggle-user-role'),
			{
				'id': self.seller.id,
				'is_admin': 'true',
			},
		)

		payload = json.loads(response.content)
		self.seller.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertTrue(self.seller.is_superuser)
		self.assertTrue(self.seller.is_staff)

	def test_admin_can_update_own_account(self):
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('update-user-account'),
			{
				'id': self.admin.id,
				'username': 'MarcosAdmin',
				'email': 'marcos@example.com',
				'password': '',
				'is_admin': 'true',
			},
		)

		payload = json.loads(response.content)
		self.admin.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'success')
		self.assertEqual(self.admin.username, 'MarcosAdmin')
		self.assertEqual(self.admin.email, 'marcos@example.com')
		self.assertTrue(self.admin.is_superuser)
		self.assertTrue(self.admin.is_staff)

	def test_last_admin_cannot_remove_own_admin_role_via_account_update(self):
		self.other_admin.is_superuser = False
		self.other_admin.is_staff = False
		self.other_admin.save(update_fields=['is_superuser', 'is_staff'])
		self.client.force_login(self.admin)

		response = self.client.post(
			reverse('update-user-account'),
			{
				'id': self.admin.id,
				'username': 'Marcos',
				'email': 'marcos@example.com',
				'password': '',
				'is_admin': 'false',
			},
		)

		payload = json.loads(response.content)
		self.admin.refresh_from_db()

		self.assertEqual(response.status_code, 200)
		self.assertEqual(payload['status'], 'failed')
		self.assertTrue(self.admin.is_superuser)
		self.assertTrue(self.admin.is_staff)
