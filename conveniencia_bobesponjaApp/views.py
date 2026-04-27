from django.shortcuts import redirect, render
from django.http import HttpResponse
from .models import Categorys, Products, Sales, Salesitems
from django.db.models import Count, Sum, Q
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from smtplib import SMTPAuthenticationError
import json, sys
from datetime import datetime,date
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.crypto import get_random_string
from django.urls import reverse
from functools import wraps
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'Acesso permitido apenas ao administrador.', fail_silently=True)
            return redirect('pos-page')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def is_overnight_period(reference_dt=None):
    current_dt = timezone.localtime(reference_dt or timezone.now())
    return 0 <= current_dt.hour < 6


def get_product_active_price(product, reference_dt=None):
    if is_overnight_period(reference_dt):
        overnight_price = float(getattr(product, 'overnight_price', 0) or 0)
        if overnight_price > 0:
            return overnight_price
    return float(product.price)


def parse_brl_currency(value, default=0):
    if value is None:
        return default

    cleaned_value = str(value).strip()
    if cleaned_value == '':
        return default

    cleaned_value = cleaned_value.replace('R$', '').replace(' ', '')
    if ',' in cleaned_value:
        cleaned_value = cleaned_value.replace('.', '').replace(',', '.')

    try:
        return float(cleaned_value)
    except (TypeError, ValueError):
        return default


def format_brl(value):
    normalized = float(value or 0)
    formatted = f'{normalized:,.2f}'
    return f'R$ {formatted.replace(",", "_").replace(".", ",").replace("_", ".")}'


def about(request):
    context={
        'title': 'Sobre a Conveniência Bob Esponja',
        'description': 'A conveniência Bob Esponja é uma distribuidora de bebidas.'
    }
    return render(request, 'conveniencia/about.html', context)


#Login
def login_user(request):
    logout(request)
    resp = {"status":'failed','msg':''}
    username = ''
    password = ''
    if request.POST:
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                resp['status']='success'
            else:
                resp['msg'] = "Nome de usuário ou senha incorretos"
        else:
            resp['msg'] = "Nome de usuário ou senha incorretos"
    return HttpResponse(json.dumps(resp),content_type='application/json')      


def register_user(request):
    resp = {"status": 'failed', 'msg': ''}
    if request.method == 'POST':
        if not request.user.is_authenticated or not request.user.is_superuser:
            resp['msg'] = 'Apenas administradores podem criar novos usuários.'
            return HttpResponse(json.dumps(resp), content_type='application/json', status=403)

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        is_admin = request.POST.get('is_admin', '').lower() in ['1', 'true', 'on', 'yes']

        if not username or not password:
            resp['msg'] = 'Preencha os campos obrigatórios.'
        elif password != confirm_password:
            resp['msg'] = 'As senhas não coincidem.'
        elif User.objects.filter(username=username).exists():
            resp['msg'] = 'Este nome de usuário já está em uso.'
        else:
            try:
                user = User.objects.create_user(username=username, email=email, password=password)
                user.is_superuser = is_admin
                user.is_staff = is_admin
                user.is_active = True
                user.save(update_fields=['is_superuser', 'is_staff', 'is_active'])
                resp['status'] = 'success'
                resp['msg'] = 'Administrador criado com sucesso.' if is_admin else 'Vendedor criado com sucesso.'
            except Exception:
                resp['msg'] = 'Não foi possível criar o usuário.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


