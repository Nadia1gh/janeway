from django.test import TestCase

from review import logic
from review.models import ReviewerPoolMembership
from utils.testing import helpers


class TestReviewerPoolCandidates(TestCase):
    def setUp(self):
        self.journal, _ = helpers.create_journals()
        self.article = helpers.create_article(
            title="Test Article",
            journal=self.journal,
        )

        self.pool_account = helpers.create_user(
            "pool@example.com",
            [],
            self.journal,
        )
        self.legacy_account = helpers.create_user(
            "legacy@example.com",
            ["reviewer"],
            self.journal,
        )
        self.inactive_account = helpers.create_user(
            "inactive@example.com",
            [],
            self.journal,
        )
        self.blocked_account = helpers.create_user(
            "blocked@example.com",
            [],
            self.journal,
        )
        self.unavailable_account = helpers.create_user(
            "unavailable@example.com",
            [],
            self.journal,
        )

    def test_only_active_available_members_are_candidates(self):
        ReviewerPoolMembership.objects.create(
            account=self.pool_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=True,
        )
        ReviewerPoolMembership.objects.create(
            account=self.inactive_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_INACTIVE,
            is_available=True,
        )
        ReviewerPoolMembership.objects.create(
            account=self.blocked_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_BLOCKED,
            is_available=True,
        )
        ReviewerPoolMembership.objects.create(
            account=self.unavailable_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=False,
        )

        candidates = logic.get_reviewer_pool_candidates(self.article)

        self.assertIn(self.pool_account, candidates)
        self.assertNotIn(self.inactive_account, candidates)
        self.assertNotIn(self.blocked_account, candidates)
        self.assertNotIn(self.unavailable_account, candidates)

    def test_exclude_pks(self):
        ReviewerPoolMembership.objects.create(
            account=self.pool_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=True,
        )

        candidates = logic.get_reviewer_pool_candidates(
            self.article,
            exclude_pks=[self.pool_account.pk],
        )

        self.assertNotIn(self.pool_account, candidates)

    def test_unavailable_active_member_is_excluded(self):
        ReviewerPoolMembership.objects.create(
            account=self.unavailable_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=False,
        )

        candidates = logic.get_reviewer_pool_candidates(self.article)

        self.assertNotIn(self.unavailable_account, candidates)

    def test_get_reviewer_candidates_includes_pool_and_legacy_reviewers(self):
        ReviewerPoolMembership.objects.create(
            account=self.pool_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=True,
        )

        candidates = logic.get_reviewer_candidates(self.article)

        candidate_pks = set(candidates.values_list("pk", flat=True))

        self.assertIn(self.pool_account.pk, candidate_pks)
        self.assertIn(self.legacy_account.pk, candidate_pks)

    def test_get_reviewer_candidates_keeps_article_exclusions(self):
        ReviewerPoolMembership.objects.create(
            account=self.pool_account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            is_available=True,
        )

        candidates = logic.get_reviewer_candidates(
            self.article,
            user=self.pool_account,
        )

        candidate_pks = set(candidates.values_list("pk", flat=True))

        self.assertNotIn(self.pool_account.pk, candidate_pks)