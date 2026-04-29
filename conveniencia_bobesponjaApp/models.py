from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
from unicodedata import category
from django.utils import timezone

class Categorys(models.Model):
    name = models.TextField()
    description = models.TextField()
    status= models.IntegerField(default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name

 
class Products(models.Model):
    code=models.CharField(max_length=100)
    category_id = models.ForeignKey(Categorys, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField()
    price = models.FloatField(default=0)
    overnight_price = models.FloatField(default=0)
    quantity = models.IntegerField(default=0)
    status= models.IntegerField(default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code + ' - ' + self.name
    




class Sales(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    code=models.CharField(max_length=100)
    sub_total = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)

    tendered = models.FloatField(default=0)
    amount_change = models.FloatField(default=0)
    payment_methods = models.CharField(max_length=100, default='DINHEIRO')
    payment_other_detail = models.CharField(max_length=120, blank=True, default='')
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def get_payment_methods_display(self):
        labels = {
            'CREDITO': 'Credito',
            'DEBITO': 'Debito',
            'PIX': 'Pix',
            'DINHEIRO': 'Dinheiro',
            'OUTRO': 'Outro',
        }
        methods = [m.strip().upper() for m in (self.payment_methods or '').split(',') if m.strip()]
        return ', '.join(labels.get(method, method.title()) for method in methods)


class Salesitems(models.Model):
    sale_id = models.ForeignKey(Sales, on_delete=models.CASCADE)
    product_id = models.ForeignKey(Products, on_delete=models.CASCADE)
    price = models.FloatField(default=0)
    qty = models.IntegerField(default=0)
    total_price = models.FloatField(default=0)

    @property
    def total(self):
        return self.total_price