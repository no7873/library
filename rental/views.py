import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, F, ExpressionWrapper, DateField
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView, DetailView
from datetime import timedelta
from datetime import datetime

from .models import *
# Create your views here.
def rentbook_in_category(request, category_slug=None):
    current_category = None
    categories = Rentcategory.objects.all()
    products = Rentbook.objects.filter(available_display=True)

    if category_slug:
        current_category = get_object_or_404(Rentcategory, slug=category_slug)
        products = products.filter(category=current_category)

    return render(request, 'shop/rent_list.html',
                  {'current_category': current_category, 'categories': categories, 'products': products})

def rentbook_detail(request, id, product_slug=None):
    product = get_object_or_404(Rentbook, id=id, slug=product_slug)
    # reserve = get_object_or_404(Reservation, bookid=id)
    user = request.user

    reserve_count = Reservation.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'),0))
    rental_count = Rental.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'), 0))
    user_count = Reservation.objects.filter(cust_num=user).values('cust_num').aggregate(
        total=Coalesce(Count('cust_num'), 0))
    rc = reserve_count.get('total')#예약총권수
        # print(rc)
    rtc = rental_count.get('total')#대여총권수
    rcp = rc + 1
    rental_date = Rental.objects.filter(rbook_id=id).order_by('due').annotate(
        delta=ExpressionWrapper(F('due') + timedelta(days=1), output_field=DateField()))
    reserve_date = Reservation.objects.filter(rbook_id=id).order_by('exp').annotate(
        delta=ExpressionWrapper(F('exp') + timedelta(days=15), output_field=DateField())).values()
    if rtc > rc:#대여 인원수가 예약 인원수 보다 많은 경우
        rental_date = rental_date[rc:rcp]

    else: #예약 인원수가 대여 인원수 보다 많은 겨우
        reserve_date = reserve_date.last()

    return render(request, 'shop/rent_detail.html', {'product':product, 'reserve_count':reserve_count, 'rental_count':rental_count, 'rental_date':rental_date, 'reserve_date':reserve_date, 'user_count':user_count })

@login_required
@require_POST
def reserve(request, id):
    product = get_object_or_404(Rentbook, id=id)
    user = request.user

    reserve_count = Reservation.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'), 0))
    rental_count = Rental.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'), 0))
    rc = reserve_count.get('total')
    rtc = rental_count.get('total')
    rcp = rc + 1

    if rtc > rc:  # 대여 인원수가 예약 인원수 보다 많은 경우
        global rental_date
        rental_date = Rental.objects.filter(rbook_id=id).order_by('due').annotate(
            delta=ExpressionWrapper(F('due') + timedelta(days=1), output_field=DateField()))[rc:rcp]
        if request.method == 'POST':
            reserve = Reservation.objects.create(
                rbook_id=product,
                cust_num=user,
                exp=rental_date[0].delta
            )
            reserve.save()
    else:
        reserve_date = Reservation.objects.filter(rbook_id=id).order_by('exp').annotate(
            delta=ExpressionWrapper(F('exp') + timedelta(days=15), output_field=DateField())).values().last()
        delta = reserve_date.get('delta')
        if request.method == 'POST':
            reserve = Reservation.objects.create(
                rbook_id=product,
                cust_num=user,
                exp=delta
            )
            reserve.save()


    return render(request, 'shop/reserve.html', {'product':product})