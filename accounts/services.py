from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse


TOKEN_SALT = 'securepay.email-verification.v1'
TOKEN_MAX_AGE = 60 * 60 * 24


def send_email_verification(*, user, request):
    token = signing.dumps({'user_id': user.pk, 'email': user.email}, salt=TOKEN_SALT)
    link = request.build_absolute_uri(reverse('accounts:verify_email', kwargs={'token': token}))
    send_mail(
        subject='Verify your SecurePay email address',
        message=(
            f'Hello {user.display_name},\n\n'
            f'Confirm your email address within 24 hours to activate your SecurePay account:\n\n{link}\n\n'
            'If you did not create this account, you can ignore this email.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def verify_email_token(token):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        user = get_user_model().objects.get(
            pk=payload['user_id'],
            email=payload['email'],
            is_active=False,
        )
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError, ValueError, get_user_model().DoesNotExist):
        return False
    user.is_active = True
    user.save(update_fields=('is_active',))
    return True
