import datetime
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import transaction
from django.db.models import Count, Q, F, ExpressionWrapper, DateField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import FormView, DetailView, TemplateView
from datetime import timedelta
from datetime import datetime

from shop.models import Buybook
from .models import *
# Create your views here.
def rentbook_in_category(request, category_slug=None):
    current_category = None
    categories = Rentcategory.objects.all()
    products = Rentbook.objects.filter(available_display=True)

    if category_slug:
        current_category = get_object_or_404(Rentcategory, slug=category_slug)
        products = products.filter(rcategory=current_category)

    return render(request, 'shop/rent_list.html',
                  {'current_category': current_category, 'categories': categories, 'products': products})


def rentbook_detail(request, id, product_slug=None):
    product = get_object_or_404(Rentbook, id=id, slug=product_slug)
    # reserve = get_object_or_404(Reservation, bookid=id)
    user = request.user

    reserve_count = Reservation.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'),0))
    rental_count = Rental.objects.filter(rbook_id=id).values('rbook_id').aggregate(total=Coalesce(Count('rbook_id'), 0))
    if user.is_authenticated:
        global user_count, rental_date, reserve_date
        user_count = Reservation.objects.filter(cust_num=user, rbook_id=id).values('cust_num').aggregate(
            total=Coalesce(Count('cust_num'), 0))
        rental_user = Rental.objects.filter(cust_num=user, rbook_id=id).values('cust_num').aggregate(total=Coalesce(Count('cust_num'), 0))
        rental_state = Rental.objects.filter(cust_num=user, rbook_id=id).values('rental_state').first()

        rc = reserve_count.get('total')  # ???????????????
        # print(rc)
        rtc = rental_count.get('total')  # ???????????????
        rcp = rc + 1
        rental_date = Rental.objects.filter(rbook_id=id).order_by('due').annotate(
            delta=ExpressionWrapper(F('due') + timedelta(days=1), output_field=DateField()))
        reserve_date = Reservation.objects.filter(rbook_id=id).order_by('exp').annotate(
            delta=ExpressionWrapper(F('exp') + timedelta(days=15), output_field=DateField())).values()
        reserve_rental = Reservation.objects.filter(rbook_id=id).order_by('apply').first()
        if rtc > rc:  # ?????? ???????????? ?????? ????????? ?????? ?????? ??????
            rental_date = rental_date[rc:rcp]

        else:  # ?????? ???????????? ?????? ????????? ?????? ?????? ??????
            reserve_date = reserve_date.last()
        return render(request, 'shop/rent_detail.html', {'product':product, 'reserve_count':reserve_count, 'rental_count':rental_count, 'rental_date':rental_date, 'reserve_date':reserve_date, 'user_count':user_count, 'rental_user':rental_user, 'rental_state':rental_state, 'reserve_rental':reserve_rental })
    else:
        return render(request, 'shop/rent_detail.html', {'product':product, 'reserve_count':reserve_count, 'rental_count':rental_count, 'rental_date':rental_date, 'reserve_date':reserve_date })

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

    if rtc > rc:  # ?????? ???????????? ?????? ????????? ?????? ?????? ??????
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

def rental_history(request, pk):
    # rentals = Rental.objects.filter(cust_num=request.user)
    # return render(request, 'history/rental_history.html', {'rentals':rentals})
    categories = Rentcategory.objects.all()
    user = User.objects.get(pk=pk)
    rentals = Rental.objects.filter(cust_num=user.id)

    user = User.objects.get(pk=pk)
    reserves = Reservation.objects.filter(cust_num=user.id)
    book_id = reserves.values('rbook_id')
    products = Rentbook.objects.filter(id__in=book_id)
    context = {'user':user, 'rentals': rentals, 'reserves': reserves, 'categories': categories, 'products':products}
    return render(request, 'history/rental_history.html', context)

@login_required
@require_POST
def rental(request, id):
    product = get_object_or_404(Rentbook, id=id)
    user = request.user

    if request.method == 'POST':
        book = get_object_or_404(Rentbook, id=id)
        book.rent_stock(request.user)
        rental = Rental.objects.create(
            rbook_id=product,
            cust_num=user,
            rent_date=date.today(),
            due = date.today() + timedelta(days=14),
        )
        rental.save()
        return render(request, 'shop/rental.html', {'product': product})

    else:
        return render(request, 'shop/rent_list.html', {'product': product})


def rental_return(request, id, pk):
    rental = get_object_or_404(Rental, id=id)
    rentalid = Rental.objects.filter(id=id).values('rbook_id')
    user = User.objects.get(pk=pk)

    if request.method == 'GET':
        book = get_object_or_404(Rentbook, id__in=rentalid)
        book.rstock += 1
        rental.rental_state = '????????????'


    book.save()
    rental.save()
    # context={'user':user, 'rental':rental}
    # return HttpResponse(json.dumps(context), content_type="application/json")
    return render(request, 'history/return_finish.html', {'user':user, 'rental':rental})
