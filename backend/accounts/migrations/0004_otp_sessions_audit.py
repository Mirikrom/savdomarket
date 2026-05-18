"""Auth overhaul migration.

Adds OTP/session/audit infrastructure, tightens the User model and removes the
legacy ``PasswordResetCode`` table (it was insecure — codes were stored in
plaintext and returned via the API response).
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_preferred_language_passwordresetcode'),
    ]

    operations = [
        migrations.DeleteModel(name='PasswordResetCode'),

        migrations.AddField(
            model_name='user',
            name='phone_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='failed_login_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='last_password_changed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(max_length=20, unique=True),
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['phone'], name='accounts_us_phone_idx'),
        ),

        migrations.CreateModel(
            name='OtpCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('destination', models.CharField(db_index=True, max_length=255)),
                ('purpose', models.CharField(choices=[('registration', 'Registration'), ('login', 'Login'), ('password_reset', 'Password reset'), ('phone_change', 'Phone change')], max_length=32)),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('email', 'Email'), ('telegram', 'Telegram')], default='sms', max_length=16)),
                ('code_hash', models.CharField(max_length=255)),
                ('expires_at', models.DateTimeField()),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('max_attempts', models.PositiveSmallIntegerField(default=5)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
            ],
            options={
                'indexes': [models.Index(fields=['destination', 'purpose', 'expires_at'], name='accounts_ot_dest_pp_idx')],
            },
        ),

        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('refresh_jti', models.CharField(max_length=64, unique=True)),
                ('device_name', models.CharField(blank=True, max_length=255)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('last_used_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-last_used_at'],
                'indexes': [
                    models.Index(fields=['user', 'revoked_at'], name='accounts_us_user_rv_idx'),
                    models.Index(fields=['refresh_jti'], name='accounts_us_jti_idx'),
                ],
            },
        ),

        migrations.CreateModel(
            name='AuthAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event', models.CharField(choices=[
                    ('otp_requested', 'OTP requested'),
                    ('otp_verified', 'OTP verified'),
                    ('otp_failed', 'OTP failed'),
                    ('register_completed', 'Registration completed'),
                    ('login_success', 'Login success'),
                    ('login_failed', 'Login failed'),
                    ('account_locked', 'Account locked'),
                    ('password_reset_requested', 'Password reset requested'),
                    ('password_changed', 'Password changed'),
                    ('logout', 'Logout'),
                    ('session_revoked', 'Session revoked'),
                ], max_length=48)),
                ('destination', models.CharField(blank=True, max_length=255)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auth_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'event'], name='accounts_aa_user_ev_idx'),
                    models.Index(fields=['event', 'created_at'], name='accounts_aa_ev_ct_idx'),
                ],
            },
        ),
    ]
