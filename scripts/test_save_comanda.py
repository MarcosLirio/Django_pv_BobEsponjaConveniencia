from django.test import Client
from django.contrib.auth.models import User
from conveniencia_bobesponjaApp.models import Categorys, Products, Customers, Sales
import json
# prepare client and user
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
# login
c.force_login(u)
cat=Categorys.objects.create(name='CatT',description='d',status=1)
p=Products.objects.create(code='999',category_id=cat,name='ProdT',price=5.0,quantity=10,status=1)
cust=Customers.objects.create(name='Cliente Test',phone='999',active=True)
resp=c.post('/save-pos', {
 'sale_action':'open_comanda',
 'comanda_code':'COM1',
 'product_id[]':[str(p.id)],
 'qty[]':['1'],
 'price[]':['5.0'],
 'customer_id': str(cust.id),
}, follow=True)
print('status', resp.status_code)
try:
    payload=json.loads(resp.content)
except Exception as e:
    payload={'raw': resp.content.decode('utf-8')}
print('payload:', payload)
print('sales_count', Sales.objects.count())
if Sales.objects.exists():
    s=Sales.objects.last()
    print('sale id', s.id, 'customer_id', getattr(s.customer, 'id', None), 'comanda', s.comanda_code)
