from django.contrib import admin

from conveniencia_bobesponjaApp.models import (
	Categorys,
	Customers,
	FinanceReminders,
	PayableAccounts,
	Products,
	Sales,
	Salesitems,
	SupplierProductPrices,
	Suppliers,
)


admin.site.register(Categorys)
admin.site.register(Customers)
admin.site.register(Products)
admin.site.register(Sales)
admin.site.register(Salesitems)
admin.site.register(Suppliers)
admin.site.register(SupplierProductPrices)
admin.site.register(PayableAccounts)
admin.site.register(FinanceReminders)