def forgot_password(request):
    resp = {'status': 'failed', 'msg': ''}
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            resp['msg'] = 'Informe o e-mail cadastrado.'
        else:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                resp['msg'] = 'Nenhum usuário encontrado com este e-mail.'
            elif not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD or 'console.EmailBackend' in settings.EMAIL_BACKEND:
                resp['msg'] = 'Configure um e-mail remetente com SMTP e Senha de App para liberar o envio real.'
            else:
                try:
                    temp_password = get_random_string(10)
                    change_url = request.build_absolute_uri(reverse('change-password-page')) + f'?identifier={email}'
                    plain_message = (
                        f'Olá, {user.username}!\n\n'
                        f'Sua nova senha temporária é: {temp_password}\n\n'
                        f'Para alterar sua senha, acesse: {change_url}'
                    )
                    html_message = f'''
                        <div style="font-family: Arial, sans-serif; padding: 16px;">
                            <h2>Recuperação de senha</h2>
                            <p>Olá, <strong>{user.username}</strong>!</p>
                            <p>Sua nova senha temporária é:</p>
                            <p style="font-size: 18px; font-weight: bold; color: #0d6efd;">{temp_password}</p>
                            <p>Se quiser, altere sua senha clicando no botão abaixo:</p>
                            <p>
                                <a href="{change_url}" style="background:#198754;color:#fff;padding:10px 16px;text-decoration:none;border-radius:6px;display:inline-block;">
                                    Alterar senha
                                </a>
                            </p>
                        </div>
                    '''
                    with transaction.atomic():
                        user.set_password(temp_password)
                        user.save()
                        send_mail(
                            subject='Recuperação de senha - Sistema de Vendas',
                            message=plain_message,
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                            recipient_list=[email],
                            fail_silently=False,
                            html_message=html_message,
                        )
                    resp['status'] = 'success'
                    resp['msg'] = 'Uma senha temporária foi enviada para o seu e-mail.'
                except SMTPAuthenticationError:
                    resp['msg'] = 'O Gmail recusou o login SMTP. Ative a verificação em 2 etapas e use uma Senha de App do Google.'
                except Exception:
                    resp['msg'] = 'Não foi possível enviar o e-mail de recuperação.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


def change_password_page(request):
    identifier = request.GET.get('identifier', '')
    return render(request, 'conveniencia/change_password.html', {'identifier': identifier})


def change_password_login(request):
    resp = {'status': 'failed', 'msg': ''}
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not identifier or not current_password or not new_password:
            resp['msg'] = 'Preencha os campos obrigatórios.'
        elif new_password != confirm_password:
            resp['msg'] = 'As novas senhas não coincidem.'
        else:
            user = User.objects.filter(username=identifier).first()
            if not user:
                user = User.objects.filter(email__iexact=identifier).first()

            if not user:
                resp['msg'] = 'Usuário não encontrado.'
            else:
                auth_user = authenticate(username=user.username, password=current_password)
                if auth_user is None:
                    resp['msg'] = 'Senha atual incorreta.'
                else:
                    try:
                        user.set_password(new_password)
                        user.save()
                        resp['status'] = 'success'
                        resp['msg'] = 'Senha alterada com sucesso.'
                    except Exception:
                        resp['msg'] = 'Não foi possível alterar a senha.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@admin_required
def users_page(request):
    search_query = request.GET.get('search', '').strip()
    profile_filter = request.GET.get('profile', '').strip()

    users = User.objects.all().annotate(total_sales_count=Count('sales'), total_sales_amount=Sum('sales__grand_total')).order_by('-is_superuser', 'username')

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    if profile_filter == 'admin':
        users = users.filter(is_superuser=True)
    elif profile_filter == 'seller':
        users = users.filter(is_superuser=False)

    ranking_users = User.objects.all().annotate(
        total_sales_count=Count('sales'),
        total_sales_amount=Sum('sales__grand_total')
    ).order_by('-total_sales_amount', '-total_sales_count', 'username')[:5]

    context = {
        'page_title': 'Gerenciar Usuários',
        'users': users,
        'ranking_users': ranking_users,
        'search_query': search_query,
        'profile_filter': profile_filter,
    }
    return render(request, 'conveniencia/users.html', context)


@admin_required
def toggle_user_status(request):
    resp = {'status': 'failed', 'msg': ''}
    user_id = request.POST.get('id')
    try:
        user_obj = User.objects.filter(id=user_id).first()
        if not user_obj:
            resp['msg'] = 'Usuário não encontrado.'
        elif user_obj.is_superuser:
            resp['msg'] = 'O superusuário principal não pode ser alterado.'
        elif user_obj == request.user:
            resp['msg'] = 'Você não pode alterar o próprio status aqui.'
        else:
            user_obj.is_active = not user_obj.is_active
            user_obj.save()
            resp['status'] = 'success'
            resp['msg'] = 'Status do usuário atualizado com sucesso.'
            messages.success(request, 'Status do usuário atualizado com sucesso.', fail_silently=True)
    except Exception:
        resp['msg'] = 'Não foi possível atualizar o usuário.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@admin_required
