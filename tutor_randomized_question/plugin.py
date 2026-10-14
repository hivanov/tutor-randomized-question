"""
Tutor plugin for Randomized Multi-Choice Question with Case Grading.
"""

from tutor import hooks

# Configuration defaults
hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("RANDOMIZED_QUESTION_ENABLE", True),
        ("RANDOMIZED_QUESTION_PIP_REQUIREMENT", "openedx-randomized-question-xblock"),
    ]
)

# Injects the XBlock pip dependency into Open edX LMS & CMS Docker image build
hooks.Filters.ENV_PATCHES.add_items(
    [
        (
            "openedx-dockerfile-post-python-requirements",
            """
# Install Randomized Question XBlock
RUN pip install {{ RANDOMIZED_QUESTION_PIP_REQUIREMENT }}
""",
        ),
        (
            "openedx-lms-common-settings",
            """
# Randomized Question XBlock Feature Flags
FEATURES["ENABLE_RANDOMIZED_QUESTION_XBLOCK"] = True
""",
        ),
        (
            "openedx-cms-common-settings",
            """
# Randomized Question XBlock Feature Flags
FEATURES["ENABLE_RANDOMIZED_QUESTION_XBLOCK"] = True
""",
        ),
    ]
)
