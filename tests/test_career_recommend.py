"""입력 근거·중복·불확실성을 직무 추천 결과와 대조함."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from career.catalog import load_catalog
from career.recommend import (ACTIVITIES, DEGREES, EXPERIENCES, INTERESTS, MAJORS, RULES,
                              Education, Profile, first_group, recommend)


class CareerRecommendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()

    def test_no_rank_from_education_or_job_title_alone(self):
        for profile in (Profile(), Profile(education=(Education("doctor", "computing"),)),
                        Profile(experiences=("backend", "ml")),
                        Profile(activities=("unknown",), interests=("unknown",))):
            self.assertEqual(recommend(profile, self.catalog), ())

    def test_degree_level_does_not_raise_rank_or_exclude_careers(self):
        profiles = [Profile(education=(Education(degree, "design"),), activities=("ui",), interests=("interaction",))
                    for degree in DEGREES]
        scores = [[(row.role_id, row.strength) for row in recommend(profile, self.catalog)] for profile in profiles]
        self.assertTrue(all(score == scores[0] for score in scores))
        self.assertEqual(scores[0][0][0], "frontend")
        self.assertEqual(recommend(replace(profiles[0], education=()), self.catalog)[0].role_id, "frontend")

    def test_multiple_majors_and_jobs_keep_their_own_evidence(self):
        profile = Profile(education=(Education("bachelor", "design"), Education("master", "math")),
                          experiences=("frontend", "data"), activities=("ui", "data"))
        result = {row.role_id: row for row in recommend(profile, self.catalog)}
        self.assertEqual(result["frontend"].education, (Education("bachelor", "design"),))
        self.assertEqual(result["data_engineering"].education, (Education("master", "math"),))
        self.assertEqual(result["frontend"].experiences, ("frontend",))
        self.assertEqual(result["data_engineering"].experiences, ("data",))

    def test_reordering_and_duplicate_rows_do_not_change_results(self):
        profile = Profile((Education("bachelor", "computing"), Education("master", "math")),
                          ("data", "backend"), ("data", "api"), ("service", "data"))
        repeated = Profile(profile.education[::-1] * 2, profile.experiences[::-1] * 2,
                           profile.activities[::-1] * 2, profile.interests[::-1] * 2)
        self.assertEqual(recommend(profile, self.catalog), recommend(repeated, self.catalog))
        degree = replace(profile, education=profile.education + (Education("doctor", "computing"),))
        self.assertEqual([(r.role_id, r.strength) for r in recommend(profile, self.catalog)],
                         [(r.role_id, r.strength) for r in recommend(degree, self.catalog)])

    def test_interest_can_change_direction_despite_previous_career(self):
        profile = Profile((Education("doctor", "mechanical"),), ("mechanical", "embedded"),
                          ("hardware", "control"), ("interaction",))
        results = recommend(profile, self.catalog)
        self.assertIn(results[0].role_id, ("frontend", "qa"))
        control = next(row for row in results if row.role_id == "robot_control")
        self.assertGreater(results[0].strength, control.strength)

    def test_non_developer_tasks_and_unknown_background_still_connect(self):
        profile = Profile((Education("bachelor", "other"),), ("other",), ("document", "requirements"))
        results = recommend(profile, self.catalog)
        self.assertEqual(results[0].role_id, "qa")
        self.assertTrue(all(not row.education and not row.experiences for row in results))
        logistics = Profile(experiences=("logistics",), activities=("data", "automation"))
        self.assertEqual(recommend(logistics, self.catalog)[0].role_id, "data_engineering")

    def test_background_resolves_equal_interests_without_stereotyping_new_goal(self):
        bare = Profile(interests=("service",))
        developer = replace(bare, experiences=("backend",), activities=("api",),
                            education=(Education("bachelor", "computing"),))
        self.assertNotEqual(recommend(bare, self.catalog), recommend(developer, self.catalog))
        self.assertIn(recommend(developer, self.catalog)[0].role_id, ("backend", "robot_backend"))

    def test_unrelated_background_does_not_route_to_quality_assurance(self):
        bare = Profile(activities=("requirements", "document"), interests=("interaction",))
        background = replace(bare, education=(Education("bachelor", "humanities"),),
                             experiences=("sales", "health", "education"))
        self.assertEqual(recommend(bare, self.catalog), recommend(background, self.catalog))

    def test_boundary_ties_are_not_hidden_by_catalog_order(self):
        results = recommend(Profile(interests=("service",)), self.catalog)
        self.assertGreater(len(first_group(results)), 3)
        reversed_catalog = replace(self.catalog, roles=self.catalog.roles[::-1])
        self.assertEqual(results, recommend(Profile(interests=("service",)), reversed_catalog))

    def test_rule_coverage_uses_existing_catalog_and_known_choices(self):
        self.assertEqual(set(RULES), {role["id"] for role in self.catalog.roles})
        for rule in RULES.values():
            for values, known in ((rule.interests, INTERESTS), (rule.activities, ACTIVITIES),
                                  (rule.experiences, EXPERIENCES), (rule.majors, MAJORS)):
                self.assertTrue(set(values) <= known.keys())
        self.assertTrue(set(scene for _, scene in INTERESTS.values()) <= RULES.keys())

    def test_offline_partial_catalog_has_no_invented_roles(self):
        small = replace(self.catalog, roles=(self.catalog.role("frontend"),))
        with patch("socket.socket", side_effect=AssertionError("네트워크 사용")):
            result = recommend(Profile(interests=("interaction",)), small)
        self.assertEqual([row.role_id for row in result], ["frontend"])
        self.assertEqual(recommend(Profile(interests=("interaction",)), replace(small, roles=())), ())
