from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.urls import reverse
from django_redis import get_redis_connection
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re

# Create your views here.
from django.views.generic import View

from apps.goods.models import GoodsSKU
from apps.user.models import User,Address
from celery_tasks.tasks import send_register_active_email

# /user/register
from utils.mixin import LoginRequiredMixin


def register(request):
    if request.method == 'GET':
        '''显示注册页面'''
        return render(request, 'register.html')
    else:
        '''注册处理'''
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 接收数据的校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 检验用户名是否已存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理：注册处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # 返回应答
        return redirect(reversed('goods:index'))

# /user/register 类试图方式
class RegisterView(View):
    def get(self,request):
        '''显示注册页面'''
        return render(request, 'register.html')

    def post(self,request):
        '''注册处理'''
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 接收数据的校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 检验用户名是否已存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理：注册处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8080/user/active/3
        # 激活链接中需要包含用户的身份信息，并且要把身份信息加密

        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY,3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info).decode()

        # 发邮件
        send_register_active_email.delay(email,username,token)

        # 返回应答
        return redirect(reverse('goods:index'))

class ActiveView(View):
    '''用户激活'''
    def get(self,request,token):
        # 解密获取的要激活的用户id
        serializer = Serializer(settings.SECRET_KEY,3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']

            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期(1h)
            return HttpResponse('激活链接已过期')

# /user/login
class LoginView(View):
    def get(self,request):
        '''显示登录页面'''
        # 判断是否记住用户
        if 'username' in request.COOKIES:
            username =  request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html',{'username':username,'checked':checked})

    def post(self,request):
        '''登录处理'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 接收数据的校验
        if not all([username, password]):
            # 数据不完整
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 进行业务处理：登录处理
        user = authenticate(username=username,password=password)
        if user is not None:
            # 用户名正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request,user)

                # 获取登录后所要跳转到的地址
                # 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))

                # 跳转到next_url
                response =  redirect(next_url)

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')

                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                # 返回应答
                return response
            else:
                # 用户未激活
                return render(request,'login.html',{'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request,'login.html',{'errmsg':'用户名或密码错误'})

# /user/logout
class LogoutView(View):
    def get(self,request):
        logout(request)
        # 跳转到首页
        return redirect(reverse('goods:index'))

# /user
class UserInfoView(LoginRequiredMixin,View):
    '''用户中心-信息页'''
    def get(self,request):
        '''显示'''
        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的历史浏览记录
        conn = get_redis_connection('default')
        history_key = 'history_%d'%user.id

        # 获取用户最新浏览的5个商品的id
        sku_ids = conn.lrange(history_key,0,4)
        # 从数据库中查询用户浏览商品的具体信息
        goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        goods_res = []
        for a_id in sku_ids:
            for goods in goods_li:
                if a_id == goods.id:
                    goods_res.append(goods)

        # 组织上下文
        context = {'page':'user','address':address,'goods_res':goods_res}


        return render(request,'user_center_info.html',context)

# /user/order
class UserOrderView(LoginRequiredMixin,View):
    '''用户中心-订单页'''
    def get(self,request):
        '''显示'''
        return render(request,'user_center_order.html',{'page':'order'})

# /user/address
class AddressView(LoginRequiredMixin,View):
    '''用户中心-地址页'''
    def get(self,request):
        '''显示'''
        user = request.user
        # 获取用户的默认收货地址
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.objects.get_default_address(user)
        return render(request,'user_center_site.html',{'page':'address','address':address})

    def post(self,request):
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':'数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
            return render(request,'user_center_site.html',{'errmsg':'手机格式不正确'})
        # 业务处理
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        # 获取登录用户对应的User对象
        user = request.user
        # try:
        #     address = Address.objects.get(user=user,is_default=True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        # 返回应答,刷新地址页面
        return redirect(reverse('user:address')) # get请求方式