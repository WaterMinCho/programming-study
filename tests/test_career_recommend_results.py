"""명시적인 경력 검토에서 근거·동률·입력 변경을 확인함."""
from dataclasses import replace
import unittest

from career.catalog import load_catalog
from career.recommend import DEGREES, Education, Profile, first_group, recommend


class ExperienceReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def review(self, profile, catalog=None):
        return recommend(profile, catalog or self.catalog, include_experience_only=True)

    def test_experience_only_has_reasons_without_invented_activities(self):
        result = self.review(Profile(experiences=("backend",)))
        self.assertEqual({row.role_id for row in result},
                         {"backend", "robot_backend", "platform_infrastructure", "data_engineering"})
        for row in result:
            self.assertEqual(row.experiences, ("backend",))
            self.assertEqual(row.activities, ())
            self.assertEqual(row.interests, ())

    def test_broad_background_and_degree_alone_do_not_assign_a_career(self):
        for profile in (Profile(), Profile(education=(Education("doctor", "computing"),)),
                        Profile(experiences=("other", "research", "sales", "logistics", "mechanical")),
                        Profile(experiences=("unknown",))):
            with self.subTest(profile=profile):
                self.assertEqual(self.review(profile), ())

    def test_explicit_interest_still_takes_priority_over_experience(self):
        profile = Profile(experiences=("backend",), interests=("interaction",))
        self.assertEqual(self.review(profile), recommend(profile, self.catalog))
        self.assertEqual({row.role_id for row in self.review(profile)}, {"frontend", "qa"})

    def test_degrees_duplicates_and_catalog_order_do_not_break_ties(self):
        base = Profile(experiences=("backend",))
        results = self.review(base)
        self.assertEqual(first_group(results), results)
        self.assertEqual(self.review(replace(base, experiences=("backend", "backend"))), results)
        self.assertEqual(self.review(base, replace(self.catalog, roles=self.catalog.roles[::-1])), results)
        scores = [[(r.role_id, r.strength) for r in self.review(
            replace(base, education=(Education(degree, "computing"),)))] for degree in DEGREES]
        self.assertTrue(all(score == scores[0] for score in scores))

