# Frame spec for the agent-skill-builder demo GIF.
# Rendered by scripts/render_demo.py (canonical path: demo.tape via vhs).
#
# Output shown is REAL: captured from
#   python3 scripts/validate_skill.py examples/tool-using examples/minimal   (PASS)
#   python3 scripts/validate_skill.py <a broken skill dir>                   (FAIL)
# The broken skill (unscoped Bash grant + a broken relative link) is created in
# a temp dir only to capture output; it is not committed.

TITLE = "agent-skill-builder — validate_skill.py"

FRAMES = [
    ("out", [
        [("# The validator turns the skill-quality checklist into machine checks.", "dim")],
        [("# Green means ship it. Red means fix it before a session ever loads it.", "dim")],
    ], 1700),

    ("cmd", "python3 scripts/validate_skill.py examples/tool-using examples/minimal"),
    ("out", [
        "",
        [("examples/tool-using: ", "fg"), ("PASS", "green")],
        [("  warning: frontmatter name `commit` != directory `tool-using` — the "
          "directory name is the command; `name` is only a display label (fine "
          "if intentional)", "yellow")],
        "",
        [("examples/minimal: ", "fg"), ("PASS", "green")],
        [("  warning: frontmatter name `summarize-changes` != directory `minimal` "
          "— the directory name is the command; `name` is only a display label "
          "(fine if intentional)", "yellow")],
    ], 900),
    ("out", [
        "",
        [("$ echo $?  ", "dim"), ("0", "green"), ("   # CI-friendly: warnings pass, "
         "the exit code is clean", "dim")],
    ], 2400),

    ("clear",),
    ("out", [
        [("# Now a deliberately broken skill: an unscoped Bash grant and a dead link.", "dim")],
    ], 1500),
    ("cmd", "python3 scripts/validate_skill.py /tmp/bad-skill"),
    ("out", [
        "",
        [("/tmp/bad-skill: ", "fg"), ("FAIL", "red")],
        [("  ERROR: broken relative link: references/missing.md", "red")],
        [("  warning: frontmatter name `bad-example` != directory `bad-skill` — "
          "the directory name is the command; `name` is only a display label "
          "(fine if intentional)", "yellow")],
        [("  warning: `allowed-tools` grants unscoped `Bash` — scope it, e.g. "
          "Bash(git add *)", "yellow")],
    ], 900),
    ("out", [
        "",
        [("$ echo $?  ", "dim"), ("1", "red"), ("   # exit 1 blocks the commit — the "
         "broken link is a hard error", "dim")],
    ], 2600),
]
