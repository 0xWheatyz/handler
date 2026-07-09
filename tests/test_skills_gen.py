"""Role-based forge skills generation (committed into the managed repo)."""

from __future__ import annotations

from handler.control import skills_gen


def test_skill_files_cover_every_role():
    files = skills_gen.skill_files()
    paths = set(files)
    for role in ("forge-workflow", "forge-junior", "forge-senior", "forge-deploy"):
        assert f".claude/skills/{role}/SKILL.md" in paths


def test_skill_files_have_frontmatter():
    for _, contents in skills_gen.skill_files().items():
        assert contents.startswith("---\nname: ")
        assert "description:" in contents


def test_senior_skill_references_the_approval_command():
    senior = skills_gen.skill_files()[".claude/skills/forge-senior/SKILL.md"]
    assert "handler approve" in senior
    assert "handler reject" in senior


def test_write_skills_materializes_files(tmp_path):
    written = skills_gen.write_skills(str(tmp_path))
    assert len(written) == 4
    junior = tmp_path / ".claude" / "skills" / "forge-junior" / "SKILL.md"
    assert junior.exists()
    assert "junior developer" in junior.read_text()
