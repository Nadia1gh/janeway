from django.test import TestCase

from core.models import AccountRole
from review.models import ReviewerPoolMembership
from submission.models import FrozenAuthor
from utils.testing import helpers


class TestReviewerPoolMembershipSignal(TestCase):
    def setUp(self):
        self.journal, _ = helpers.create_journals()
        self.article = helpers.create_article(
            title="Test Article",
            journal=self.journal,
        )
        self.account = helpers.create_user(
            "author_one@email.com",
            ["author"],
            self.journal,
        )

    def test_frozen_author_creates_reviewer_pool_membership(self):
        helpers.create_frozen_author(
            self.article,
            author=self.account,
        )

        membership = ReviewerPoolMembership.objects.get(
            account=self.account,
            journal=self.journal,
        )

        self.assertEqual(
            membership.status,
            ReviewerPoolMembership.STATUS_CANDIDATE,
        )
        self.assertEqual(
            membership.source,
            ReviewerPoolMembership.SOURCE_AUTHOR,
        )
        self.assertTrue(membership.is_available)

    def test_existing_membership_is_not_overwritten(self):
        membership = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_BLOCKED,
            source=ReviewerPoolMembership.SOURCE_MANUAL,
            is_available=False,
        )

        helpers.create_frozen_author(
            self.article,
            author=self.account,
        )

        membership.refresh_from_db()

        self.assertEqual(
            membership.status,
            ReviewerPoolMembership.STATUS_BLOCKED,
        )
        self.assertEqual(
            membership.source,
            ReviewerPoolMembership.SOURCE_MANUAL,
        )
        self.assertFalse(membership.is_available)

    def test_author_does_not_get_reviewer_role(self):
        helpers.create_frozen_author(
            self.article,
            author=self.account,
        )

        self.assertFalse(
            AccountRole.objects.filter(
                user=self.account,
                journal=self.journal,
                role__slug="reviewer",
            ).exists()
        )
