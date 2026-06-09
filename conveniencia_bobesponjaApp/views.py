from django.shortcuts import redirect, render
from django.http import HttpResponse
from .models import Categorys, Customers, FinanceReminders, PayableAccounts, Products, Sales, Salesitems, SupplierProductPrices, Suppliers
from django.db.models import Count, Sum, Q, Prefetch
from django.db.models.functions import TruncHour
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from smtplib import SMTPAuthenticationError
import json, sys, re
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
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
try:
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, 'save_pos.log')
    # avoid adding multiple handlers when module reloaded
    if not any(isinstance(h, logging.FileHandler) and os.path.abspath(getattr(h, 'baseFilename', '')) == os.path.abspath(log_file) for h in logger.handlers):
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
except Exception:
    logging.exception('Failed to configure file logger for save_pos')


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


def generate_internal_product_code():
    allowed_chars = '0123456789'
    for _ in range(50):
        generated_code = f"29{get_random_string(11, allowed_chars=allowed_chars)}"
        if not Products.objects.filter(code=generated_code).exists():
            return generated_code
    raise ValueError('Nao foi possivel gerar um codigo interno unico para o produto.')


def format_brl(value):
    normalized = float(value or 0)
    formatted = f'{normalized:,.2f}'
    return f'R$ {formatted.replace(",", "_").replace(".", ",").replace("_", ".")}'


def parse_decimal_value(value, default=Decimal('0')):
    if value is None:
        return default

    cleaned_value = str(value).strip()
    if cleaned_value == '':
        return default

    cleaned_value = cleaned_value.replace('R$', '').replace(' ', '')
    if ',' in cleaned_value:
        cleaned_value = cleaned_value.replace('.', '').replace(',', '.')

    try:
        return Decimal(cleaned_value)
    except (InvalidOperation, TypeError, ValueError):
        return default


def normalize_customer_name(value):
    normalized = str(value or '').strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def resolve_customer_from_payload(customer_name, customer_phone=''):
    normalized_name = normalize_customer_name(customer_name)
    normalized_phone = str(customer_phone or '').strip()

    if not normalized_name:
        return None

    customer = Customers.objects.filter(name__iexact=normalized_name).first()
    if customer is None:
        customer = Customers.objects.create(
            name=normalized_name,
            phone=normalized_phone,
        )
        return customer

    updated_fields = []
    if normalized_phone and customer.phone != normalized_phone:
        customer.phone = normalized_phone
        updated_fields.append('phone')
    if updated_fields:
        customer.save(update_fields=updated_fields)
    return customer


def generate_comanda_code(customer=None):
    timestamp_code = timezone.localtime(timezone.now()).strftime('%Y%m%d%H%M%S')
    if customer and str(customer.name or '').strip():
        safe_customer_name = re.sub(r'[^A-Z0-9]+', '-', customer.name.upper()).strip('-')
        return f'{safe_customer_name or "CLIENTE"}-{timestamp_code}'
    return f'COMANDA-{timestamp_code}'


def about(request):
    context={
        'title': 'Sobre a Conveniência Bob Esponja',
        'description': 'A conveniência Bob Esponja é uma distribuidora de bebidas.'
    }
    return render(request, 'conveniencia/about.html', context)


def login_page(request):
    if request.user.is_authenticated:
        return redirect('home-page')

    context = {
        'can_self_register_initial': not User.objects.exists(),
    }
    return render(request, 'conveniencia/login.html', context)


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
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not username or not password:
            resp['msg'] = 'Preencha os campos obrigatórios.'
        elif password != confirm_password:
            resp['msg'] = 'As senhas não coincidem.'
        else:
            try:
                with transaction.atomic():
                    first_user_registration = not User.objects.exists()

                    if not first_user_registration and (not request.user.is_authenticated or not request.user.is_superuser):
                        resp['msg'] = 'Cadastro inicial já foi concluído. Apenas administradores podem criar novos usuários.'
                        return HttpResponse(json.dumps(resp), content_type='application/json', status=403)

                    if User.objects.filter(username=username).exists():
                        resp['msg'] = 'Este nome de usuário já está em uso.'
                        return HttpResponse(json.dumps(resp), content_type='application/json')

                    is_admin = first_user_registration or request.POST.get('is_admin', '').lower() in ['1', 'true', 'on', 'yes']

                    user = User.objects.create_user(username=username, email=email, password=password)
                    user.is_superuser = is_admin
                    user.is_staff = is_admin
                    user.is_active = True
                    user.save(update_fields=['is_superuser', 'is_staff', 'is_active'])

                resp['status'] = 'success'
                if first_user_registration:
                    resp['msg'] = 'Conta inicial criada com sucesso. Você já pode entrar como administrador.'
                else:
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
                    base_change_url = request.build_absolute_uri(reverse('change-password-page'))
                    preferred_scheme = getattr(settings, 'DEFAULT_SCHEME', 'https')
                    if preferred_scheme in {'http', 'https'}:
                        base_change_url = base_change_url.replace('http://', f'{preferred_scheme}://', 1).replace('https://', f'{preferred_scheme}://', 1)
                    change_url = f'{base_change_url}?identifier={email}'
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
    if not request.user or not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
        return redirect('login')
    
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


@login_required
def customers(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    customers_list = Customers.objects.all().order_by('name', 'id')

    if search_query:
        customers_list = customers_list.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(notes__icontains=search_query)
        )

    if status_filter == '1':
        customers_list = customers_list.filter(active=True)
    elif status_filter == '0':
        customers_list = customers_list.filter(active=False)

    context = {
        'page_title': 'Clientes',
        'customers': customers_list,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'conveniencia/customers.html', context)


@login_required
def manage_customer(request):
    customer = {}
    if request.method == 'GET':
        data = request.GET
        customer_id = str(data.get('id', '')).strip()
        if customer_id.isnumeric() and int(customer_id) > 0:
            customer = Customers.objects.filter(id=customer_id).first()

    context = {
        'customer': customer,
    }
    return render(request, 'conveniencia/manage_customer.html', context)


@login_required
def select_customer_modal(request):
    search_query = request.GET.get('search', '').strip()
    customers_list = Customers.objects.filter(active=True).order_by('name', 'id')
    if search_query:
        customers_list = customers_list.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    context = {
        'customers': customers_list,
        'search_query': search_query,
    }
    return render(request, 'conveniencia/select_customer_modal.html', context)


