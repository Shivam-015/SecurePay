from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('display_name', 'email', 'role')
        widgets = {
            'display_name': forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'How should we address you?'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}),
            'role': forms.RadioSelect,
        }

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data['email']).strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email', 'placeholder': 'you@example.com'}),
    )

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class VerificationEmailForm(forms.Form):
    email = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}),
    )
