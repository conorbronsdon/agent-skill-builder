import tempfile
import unittest
from pathlib import Path

from scripts import validate_skill
from scripts.validate_skill import parse_frontmatter, validate


class ValidateSkillTests(unittest.TestCase):
    def make_skill(self, name, frontmatter, body="Follow the task instructions."):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name) / name
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8"
        )
        return directory

    def test_valid_portable_skill_passes(self):
        skill = self.make_skill(
            "data-review",
            "name: data-review\ndescription: Reviews data when a user requests a quality check.",
        )
        errors, warnings = validate(skill, "agentskills")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_portable_name_must_match_directory(self):
        skill = self.make_skill(
            "data-review",
            "name: other-name\ndescription: Reviews data when requested.",
        )
        errors, _ = validate(skill, "agentskills")
        self.assertTrue(any("match directory" in error for error in errors))

    def test_portable_requires_name_and_description(self):
        skill = self.make_skill("empty", "license: MIT")
        errors, _ = validate(skill, "agentskills")
        self.assertTrue(any("requires `name`" in error for error in errors))
        self.assertTrue(any("requires a non-empty `description`" in error for error in errors))

    def test_claude_accepts_current_background_and_boolean_aliases(self):
        skill = self.make_skill(
            "deploy",
            "name: deploy\ndescription: Deploys on explicit request.\n"
            "disable-model-invocation: yes\ncontext: fork\nbackground: no",
            "## Task\n\n1. Run git push after approval.",
        )
        errors, warnings = validate(skill)
        self.assertEqual(errors, [])
        self.assertFalse(any("side-effect" in warning for warning in warnings))

    def test_invalid_boolean_fails(self):
        skill = self.make_skill(
            "deploy",
            "name: deploy\ndescription: Deploys on explicit request.\nbackground: sometimes",
        )
        errors, _ = validate(skill)
        self.assertTrue(any("recognized boolean" in error for error in errors))

    def test_named_argument_counts_as_consumed(self):
        skill = self.make_skill(
            "fix-issue",
            "name: fix-issue\ndescription: Fixes an issue.\n"
            "argument-hint: '[issue]'\narguments: issue",
            "Fix issue $issue.",
        )
        _, warnings = validate(skill)
        self.assertFalse(any("does not consume" in warning for warning in warnings))

    def test_unused_argument_hint_warns(self):
        skill = self.make_skill(
            "fix-issue",
            "name: fix-issue\ndescription: Fixes an issue.\nargument-hint: '[issue]'",
        )
        _, warnings = validate(skill)
        self.assertTrue(any("does not consume" in warning for warning in warnings))

    def test_duplicate_frontmatter_key_fails(self):
        _, _, error = parse_frontmatter(
            "---\nname: first\nname: second\ndescription: Duplicate.\n---\nBody\n"
        )
        self.assertIn("duplicate", error)

    def test_ungated_side_effect_warns(self):
        skill = self.make_skill(
            "ship",
            "name: ship\ndescription: Ships a release.",
            "1. Run git push origin main.",
        )
        _, warnings = validate(skill)
        self.assertTrue(any("ungated side-effect" in warning for warning in warnings))

    def test_gated_or_explanatory_side_effect_does_not_warn(self):
        skill = self.make_skill(
            "ship",
            "name: ship\ndescription: Reviews a release workflow.",
            "Anything that changes external state, such as `git push`, requires confirmation.",
        )
        _, warnings = validate(skill)
        self.assertFalse(any("side-effect" in warning for warning in warnings))

    def test_dynamic_command_rejects_argument_interpolation(self):
        skill = self.make_skill(
            "lookup",
            "name: lookup\ndescription: Looks up a user-provided item.\nargument-hint: '[query]'",
            "!`tool lookup $ARGUMENTS`\n\nSummarize the result.",
        )
        errors, _ = validate(skill)
        self.assertTrue(any("interpolates skill arguments" in error for error in errors))

    def test_dynamic_command_allows_environment_variable(self):
        skill = self.make_skill(
            "environment",
            "name: environment\ndescription: Reports the current environment.",
            "!`printf $SHELL`\n\nReport the configured shell.",
        )
        errors, _ = validate(skill)
        self.assertFalse(any("interpolates skill arguments" in error for error in errors))

    def test_dynamic_command_rejects_side_effect(self):
        skill = self.make_skill(
            "ship",
            "name: ship\ndescription: Ships a release.",
            "!`git push origin main`",
        )
        errors, _ = validate(skill)
        self.assertTrue(any("dynamic command injection performs" in error for error in errors))

    def test_relative_link_has_positive_and_negative_controls(self):
        skill = self.make_skill(
            "guide",
            "name: guide\ndescription: Loads a guide when requested.",
            "Read [the guide](references/guide.md).",
        )
        reference = skill / "references"
        reference.mkdir()
        (reference / "guide.md").write_text("# Guide\n", encoding="utf-8")
        errors, _ = validate(skill)
        self.assertFalse(any("broken relative link" in error for error in errors))
        (reference / "guide.md").unlink()
        errors, _ = validate(skill)
        self.assertTrue(any("broken relative link" in error for error in errors))

    def test_credential_detector_has_positive_and_negative_controls(self):
        skill = self.make_skill(
            "secrets",
            "name: secrets\ndescription: Documents credential handling.",
            "Never include tokens such as ghp_EXAMPLE.",
        )
        errors, _ = validate(skill)
        self.assertFalse(any("credential" in error for error in errors))
        (skill / "SKILL.md").write_text(
            "---\nname: secrets\ndescription: Bad fixture.\n---\n"
            "ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ\n",
            encoding="utf-8",
        )
        errors, _ = validate(skill)
        self.assertTrue(any("credential" in error for error in errors))

