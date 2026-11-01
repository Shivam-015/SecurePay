from django import forms
from django.core.exceptions import ValidationError

from .models import Category, Gig


class GigForm(forms.ModelForm):
    class Meta:
        model = Gig
        fields = ('title', 'category', 'description', 'starting_price', 'currency', 'delivery_days', 'status')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'What will you help a client accomplish?'}),
            'category': forms.Select(),
            'description': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Describe what is included, what the client will receive, and any useful boundaries.'}),
            'starting_price': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'placeholder': 'e.g. 5000'}),
            'currency': forms.TextInput(attrs={'maxlength': 3, 'placeholder': 'INR'}),
            'delivery_days': forms.NumberInput(attrs={'min': 1, 'step': 1, 'placeholder': 'e.g. 7'}),
            'status': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['currency'].initial = 'INR'
        self.fields['status'].help_text = 'Paused services are hidden from search and can be reactivated later.'

    def clean_currency(self):
        return self.cleaned_data['currency'].strip().upper()


class GigFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, label='Search services')
    category = forms.ModelChoiceField(required=False, queryset=Category.objects.none(), empty_label='All categories')
    min_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label='Minimum price')
    max_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label='Maximum price')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['q'].widget.attrs.update({
            'placeholder': 'Search by service, skill, or category',
            'aria-label': 'Search services',
        })

    def clean(self):
        cleaned_data = super().clean()
        minimum = cleaned_data.get('min_price')
        maximum = cleaned_data.get('max_price')
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValidationError('Minimum price must be lower than maximum price.')
        return cleaned_data