def update_user_account(request):
    resp = {'status': 'failed', 'msg': ''}
    user_id = request.POST.get('id')
    try:
        user_obj = User.objects.filter(id=user_id).first()
        if not user_obj:
            resp['msg'] = 'Usuário não encontrado.'
        else:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            is_admin = request.POST.get('is_admin', '').lower() in ['1', 'true', 'on', 'yes']

            if not username:
                resp['msg'] = 'O nome de usuário é obrigatório.'
            elif User.objects.exclude(id=user_obj.id).filter(username=username).exists():
                resp['msg'] = 'Já existe outro usuário com esse nome.'
            elif not is_admin and user_obj.is_superuser and User.objects.filter(is_superuser=True).exclude(id=user_obj.id).count() <= 0:
                resp['msg'] = 'Voce nao pode remover seu proprio perfil de administrador aqui.'
            else:
                user_obj.username = username
                user_obj.email = email
                user_obj.is_superuser = is_admin
                user_obj.is_staff = is_admin
                if password:
                    user_obj.set_password(password)
                user_obj.save()
                resp['status'] = 'success'
                resp['msg'] = 'Usuário atualizado com sucesso.'
                messages.success(request, 'Usuário atualizado com sucesso.', fail_silently=True)
    except Exception:
        resp['msg'] = 'Não foi possível atualizar o usuário.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@admin_required
def toggle_user_role(request):
    resp = {'status': 'failed', 'msg': ''}
    user_id = request.POST.get('id')
    make_admin = request.POST.get('is_admin', '').lower() in ['1', 'true', 'on', 'yes']

    try:
        user_obj = User.objects.filter(id=user_id).first()
        if not user_obj:
            resp['msg'] = 'Usuário não encontrado.'
        elif user_obj == request.user:
            resp['msg'] = 'Voce nao pode alterar o proprio perfil por esta chavinha.'
        elif not make_admin and user_obj.is_superuser and User.objects.filter(is_superuser=True).exclude(id=user_obj.id).count() <= 0:
            resp['msg'] = 'O sistema precisa manter pelo menos um administrador.'
        else:
            user_obj.is_superuser = make_admin
            user_obj.is_staff = make_admin
            user_obj.save(update_fields=['is_superuser', 'is_staff'])
            resp['status'] = 'success'
            resp['msg'] = 'Perfil atualizado com sucesso.'
            messages.success(request, 'Perfil do usuário atualizado com sucesso.', fail_silently=True)
    except Exception:
        resp['msg'] = 'Não foi possível atualizar o perfil do usuário.'

    return HttpResponse(json.dumps(resp), content_type='application/json')


@admin_required
def delete_user_account(request):
    resp = {'status': 'failed', 'msg': ''}
    user_id = request.POST.get('id')
    try:
        user_obj = User.objects.filter(id=user_id).first()
        if not user_obj:
            resp['msg'] = 'Usuário não encontrado.'
        elif user_obj.is_superuser:
            resp['msg'] = 'O superusuário principal não pode ser excluído.'
        elif user_obj == request.user:
            resp['msg'] = 'Você não pode excluir a própria conta.'
        else:
            user_obj.delete()
            resp['status'] = 'success'
            resp['msg'] = 'Usuário excluído com sucesso.'
            messages.success(request, 'Usuário excluído com sucesso.', fail_silently=True)
    except Exception:
        resp['msg'] = 'Não foi possível excluir o usuário.'
    return HttpResponse(json.dumps(resp), content_type='application/json')


#Logout
def logoutuser(request):
    logout(request)
    return redirect('/')