class SideEffectDetectionTests(unittest.TestCase):
    """Regressions from a review of the v0.2 hardening. Each of these returned
    the wrong answer on the branch as submitted."""

    def test_a_backticked_command_is_detected(self):
        """The single most common way a skill writes a command. Backticks
        survived the prefix strip, so the anchored match never saw the command
        and every one of these read as clean."""
        self.assertEqual(
            validate_skill.executable_side_effects("run `git push origin main`"),
            ["git push"],
        )

    def test_a_mid_sentence_command_is_detected(self):
        """re.match anchored at line start, so prose around the command hid it."""
        self.assertEqual(
            validate_skill.executable_side_effects(
                "Then run `git push origin main` to publish the release."
            ),
            ["git push"],
        )

    def test_a_bulleted_backticked_command_is_detected(self):
        self.assertEqual(
            validate_skill.executable_side_effects("- run `rm -rf build`"),
            ["rm -r"],
        )

    def test_a_negation_still_suppresses_its_own_command(self):
        for body in ("Do not run git push origin main.", "Don't run `rm -rf build`."):
            self.assertEqual(validate_skill.executable_side_effects(body), [], body)

    def test_a_negation_about_something_else_does_not_suppress(self):
        """The old check killed the whole line on any negation in it, so
        "Never skip this: ..." disarmed the command after the colon. The
        negation governs the clause it is in."""
        self.assertEqual(
            validate_skill.executable_side_effects("Never skip this: run git push origin main."),
            ["git push"],
        )


class GateScopeTests(unittest.TestCase):
    def test_a_gate_on_an_unrelated_step_does_not_disarm_the_warning(self):
        """GATE_RE.search(body) was body-global: one "Confirm" anywhere bought a
        free pass for every ungated command in the document."""
        body = "1. Confirm the tests pass.\n2. Run git push origin main.\n3. Run rm -rf build."
        self.assertEqual(validate_skill.ungated_side_effects(body), ["git push", "rm -r"])

    def test_a_gate_in_the_same_step_does_disarm_it(self):
        body = "1. Confirm with the user, then run git push origin main."
        self.assertEqual(validate_skill.ungated_side_effects(body), [])

    def test_each_step_is_judged_on_its_own_gate(self):
        body = (
            "1. Ask for approval, then run `git push origin main`.\n"
            "2. Run `rm -rf build`.\n"
        )
        self.assertEqual(validate_skill.ungated_side_effects(body), ["rm -r"])


class VersionKeyTests(unittest.TestCase):
    def test_version_is_accepted_under_both_profiles(self):
        """`version` was in the pre-refactor KNOWN_KEYS. Dropping it turned an
        optional portable field into a warning under claude-code and a hard
        error (exit 1) under agentskills, breaking CI for any skill carrying
        it -- with no changelog entry."""
        self.assertIn("version", validate_skill.CLAUDE_KEYS)
        self.assertIn("version", validate_skill.AGENT_SKILLS_KEYS)


if __name__ == "__main__":
    unittest.main()
