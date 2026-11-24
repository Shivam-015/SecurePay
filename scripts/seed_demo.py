"""Seed demo data for SecurePay (local demo only; no real money or data).

Run it without rebuilding the image by piping it into the Django shell.

Kubernetes:
  kubectl -n securepay exec -i deployment/securepay-web -- python manage.py shell < scripts/seed_demo.py
Docker Compose:
  docker compose exec -T web python manage.py shell < scripts/seed_demo.py

It is idempotent: if the demo users already exist it exits without changes.
All demo accounts share DEMO_PASSWORD below. Change it if you like; these
accounts are for local demos only.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from auditlog.services import agreement_fingerprint, record_event
from contracts.models import Contract, Milestone
from contracts.services import request_revision, respond_to_proposal, submit_milestone
from disputes.models import Dispute
from disputes.services import add_dispute_message, open_dispute
from marketplace.models import Category, Gig
from messaging.models import Conversation, Message
from notifications.services import notify_contract_counterparty
from payments.services import simulate_funding, simulate_release
from reviews.models import Review

DEMO_PASSWORD = 'Demo-Pass-2026!'
DOMAIN = 'securepay.demo'

User = get_user_model()

if User.objects.filter(email__endswith='@' + DOMAIN).exists():
    print('Demo data already present (users @%s exist). Nothing changed.' % DOMAIN)
else:
    today = timezone.localdate()

    def make_user(slug, name, role, **extra):
        user = User.objects.create_user(
            f'{slug}@{DOMAIN}', DEMO_PASSWORD, display_name=name, role=role, is_active=True, **extra
        )
        return user

    @transaction.atomic
    def seed():
        clients = [
            make_user('client.aarav', 'Aarav Mehta', 'client'),
            make_user('client.meera', 'Meera Iyer', 'client'),
        ]
        freelancers = [
            make_user('dev.riya', 'Riya Sharma', 'freelancer'),
            make_user('design.kabir', 'Kabir Nair', 'freelancer'),
            make_user('write.zoya', 'Zoya Khan', 'freelancer'),
        ]
        staff = make_user('staff.reviewer', 'Demo Staff', 'client', is_staff=True)
        aarav, meera = clients
        riya, kabir, zoya = freelancers

        cats = {}
        for name, desc in [
            ('Web Development', 'Websites, web apps and APIs'),
            ('Design', 'Logos, UI and brand design'),
            ('Writing', 'Articles, copy and documentation'),
            ('Data & AI', 'Analytics, dashboards and ML'),
            ('Marketing', 'SEO, social media and campaigns'),
        ]:
            cats[name], _ = Category.objects.get_or_create(
                name=name, defaults={'slug': name.lower().replace(' & ', '-').replace(' ', '-'), 'description': desc}
            )

        gigs = {
            'django': Gig.objects.create(freelancer=riya, category=cats['Web Development'], title='Django website or REST API', description='Production-ready Django site or API with tests and documentation.', starting_price=Decimal('25000'), delivery_days=14),
            'react': Gig.objects.create(freelancer=riya, category=cats['Web Development'], title='React dashboard front-end', description='Responsive dashboard built with React and charts.', starting_price=Decimal('18000'), delivery_days=10),
            'logo': Gig.objects.create(freelancer=kabir, category=cats['Design'], title='Logo and brand kit', description='Logo, colour palette and typography guide.', starting_price=Decimal('8000'), delivery_days=7),
            'ui': Gig.objects.create(freelancer=kabir, category=cats['Design'], title='Mobile app UI design', description='High-fidelity screens and clickable prototype.', starting_price=Decimal('15000'), delivery_days=12),
            'blog': Gig.objects.create(freelancer=zoya, category=cats['Writing'], title='SEO blog articles (5 posts)', description='Researched, original 1,000-word articles.', starting_price=Decimal('6000'), delivery_days=8),
            'docs': Gig.objects.create(freelancer=zoya, category=cats['Writing'], title='Technical documentation', description='Developer guides and API docs.', starting_price=Decimal('9000'), delivery_days=9, status=Gig.Status.PAUSED),
        }

        def propose(client, gig, title, scope, milestones, terms='Payment is released per approved milestone.'):
            total = sum((m[1] for m in milestones), Decimal('0.00'))
            contract = Contract.objects.create(
                client=client, freelancer=gig.freelancer, gig=gig, title=title, scope=scope,
                terms=terms, total_amount=total, currency=gig.currency,
            )
            for i, (mtitle, amount, days, desc) in enumerate(milestones, start=1):
                Milestone.objects.create(contract=contract, sequence=i, title=mtitle, amount=amount, description=desc, due_date=today + timedelta(days=days))
            record_event(contract=contract, actor=client, event_type='contract_proposed', payload={
                'gig_id': gig.pk, 'milestone_count': len(milestones), 'total_amount': str(total),
                'currency': contract.currency, 'agreement_hash': agreement_fingerprint(contract),
            })
            notify_contract_counterparty(contract=contract, actor=client, kind='contract_proposed', title='New contract proposal', message=f'{client.display_name} sent you a contract proposal.')
            return contract

        def say(contract, sender, body):
            conv, _ = Conversation.objects.get_or_create(contract=contract)
            Message.objects.create(conversation=conv, sender=sender, body=body)

        def deliver(milestone, freelancer, client, note='Delivered as agreed.'):
            simulate_funding(milestone_id=milestone.pk, actor=client)
            submit_milestone(milestone_id=milestone.pk, actor=freelancer, values={'kind': 'text', 'content': note})

        # A: completed contract, both milestones released, reviews and messages
        a = propose(aarav, gigs['django'], 'Company website rebuild', 'Rebuild the marketing site in Django with a contact form.', [
            ('Design and setup', Decimal('10000'), 5, 'Project skeleton and page layouts.'),
            ('Build and launch', Decimal('15000'), 14, 'Implementation, tests and deployment.'),
        ])
        respond_to_proposal(contract_id=a.pk, actor=riya, decision=Contract.Status.ACCEPTED, note='Happy to start.')
        say(a, aarav, 'Hi Riya, thanks for accepting. Can we start this week?')
        say(a, riya, 'Yes, I will share the first layouts in two days.')
        for m in a.milestones.all():
            deliver(m, riya, aarav, f'Completed: {m.title}.')
            simulate_release(milestone_id=m.pk, actor=aarav)
        Review.objects.create(contract=a, reviewer=aarav, reviewee=riya, rating=5, comment='Fast, clear and well tested.')
        Review.objects.create(contract=a, reviewer=riya, reviewee=aarav, rating=5, comment='Clear brief and prompt approvals.')

        # B: in progress, first milestone released, second funded and awaiting delivery, revision request on third
        b = propose(meera, gigs['logo'], 'Brand identity for cafe', 'Logo, palette and typography for a new cafe.', [
            ('Logo concepts', Decimal('4000'), 4, 'Three concepts.'),
            ('Final logo files', Decimal('4000'), 8, 'Final files in all formats.'),
        ])
        respond_to_proposal(contract_id=b.pk, actor=kabir, decision=Contract.Status.ACCEPTED)
        m1, m2 = list(b.milestones.all())
        deliver(m1, kabir, meera, 'Three logo concepts attached via link.')
        request_revision(milestone_id=m1.pk, actor=meera, note='Please warm up the colour palette.')
        submit_milestone(milestone_id=m1.pk, actor=kabir, values={'kind': 'text', 'content': 'Revised palette applied.'})
        simulate_release(milestone_id=m1.pk, actor=meera)
        simulate_funding(milestone_id=m2.pk, actor=meera)
        say(b, meera, 'Palette looks great now, thank you!')

        # C: proposal waiting for the freelancer
        propose(aarav, gigs['ui'], 'Food delivery app screens', 'Design 12 screens for a food delivery app.', [
            ('Wireframes', Decimal('6000'), 6, 'Low-fidelity wireframes.'),
            ('High-fidelity UI', Decimal('9000'), 12, 'Final visual design.'),
        ])

        # D: dispute open on a submitted milestone
        d = propose(meera, gigs['blog'], 'Five SEO blog posts', 'Five 1,000-word posts about healthy cooking.', [
            ('First batch (3 posts)', Decimal('3600'), 7, 'Three articles.'),
        ])
        respond_to_proposal(contract_id=d.pk, actor=zoya, decision=Contract.Status.ACCEPTED)
        dm = d.milestones.first()
        deliver(dm, zoya, meera, 'Three posts delivered in a shared document.')
        dispute = open_dispute(milestone_id=dm.pk, actor=meera, reason=Dispute.Reason.QUALITY, description='Two articles have too little detail on the agreed topics.')
        add_dispute_message(dispute_id=dispute.pk, actor=zoya, body='I can expand both articles within two days if needed.')

        # E: declined proposal
        e = propose(aarav, gigs['react'], 'Analytics dashboard', 'Interactive analytics dashboard.', [
            ('Dashboard build', Decimal('18000'), 10, 'Full build.'),
        ])
        respond_to_proposal(contract_id=e.pk, actor=riya, decision=Contract.Status.REJECTED, note='Fully booked this month.')

        return staff

    seed()
    print('Demo data created.')
    print('Accounts: client.aarav / client.meera / dev.riya / design.kabir / write.zoya / staff.reviewer  @' + DOMAIN)
    print('Shared password: see DEMO_PASSWORD in scripts/seed_demo.py')