@login_required
def save_customer(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}

    try:
        customer_id = str(data.get('id', '')).strip()
        name = normalize_customer_name(data.get('name', ''))
        phone = str(data.get('phone', '')).strip()
        notes = str(data.get('notes', '')).strip()
        active = str(data.get('active', '1')).strip() in {'1', 'true', 'on', 'yes'}
        require_duplicate_confirmation = str(data.get('require_duplicate_confirmation', '0')).strip() in {'1', 'true', 'on', 'yes'}
        confirm_duplicate_update = str(data.get('confirm_duplicate_update', '0')).strip() in {'1', 'true', 'on', 'yes'}

        if not name:
            raise ValueError('Informe o nome do cliente.')
        if len(name) > 150:
            raise ValueError('O nome do cliente deve ter no maximo 150 caracteres.')
        if len(phone) > 30:
            raise ValueError('O telefone deve ter no maximo 30 caracteres.')

        if customer_id.isnumeric() and int(customer_id) > 0:
            customer = Customers.objects.filter(id=int(customer_id)).first()
            if not customer:
                raise ValueError('Cliente nao encontrado.')
            customer.name = name
            customer.phone = phone
            customer.notes = notes
            customer.active = active
            customer.save()
            messages.success(request, 'Cliente atualizado com sucesso.')
        else:
            customer = Customers.objects.filter(name__iexact=name).first()
            if customer:
                if require_duplicate_confirmation and not confirm_duplicate_update:
                    resp['status'] = 'confirm_required'
                    resp['msg'] = 'Esse cliente ja existe. Deseja sobrepor/atualizar o cadastro existente?'
                    resp['customer_id'] = customer.id
                    resp['customer_name'] = customer.name
                    resp['customer_phone'] = customer.phone
                    return HttpResponse(json.dumps(resp), content_type='application/json')
                customer.name = name
                if phone:
                    customer.phone = phone
                if notes:
                    customer.notes = notes
                customer.active = active
                customer.save()
                messages.success(request, 'Cliente ja existente vinculado com sucesso.')
            else:
                customer = Customers(
                    name=name,
                    phone=phone,
                    notes=notes,
                    active=active,
                )
                customer.save()
                messages.success(request, 'Cliente cadastrado com sucesso.')

        resp['status'] = 'success'
        resp['customer_id'] = customer.id
        resp['customer_name'] = customer.name
        resp['customer_phone'] = customer.phone
    except Exception as e:
        resp['msg'] = str(e)

    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def delete_customer(request):
    data = request.POST
    resp = {'status': ''}
    try:
        customer = Customers.objects.filter(id=data['id']).first()
        if not customer:
            raise ValueError('Cliente nao encontrado.')
        customer.delete()
        resp['status'] = 'success'
        messages.success(request, 'Cliente removido com sucesso.')
    except Exception:
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def suppliers(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    suppliers_list = Suppliers.objects.prefetch_related(
        Prefetch('product_prices', queryset=SupplierProductPrices.objects.select_related('product').order_by('product__name'))
    ).all().order_by('id')
    if search_query:
        suppliers_list = suppliers_list.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    if status_filter == '1':
        suppliers_list = suppliers_list.filter(active=True)
    elif status_filter == '0':
        suppliers_list = suppliers_list.filter(active=False)

    context = {
        'page_title': 'Fornecedores',
        'suppliers': suppliers_list,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'conveniencia/suppliers.html', context)


@login_required
def manage_supplier(request):
    supplier = {}
    supplier_id = str(request.GET.get('id', '')).strip()
    if supplier_id.isnumeric() and int(supplier_id) > 0:
        supplier = Suppliers.objects.filter(id=int(supplier_id)).first()

    return render(request, 'conveniencia/manage_supplier.html', {'supplier': supplier})


@login_required
def save_supplier(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}
    try:
        supplier_id = str(data.get('id', '')).strip()
        name = str(data.get('name', '')).strip()
        phone = str(data.get('phone', '')).strip()
        address = str(data.get('address', '')).strip()
        active = str(data.get('active', '1')).strip() in {'1', 'true', 'on', 'yes'}

        if not name:
            raise ValueError('Informe o nome do fornecedor.')

        if supplier_id.isnumeric() and int(supplier_id) > 0:
            supplier = Suppliers.objects.filter(id=int(supplier_id)).first()
            if not supplier:
                raise ValueError('Fornecedor nao encontrado.')
            supplier.name = name
            supplier.phone = phone
            supplier.address = address
            supplier.active = active
            supplier.save()
            messages.success(request, 'Fornecedor atualizado com sucesso.')
        else:
            Suppliers.objects.create(name=name, phone=phone, address=address, active=active)
            messages.success(request, 'Fornecedor cadastrado com sucesso.')
        resp['status'] = 'success'
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def delete_supplier(request):
    resp = {'status': 'failed'}
    try:
        supplier = Suppliers.objects.filter(id=request.POST.get('id')).first()
        if not supplier:
            raise ValueError('Fornecedor nao encontrado.')
        supplier.delete()
        resp['status'] = 'success'
        messages.success(request, 'Fornecedor removido com sucesso.')
    except Exception:
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def supplier_prices(request):
    product_filter = str(request.GET.get('product_id', '')).strip()

    prices_qs = SupplierProductPrices.objects.select_related('supplier', 'product').all().order_by('product__name', 'price')
    if product_filter.isnumeric():
        prices_qs = prices_qs.filter(product_id=int(product_filter))

    price_data = []
    best_price_map = {}
    for item in prices_qs:
        product_id = item.product_id
        if product_id not in best_price_map or item.price < best_price_map[product_id]:
            best_price_map[product_id] = item.price

    for item in prices_qs:
        price_data.append({
            'id': item.id,
            'supplier': item.supplier.name,
            'product': item.product.name,
            'price': item.price,
            'notes': item.notes,
            'is_best': item.price == best_price_map.get(item.product_id),
        })

    context = {
        'page_title': 'Comparativo de Custos',
        'prices': price_data,
        'products': Products.objects.filter(status=1).order_by('name'),
        'suppliers': Suppliers.objects.filter(active=True).order_by('name'),
        'product_filter': product_filter,
    }
    return render(request, 'conveniencia/supplier_prices.html', context)


@login_required
def manage_supplier_price(request):
    price_entry = {}
    entry_id = str(request.GET.get('id', '')).strip()
    if entry_id.isnumeric() and int(entry_id) > 0:
        price_entry = SupplierProductPrices.objects.filter(id=int(entry_id)).first()

    context = {
        'price_entry': price_entry,
        'products': Products.objects.filter(status=1).order_by('name'),
        'suppliers': Suppliers.objects.filter(active=True).order_by('name'),
    }
    return render(request, 'conveniencia/manage_supplier_price.html', context)


@login_required
def save_supplier_price(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}
    try:
        entry_id = str(data.get('id', '')).strip()
        supplier_id = str(data.get('supplier_id', '')).strip()
        product_id = str(data.get('product_id', '')).strip()
        price = parse_brl_currency(data.get('price', 0), 0)
        notes = str(data.get('notes', '')).strip()

        if not supplier_id.isnumeric() or not Suppliers.objects.filter(id=int(supplier_id)).exists():
            raise ValueError('Fornecedor invalido.')
        if not product_id.isnumeric() or not Products.objects.filter(id=int(product_id)).exists():
            raise ValueError('Produto invalido.')
        if price <= 0:
            raise ValueError('Informe um preco valido.')

        if entry_id.isnumeric() and int(entry_id) > 0:
            entry = SupplierProductPrices.objects.filter(id=int(entry_id)).first()
            if not entry:
                raise ValueError('Registro nao encontrado.')
            entry.supplier_id = int(supplier_id)
            entry.product_id = int(product_id)
            entry.price = price
            entry.notes = notes
            entry.save()
            messages.success(request, 'Preco de fornecedor atualizado com sucesso.')
        else:
            entry, created = SupplierProductPrices.objects.get_or_create(
                supplier_id=int(supplier_id),
                product_id=int(product_id),
                defaults={'price': price, 'notes': notes},
            )
            if not created:
                entry.price = price
                entry.notes = notes
                entry.save()
                messages.success(request, 'Preco atualizado para o par fornecedor/produto existente.')
            else:
                messages.success(request, 'Preco de fornecedor cadastrado com sucesso.')

        resp['status'] = 'success'
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def delete_supplier_price(request):
    resp = {'status': 'failed'}
    try:
        entry = SupplierProductPrices.objects.filter(id=request.POST.get('id')).first()
        if not entry:
            raise ValueError('Registro nao encontrado.')
        entry.delete()
        resp['status'] = 'success'
        messages.success(request, 'Registro de preco removido com sucesso.')
    except Exception:
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def manage_supplier_product_create(request):
    supplier_id = str(request.GET.get('supplier_id', '')).strip()
    supplier = None
    if supplier_id.isnumeric() and int(supplier_id) > 0:
        supplier = Suppliers.objects.filter(id=int(supplier_id)).first()
    products = Products.objects.filter(status=1).select_related('category_id').order_by('name')
    products_json = json.dumps([
        {
            'id': product.id,
            'code': product.code or '',
            'name': product.name or '',
            'description': product.description or '',
            'price': float(product.price or 0),
            'category_id': product.category_id.id if product.category_id else None,
            'category_name': product.category_id.name if product.category_id else '',
        }
        for product in products
    ])
    context = {
        'supplier': supplier,
        'supplier_id': supplier_id,
        'categories': Categorys.objects.filter(status=1).order_by('name'),
        'products_json': mark_safe(products_json),
    }
    return render(request, 'conveniencia/manage_supplier_product_create.html', context)


@login_required
def save_supplier_product_create(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}
    try:
        supplier_id = str(data.get('supplier_id', '')).strip()
        product_id = str(data.get('product_id', '')).strip()
        product_search = str(data.get('product_search', '')).strip()
        category_id = str(data.get('category_id', '')).strip()
        name = str(data.get('name', '')).strip()
        description = str(data.get('description', '')).strip()
        sale_price = parse_brl_currency(data.get('sale_price', 0), 0)
        cost_price = parse_brl_currency(data.get('cost_price', 0), 0)

        if not supplier_id.isnumeric() or not Suppliers.objects.filter(id=int(supplier_id)).exists():
            raise ValueError('Fornecedor invalido.')

        product = None
        if product_id.isnumeric() and Products.objects.filter(id=int(product_id)).exists():
            product = Products.objects.get(id=int(product_id))
        else:
            lookup_value = product_search.strip()
            if lookup_value:
                product = Products.objects.filter(
                    Q(code__iexact=lookup_value) | Q(name__iexact=lookup_value)
                ).first()
                if not product:
                    partial_matches = Products.objects.filter(
                        Q(code__icontains=lookup_value) | Q(name__icontains=lookup_value)
                    )
                    if partial_matches.count() == 1:
                        product = partial_matches.first()

        if not product:
            if not category_id.isnumeric() or not Categorys.objects.filter(id=int(category_id)).exists():
                raise ValueError('Categoria invalida.')
            if not name:
                raise ValueError('Informe o nome do produto.')
            if not description:
                raise ValueError('Informe a descricao do produto.')
            if sale_price <= 0:
                raise ValueError('Informe um preco de venda valido.')

            product = Products(
                code=generate_internal_product_code(),
                category_id=Categorys.objects.get(id=int(category_id)),
                name=name,
                description=description,
                price=sale_price,
                overnight_price=0,
                quantity=0,
                infinite_stock=False,
                status=1,
            )
            product.save()
            messages.success(request, f'Produto "{name}" cadastrado com sucesso.')
        else:
            messages.success(request, f'Produto existente "{product.name}" reutilizado com sucesso.')

        # Salva preços específicos do fornecedor: custo e preco de venda (quando informado)
        if cost_price > 0 or sale_price > 0:
            defaults = {}
            if cost_price > 0:
                defaults['cost_price'] = cost_price
            if sale_price > 0:
                defaults['sale_price'] = sale_price
            # Mantém compatibilidade com campo legado 'price' preenchendo com cost_price quando disponível
            if cost_price > 0:
                defaults['price'] = cost_price
            SupplierProductPrices.objects.update_or_create(
                supplier_id=int(supplier_id),
                product_id=product.id,
                defaults=defaults,
            )
        resp['status'] = 'success'
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def receivables_dashboard(request):
    open_sales = Sales.objects.select_related('customer', 'user').filter(status=Sales.STATUS_OPEN).exclude(customer__isnull=True).order_by('-date_updated')
    if not request.user.is_superuser:
        open_sales = open_sales.filter(user=request.user)

    receivable_by_customer = {}
    receivable_rows = []
    total_receivable = Decimal('0')

    for sale in open_sales:
        balance_due = Decimal(str(sale.grand_total or 0)) - Decimal(str(sale.tendered or 0))
        if balance_due <= 0:
            continue
        total_receivable += balance_due
        customer_id = sale.customer_id
        if customer_id not in receivable_by_customer:
            receivable_by_customer[customer_id] = {
                'customer': sale.customer,
                'total_due': Decimal('0'),
                'comandas': 0,
                'last_update': sale.date_updated,
            }
        receivable_by_customer[customer_id]['total_due'] += balance_due
        receivable_by_customer[customer_id]['comandas'] += 1
        if sale.date_updated > receivable_by_customer[customer_id]['last_update']:
            receivable_by_customer[customer_id]['last_update'] = sale.date_updated

        receivable_rows.append({
            'sale_id': sale.id,
            'comanda_code': sale.comanda_code,
            'customer_name': sale.customer.name,
            'cashier': sale.user.username if sale.user else 'Sistema',
            'grand_total': sale.grand_total,
            'paid': sale.tendered,
            'balance_due': float(balance_due),
            'date_added': sale.date_added,
        })

    history_qs = Sales.objects.select_related('customer', 'user').filter(status=Sales.STATUS_CLOSED).exclude(customer__isnull=True).order_by('-date_updated')[:100]
    if not request.user.is_superuser:
        history_qs = history_qs.filter(user=request.user)

    context = {
        'page_title': 'Contas a Receber',
        'customer_summaries': list(receivable_by_customer.values()),
        'receivable_rows': receivable_rows,
        'total_receivable': total_receivable,
        'history_rows': history_qs,
    }
    return render(request, 'conveniencia/receivables.html', context)


@login_required
def cash_closing(request):
    ref_date = str(request.GET.get('date', '')).strip()
    if not ref_date:
        ref_date = timezone.localdate().strftime('%Y-%m-%d')

    try:
        target_date = datetime.strptime(ref_date, '%Y-%m-%d').date()
    except Exception:
        target_date = timezone.localdate()
        ref_date = target_date.strftime('%Y-%m-%d')

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())

    sales_qs = Sales.objects.filter(status=Sales.STATUS_CLOSED, date_added__gte=day_start, date_added__lte=day_end)
    if not request.user.is_superuser:
        sales_qs = sales_qs.filter(user=request.user)

    total_sales_count = sales_qs.count()
    total_closed_amount = sales_qs.aggregate(v=Sum('grand_total'))['v'] or 0
    total_received_amount = sales_qs.aggregate(v=Sum('tendered'))['v'] or 0
    avg_ticket = (total_closed_amount / total_sales_count) if total_sales_count else 0

    open_due_qs = Sales.objects.filter(status=Sales.STATUS_OPEN)
    if not request.user.is_superuser:
        open_due_qs = open_due_qs.filter(user=request.user)
    open_due_total = Decimal('0')
    for sale in open_due_qs:
        open_due_total += Decimal(str(sale.grand_total or 0)) - Decimal(str(sale.tendered or 0))

    payment_breakdown = {
        'DINHEIRO': 0,
        'PIX': 0,
        'CREDITO': 0,
        'DEBITO': 0,
        'OUTRO': 0,
    }
    for sale in sales_qs:
        methods = [m.strip().upper() for m in (sale.payment_methods or '').split(',') if m.strip()]
        for method in methods:
            if method in payment_breakdown:
                payment_breakdown[method] += 1

    context = {
        'page_title': 'Fechamento de Caixa',
        'ref_date': ref_date,
        'total_sales_count': total_sales_count,
        'total_closed_amount': total_closed_amount,
        'total_received_amount': total_received_amount,
        'avg_ticket': avg_ticket,
        'open_due_total': open_due_total,
        'payment_breakdown': payment_breakdown,
        'sales_rows': sales_qs.order_by('-date_added')[:200],
    }
    return render(request, 'conveniencia/cash_closing.html', context)


