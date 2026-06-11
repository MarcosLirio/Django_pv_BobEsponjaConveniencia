import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Categorys, Products, Sales

class ComandasIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t_idem', password='pass')
        self.category = Categorys.objects.create(name='TestCat', description='desc', status=1)
        self.product = Products.objects.create(
            code='0001112223334',
            category_id=self.category,
            name='Produto Idem',
            description='Produto para testes de idempotencia',
            price=5.0,
            quantity=10,
            status=1,
        )
        self.client.force_login(self.user)

    def test_checkout_idempotency_prevents_duplicate_sales(self):
        payload = {
            'product_id[]': [str(self.product.id)],
            'qty[]': ['1'],
            'price[]': [str(self.product.price)],
            'sale_action': 'checkout',
            'tendered_amount': '0',
            'discount_type': 'VALUE',
            'discount_value': '0',
            'idempotency_key': 'test-dup-0001',
        }
        r1 = self.client.post(reverse('save-pos'), payload)
        r2 = self.client.post(reverse('save-pos'), payload)

        p1 = json.loads(r1.content)
        p2 = json.loads(r2.content)

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(Sales.objects.filter(user=self.user).count(), 1)
        self.assertEqual(p1['status'], 'success')
        self.assertEqual(p2['status'], 'success')

    def test_open_comanda_edits_do_not_change_stock_until_checkout(self):
        # create open comanda with qty 1
        r_open = self.client.post(reverse('save-pos'), {
            'sale_action': 'open_comanda',
            'comanda_code': 'OPEN-TEST',
            'product_id[]': [str(self.product.id)],
            'qty[]': ['1'],
            'price[]': [str(self.product.price)],
            'tendered_amount': '0',
        })
        p_open = json.loads(r_open.content)
        sale_id = p_open.get('sale_id')
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

        # edit open comanda to qty 3
        r_edit = self.client.post(reverse('save-pos'), {
            'sale_id': str(sale_id),
            'sale_action': 'open_comanda',
            'product_id[]': [str(self.product.id)],
            'qty[]': ['3'],
            'price[]': [str(self.product.price)],
        })
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

        # finalize (checkout) and expect stock decreased by 3
        r_checkout = self.client.post(reverse('save-pos'), {
            'sale_id': str(sale_id),
            'sale_action': 'checkout',
            'product_id[]': [str(self.product.id)],
            'qty[]': ['3'],
            'price[]': [str(self.product.price)],
            'tendered_amount': '0',
        })
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 7)
