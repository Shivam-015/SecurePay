from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ('body',)
        widgets = {'body': forms.Textarea(attrs={
            'rows': 3,
            'maxlength': 4000,
            'placeholder': 'Write a clear update or question…',
        })}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write a message before sending.')
        return body