@login_required
def home(request):
    now = datetime.now()
    current_year = now.strftime("%Y")
    current_month = now.strftime("%m")
    current_day = now.strftime("%d")
    categories = len(Categorys.objects.all()) if request.user.is_superuser else 0
    products = len(Products.objects.all()) if request.user.is_superuser else 0
    today_sales = Sales.objects.filter(
        date_added__year=current_year,
        date_added__month=current_month,
        date_added__day=current_day
    )
    if not request.user.is_superuser:
        today_sales = today_sales.filter(user=request.user)
    transaction = today_sales.count()
    total_sales = sum(today_sales.values_list('grand_total', flat=True))
    context = {
        'page_title':'Início',
        'categories' : categories,
        'products' : products,
        'transaction' : transaction,
        'total_sales' : total_sales,
    }
    return render(request, 'conveniencia/home.html',context)

@admin_required
def category(request):
    category_list = Categorys.objects.all()
    context = {
        'page_title': 'Lista de Categorias',
        'category': category_list
    }
    return render(request, 'conveniencia/category.html', context)

@admin_required
def manage_category(request):
    category = {}
    if request.method == 'GET':
        data =  request.GET
        id = ''
        if 'id' in data:
            id= data['id']
        if id.isnumeric() and int(id) > 0:
            category = Categorys.objects.filter(id=id).first()
    
    context = {
        'category' : category
    }
    return render(request, 'conveniencia/manage_category.html',context)

@admin_required
def save_category(request):
    data = request.POST
    respo = {"status": 'failed', 'msg': ''}

    try:
        if data['id'].isnumeric() and int(data['id'])>0:
            save_cat = Categorys.objects.filter(id=data['id']).update(name=data['name'], description=data['description'], status=data['status'])
        else:
            save_category=Categorys(name=data['name'], description=data['description'], status=data['status'])
            save_category.save()
        respo['status']='success'
        messages.success(request, 'Categoria salva com sucesso.')
    except:
        respo["status"]='failed' 
    return HttpResponse(json.dumps(respo), content_type="application/json")


@admin_required
def delete_category(request):
    data = request.POST
    resp = {"status": ''}
    try:
        category = Categorys.objects.filter(id = data['id']).delete()
        resp['status']='success'
        messages.success(request, 'Categoria deletada com sucesso.')
    except: 
        resp['status']='failed'
    return HttpResponse(json.dumps(resp), content_type="application/json")


@admin_required
def products(request):
    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    
    # Start with all products
    products_list = Products.objects.all()
    
    # Apply search filter (name, code, description)
    if search_query:
        products_list = products_list.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        products_list = products_list.filter(category_id__id=category_filter)
    
    # Apply status filter
    if status_filter:
        products_list = products_list.filter(status=status_filter)
    
    # Get categories for filter dropdown
    categories = Categorys.objects.filter(status=1).all()
    
    context = {
        'page_title': 'Lista de Produtos',
        'products': products_list,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter
    }
    return render(request, 'conveniencia/products.html', context)

@admin_required
def manage_product(request):
    product = {}
    category = Categorys.objects.filter(status=1).all()
    if request.method == 'GET':
        data=request.GET
        id=''
        if('id' in data):
            id=data['id']
            if id.isnumeric() and int(id)>0:
                product = Products.objects.filter(id=id).first()

    context={
        'product': product,
        'categories': category
    }
    return render(request, 'conveniencia/manage_product.html', context)

def test(request):
    categories = Categorys.objects.all()
    context = {
        'categories' : categories
    }
    return render(request, 'conveniencia_App/test.html',context)

