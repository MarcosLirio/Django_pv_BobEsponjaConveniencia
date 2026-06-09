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
    code=models.CharField(max_length=100, blank=True)
    category_id = models.ForeignKey(Categorys, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField()
    price = models.FloatField(default=0)
    overnight_price = models.FloatField(default=0)
    quantity = models.IntegerField(default=0)
    infinite_stock = models.BooleanField(default=False)
    status= models.IntegerField(default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code + ' - ' + self.name
    


class Customers(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    active = models.BooleanField(default=True)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.phone:
            return f'{self.name} - {self.phone}'
        return self.name





class Sales(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Aberta'),
        (STATUS_CLOSED, 'Fechada'),
    ]
    DISCOUNT_TYPE_VALUE = 'VALUE'
    DISCOUNT_TYPE_PERCENT = 'PERCENT'
    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_TYPE_VALUE, 'Valor'),
        (DISCOUNT_TYPE_PERCENT, 'Percentual'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    customer = models.ForeignKey(Customers, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    code=models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_CLOSED)
    comanda_code = models.CharField(max_length=80, blank=True, default='')  # Aceita nome ou número
    sub_total = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default=DISCOUNT_TYPE_VALUE)
    discount_value = models.FloatField(default=0)
    discount_amount = models.FloatField(default=0)

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
    # NOVO CAMPO: Guarda quanto dessa quantidade já saiu do estoque
    qty_baixada = models.IntegerField(default=0)  
    total_price = models.FloatField(default=0)

    @property
    def total(self):
        return self.total_price



class Suppliers(models.Model):
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=40, blank=True, default='')
    address = models.TextField(blank=True, default='')
    active = models.BooleanField(default=True)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SupplierProductPrices(models.Model):
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, related_name='product_prices')
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name='supplier_prices')
    price = models.FloatField(default=0)
    cost_price = models.FloatField(default=0)
    sale_price = models.FloatField(default=0)
    notes = models.CharField(max_length=160, blank=True, default='')
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('supplier', 'product')


class PayableAccounts(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_PAID = 'PAID'
    STATUS_OVERDUE = 'OVERDUE'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Em aberto'),
        (STATUS_PAID, 'Pago'),
        (STATUS_OVERDUE, 'Atrasado'),
    ]

    description = models.CharField(max_length=180)
    supplier = models.ForeignKey(Suppliers, on_delete=models.SET_NULL, null=True, blank=True, related_name='payables')
    amount = models.FloatField(default=0)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    notes = models.TextField(blank=True, default='')
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)


class FinanceReminders(models.Model):
    TYPE_RECEIVABLE = 'RECEIVABLE'
    TYPE_PAYABLE = 'PAYABLE'
    TYPE_GENERAL = 'GENERAL'
    TYPE_CHOICES = [
        (TYPE_RECEIVABLE, 'Receber'),
        (TYPE_PAYABLE, 'Pagar'),
        (TYPE_GENERAL, 'Geral'),
    ]
    STATUS_PENDING = 'PENDING'
    STATUS_DONE = 'DONE'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_DONE, 'Concluido'),
    ]

    title = models.CharField(max_length=160)
    reminder_type = models.CharField(max_length=12, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    due_date = models.DateField(null=True, blank=True)
    amount = models.FloatField(default=0)
    customer = models.ForeignKey(Customers, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_reminders')
    notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)