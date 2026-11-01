from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import GigFilterForm, GigForm
from .models import Category, Gig
from reviews.models import Review
from django.db.models import Avg


def gig_list(request):
    form = GigFilterForm(request.GET or None)
    gigs = Gig.objects.filter(status=Gig.Status.ACTIVE, category__is_active=True).select_related('freelancer', 'category')
    if form.is_valid():
        query = form.cleaned_data.get('q')
        category = form.cleaned_data.get('category')
        minimum = form.cleaned_data.get('min_price')
        maximum = form.cleaned_data.get('max_price')
        if query:
            gigs = gigs.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(freelancer__display_name__icontains=query)
            )
        if category:
            gigs = gigs.filter(category=category)
        if minimum is not None:
            gigs = gigs.filter(starting_price__gte=minimum)
        if maximum is not None:
            gigs = gigs.filter(starting_price__lte=maximum)
    page = Paginator(gigs, 12).get_page(request.GET.get('page'))
    return render(request, 'marketplace/gig_list.html', {
        'filter_form': form,
        'page_obj': page,
        'active_categories': Category.objects.filter(is_active=True),
    })


def gig_detail(request, slug):
    gig = get_object_or_404(
        Gig.objects.select_related('freelancer', 'category'),
        slug=slug,
    )
    is_owner = request.user.is_authenticated and request.user == gig.freelancer
    if (gig.status != Gig.Status.ACTIVE or not gig.category.is_active) and not is_owner:
        return redirect('marketplace:gig_list')
    reviews = Review.objects.filter(contract__gig=gig, reviewee=gig.freelancer).select_related('reviewer', 'contract')
    rating_average = reviews.aggregate(value=Avg('rating'))['value']
    return render(request, 'marketplace/gig_detail.html', {
        'gig': gig,
        'gig_reviews': reviews[:10],
        'rating_average': rating_average,
        'review_count': reviews.count(),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def gig_create(request):
    if request.user.role != request.user.Role.FREELANCER:
        messages.error(request, 'Only freelancer accounts can publish services.')
        return redirect('marketplace:gig_list')
    form = GigForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        gig = form.save(commit=False)
        gig.freelancer = request.user
        gig.save()
        messages.success(request, 'Your service is now on the marketplace.')
        return redirect('marketplace:gig_detail', slug=gig.slug)
    return render(request, 'marketplace/gig_form.html', {'form': form, 'is_edit': False})


@login_required
@require_http_methods(['GET', 'POST'])
def gig_edit(request, slug):
    gig = get_object_or_404(Gig, slug=slug, freelancer=request.user)
    if request.user.role != request.user.Role.FREELANCER:
        return redirect('marketplace:gig_list')
    form = GigForm(request.POST or None, instance=gig)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your service details have been updated.')
        return redirect('marketplace:gig_detail', slug=gig.slug)
    return render(request, 'marketplace/gig_form.html', {'form': form, 'gig': gig, 'is_edit': True})
