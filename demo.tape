# demo.tape — canonical vhs recording script for docs/demo.gif
#
# Regenerate with vhs (https://github.com/charmbracelet/vhs):
#     vhs demo.tape
#
# vhs runs the commands in a real shell, so the PASS/FAIL output is captured
# live. If vhs/ttyd/ffmpeg are unavailable, use the Pillow fallback renderer,
# which bakes in the same captured output:
#     python3 scripts/render_demo.py      # -> docs/demo.gif
# Verify theme names with `vhs themes | grep -i dracula` before rendering.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 420
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 45ms

# --- Beat 1: two valid example skills pass -----------------------------------
Type "python3 scripts/validate_skill.py examples/tool-using examples/minimal"
Enter
Sleep 2s

Type "echo $?"
Enter
Sleep 2s

# --- Beat 2: a deliberately broken skill fails -------------------------------
# Unscoped Bash grant + a dead relative link -> ERROR + warnings, exit 1.
Type "mkdir -p /tmp/bad-skill"
Enter
Type `printf -- '---\nname: bad-example\ndescription: Does stuff with things and processes the data and reports it back to you in a nice format for review later on.\nallowed-tools: Bash, Read\n---\n\n# Bad Example\n\nSee [the reference](references/missing.md) for details.\n' > /tmp/bad-skill/SKILL.md`
Enter
Sleep 500ms

Type "python3 scripts/validate_skill.py /tmp/bad-skill"
Enter
Sleep 2s

Type "echo $?"
Enter
Sleep 3s