@login_required
def management_reports(request):
    data_inicio = str(request.GET.get('data_inicio', '')).strip()
    data_fim = str(request.GET.get('data_fim', '')).strip()

    sales_qs = Sales.objects.filter(status=Sales.STATUS_CLOSED)
    if not request.user.is_superuser:
        sales_qs = sales_qs.filter(user=request.user)

    if data_inicio:
        try:
            sales_qs = sales_qs.filter(date_added__gte=datetime.strptime(data_inicio, '%Y-%m-%d'))
        except Exception:
            data_inicio = ''
    if data_fim:
        try:
            fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            sales_qs = sales_qs.filter(date_added__lte=fim)
        except Exception:
            data_fim = ''

    top_products = Salesitems.objects.filter(sale_id__in=sales_qs).values('product_id__name').annotate(
        qty_sum=Sum('qty'),
        total_sum=Sum('total_price')
    ).order_by('-qty_sum')[:10]

    peak_hours = sales_qs.annotate(hour_bucket=TruncHour('date_added')).values('hour_bucket').annotate(
        sales_count=Count('id'),
        total_sum=Sum('grand_total')
    ).order_by('-sales_count')[:10]

    top_customers = sales_qs.exclude(customer__isnull=True).values('customer__name').annotate(
        total_spent=Sum('grand_total'),
        sales_count=Count('id')
    ).order_by('-total_spent')[:10]

    low_stock_products = Products.objects.filter(status=1, infinite_stock=False, quantity__lte=5).order_by('quantity', 'name')[:20]

    context = {
        'page_title': 'Relatórios Gerenciais',
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'top_products': top_products,
        'peak_hours': peak_hours,
        'top_customers': top_customers,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'conveniencia/management_reports.html', context)


