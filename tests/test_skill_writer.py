from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import skill_writer  # noqa: E402
import version_manager  # noqa: E402
from skill_presets import (  # noqa: E402
    get_character_preset,
    get_research_profile_preset,
    resolve_existing_storage_root,
)


class SkillWriterTest(unittest.TestCase):
    def test_create_colleague_keeps_legacy_names_and_adds_engine_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "colleague"
            meta = {
                "name": "Eulalie",
                "profile": {
                    "company": "ByteDance",
                    "level": "L2-1",
                    "role": "Backend Engineer",
                    "mbti": "INTJ",
                },
                "tags": {
                    "personality": ["direct", "data-driven"],
                    "culture": ["byte-dance-style"],
                },
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "zhangsan",
                meta,
                "Work body",
                "Persona body",
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            combined_skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            work_skill = (skill_dir / "work_skill.md").read_text(encoding="utf-8")
            persona_skill = (skill_dir / "persona_skill.md").read_text(encoding="utf-8")

            self.assertEqual(saved_meta["schema_version"], "3")
            self.assertEqual(saved_meta["kind"], "meta-skill")
            self.assertEqual(saved_meta["character"], "colleague")
            self.assertEqual(saved_meta["preset"], "dot.colleague.v1")
            self.assertEqual(saved_meta["type"], "colleague")
            self.assertEqual(saved_meta["id"], "meta-skill.colleague.zhangsan")
            self.assertEqual(saved_meta["artifacts"]["combined_name"], "colleague_zhangsan")
            self.assertEqual(saved_meta["artifacts"]["combined_command"], "colleague-zhangsan")
            self.assertEqual(saved_meta["compat"]["legacy_command"], "/create-colleague")
            self.assertEqual(manifest["kind"], "meta-skill")
            self.assertEqual(manifest["character"], "colleague")
            self.assertEqual(manifest["preset"], "dot.colleague.v1")
            self.assertEqual(manifest["install"]["slash_commands"]["default"], "colleague-zhangsan")
            self.assertEqual(
                manifest["install"]["compatible_runtimes"],
                ["claude-code", "openclaw", "hermes", "codex"],
            )
            self.assertEqual(
                manifest["install"]["installers"]["openclaw"],
                "tools/install_openclaw_generated_skill.py",
            )
            self.assertEqual(
                manifest["install"]["installers"]["codex"],
                "tools/install_codex_generated_skill.py",
            )
            self.assertIn("name: colleague_zhangsan", combined_skill)
            self.assertIn("## PART A: Work", combined_skill)
            self.assertIn("name: colleague_zhangsan_work", work_skill)
            self.assertIn("work capability only", work_skill)
            self.assertIn("name: colleague_zhangsan_persona", persona_skill)
            self.assertIn("persona only", persona_skill)

    def test_create_relationship_uses_character_preset_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "relationship"
            meta = {
                "character": "relationship",
                "name": "Mireille",
                "profile": {
                    "role": "Designer",
                },
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "mireille",
                meta,
                "Work body",
                "Persona body",
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            combined_skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

            self.assertEqual(saved_meta["kind"], "meta-skill")
            self.assertEqual(saved_meta["character"], "relationship")
            self.assertEqual(saved_meta["preset"], "dot.relationship.v1")
            self.assertEqual(saved_meta["type"], "relationship")
            self.assertEqual(saved_meta["classification"]["gallery_category"], "Relationship")
            self.assertEqual(saved_meta["compat"]["legacy_storage_root"], "skills/relationship")
            self.assertEqual(manifest["id"], "meta-skill.relationship.mireille")
            self.assertEqual(manifest["character"], "relationship")
            self.assertEqual(saved_meta["artifacts"]["combined_command"], "relationship-mireille")
            self.assertIn("name: relationship_mireille", combined_skill)

    def test_create_skill_renders_english_chrome_when_language_is_zh_cn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "relationship"
            meta = {
                "character": "relationship",
                "name": "Mireille",
                "classification": {
                    "language": "zh-CN",
                },
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "mireille",
                meta,
                "Work body",
                "Persona body",
            )

            combined_skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            work_skill = (skill_dir / "work_skill.md").read_text(encoding="utf-8")
            persona_skill = (skill_dir / "persona_skill.md").read_text(encoding="utf-8")

            self.assertIn("## PART A: Work", combined_skill)
            self.assertIn("## Operating Rules", combined_skill)
            self.assertIn("work capability only", work_skill)
            self.assertIn("persona only", persona_skill)

    def test_create_celebrity_adds_research_dirs_and_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "celebrity"
            meta = {
                "character": "celebrity",
                "name": "Zadie Smith",
                "profile": {
                    "identity": "Novelist",
                    "known_for": "Essay and criticism",
                },
                "tags": ["literature", "essay", "public-intellectual"],
                "knowledge_sources": ["interview", "essay"],
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "zadie_smith",
                meta,
                "Work body",
                "Persona body",
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_meta["character"], "celebrity")
            self.assertEqual(saved_meta["preset"], "dot.celebrity.v1")
            self.assertEqual(saved_meta["research_profile"], "budget-friendly")
            self.assertIn("research_tools", saved_meta["engine"])
            self.assertEqual(saved_meta["engine"]["research_profile"], "budget-friendly")
            self.assertIn("research_tools", manifest["toolchain"])
            self.assertEqual(manifest["research_profile"], "budget-friendly")
            self.assertEqual(
                saved_meta["classification"]["tags"],
                ["literature", "essay", "public-intellectual"],
            )
            self.assertIn("Novelist", saved_meta["summary"])
            self.assertIn("Essay and criticism", saved_meta["summary"])
            self.assertTrue((skill_dir / "knowledge" / "research" / "raw").exists())
            self.assertTrue((skill_dir / "knowledge" / "research" / "merged").exists())
            self.assertTrue((skill_dir / "knowledge" / "transcripts").exists())
            self.assertTrue((skill_dir / "knowledge" / "subtitles").exists())

    def test_create_celebrity_budget_unfriendly_embeds_profile_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "celebrity"
            meta = {
                "character": "celebrity",
                "research_profile": "budget-unfriendly",
                "name": "Xu Zhisheng",
                "classification": {"language": "zh-CN"},
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "xu_zhisheng",
                meta,
                "Work body",
                "Persona body",
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(saved_meta["research_profile"], "budget-unfriendly")
            self.assertEqual(saved_meta["engine"]["quality_profile"], "budget-unfriendly")
            self.assertIn(
                "prompts/celebrity/budget_unfriendly/research.md",
                saved_meta["engine"]["research_profile_bundle"].values(),
            )
            self.assertIn(
                "prompts/celebrity/budget_unfriendly/audit.md",
                saved_meta["engine"]["research_profile_bundle"].values(),
            )
            self.assertIn(
                "references/celebrity_budget_unfriendly_framework.md",
                saved_meta["engine"]["research_profile_references"],
            )
            self.assertEqual(manifest["research_profile"], "budget-unfriendly")
            self.assertEqual(manifest["toolchain"]["quality_profile"], "budget-unfriendly")
            self.assertEqual(manifest["toolchain"]["merge_strategy"], "deep")

    def test_create_celebrity_accepts_string_profile_from_runtime_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "celebrity"
            meta = {
                "character": "celebrity",
                "name": "Xu Zhisheng",
                "display_name": "Xu Zhisheng",
                "classification": {"language": "zh-CN"},
                "profile": "Chinese stand-up comedian known for self-deprecating observational comedy.",
            }

            skill_dir = skill_writer.create_skill(
                base_dir,
                "xu_zhisheng",
                meta,
                "Work body",
                "Persona body",
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(
                saved_meta["profile"],
                "Chinese stand-up comedian known for self-deprecating observational comedy.",
            )
            self.assertIn("Chinese stand-up comedian", saved_meta["summary"])

    def test_update_regenerates_manifest_and_archives_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "colleague"
            skill_dir = skill_writer.create_skill(
                base_dir,
                "zhangsan",
                {"name": "Eulalie"},
                "Initial work",
                "Initial persona",
            )

            new_version = skill_writer.update_skill(
                skill_dir,
                work_patch="More work",
                correction={"scene": "challenged", "wrong": "apologize", "correct": "ask for evidence"},
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            archived_manifest = skill_dir / "versions" / "v1" / "manifest.json"
            persona_doc = (skill_dir / "persona.md").read_text(encoding="utf-8")

            self.assertEqual(new_version, "v2")
            self.assertEqual(saved_meta["version"], "v2")
            self.assertEqual(saved_meta["corrections_count"], 1)
            self.assertTrue(archived_manifest.exists())
            self.assertEqual(manifest["entrypoints"]["default"], "SKILL.md")
            self.assertIn("apologize", persona_doc)
            self.assertIn("ask for evidence", persona_doc)

    def test_update_accepts_multiple_persona_corrections_in_one_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "celebrity"
            skill_dir = skill_writer.create_skill(
                base_dir,
                "zhou-qimo",
                {
                    "character": "celebrity",
                    "name": "Zhou Qimo",
                    "classification": {"language": "zh-CN"},
                },
                "Initial work",
                "Initial persona",
            )

            new_version = skill_writer.update_skill(
                skill_dir,
                correction={
                    "persona_corrections": [
                        {
                            "scene": "setting up a situation",
                            "wrong": "judges immediately",
                            "correct": "first makes the situation feel ordinary, then lightly points at the absurdity",
                        },
                        {
                            "scene": "stating a position",
                            "wrong": "turns it into obvious self-mockery",
                            "correct": "admits together with the audience that everyone is inside the situation",
                        },
                    ]
                },
            )

            saved_meta = json.loads((skill_dir / "meta.json").read_text(encoding="utf-8"))
            persona_doc = (skill_dir / "persona.md").read_text(encoding="utf-8")

            self.assertEqual(new_version, "v2")
            self.assertEqual(saved_meta["corrections_count"], 2)
            self.assertIn("judges immediately", persona_doc)
            self.assertIn("obvious self-mockery", persona_doc)
            self.assertEqual(persona_doc.count("## Correction Log"), 1)

    def test_update_replaces_existing_markdown_sections_instead_of_appending_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "celebrity"
            skill_dir = skill_writer.create_skill(
                base_dir,
                "zhou-qimo",
                {
                    "character": "celebrity",
                    "name": "Zhou Qimo",
                    "classification": {"language": "zh-CN"},
                },
                "\n".join(
                    [
                        "# Work",
                        "",
                        "## Expression Standards",
                        "",
                        "- Original phrasing",
                        "",
                        "## Output Style",
                        "",
                        "- Original structure",
                    ]
                ),
                "\n".join(
                    [
                        "# Persona",
                        "",
                        "## Layer 2: Expression DNA",
                        "",
                        "Old content",
                        "",
                        "## Layer 3: Mental Models",
                        "",
                        "Keep unchanged",
                    ]
                ),
            )

            skill_writer.update_skill(
                skill_dir,
                work_patch="\n".join(
                    [
                        "## Expression Standards",
                        "",
                        "- New rhythm control",
                        "",
                        "## Output Style",
                        "",
                        "- New structure template",
                    ]
                ),
                persona_patch="\n".join(
                    [
                        "## Layer 2: Expression DNA",
                        "",
                        "New content",
                    ]
                ),
            )

            work_doc = (skill_dir / "work.md").read_text(encoding="utf-8")
            persona_doc = (skill_dir / "persona.md").read_text(encoding="utf-8")

            self.assertEqual(work_doc.count("## Expression Standards"), 1)
            self.assertEqual(work_doc.count("## Output Style"), 1)
            self.assertIn("New rhythm control", work_doc)
            self.assertNotIn("Original phrasing", work_doc)
            self.assertEqual(persona_doc.count("## Layer 2: Expression DNA"), 1)
            self.assertIn("New content", persona_doc)
            self.assertNotIn("Old content", persona_doc)


class VersionManagerTest(unittest.TestCase):
    def test_backup_and_rollback_include_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "skills" / "colleague"
            skill_dir = skill_writer.create_skill(
                base_dir,
                "zhangsan",
                {"name": "Eulalie"},
                "v1 work",
                "v1 persona",
            )

            version_manager.backup_current_version(skill_dir)
            skill_writer.update_skill(skill_dir, work_patch="v2 work")

            success = version_manager.rollback(skill_dir, "v1")
            restored_work = (skill_dir / "work.md").read_text(encoding="utf-8")

            self.assertTrue(success)
            self.assertIn("v1 work", restored_work)
            self.assertTrue((skill_dir / "versions" / "v1" / "manifest.json").exists())

    def test_version_manager_can_still_resolve_legacy_colleagues_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path.cwd()
            try:
                os.chdir(tmp_dir)
                legacy_base_dir = Path("colleagues")
                skill_writer.create_skill(
                    legacy_base_dir,
                    "zhangsan",
                    {"name": "Eulalie"},
                    "v1 work",
                    "v1 persona",
                )

                resolved = resolve_existing_storage_root("colleague", slug="zhangsan")
                self.assertEqual(resolved, Path("colleagues"))
            finally:
                os.chdir(cwd)


class PromptPresetTest(unittest.TestCase):
    def test_character_prompt_bundles_exist(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        for character in ("colleague", "relationship", "celebrity"):
            preset = get_character_preset(character)
            for prompt_path in preset["prompt_bundle"].values():
                if not isinstance(prompt_path, str) or not prompt_path.startswith("prompts/"):
                    continue
                self.assertTrue(
                    (project_root / prompt_path).exists(),
                    f"missing prompt file for {character}: {prompt_path}",
                )
            for tool_path in preset.get("research_tools", {}).values():
                self.assertTrue(
                    (project_root / tool_path).exists(),
                    f"missing research tool for {character}: {tool_path}",
                )
            for profile_name in preset.get("research_profiles", {}):
                profile = get_research_profile_preset(character, profile_name)
                for prompt_path in profile.get("prompt_bundle", {}).values():
                    if not isinstance(prompt_path, str) or not prompt_path.startswith("prompts/"):
                        continue
                    self.assertTrue(
                        (project_root / prompt_path).exists(),
                        f"missing profile prompt file for {character}/{profile_name}: {prompt_path}",
                    )
                for reference_path in profile.get("references", []):
                    self.assertTrue(
                        (project_root / reference_path).exists(),
                        f"missing profile reference for {character}/{profile_name}: {reference_path}",
                    )

        friendly_prompt = (project_root / "prompts" / "celebrity" / "research.md").read_text(encoding="utf-8")
        self.assertIn("01_core_profile.md", friendly_prompt)
        self.assertIn("03_expression_and_reception.md", friendly_prompt)
        self.assertIn(
            "do not collapse the whole pass into one monolithic note",
            friendly_prompt.lower(),
        )
        self.assertIn("actual inspected pages", friendly_prompt)

        strict_prompt = (
            project_root
            / "prompts"
            / "celebrity"
            / "budget_unfriendly"
            / "research.md"
        ).read_text(encoding="utf-8")
        self.assertIn("01_writings.md", strict_prompt)
        self.assertIn("06_timeline.md", strict_prompt)
        self.assertIn("at least 8 grounded source URLs", strict_prompt)
        self.assertIn("Do not replace these six files with one merged scratchpad", strict_prompt)
        self.assertIn("actual inspected pages", strict_prompt)


if __name__ == "__main__":
    unittest.main()
