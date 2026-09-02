from enum import Enum


class WorkCategory(str, Enum):
    """Classification fields used by the Jordanian Government Tenders Department."""

    ROADS = "roads"
    BUILDINGS = "buildings"
    ELECTROMECHANICAL = "electromechanical"
    WATER_AND_SEWERAGE = "water_and_sewerage"
    OTHER_WORKS = "other_works"


class ClassificationGrade(int, Enum):
    """Contractor classification grades 1 to 6. Grade 1 is the highest."""

    GRADE_1 = 1
    GRADE_2 = 2
    GRADE_3 = 3
    GRADE_4 = 4
    GRADE_5 = 5
    GRADE_6 = 6

    def meets(self, required: "ClassificationGrade") -> bool:
        # A lower number is a higher grade.
        return self.value <= required.value


class RuleStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Verdict(str, Enum):
    QUALIFIED = "qualified"
    CONDITIONALLY_QUALIFIED = "conditionally_qualified"
    NOT_QUALIFIED = "not_qualified"
