from django.test import Client
from django.contrib.auth.models import User
from conveniencia_bobesponjaApp.models import Categorys, Products, Customers, Sales
import json

c=Client()
u = User.objects.filter(username='test_check_user').first()
if not u:
    u = User.objects.create_user('test_check_user','t@t.com','123456')
else:
    try:
        u.email = 't@t.com'
        u.set_password('123456')
        u.save()
    except Exception:
        pass
c.force_login(u)
cat=Categorys.objects.create(name='CatT2',description='d',status=1)
p=Products.objects.create(code='9999',category_id=cat,name='ProdT2',price=5.0,quantity=10,status=1)
cust=Customers.objects.create(name='Cliente Test 2',phone='998',active=True)
# open comanda
resp=c.post('/save-pos', {
 'sale_action':'open_comanda',
 'comanda_code':'COM_TEST_CHECKOUT',
 'product_id[]':[str(p.id)],
 'qty[]':['1'],
 'price[]':['5.0'],
 'customer_id': str(cust.id),
}, follow=True)
print('open status', resp.status_code)
try:
    payload=json.loads(resp.content)
except Exception as e:
    payload={'raw': resp.content.decode('utf-8')}
print('open payload:', payload)
if Sales.objects.exists():
    s=Sales.objects.last()
    print('created sale id', s.id, 'status', s.status, 'comanda', s.comanda_code)
    # try checkout
    resp2=c.post('/save-pos', {
     'sale_action':'checkout',
     'sale_id': str(s.id),
     'product_id[]':[str(p.id)],
     'qty[]':['1'],
     'price[]':['5.0'],
     'tendered_amount': '5.0',
     'payment_methods': 'dinheiro',
     'comanda_code': s.comanda_code,
    }, follow=True)
    print('checkout status', resp2.status_code)
    try:
        payload2=json.loads(resp2.content)
    except Exception as e:
        payload2={'raw': resp2.content.decode('utf-8')}
    print('checkout payload:', payload2)
else:
    print('No sale created to checkout')