@admin_required
def save_product(request):
    data = request.POST
    resp = {"status": 'failed'}
    id = ''
    if 'id' in data:
        id = data['id']
    code_exists = False
    if id.isnumeric() and int(id)>0:
        code_exists = Products.objects.exclude(id=id).filter(code=data['code']).exists()
    else:
        code_exists = Products.objects.filter(code=data['code']).exists()
    if code_exists:
        resp['msg']='Código do produto já existe no banco de dados.'
    else:
        category = Categorys.objects.filter(id=data['category_id']).first()
        try:
            quantity = 0
            overnight_price = 0
            base_price = 0
            try:
                quantity = int(data.get('quantity', 0))
            except (ValueError, TypeError):
                quantity = 0
            base_price = parse_brl_currency(data.get('price', 0), 0)
            overnight_price = parse_brl_currency(data.get('overnight_price', 0), 0)
            if (data['id'].isnumeric() and int(data['id'])>0):
                save_product = Products.objects.filter(id=data['id']).first()
                if save_product:
                    save_product.code = data['code']
                    save_product.category_id = category
                    save_product.name = data['name']
                    save_product.description = data['description']
                    save_product.price = base_price
                    save_product.overnight_price = overnight_price
                    save_product.quantity = quantity
                    save_product.status = data['status']
                    save_product.save()
            else:
                save_product = Products(code=data['code'], category_id=category, name=data['name'], description=data['description'], price=base_price, overnight_price=overnight_price, quantity=quantity, status=data['status'])
                save_product.save()
            resp['status']='success'
            messages.success(request, 'Produto salvo com sucesso.')
        except:
            resp['status']='failed'
    return HttpResponse(json.dumps(resp), content_type="application/json")

@admin_required
def delete_product(request):
    data = request.POST
    resp = {"status": ''}
    try:
        product = Products.objects.filter(id=data['id']).delete()
        resp['status']='success'
        messages.success(request, 'Produto deletado com sucesso.')
    except:
        resp['status']='failed'
    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def pos(request):
    products = Products.objects.filter(status=1)
    products_json = []
    overnight_mode = is_overnight_period()
    for product in products:
        active_price = get_product_active_price(product)
        products_json.append({
            'id': product.id,
            'code': product.code,
            'name': product.name,
            'price': active_price,
            'base_price': float(product.price),
            'overnight_price': float(product.overnight_price),
            'overnight_mode': overnight_mode,
            'quantity': product.quantity,
        })
    context = {
        'page_title': 'Ponto de Venda',
        'products': products,
        'product_json': mark_safe(json.dumps(products_json)),
        'overnight_mode': overnight_mode,
    }
    return render(request, 'conveniencia/pos.html', context)

@login_required
def checkout_modal(request):
    grand_total = 0
    if 'grand_total' in request.GET:
        grand_total = request.GET['grand_total']
    context = {
        'grand_total' : grand_total,
    }
    return render(request, 'conveniencia/checkout.html',context)