@login_required
def reminders_accounts(request):
    today = timezone.localdate()
    PayableAccounts.objects.filter(status=PayableAccounts.STATUS_OPEN, due_date__lt=today).update(status=PayableAccounts.STATUS_OVERDUE)

    payables = PayableAccounts.objects.select_related('supplier').all().order_by('due_date', '-id')
    reminders = FinanceReminders.objects.select_related('customer').all().order_by('status', 'due_date', '-id')

    context = {
        'page_title': 'Anotações e Lembretes',
        'payables': payables,
        'reminders': reminders,
        'suppliers': Suppliers.objects.filter(active=True).order_by('name'),
        'customers': Customers.objects.filter(active=True).order_by('name'),
    }
    return render(request, 'conveniencia/reminders_accounts.html', context)


@login_required
def manage_payable_account(request):
    payable = {}
    payable_id = str(request.GET.get('id', '')).strip()
    if payable_id.isnumeric() and int(payable_id) > 0:
        payable = PayableAccounts.objects.filter(id=int(payable_id)).first()

    context = {
        'payable': payable,
        'suppliers': Suppliers.objects.filter(active=True).order_by('name'),
    }
    return render(request, 'conveniencia/manage_payable_account.html', context)


@login_required
def save_payable_account(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}
    try:
        payable_id = str(data.get('id', '')).strip()
        description = str(data.get('description', '')).strip()
        supplier_id = str(data.get('supplier_id', '')).strip()
        amount = parse_brl_currency(data.get('amount', 0), 0)
        due_date = str(data.get('due_date', '')).strip()
        status = str(data.get('status', PayableAccounts.STATUS_OPEN)).strip().upper()
        notes = str(data.get('notes', '')).strip()

        if not description:
            raise ValueError('Informe a descricao da conta.')
        if amount <= 0:
            raise ValueError('Informe um valor valido.')
        if not due_date:
            raise ValueError('Informe a data de vencimento.')
        if status not in {PayableAccounts.STATUS_OPEN, PayableAccounts.STATUS_PAID, PayableAccounts.STATUS_OVERDUE}:
            status = PayableAccounts.STATUS_OPEN

        supplier_fk = int(supplier_id) if supplier_id.isnumeric() else None

        if payable_id.isnumeric() and int(payable_id) > 0:
            payable = PayableAccounts.objects.filter(id=int(payable_id)).first()
            if not payable:
                raise ValueError('Conta nao encontrada.')
            payable.description = description
            payable.supplier_id = supplier_fk
            payable.amount = amount
            payable.due_date = due_date
            payable.status = status
            payable.notes = notes
            payable.save()
            messages.success(request, 'Conta a pagar atualizada com sucesso.')
        else:
            PayableAccounts.objects.create(
                description=description,
                supplier_id=supplier_fk,
                amount=amount,
                due_date=due_date,
                status=status,
                notes=notes,
            )
            messages.success(request, 'Conta a pagar cadastrada com sucesso.')

        resp['status'] = 'success'
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def delete_payable_account(request):
    resp = {'status': 'failed'}
    try:
        payable = PayableAccounts.objects.filter(id=request.POST.get('id')).first()
        if not payable:
            raise ValueError('Conta nao encontrada.')
        payable.delete()
        resp['status'] = 'success'
        messages.success(request, 'Conta a pagar removida com sucesso.')
    except Exception:
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def manage_finance_reminder(request):
    reminder = {}
    reminder_id = str(request.GET.get('id', '')).strip()
    if reminder_id.isnumeric() and int(reminder_id) > 0:
        reminder = FinanceReminders.objects.filter(id=int(reminder_id)).first()

    context = {
        'reminder': reminder,
        'customers': Customers.objects.filter(active=True).order_by('name'),
    }
    return render(request, 'conveniencia/manage_finance_reminder.html', context)


