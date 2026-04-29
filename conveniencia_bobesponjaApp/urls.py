from . import views
from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView

urlpatterns = [
    path('about/', views.about, name='about-page'),
    path('redirect-admin', RedirectView.as_view(url="/admin"),name="redirect-admin"),
    path('', views.home, name="home-page"),
    path('login', views.login_page, name="login"),
    path('userlogin', views.login_user, name="login-user"),
    path('register-user', views.register_user, name="register-user"),
    path('forgot-password', views.forgot_password, name="forgot-password"),
    path('change-password', views.change_password_page, name="change-password-page"),
    path('change-password-login', views.change_password_login, name="change-password-login"),
    path('users', views.users_page, name="users-page"),
    path('toggle-user-role', views.toggle_user_role, name="toggle-user-role"),
    path('toggle-user-status', views.toggle_user_status, name="toggle-user-status"),
    path('update-user-account', views.update_user_account, name="update-user-account"),
    path('delete-user-account', views.delete_user_account, name="delete-user-account"),
    path('logout', views.logoutuser, name="logout"),
    path('category', views.category, name="category-page"),
    path('manage_category', views.manage_category, name="manage_category-page"),
    path('save_category', views.save_category, name="save-category-page"),
    path('delete_category', views.delete_category, name="delete-category"),
    path('products', views.products, name="product-page"),
    path('manage_product', views.manage_product, name="manage_product-page"),
    path('test', views.test, name="test-page"),
    path('save_product', views.save_product, name="save-product-page"),
    path('delete_product', views.delete_product, name="delete-product"),
    path('pos', views.pos, name="pos-page"),
    path('checkout-modal', views.checkout_modal, name="checkout-modal"),
    path('save-pos', views.save_pos, name="save-pos"),
    path('sales', views.salesList, name="sales-page"),
    path('receipt', views.receipt, name="receipt-modal"),
    path('delete_sale', views.delete_sale, name="delete-sale"),
    path('generate-sales-report', views.generate_sales_report, name="generate-sales-report"),

]