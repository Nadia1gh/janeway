from django.test import TestCase
from django.urls import reverse

from core.middleware import get_site_resources
from core.models import AccountRole
from review.models import ReviewerPoolMembership
from utils.testing import helpers


class TestReviewerPoolManager(TestCase):
    
    def setUp(self):
        self.press = helpers.create_press()

        self.journal, self.journal_two = helpers.create_journals()

        self.editor = helpers.create_user(
            "reviewer-pool-editor@example.com",
            roles=["editor"],
            journal=self.journal,
        )
        self.editor.is_active = True
        self.editor.save()

        self.journal_manager = helpers.create_user(
            "reviewer-pool-manager@example.com",
            roles=["journal-manager"],
            journal=self.journal,
        )
        self.journal_manager.is_active = True
        self.journal_manager.save()

        self.other_user = helpers.create_user(
            "reviewer-pool-user@example.com",
        )
        self.other_user.is_active = True
        self.other_user.save()

        self.account = helpers.create_user(
            "pool-member@example.com",
            first_name="Pool",
            last_name="Member",
        )
        self.account.is_active = True
        self.account.save()

        self.other_journal_account = helpers.create_user(
            "other-journal-member@example.com",
            first_name="Other",
            last_name="Journal",
        )
        self.other_journal_account.is_active = True
        self.other_journal_account.save()

        self.membership = ReviewerPoolMembership.objects.create(
            account=self.account,
            journal=self.journal,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            source=ReviewerPoolMembership.SOURCE_MANUAL,
            is_available=True,
        )

        self.other_membership = ReviewerPoolMembership.objects.create(
            account=self.other_journal_account,
            journal=self.journal_two,
            status=ReviewerPoolMembership.STATUS_ACTIVE,
            source=ReviewerPoolMembership.SOURCE_MANUAL,
            is_available=True,
        )


    def test_editor_can_open_reviewer_pool(self):
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("review_reviewer_pool"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reviewer Pool")
        self.assertContains(response, self.account.email)

    def test_journal_manager_can_open_reviewer_pool(self):
        self.client.force_login(self.journal_manager)

        response = self.client.get(
            reverse("review_reviewer_pool"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.account.email)

    def test_unrelated_user_cannot_open_reviewer_pool(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("review_reviewer_pool"),
        )

        self.assertNotEqual(response.status_code, 200)

    def test_reviewer_pool_is_scoped_to_current_journal(self):
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse("review_reviewer_pool"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.account.email)
        self.assertNotContains(
            response,
            self.other_journal_account.email,
        )

    def test_editor_can_add_reviewer_pool_member(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("review_add_reviewer_pool_member"),
            {
                "account": self.other_user.pk,
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "source": ReviewerPoolMembership.SOURCE_MANUAL,
                "is_available": "on",
                "notes": "Added manually",
            },
        )

        self.assertEqual(response.status_code, 302)

        membership = ReviewerPoolMembership.objects.get(
            account=self.other_user,
            journal=self.journal,
        )

        self.assertEqual(
            membership.status,
            ReviewerPoolMembership.STATUS_ACTIVE,
        )
        self.assertEqual(
            membership.source,
            ReviewerPoolMembership.SOURCE_MANUAL,
        )
        self.assertTrue(membership.is_available)
        self.assertEqual(membership.notes, "Added manually")

    def test_duplicate_reviewer_pool_member_is_rejected(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("review_add_reviewer_pool_member"),
            {
                "account": self.account.pk,
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "source": ReviewerPoolMembership.SOURCE_MANUAL,
                "is_available": "on",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            ReviewerPoolMembership.objects.filter(
                account=self.account,
                journal=self.journal,
            ).count(),
            1,
        )

    def test_editor_can_edit_reviewer_pool_member(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "review_edit_reviewer_pool_member",
                kwargs={"membership_id": self.membership.pk},
            ),
            {
                "status": ReviewerPoolMembership.STATUS_INACTIVE,
                "is_available": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.membership.refresh_from_db()

        self.assertEqual(
            self.membership.status,
            ReviewerPoolMembership.STATUS_INACTIVE,
        )
        self.assertFalse(self.membership.is_available)

    def test_membership_from_another_journal_cannot_be_edited(self):
        self.client.force_login(self.editor)

        response = self.client.get(
            reverse(
                "review_edit_reviewer_pool_member",
                kwargs={"membership_id": self.other_membership.pk},
            ),
        )

        self.assertEqual(response.status_code, 404)

    def test_membership_from_another_journal_cannot_be_updated(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse(
                "review_edit_reviewer_pool_member",
                kwargs={"membership_id": self.other_membership.pk},
            ),
            {
                "status": ReviewerPoolMembership.STATUS_BLOCKED,
                "is_available": "",
            },
        )

        self.assertEqual(response.status_code, 404)

        self.other_membership.refresh_from_db()

        self.assertEqual(
            self.other_membership.status,
            ReviewerPoolMembership.STATUS_ACTIVE,
        )
        self.assertTrue(self.other_membership.is_available)

    def test_legacy_reviewer_role_is_not_added_when_adding_pool_member(self):
        self.client.force_login(self.editor)

        response = self.client.post(
            reverse("review_add_reviewer_pool_member"),
            {
                "account": self.other_user.pk,
                "status": ReviewerPoolMembership.STATUS_ACTIVE,
                "source": ReviewerPoolMembership.SOURCE_MANUAL,
                "is_available": "on",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            AccountRole.objects.filter(
                user=self.other_user,
                journal=self.journal,
                role__slug="reviewer",
            ).exists(),
        )