@login_required
def save_finance_reminder(request):
    data = request.POST
    resp = {'status': 'failed', 'msg': ''}
    try:
        reminder_id = str(data.get('id', '')).strip()
        title = str(data.get('title', '')).strip()
        reminder_type = str(data.get('reminder_type', FinanceReminders.TYPE_GENERAL)).strip().upper()
        due_date = str(data.get('due_date', '')).strip() or None
        amount = parse_brl_currency(data.get('amount', 0), 0)
        customer_id = str(data.get('customer_id', '')).strip()
        notes = str(data.get('notes', '')).strip()
        status = str(data.get('status', FinanceReminders.STATUS_PENDING)).strip().upper()

        if not title:
            raise ValueError('Informe o titulo do lembrete.')
        if reminder_type not in {FinanceReminders.TYPE_RECEIVABLE, FinanceReminders.TYPE_PAYABLE, FinanceReminders.TYPE_GENERAL}:
            reminder_type = FinanceReminders.TYPE_GENERAL
        if status not in {FinanceReminders.STATUS_PENDING, FinanceReminders.STATUS_DONE}:
            status = FinanceReminders.STATUS_PENDING

        customer_fk = int(customer_id) if customer_id.isnumeric() else None

        if reminder_id.isnumeric() and int(reminder_id) > 0:
            reminder = FinanceReminders.objects.filter(id=int(reminder_id)).first()
            if not reminder:
                raise ValueError('Lembrete nao encontrado.')
            reminder.title = title
            reminder.reminder_type = reminder_type
            reminder.due_date = due_date
            reminder.amount = amount
            reminder.customer_id = customer_fk
            reminder.notes = notes
            reminder.status = status
            reminder.save()
            messages.success(request, 'Lembrete atualizado com sucesso.')
        else:
            FinanceReminders.objects.create(
                title=title,
                reminder_type=reminder_type,
                due_date=due_date,
                amount=amount,
                customer_id=customer_fk,
                notes=notes,
                status=status,
            )
            messages.success(request, 'Lembrete cadastrado com sucesso.')

        resp['status'] = 'success'
    except Exception as e:
        resp['msg'] = str(e)
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def delete_finance_reminder(request):
    resp = {'status': 'failed'}
    try:
        reminder = FinanceReminders.objects.filter(id=request.POST.get('id')).first()
        if not reminder:
            raise ValueError('Lembrete nao encontrado.')
        reminder.delete()
        resp['status'] = 'success'
        messages.success(request, 'Lembrete removido com sucesso.')
    except Exception:
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type='application/json')


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
    product_without_barcode = str(data.get('product_without_barcode', '')).strip().lower() in {'1', 'true', 'on', 'yes'}
    raw_code = data.get('code', '').strip()
    if product_without_barcode:
        if id.isnumeric() and int(id) > 0:
            existing_product = Products.objects.filter(id=id).first()
            if existing_product and str(existing_product.code or '').startswith('29'):
                raw_code = existing_product.code
            else:
                raw_code = generate_internal_product_code()
        else:
            raw_code = generate_internal_product_code()
    code_exists = False
    if raw_code:
        if id.isnumeric() and int(id)>0:
            code_exists = Products.objects.exclude(id=id).filter(code=raw_code).exists()
        else:
            code_exists = Products.objects.filter(code=raw_code).exists()
    if code_exists:
        resp['msg']='Código do produto já existe no banco de dados.'
    else:
        category = Categorys.objects.filter(id=data['category_id']).first()
        try:
            quantity = 0
            overnight_price = 0
            base_price = 0
            infinite_stock = str(data.get('infinite_stock', '')).strip().lower() in {'1', 'true', 'on', 'yes'}
            try:
                quantity = int(data.get('quantity', 0))
            except (ValueError, TypeError):
                quantity = 0
            if infinite_stock:
                quantity = 0
            base_price = parse_brl_currency(data.get('price', 0), 0)
            overnight_price = parse_brl_currency(data.get('overnight_price', 0), 0)
            if (data['id'].isnumeric() and int(data['id'])>0):
                save_product = Products.objects.filter(id=data['id']).first()
                if save_product:
                    save_product.code = raw_code
                    save_product.category_id = category
                    save_product.name = data['name']
                    save_product.description = data['description']
                    save_product.price = base_price
                    save_product.overnight_price = overnight_price
                    save_product.quantity = quantity
                    save_product.infinite_stock = infinite_stock
                    save_product.status = data['status']
                    save_product.save()
            else:
                save_product = Products(code=raw_code, category_id=category, name=data['name'], description=data['description'], price=base_price, overnight_price=overnight_price, quantity=quantity, infinite_stock=infinite_stock, status=data['status'])
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
    customers_json = []
    open_comandas = []
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
            'infinite_stock': bool(product.infinite_stock),
        })
    for customer in Customers.objects.filter(active=True).order_by('name'):
        customers_json.append({
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
        })
    open_sales = Sales.objects.filter(status=Sales.STATUS_OPEN)
    if not request.user.is_superuser:
        open_sales = open_sales.filter(user=request.user)
    open_sales = open_sales.prefetch_related('salesitems_set__product_id').order_by('-date_updated', '-id')
    for sale in open_sales:
        sale_items = []
        for item in sale.salesitems_set.all():
            sale_items.append({
                'product_id': item.product_id_id,
                'qty': int(item.qty),
                'price': float(item.price),
            })
        open_comandas.append({
            'id': sale.id,
            'code': sale.code,
            'comanda_code': sale.comanda_code,
            'customer_id': sale.customer.id if sale.customer else None,
            'customer_name': sale.customer.name if sale.customer else '',
            'customer_phone': sale.customer.phone if sale.customer else '',
            'sub_total': float(sale.sub_total),
            'grand_total': float(sale.grand_total),
            'tendered': float(sale.tendered),
            'balance_due': max(float(sale.grand_total) - float(sale.tendered), 0),
            'item_count': len(sale_items),
            'items': sale_items,
        })
    context = {
        'page_title': 'Ponto de Venda',
        'products': products,
        'product_json': mark_safe(json.dumps(products_json)),
        'customers_json': mark_safe(json.dumps(customers_json)),
        'open_comandas_json': mark_safe(json.dumps(open_comandas)),
        'overnight_mode': overnight_mode,
    }
    return render(request, 'conveniencia/pos.html', context)

@login_required
def get_open_comandas_json(request):
    """Retorna JSON das comandas abertas para recarregamento no POS"""
    open_comandas = []
    open_sales = Sales.objects.filter(status=Sales.STATUS_OPEN)
    if not request.user.is_superuser:
        open_sales = open_sales.filter(user=request.user)
    open_sales = open_sales.prefetch_related('salesitems_set__product_id').order_by('-date_updated', '-id')
    
    for sale in open_sales:
        sale_items = []
        for item in sale.salesitems_set.all():
            sale_items.append({
                'product_id': item.product_id_id,
                'qty': int(item.qty),
                'price': float(item.price),
            })
        open_comandas.append({
            'id': sale.id,
            'code': sale.code,
            'comanda_code': sale.comanda_code,
            'customer_id': sale.customer.id if sale.customer else None,
            'customer_name': sale.customer.name if sale.customer else '',
            'customer_phone': sale.customer.phone if sale.customer else '',
            'sub_total': float(sale.sub_total),
            'grand_total': float(sale.grand_total),
            'tendered': float(sale.tendered),
            'balance_due': max(float(sale.grand_total) - float(sale.tendered), 0),
            'item_count': len(sale_items),
            'items': sale_items,
        })
    
    return HttpResponse(json.dumps({'status': 'success', 'data': open_comandas}), content_type='application/json')

@login_required
def checkout_modal(request):
    grand_total = parse_decimal_value(request.GET.get('grand_total', 0), Decimal('0'))
    comanda_code = ''
    sale_id = ''
    customer_name = ''
    remaining_due = None
    if 'comanda_code' in request.GET:
        comanda_code = str(request.GET.get('comanda_code', '')).strip()
    if 'sale_id' in request.GET:
        sale_id = str(request.GET.get('sale_id', '')).strip()
        if sale_id.isnumeric():
            sale = Sales.objects.select_related('customer').filter(id=int(sale_id)).first()
            if sale and sale.status == Sales.STATUS_OPEN:
                customer_name = sale.customer.name if sale.customer else ''
                remaining_due = max(float(grand_total) - float(sale.tendered), 0)
                grand_total = remaining_due
    context = {
        'grand_total' : grand_total,
        'comanda_code': comanda_code,
        'sale_id': sale_id,
        'customer_name': customer_name,
        'remaining_due': remaining_due,
    }
    return render(request, 'conveniencia/checkout.html',context)

