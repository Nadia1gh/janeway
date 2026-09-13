from unittest.mock import patch

from django.test import TestCase

from core.models import AccountRole
from review import logic
from review.models import ReviewerPoolMembership
from utils import setting_handler
from utils.testing import helpers


class TestReviewerPoolCandidates(TestCase):
    def setUp(self):
        self.journal, self.journal_two = helpers.create_journals()
        helpers.create_roles(["author"])

        self.article = helpers.create_article(
            title="Test Article",
            journal=self.journal,
        )

        self.review_form = helpers.create_review_form(self.journal)

        setting_handler.save_setting(
            setting_group_name="general",
            setting_name="default_review_form",
            journal=self.journal,
            value=str(self.review_form.pk),
        )

        setting_handler.save_setting(
            setting_group_name="general",
            setting_name="default_review_visibility",
            journal=self.journal,
            value="double-blind",
        )

        setting_handler.save_setting(
            setting_group_name="general",
            setting_name="default_review_days",
            journal=self.journal,
            value="30",
        )

        self.editor = helpers.create_user(
            "editor@example.com",
            ["editor"],
            self.journal,
        )

        self.pool_account = helpers.create_user(
            "pool-reviewer@example.com",
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
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        ReviewerPoolMembership.objects.update_or_create(
            account=self.inactive_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_INACTIVE,
                "is_available": True,
            },
        )

        ReviewerPoolMembership.objects.update_or_create(
            account=self.blocked_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_BLOCKED,
                "is_available": True,
            },
        )

        ReviewerPoolMembership.objects.update_or_create(
            account=self.unavailable_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": False,
            },
        )

        candidates = logic.get_reviewer_pool_candidates(
            self.article,
        )

        self.assertIn(
            self.pool_account,
            candidates,
        )
        self.assertNotIn(
            self.inactive_account,
            candidates,
        )
        self.assertNotIn(
            self.blocked_account,
            candidates,
        )
        self.assertNotIn(
            self.unavailable_account,
            candidates,
        )

    def test_exclude_pks(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        candidates = logic.get_reviewer_pool_candidates(
            self.article,
            exclude_pks=[self.pool_account.pk],
        )

        self.assertNotIn(
            self.pool_account,
            candidates,
        )

    def test_unavailable_active_member_is_excluded(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.unavailable_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": False,
            },
        )

        candidates = logic.get_reviewer_pool_candidates(
            self.article,
        )

        self.assertNotIn(
            self.unavailable_account,
            candidates,
        )

    def test_get_reviewer_candidates_includes_pool_and_legacy_reviewers(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        candidates = logic.get_reviewer_candidates(
            self.article,
        )

        candidate_pks = set(
            candidates.values_list(
                "pk",
                flat=True,
            )
        )

        self.assertIn(
            self.pool_account.pk,
            candidate_pks,
        )
        self.assertIn(
            self.legacy_account.pk,
            candidate_pks,
        )

    def test_get_reviewer_candidates_keeps_article_exclusions(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        candidates = logic.get_reviewer_candidates(
            self.article,
            user=self.pool_account,
        )

        candidate_pks = set(
            candidates.values_list(
                "pk",
                flat=True,
            )
        )

        self.assertNotIn(
            self.pool_account.pk,
            candidate_pks,
        )

    def test_reviewer_pool_candidates_exclude_article_authors(self):
        author = helpers.create_user(
            "pool-author@example.com",
            [],
            self.journal,
        )

        self.article.authors.add(author)
        self.article.snapshot_authors()

        ReviewerPoolMembership.objects.update_or_create(
            account=author,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        candidates = logic.get_reviewer_pool_candidates(
            self.article,
        )

        self.assertNotIn(
            author.pk,
            candidates.values_list(
                "pk",
                flat=True,
            ),
        )

    def test_pool_member_is_eligible_for_assignment(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        self.assertTrue(
            logic.is_eligible_reviewer(
                self.article,
                self.pool_account,
            )
        )

    def test_legacy_reviewer_is_eligible_for_assignment(self):
        self.assertTrue(
            logic.is_eligible_reviewer(
                self.article,
                self.legacy_account,
            )
        )

    def test_article_author_is_not_eligible_for_assignment(self):
        author = helpers.create_user(
            "article-author@example.com",
            [],
            self.journal,
        )

        self.article.authors.add(author)
        self.article.snapshot_authors()

        ReviewerPoolMembership.objects.update_or_create(
            account=author,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        self.assertFalse(
            logic.is_eligible_reviewer(
                self.article,
                author,
            )
        )

    def test_article_coauthor_is_not_eligible_for_assignment(self):
        author = helpers.create_user(
            "article-coauthor@example.com",
            [],
            self.journal,
        )

        coauthor = helpers.create_user(
            "article-coauthor-two@example.com",
            [],
            self.journal,
        )

        self.article.authors.add(
            author,
            coauthor,
        )
        self.article.snapshot_authors()

        ReviewerPoolMembership.objects.update_or_create(
            account=coauthor,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        self.assertFalse(
            logic.is_eligible_reviewer(
                self.article,
                coauthor,
            )
        )

    def test_article_author_who_is_legacy_reviewer_is_not_eligible(self):
        author = helpers.create_user(
            "author-legacy-reviewer@example.com",
            ["reviewer"],
            self.journal,
        )

        self.article.authors.add(author)
        self.article.snapshot_authors()

        self.assertFalse(
            logic.is_eligible_reviewer(
                self.article,
                author,
            )
        )

    def test_blocked_pool_member_is_not_eligible_for_assignment(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.blocked_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_BLOCKED,
                "is_available": True,
            },
        )

        self.assertFalse(
            logic.is_eligible_reviewer(
                self.article,
                self.blocked_account,
            )
        )

    def test_quick_assign_accepts_active_pool_member_without_reviewer_role(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.pool_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        request = self.client.request().wsgi_request
        request.user = self.editor
        request.journal = self.journal

        default_form_setting = setting_handler.get_setting(
            "general",
            "default_review_form",
            self.journal,
        )
        default_visibility_setting = setting_handler.get_setting(
            "general",
            "default_review_visibility",
            self.journal,
        )
        default_days_setting = setting_handler.get_setting(
            "general",
            "default_review_days",
            self.journal,
        )

        self.assertEqual(
            int(default_form_setting.processed_value),
            self.review_form.pk,
        )
        self.assertEqual(
            default_visibility_setting.value,
            "double-blind",
        )
        self.assertEqual(
            default_days_setting.value,
            "30",
        )

        with patch(
            "review.logic.get_reviewer_notification",
            return_value="",
        ), patch(
            "review.logic.event_logic.Events.raise_event",
        ):
            assignment = logic.quick_assign(
                request,
                self.article,
                reviewer_user=self.pool_account,
            )

        self.assertIsNotNone(assignment)
        self.assertEqual(
            assignment.reviewer,
            self.pool_account,
        )
        self.assertFalse(
            AccountRole.objects.filter(
                user=self.pool_account,
                journal=self.journal,
                role__slug="reviewer",
            ).exists()
        )

    def test_quick_assign_rejects_blocked_pool_member(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.blocked_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_BLOCKED,
                "is_available": True,
            },
        )

        request = self.client.request().wsgi_request
        request.user = self.editor
        request.journal = self.journal

        result = logic.quick_assign(
            request,
            self.article,
            reviewer_user=self.blocked_account,
        )

        self.assertIsNone(result)
        self.assertFalse(
            self.article.reviewassignment_set.filter(
                reviewer=self.blocked_account,
            ).exists()
        )

    def test_quick_assign_rejects_inactive_pool_member(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.inactive_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_INACTIVE,
                "is_available": True,
            },
        )

        request = self.client.request().wsgi_request
        request.user = self.editor
        request.journal = self.journal

        result = logic.quick_assign(
            request,
            self.article,
            reviewer_user=self.inactive_account,
        )

        self.assertIsNone(result)
        self.assertFalse(
            self.article.reviewassignment_set.filter(
                reviewer=self.inactive_account,
            ).exists()
        )

    def test_quick_assign_rejects_unavailable_pool_member(self):
        ReviewerPoolMembership.objects.update_or_create(
            account=self.unavailable_account,
            journal=self.journal,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": False,
            },
        )

        request = self.client.request().wsgi_request
        request.user = self.editor
        request.journal = self.journal

        result = logic.quick_assign(
            request,
            self.article,
            reviewer_user=self.unavailable_account,
        )

        self.assertIsNone(result)
        self.assertFalse(
            self.article.reviewassignment_set.filter(
                reviewer=self.unavailable_account,
            ).exists()
        )

    def test_quick_assign_rejects_pool_member_from_different_journal(self):
        other_account = helpers.create_user(
            "other-journal-reviewer@example.com",
            [],
            self.journal_two,
        )

        ReviewerPoolMembership.objects.update_or_create(
            account=other_account,
            journal=self.journal_two,
            defaults={
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "is_available": True,
            },
        )

        request = self.client.request().wsgi_request
        request.user = self.editor
        request.journal = self.journal

        result = logic.quick_assign(
            request,
            self.article,
            reviewer_user=other_account,
        )

        self.assertIsNone(result)
        self.assertFalse(
            self.article.reviewassignment_set.filter(
                reviewer=other_account,
            ).exists()
        )