@login_required
def save_pos(request):
    resp = {'status':'failed','msg':''}
    data = request.POST
    pref = datetime.now().year + datetime.now().year
    i = 1
    while True:
        code = '{:0>5}'.format(i)
        i += int(1)
        check = Sales.objects.filter(code = str(pref) + str(code)).all()
        if len(check) <= 0:
            break
    code = str(pref) + str(code)

    try:
        product_ids = data.getlist('product_id[]')
        quantities = data.getlist('qty[]')
        prices = data.getlist('price[]')
        sale_items_payload = []
        computed_sub_total = 0

        if not product_ids:
            raise ValueError('Adicione pelo menos um item antes de finalizar a venda.')

        with transaction.atomic():
            for index, product_id in enumerate(product_ids):
                product = Products.objects.select_for_update().filter(id=product_id, status=1).first()
                if not product:
                    raise ValueError('Um dos produtos informados nao esta mais disponivel para venda.')

                try:
                    qty = int(float(quantities[index]))
                except (TypeError, ValueError, IndexError):
                    raise ValueError('Foi encontrado um item com quantidade ou preco invalido.')

                try:
                    submitted_price = Decimal(str(prices[index]))
                except (TypeError, ValueError, IndexError, InvalidOperation):
                    raise ValueError('Foi encontrado um item com quantidade ou preco invalido.')

                if qty <= 0:
                    raise ValueError(f'Quantidade invalida para o produto {product.name}.')

                if product.quantity < qty:
                    raise ValueError(f'Estoque insuficiente para o produto {product.name}. Disponivel: {product.quantity}.')

                active_price = Decimal(str(get_product_active_price(product)))
                if submitted_price != active_price:
                    raise ValueError(f'O preco do produto {product.name} mudou. Adicione o item novamente para atualizar o caixa.')

                price = float(active_price)
                total = float(qty) * float(price)
                computed_sub_total += total
                sale_items_payload.append({
                    'product': product,
                    'qty': qty,
                    'price': price,
                    'total': total,
                })

            sale = Sales(
                user=request.user,
                code=code,
                sub_total=computed_sub_total,
                grand_total=computed_sub_total,
                tendered=data['tendered_amount'],
                amount_change=data['amount_change']
            )
            sale.save()
            sale_id = sale.pk

            for item in sale_items_payload:
                Salesitems(
                    sale_id=sale,
                    product_id=item['product'],
                    qty=item['qty'],
                    price=item['price'],
                    total_price=item['total']
                ).save()

                item['product'].quantity -= item['qty']
                item['product'].save(update_fields=['quantity', 'date_updated'])

        resp['status'] = 'success'
        resp['sale_id'] = sale_id
        messages.success(request, "Registro de venda salvo com sucesso.")
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def salesList(request):
    sales_queryset = Sales.objects.all().order_by('-date_added') if request.user.is_superuser else Sales.objects.filter(user=request.user).order_by('-date_added')
    sale_data = []
    for sale in sales_queryset:
        data = {}
        for field in sale._meta.get_fields(include_parents=False):
            if field.related_model is None:
                data[field.name] = getattr(sale,field.name)
        data['items'] = Salesitems.objects.filter(sale_id = sale).all()
        data['item_count'] = len(data['items'])
        data['cashier'] = sale.user.username if sale.user else 'Sistema'
        sale_data.append(data)
    context = {
        'page_title':'Transações de Vendas',
        'sale_data':sale_data,
    }
    return render(request, 'conveniencia/sales.html',context)

@login_required
def receipt(request):
    id = request.GET.get('id')
    sales_obj = Sales.objects.filter(id=id).first()
    if not sales_obj:
        return HttpResponse('Transação não encontrada.')
    if not request.user.is_superuser and sales_obj.user != request.user:
        return HttpResponse('Acesso negado.')
    transaction = {}
    for field in Sales._meta.get_fields():
        if field.related_model is None:
            transaction[field.name] = getattr(sales_obj,field.name)
    ItemList = Salesitems.objects.filter(sale_id = sales_obj).all()
    context = {
        "transaction" : transaction,
        "salesItems" : ItemList
    }

    return render(request, 'conveniencia/receipt.html',context)

@login_required
def delete_sale(request):
    resp = {'status':'failed', 'msg':''}
    id = request.POST.get('id')
    try:
        sale_qs = Sales.objects.filter(id=id)
        if not request.user.is_superuser:
            sale_qs = sale_qs.filter(user=request.user)
        deleted_count, _ = sale_qs.delete()
        if deleted_count > 0:
            resp['status'] = 'success'
            messages.success(request, 'Registro de venda deletado com sucesso.')
        else:
            resp['msg'] = 'Você não tem permissão para excluir esta venda.'
    except:
        resp['msg'] = "Ocorreu um erro"
    return HttpResponse(json.dumps(resp), content_type='application/json')