@login_required
def save_pos(request):
    resp = {'status':'failed','msg':''}
    data = request.POST
    sale_action = str(data.get('sale_action', 'checkout')).strip().lower()
    comanda_code = str(data.get('comanda_code', '')).strip().upper()
    customer_id_value = str(data.get('customer_id', '')).strip()
    customer_name = normalize_customer_name(data.get('customer_name', ''))
    print(f"[SAVE_POS] action={sale_action} comanda={comanda_code} customer_id={customer_id_value} customer_name={customer_name}")
    # Log incoming POS save attempts for debugging customer association
    try:
        _preview = {k: data.get(k) for k in ['sale_action', 'sale_id', 'comanda_code', 'customer_id', 'customer_name', 'customer_phone']}
        logger.info('save_pos called by %s payload_preview=%s', request.user.username if request.user else None, _preview)
    except Exception:
        logger.exception('Failed to log save_pos payload preview')
    try:
        full_payload = {}
        for k in data.keys():
            full_payload[k] = data.getlist(k)
        logger.info('save_pos full_payload=%s', json.dumps(full_payload, default=str, ensure_ascii=False))
    except Exception:
        logger.exception('Failed to log full save_pos payload')
    if sale_action not in {'checkout', 'open_comanda'}:
        sale_action = 'checkout'
    sale_id_value = str(data.get('sale_id', '')).strip()
    customer_phone = str(data.get('customer_phone', '')).strip()
    pref = datetime.now().year + datetime.now().year
    i = 1
    existing_sale = None

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
        computed_sub_total = Decimal('0')

        if not product_ids:
            raise ValueError('Adicione pelo menos um item antes de finalizar a venda.')

        if sale_id_value:
            if not sale_id_value.isnumeric():
                raise ValueError('Identificador da comanda invalido.')
            existing_sale = Sales.objects.filter(id=int(sale_id_value)).first()
            if not existing_sale:
                raise ValueError('Comanda nao encontrada.')
            if not request.user.is_superuser and existing_sale.user_id != request.user.id:
                raise ValueError('Voce nao tem permissao para editar esta comanda.')
            if existing_sale.status != Sales.STATUS_OPEN:
                raise ValueError('A comanda selecionada nao esta mais aberta.')
            code = existing_sale.code
            if not comanda_code:
                comanda_code = existing_sale.comanda_code

        # Se não foi enviado sale_id mas foi informado comanda_code, tentar recuperar a comanda aberta correspondente
        # Isso protege contra casos em que o frontend perdeu o campo sale_id e evita criar vendas duplicadas.
        if not sale_id_value and comanda_code:
            possible = None
            try:
                possible_qs = Sales.objects.filter(comanda_code=str(comanda_code)).filter(status=Sales.STATUS_OPEN)
                if not request.user.is_superuser:
                    possible_qs = possible_qs.filter(user=request.user)
                possible = possible_qs.order_by('-date_added').first()
            except Exception:
                possible = None
            if possible:
                existing_sale = possible
                code = existing_sale.code

        customer = None
        if customer_id_value:
            if not customer_id_value.isnumeric():
                raise ValueError('ID do cliente invalido.')
            customer = Customers.objects.filter(id=int(customer_id_value)).first()
            if not customer:
                raise ValueError('Cliente nao encontrado. Verifique se o cliente foi selecionado corretamente.')
            print(f"[SAVE_POS] Customer found by ID: {customer.id} - {customer.name}")
        if not customer and customer_name:
            print(f"[SAVE_POS] Resolving customer by name: '{customer_name}'")
            customer = resolve_customer_from_payload(customer_name, customer_phone)
            if customer:
                print(f"[SAVE_POS] Customer resolved: {customer.id} - {customer.name}")
        if not customer and existing_sale:
            customer = existing_sale.customer

        print(f"[SAVE_POS] Final customer check: sale_action={sale_action} customer={customer} (id={customer.id if customer else None})")

        try:
            logger.info('Resolved customer for save_pos customer_id=%s customer_name=%s customer_phone=%s resolved_customer_id=%s',
                        customer_id_value, customer_name, customer_phone, getattr(customer, 'id', None))
        except Exception:
            logger.exception('Failed to log resolved customer in save_pos')

        if sale_action == 'open_comanda':
            if not comanda_code:
                comanda_code = generate_comanda_code(customer)
            if len(comanda_code) > 80:
                raise ValueError('O campo da comanda deve ter no máximo 80 caracteres.')
            # Não bloqueia mais comandas abertas com mesmo nome/número

        raw_payment_methods = data.get('payment_methods', '')
        requested_payment_methods = [m.strip().lower() for m in str(raw_payment_methods).split(',') if m.strip()]
        payment_other_detail = str(data.get('payment_other_detail', '')).strip()
        payment_methods_value = ''
        tendered_amount = parse_decimal_value(data.get('tendered_amount', 0), Decimal('0'))
        amount_change = Decimal('0')
        discount_type = str(data.get('discount_type', Sales.DISCOUNT_TYPE_VALUE)).strip().upper()
        if discount_type not in {Sales.DISCOUNT_TYPE_VALUE, Sales.DISCOUNT_TYPE_PERCENT}:
            discount_type = Sales.DISCOUNT_TYPE_VALUE
        discount_value = parse_decimal_value(data.get('discount_value', 0), Decimal('0'))
        discount_amount = Decimal('0')

        if not requested_payment_methods and sale_action == 'checkout':
            requested_payment_methods = ['dinheiro']

        main_payment_methods = {'credito', 'debito', 'pix', 'dinheiro'}
        allowed_payment_methods = main_payment_methods.union({'outro'})
        invalid_methods = [m for m in requested_payment_methods if m not in allowed_payment_methods]
        if invalid_methods:
            raise ValueError('Forma de pagamento invalida informada.')

        if 'outro' not in requested_payment_methods:
            payment_other_detail = ''
        if len(payment_other_detail) > 120:
            raise ValueError('O campo Outro deve ter no maximo 120 caracteres.')

        payment_methods_value = ','.join(method.upper() for method in requested_payment_methods)

        with transaction.atomic():
            if existing_sale:
                existing_sale = Sales.objects.select_for_update().filter(id=existing_sale.id).first()
                if not existing_sale or existing_sale.status != Sales.STATUS_OPEN:
                    raise ValueError('A comanda selecionada nao esta mais aberta.')
                if not request.user.is_superuser and existing_sale.user_id != request.user.id:
                    raise ValueError('Voce nao tem permissao para editar esta comanda.')
                previous_tendered = Decimal(str(existing_sale.tendered))
                # Build map of previously reserved quantities for this sale to allow idempotent adjustments
                prev_items_q = {}
                prev_items_list = list(existing_sale.salesitems_set.all())
                for pi in prev_items_list:
                    pid = int(getattr(pi.product_id, 'id', getattr(pi, 'product_id_id', None) or 0))
                    prev_items_q[pid] = prev_items_q.get(pid, 0) + int(getattr(pi, 'qty', 0))
                try:
                    logger.info('save_pos prev_items_q=%s for existing_sale_id=%s', prev_items_q, existing_sale.id)
                except Exception:
                    pass
            else:
                previous_tendered = Decimal('0')
                prev_items_q = {}

            # Validate requested items against available stock considering previous reservations
            for index, product_id in enumerate(product_ids):
                product = Products.objects.select_for_update().filter(id=product_id, status=1).first()
                if not product:
                    raise ValueError('Um dos produtos informados nao esta mais disponivel para venda.')

                try:
                    qty_raw = str(quantities[index]).strip()
                    qty_decimal = Decimal(qty_raw)
                except (TypeError, ValueError, IndexError):
                    raise ValueError('Foi encontrado um item com quantidade ou preco invalido.')
                except InvalidOperation:
                    raise ValueError('Foi encontrado um item com quantidade ou preco invalido.')

                try:
                    submitted_price = Decimal(str(prices[index]))
                except (TypeError, ValueError, IndexError, InvalidOperation):
                    raise ValueError('Foi encontrado um item com quantidade ou preco invalido.')

                if qty_decimal <= 0:
                    raise ValueError(f'Quantidade invalida para o produto {product.name}.')

                if qty_decimal != qty_decimal.to_integral_value():
                    raise ValueError(f'O produto {product.name} nao permite quantidade fracionada.')

                qty_int = int(qty_decimal)
                # available stock = current product.quantity + previously reserved qty in this sale
                prev_reserved = prev_items_q.get(int(product.id), 0)
                if not product.infinite_stock:
                    available_qty = int(product.quantity) + int(prev_reserved)
                    if available_qty < qty_int:
                        raise ValueError(f'Estoque insuficiente para o produto {product.name}. Disponivel: {available_qty}.')

                active_price = Decimal(str(get_product_active_price(product)))
                if submitted_price <= 0:
                    raise ValueError(f'Preco invalido para o produto {product.name}.')

                price = float(submitted_price)
                total = Decimal(str(price)) * Decimal(qty_int)
                computed_sub_total += total
                sale_items_payload.append({
                    'product': product,
                    'qty': qty_int,
                    'price': price,
                    'total': float(total),
                })

            if sale_action == 'checkout':
                if discount_type == Sales.DISCOUNT_TYPE_PERCENT:
                    if discount_value > 100:
                        raise ValueError('O desconto percentual nao pode ser maior que 100%.')
                    discount_amount = (computed_sub_total * discount_value) / Decimal('100')
                else:
                    if discount_value > computed_sub_total:
                        raise ValueError('O desconto nao pode ser maior que o subtotal.')
                    discount_amount = discount_value
                grand_total = computed_sub_total - discount_amount
                amount_change = (previous_tendered + tendered_amount) - grand_total
                if amount_change < 0:
                    sale_action = 'open_comanda'
                    if not comanda_code:
                        comanda_code = generate_comanda_code(customer)
                elif not any(m in main_payment_methods for m in requested_payment_methods):
                    raise ValueError('Selecione pelo menos uma forma de pagamento principal (Credito, Debito, Pix ou Dinheiro).')
            else:
                grand_total = computed_sub_total
                amount_change = (previous_tendered + tendered_amount) - grand_total

            if existing_sale:
                sale = existing_sale
                sale.sub_total = float(computed_sub_total)
                sale.grand_total = float(grand_total)
                sale.discount_type = discount_type
                sale.discount_value = float(discount_value)
                sale.discount_amount = float(discount_amount)
                sale.tendered = float(previous_tendered + tendered_amount)
                sale.amount_change = float(amount_change)
                sale.payment_methods = payment_methods_value
                sale.payment_other_detail = payment_other_detail
                sale.comanda_code = comanda_code
                sale.customer = customer
                sale.status = Sales.STATUS_OPEN if sale_action == 'open_comanda' else Sales.STATUS_CLOSED
                sale.save()
                try:
                    logger.info('sale updated id=%s customer_id=%s customer_name=%s user=%s status=%s',
                                sale.pk,
                                getattr(sale.customer, 'id', None),
                                getattr(sale.customer, 'name', None),
                                sale.user.username if sale.user else None,
                                sale.status)
                except Exception:
                    logger.exception('Failed to log sale after update')

                # Ajuste de estoque por delta entre nova solicitação e itens previamente reservados
                # Construir mapa de novas quantidades por produto
                new_items_q = {}
                for it in sale_items_payload:
                    pid = int(getattr(it['product'], 'id', getattr(it['product'], 'pk', 0)))
                    new_items_q[pid] = new_items_q.get(pid, 0) + int(it['qty'])
                try:
                    logger.info('save_pos new_items_q=%s for sale_payload_count=%s', new_items_q, len(sale_items_payload))
                except Exception:
                    pass

                # Aplicar deltas (novo - anterior) sobre o estoque atual com locks
                all_pids = set(list(prev_items_q.keys()) + list(new_items_q.keys()))
                for pid in all_pids:
                    prev_q = int(prev_items_q.get(pid, 0))
                    new_q = int(new_items_q.get(pid, 0))
                    delta = new_q - prev_q
                    try:
                        logger.info('save_pos computing delta for pid=%s prev_q=%s new_q=%s delta=%s', pid, prev_q, new_q, delta)
                    except Exception:
                        pass
                    if delta == 0:
                        continue
                    prod = Products.objects.select_for_update().filter(id=pid).first()
                    if not prod:
                        # Produto removido do cadastro entre a validacao e o commit
                        raise ValueError('Produto referenciado nao existe mais: id=' + str(pid))
                    if not prod.infinite_stock:
                        before_qty = int(prod.quantity)
                        # delta > 0 reduz estoque, delta < 0 aumenta estoque
                        prod.quantity = int(prod.quantity) - int(delta)
                        if prod.quantity < 0:
                            prod.quantity = 0
                        prod.save(update_fields=['quantity', 'date_updated'])
                        try:
                            logger.info('save_pos adjusted product id=%s before=%s after=%s applied_delta=%s', pid, before_qty, prod.quantity, delta)
                        except Exception:
                            pass

                # Remover items antigos e gravar os novos
                sale.salesitems_set.all().delete()
            else:
                sale = Sales(
                    user=request.user,
                    customer=customer,
                    code=code,
                    status=Sales.STATUS_OPEN if sale_action == 'open_comanda' else Sales.STATUS_CLOSED,
                    comanda_code=comanda_code,
                    sub_total=float(computed_sub_total),
                    grand_total=float(grand_total),
                    discount_type=discount_type,
                    discount_value=float(discount_value),
                    discount_amount=float(discount_amount),
                    tendered=float(tendered_amount),
                    amount_change=float(amount_change),
                    payment_methods=payment_methods_value,
                    payment_other_detail=payment_other_detail,
                )
                sale.save()
                try:
                    logger.info('sale created id=%s customer_id=%s customer_name=%s user=%s status=%s',
                                sale.pk,
                                getattr(sale.customer, 'id', None),
                                getattr(sale.customer, 'name', None),
                                sale.user.username if sale.user else None,
                                sale.status)
                except Exception:
                    logger.exception('Failed to log sale after create')
            sale_id = sale.pk

            # Create new sale items and decrement stock accordingly (only for new sale)
            try:
                logger.info('save_pos creating sale items loop for sale_id=%s existing_sale=%s items=%s', sale.id, bool(existing_sale), len(sale_items_payload))
            except Exception:
                pass
            for item in sale_items_payload:
                si = Salesitems(
                    sale_id=sale,
                    product_id=item['product'],
                    qty=item['qty'],
                    price=item['price'],
                    total_price=item['total']
                )
                si.save()
                try:
                    logger.info('save_pos created Salesitems id=%s sale_id=%s product_id=%s qty=%s', si.id, sale.id, getattr(item['product'], 'id', getattr(item['product'], 'pk', None)), item['qty'])
                except Exception:
                    pass

                if not item['product'].infinite_stock:
                    # Se estamos atualizando uma comanda existente, o ajuste de estoque
                    # já foi feito pela lógica de delta acima; evitar decrementar novamente.
                    if not existing_sale:
                        # decrement stock by the requested quantity for new sale
                        item['product'].quantity = int(item['product'].quantity) - int(item['qty'])
                        if item['product'].quantity < 0:
                            item['product'].quantity = 0
                        item['product'].save(update_fields=['quantity', 'date_updated'])
                    else:
                        try:
                            logger.info('save_pos skipped per-item decrement because update already applied deltas for sale_id=%s product_id=%s', sale.id, getattr(item['product'], 'id', getattr(item['product'], 'pk', None)))
                        except Exception:
                            pass

        # Log final mapping of sale -> customer before responding
        try:
            logger.info('save_pos response preparing sale_id=%s sale_action=%s final_customer_id=%s final_customer_name=%s',
                        sale_id, sale_action, getattr(sale.customer, 'id', None), getattr(sale.customer, 'name', None))
        except Exception:
            logger.exception('Failed to log final save_pos response details')

        resp['status'] = 'success'
        resp['sale_id'] = sale_id
        resp['sale_action'] = sale_action
        resp['debug'] = {
            'sale_id': sale_id,
            'customer_id': sale.customer.id if sale.customer else None,
            'customer_name': sale.customer.name if sale.customer else None,
            'comanda_code': sale.comanda_code,
            'sale_status': sale.status,
            'items_count': sale.salesitems_set.count()
        }
        if sale_action == 'open_comanda':
            resp['msg'] = f'Comanda {comanda_code} salva em aberto com sucesso.'
            messages.success(request, resp['msg'])
        else:
            messages.success(request, "Registro de venda salvo com sucesso.")
    except Exception as e:
        print(f"[SAVE_POS_ERROR] {str(e)}")
        logger.exception('save_pos exception: %s', str(e))
        resp['msg'] = str(e)
        resp['status'] = 'failed'
    return HttpResponse(json.dumps(resp), content_type="application/json")

