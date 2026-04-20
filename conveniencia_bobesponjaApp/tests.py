import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Categorys, Products, Sales, Salesitems


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
				'tax': '0',
				'tax_amount': '0',
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

	def test_save_pos_blocks_sale_when_stock_is_insufficient(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('save-pos'),
			{
				'sub_total': '105.0',
				'tax': '0',
				'tax_amount': '0',
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


class RegisterUserRoleTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='Marcos', password='123456', is_superuser=True, is_staff=True)
		self.seller = User.objects.create_user(username='vendedor_base', password='123456')

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