@login_required
def generate_sales_report(request):
    from io import BytesIO
    
    # Get date filters
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    # Filter sales by date range
    sales_queryset = Sales.objects.all() if request.user.is_superuser else Sales.objects.filter(user=request.user)
    
    if data_inicio:
        try:
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
            sales_queryset = sales_queryset.filter(date_added__gte=data_inicio_dt)
        except:
            pass
    
    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d')
            data_fim_dt = data_fim_dt.replace(hour=23, minute=59, second=59)
            sales_queryset = sales_queryset.filter(date_added__lte=data_fim_dt)
        except:
            pass
    
    sales_queryset = sales_queryset.order_by('-date_added')
    
    # Calculate totals
    total_vendas = sales_queryset.count()
    total_valor = sum(s.grand_total for s in sales_queryset)
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    elements.append(Paragraph('RELATÓRIO DE VENDAS E FATURAMENTO', title_style))
    elements.append(Paragraph('Conveniência Bob Esponja', styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Date range info
    date_range = ''
    if data_inicio or data_fim:
        date_range = f'Período: {data_inicio if data_inicio else "Sem data"} até {data_fim if data_fim else "Sem data"}'
    else:
        date_range = 'Período: Todos os registros'
    
    elements.append(Paragraph(f'<b>{date_range}</b>', styles['Normal']))
    elements.append(Paragraph(f'Data de Emissão: {datetime.now().strftime("%d/%m/%Y %H:%M")}', styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Summary table
    summary_data = [
        ['Métrica', 'Valor'],
        ['Total de Vendas', str(total_vendas)],
        ['Valor Total', format_brl(total_valor)],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Detailed sales table
    elements.append(Paragraph('<b>Detalhamento de Vendas</b>', styles['Heading2']))
    elements.append(Spacer(1, 0.15*inch))
    
    sales_data = [['Data/Hora', 'Código', 'Produto', 'Qtd', 'Subtotal']]
    date_row_indices = []
    daily_total_row_indices = []
    current_date = None
    daily_total = 0.0
    
    def append_daily_total(date_total):
        if date_total is not None:
            sales_data.append(['', '', '', 'TOT DO DIA', format_brl(date_total)])
            daily_total_row_indices.append(len(sales_data) - 1)

    for sale in sales_queryset:
        sale_day = sale.date_added.strftime('%d/%m/%Y')
        if sale_day != current_date:
            if current_date is not None:
                append_daily_total(daily_total)
            current_date = sale_day
            daily_total = 0.0
            sales_data.append([f'DIA: {current_date}', '', '', '', ''])
            date_row_indices.append(len(sales_data) - 1)
        
        sale_items = Salesitems.objects.filter(sale_id=sale).all()
        if sale_items:
            for item in sale_items:
                item_subtotal = item.total_price if hasattr(item, 'total_price') else float(item.qty) * float(item.price)
                daily_total += item_subtotal
                sales_data.append([
                    sale.date_added.strftime('%d/%m/%Y %H:%M'),
                    sale.code,
                    item.product_id.name if item.product_id else '-',
                    str(item.qty),
                    format_brl(item_subtotal)
                ])
        else:
            line_subtotal = float(sale.sub_total)
            daily_total += line_subtotal
            sales_data.append([
                sale.date_added.strftime('%d/%m/%Y %H:%M'),
                sale.code,
                '-',
                '0',
                format_brl(line_subtotal)
            ])
    
    if current_date is not None:
        append_daily_total(daily_total)
    if len(sales_data) > 1:
        sales_data.append(['', '', '', 'TOTAL', format_brl(total_valor)])
        sales_table = Table(sales_data, colWidths=[1.5*inch, 1.1*inch, 2.6*inch, 0.8*inch, 1.2*inch], repeatRows=1)
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066cc')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -2), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.lightgrey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9ecef')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (2, 1), (2, -2), 'LEFT'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('SPAN', (0, -1), (3, -1)),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
            ('ALIGN', (0, -1), (3, -1), 'RIGHT'),
        ])
        for row_idx in date_row_indices:
            table_style.add('SPAN', (0, row_idx), (-1, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#d9edf7'))
            table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
            table_style.add('ALIGN', (0, row_idx), (-1, row_idx), 'LEFT')
            table_style.add('FONTSIZE', (0, row_idx), (-1, row_idx), 9)
        for row_idx in daily_total_row_indices:
            table_style.add('SPAN', (0, row_idx), (3, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f7f7f7'))
            table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
            table_style.add('FONTSIZE', (0, row_idx), (-1, row_idx), 10)
            table_style.add('ALIGN', (0, row_idx), (3, row_idx), 'RIGHT')
        sales_table.setStyle(table_style)
        elements.append(sales_table)
    else:
        elements.append(Paragraph('Nenhuma venda encontrada no período selecionado.', styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    # Return as download
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    return response
