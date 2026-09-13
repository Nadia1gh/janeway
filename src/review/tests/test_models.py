from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch
from core.models import Account, XSLFile
from journal.models import Journal
from review.models import ReviewerPoolMembership


class ReviewerPoolMembershipTests(TestCase):
    def setUp(self):
        XSLFile.objects.create(
            label=settings.DEFAULT_XSL_FILE_LABEL,
            file=ContentFile("<xsl:stylesheet version='1.0'></xsl:stylesheet>"),
            original_filename="default.xsl",
        )

        self.account = Account.objects.create(
            email="reviewer@example.com",
            first_name="Test",
            last_name="Reviewer",
        )

        self.second_account = Account.objects.create(
            email="reviewer2@example.com",
            first_name="Second",
            last_name="Reviewer",
        )
        with patch("journal.models.install.setup_submission_items"):
            self.journal = Journal.objects.create(
                code="JRN1",
            )

            self.second_journal = Journal.objects.create(
                code="JRN2",
            )

    def test_default_values(self):
        membership = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
        )

        self.assertEqual(
            membership.status,
            ReviewerPoolMembership.STATUS_CANDIDATE,
        )
        self.assertTrue(membership.is_available)

    def test_same_account_and_journal_is_unique(self):
        ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
        )

        with self.assertRaises(IntegrityError):
            ReviewerPoolMembership.objects.create(
                account=self.account,
                journal=self.journal,
            )

    def test_same_account_can_belong_to_different_journals(self):
        first = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
        )

        second = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.second_journal,
        )

        self.assertNotEqual(first.pk, second.pk)

    def test_different_accounts_can_belong_to_same_journal(self):
        first = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
        )

        second = ReviewerPoolMembership.objects.create(
            account=self.second_account,
            journal=self.journal,
        )

        self.assertNotEqual(first.pk, second.pk)