@login_required
def salesList(request):
    data_inicio = (request.GET.get('data_inicio') or '').strip()
    data_fim = (request.GET.get('data_fim') or '').strip()
    open_comandas = (request.GET.get('open_comandas') or '').strip() in {'1', 'true', 'on', 'yes'}
    customer_id = (request.GET.get('customer_id') or '').strip()

    # Base queryset: normally restrict to the current user's sales, but if filtering by customer_id
    # we want to show all sales for that customer regardless of which user created them.
    sales_queryset = Sales.objects.all() if request.user.is_superuser else Sales.objects.filter(user=request.user)

    if data_inicio:
        try:
            data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
            sales_queryset = sales_queryset.filter(date_added__gte=data_inicio_dt)
        except Exception:
            data_inicio = ''

    if data_fim:
        try:
            data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            sales_queryset = sales_queryset.filter(date_added__lte=data_fim_dt)
        except Exception:
            data_fim = ''

    if customer_id.isnumeric():
        # When a customer filter is requested, show all sales for that customer (not limited to current user)
        sales_queryset = Sales.objects.filter(customer_id=int(customer_id))
        customer_filter = Customers.objects.filter(id=int(customer_id)).first()
    else:
        customer_filter = None

    if open_comandas:
        sales_queryset = sales_queryset.filter(status=Sales.STATUS_OPEN).exclude(comanda_code__isnull=True).exclude(comanda_code='')

    sales_queryset = sales_queryset.order_by('-date_added')

    sale_data = []
    total_value = Decimal('0')
    total_open_comandas = 0
    for sale in sales_queryset:
        data = {}
        for field in sale._meta.get_fields(include_parents=False):
            if field.related_model is None:
                data[field.name] = getattr(sale,field.name)
        data['items'] = Salesitems.objects.filter(sale_id = sale).all()
        data['item_count'] = len(data['items'])
        data['cashier'] = sale.user.username if sale.user else 'Sistema'
        data['payment_methods_display'] = sale.get_payment_methods_display() or '-'
        data['payment_other_detail'] = sale.payment_other_detail
        data['status_display'] = sale.get_status_display()
        sale_data.append(data)
        total_value += Decimal(str(sale.grand_total or 0))
        if sale.status == Sales.STATUS_OPEN and sale.comanda_code:
            total_open_comandas += 1
    context = {
        'page_title':'Transações de Vendas',
        'sale_data':sale_data,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'open_comandas': open_comandas,
        'customer_id': customer_id,
        'customer_filter': customer_filter,
        'total_filtrado': len(sale_data),
        'valor_total_filtrado': total_value,
        'total_open_comandas_count': total_open_comandas,
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
    payment_methods_display = sales_obj.get_payment_methods_display() or '-'
    context = {
        "transaction" : transaction,
        "salesItems" : ItemList,
        "payment_methods_display": payment_methods_display,
        "payment_other_detail": sales_obj.payment_other_detail,
        "status_display": sales_obj.get_status_display(),
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
    
    # Get filters
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    open_comandas = (request.GET.get('open_comandas') or '').strip() in {'1', 'true', 'on', 'yes'}
    customer_id = (request.GET.get('customer_id') or '').strip()
    customer_filter = None
    
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

    if customer_id.isnumeric():
        customer_filter = Customers.objects.filter(id=int(customer_id)).first()
        if customer_filter:
            sales_queryset = sales_queryset.filter(customer_id=int(customer_id))

    if open_comandas:
        sales_queryset = sales_queryset.filter(status=Sales.STATUS_OPEN).exclude(comanda_code__isnull=True).exclude(comanda_code='')
    
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
    
    if customer_filter:
        elements.append(Paragraph(f'<b>Cliente: {customer_filter.name}</b>', styles['Normal']))
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
    
    sales_data = [['Data/Hora', 'Código', 'Pagamento', 'Produto', 'Qtd', 'Subtotal']]
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
            payment_label = sale.get_payment_methods_display() or '-'
            if sale.payment_other_detail:
                payment_label = f"{payment_label} ({sale.payment_other_detail})"
            for item in sale_items:
                item_subtotal = item.total_price if hasattr(item, 'total_price') else float(item.qty) * float(item.price)
                daily_total += item_subtotal
                sales_data.append([
                    sale.date_added.strftime('%d/%m/%Y %H:%M'),
                    sale.code,
                    payment_label,
                    item.product_id.name if item.product_id else '-',
                    str(item.qty),
                    format_brl(item_subtotal)
                ])
        else:
            line_subtotal = float(sale.sub_total)
            daily_total += line_subtotal
            payment_label = sale.get_payment_methods_display() or '-'
            if sale.payment_other_detail:
                payment_label = f"{payment_label} ({sale.payment_other_detail})"
            sales_data.append([
                sale.date_added.strftime('%d/%m/%Y %H:%M'),
                sale.code,
                payment_label,
                '-',
                '0',
                format_brl(line_subtotal)
            ])
    
    if current_date is not None:
        append_daily_total(daily_total)
    if len(sales_data) > 1:
        sales_data.append(['', '', '', '', 'TOTAL', format_brl(total_valor)])
        sales_table = Table(sales_data, colWidths=[1.1*inch, 0.9*inch, 1.7*inch, 2.0*inch, 0.55*inch, 1.05*inch], repeatRows=1)
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
            ('ALIGN', (2, 1), (3, -2), 'LEFT'),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
            ('SPAN', (0, -1), (4, -1)),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
            ('ALIGN', (0, -1), (4, -1), 'RIGHT'),
        ])
        for row_idx in date_row_indices:
            table_style.add('SPAN', (0, row_idx), (-1, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#d9edf7'))
            table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
            table_style.add('ALIGN', (0, row_idx), (-1, row_idx), 'LEFT')
            table_style.add('FONTSIZE', (0, row_idx), (-1, row_idx), 9)
        for row_idx in daily_total_row_indices:
            table_style.add('SPAN', (0, row_idx), (4, row_idx))
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f7f7f7'))
            table_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
            table_style.add('FONTSIZE', (0, row_idx), (-1, row_idx), 10)
            table_style.add('ALIGN', (0, row_idx), (4, row_idx), 'RIGHT')
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
