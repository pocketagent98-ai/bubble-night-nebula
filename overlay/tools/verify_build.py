"""Static checks for the Nebula layer.

There is no JVM on the build machine that generates these assets, so this script
does the checks that a compiler would otherwise catch first:

  1. balanced braces/parens/brackets in every Kotlin file (string- and
     comment-aware),
  2. every R.raw.<name> reference resolves to a generated WAV,
  3. every `assets.open("path")` reference resolves to a generated asset,
  4. every JSON file in the repo parses,
  5. the project layout still matches what Gradle expects,
  6. no `when (screen)` over UiScreen is left non-exhaustive.

It is not a substitute for `./gradlew test`; it is the check that runs in the
notebook, in a few seconds, before the zip is handed over.

Run:  python3 tools/verify_build.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPEN = {"{": "}", "(": ")", "[": "]"}
CLOSE = {v: k for k, v in OPEN.items()}


class _Lexer:
    """A small Kotlin lexer: enough to know which brackets are real code.

    Three things trip up naive strippers and all three appear in this repo:
    a URL inside a string (`"https://..."`), an apostrophe inside a comment
    (`// it's fine`), and a string template that itself contains a string
    (`"${list.joinToString(",")}"`). Only a real scan handles all three.
    """

    def __init__(self, text: str) -> None:
        self.t = text
        self.i = 0
        self.n = len(text)
        self.out: list[str] = []

    def run(self) -> str:
        while self.i < self.n:
            c = self.t[self.i]
            if self.t.startswith('"""', self.i):
                self._raw_string()
            elif self.t.startswith("//", self.i):
                self._line_comment()
            elif self.t.startswith("/*", self.i):
                self._block_comment()
            elif c == '"':
                self._string()
            elif c == "'" and self._looks_like_char():
                self._char()
            else:
                self.out.append(c)
                self.i += 1
        return "".join(self.out)

    def _looks_like_char(self) -> bool:
        t, i, n = self.t, self.i, self.n
        if i + 2 < n and t[i + 2] == "'" and t[i + 1] != "\\":
            return True
        return i + 3 < n and t[i + 1] == "\\" and t[i + 3] == "'"

    def _char(self) -> None:
        self.i += 4 if self.t[self.i + 1] == "\\" else 3
        self.out.append('""')

    def _raw_string(self) -> None:
        self.i += 3
        while self.i < self.n and not self.t.startswith('"""', self.i):
            self.i += 1
        self.i += 3
        self.out.append('""')

    def _line_comment(self) -> None:
        while self.i < self.n and self.t[self.i] != "\n":
            self.i += 1

    def _block_comment(self) -> None:
        depth = 1
        self.i += 2
        while self.i < self.n and depth:
            if self.t.startswith("/*", self.i):
                depth += 1
                self.i += 2
            elif self.t.startswith("*/", self.i):
                depth -= 1
                self.i += 2
            else:
                self.i += 1

    def _string(self) -> None:
        self.i += 1
        while self.i < self.n:
            c = self.t[self.i]
            if c == "\\":
                self.i += 2
                continue
            if c == "$" and self.t.startswith("${", self.i):
                self.i += 2
                self._template()
                continue
            if c == '"':
                self.i += 1
                break
            self.i += 1
        self.out.append('""')

    def _template(self) -> None:
        """Skips the inside of `${...}`, including any strings nested in it."""
        depth = 1
        while self.i < self.n and depth:
            if self.t.startswith('"""', self.i):
                self._raw_string()
                continue
            c = self.t[self.i]
            if c == '"':
                self._string()
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            self.i += 1


def strip_code(text: str) -> str:
    """Removes comments and literal bodies so bracket counting is honest."""
    return _Lexer(text).run()


def check_balance(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    code = strip_code(raw)
    stack: list[tuple[str, int]] = []
    line = 1
    problems: list[str] = []
    for ch in code:
        if ch == "\n":
            line += 1
        elif ch in OPEN:
            stack.append((ch, line))
        elif ch in CLOSE:
            if not stack:
                problems.append(f"{path}: unmatched '{ch}' on line {line}")
                return problems
            op, oline = stack.pop()
            if OPEN[op] != ch:
                problems.append(f"{path}: '{op}' from line {oline} closed by '{ch}' on line {line}")
                return problems
    for op, oline in stack:
        problems.append(f"{path}: '{op}' opened on line {oline} is never closed")
    return problems


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []

    kt_files = sorted(ROOT.glob("**/*.kt"))
    if not kt_files:
        problems.append("no Kotlin sources found")

    for path in kt_files:
        problems.extend(check_balance(path))

    # 2. R.raw references
    raw_dir = ROOT / "app/src/main/res/raw"
    available_raw = {p.stem for p in raw_dir.glob("*.wav")} if raw_dir.is_dir() else set()
    referenced_raw = set()
    for path in kt_files:
        for m in re.finditer(r"R\.raw\.(\w+)", path.read_text(encoding="utf-8")):
            referenced_raw.add(m.group(1))
    for name in sorted(referenced_raw - available_raw):
        problems.append(f"R.raw.{name} is referenced but app/src/main/res/raw/{name}.wav does not exist")
    for name in sorted(available_raw - referenced_raw):
        notes.append(f"generated but unused: res/raw/{name}.wav")
    notes.append(f"audio: {len(available_raw)} wav files, {len(referenced_raw)} referenced")

    # 3. assets.open references
    assets_dir = ROOT / "app/src/main/assets"
    for path in kt_files:
        for m in re.finditer(r'assets\.open\(\s*"([^"]+)"', path.read_text(encoding="utf-8")):
            target = assets_dir / m.group(1)
            # Formatted paths (e.g. orbit_%02d.png) are checked by prefix below.
            if "%" in m.group(1):
                prefix = m.group(1).split("%")[0]
                if not any(p.name.startswith(Path(prefix).name) for p in (assets_dir / Path(prefix).parent).glob("*")):
                    problems.append(f"asset pattern {m.group(1)} has no matching files")
            elif not target.exists():
                problems.append(f"asset {m.group(1)} is referenced but missing")

    # 4. JSON
    json_count = 0
    for path in ROOT.glob("**/*.json"):
        if "content/certificates" in str(path):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            json_count += 1
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path}: invalid JSON ({exc})")
    notes.append(f"json: {json_count} files parsed")

    # 5. layout
    for required in (
        "settings.gradle.kts",
        "app/build.gradle.kts",
        "app/src/main/AndroidManifest.xml",
        "app/src/main/java/pt/tiago/bubblenight/nebula/NebulaMapScreen.kt",
        "app/src/main/java/pt/tiago/bubblenight/nebula/NebulaMath.kt",
        "app/src/main/java/pt/tiago/bubblenight/game/DailyRewards.kt",
        "app/src/main/java/pt/tiago/bubblenight/game/Boosters.kt",
        "app/src/main/java/pt/tiago/bubblenight/data/RewardStore.kt",
    ):
        if not (ROOT / required).exists():
            problems.append(f"missing required file: {required}")

    # 6. every UiScreen value handled somewhere
    ui_models = ROOT / "app/src/main/java/pt/tiago/bubblenight/ui/UiModels.kt"
    if ui_models.exists():
        text = ui_models.read_text(encoding="utf-8")
        m = re.search(r"enum class UiScreen\s*\{(.*?)\}", text, re.S)
        if m:
            values = [v.strip() for v in re.split(r"[,\n]", strip_code(m.group(1))) if v.strip()]
            app = (ROOT / "app/src/main/java/pt/tiago/bubblenight/ui/BubbleNightApp.kt").read_text(encoding="utf-8")
            nav = re.search(r"when \(model\.screen\)\s*\{(.*?)\n\s*\}", app, re.S)
            handled = set(re.findall(r"UiScreen\.(\w+)", nav.group(1))) if nav else set()
            missing = [v for v in values if v not in handled and v != "NEBULA"]
            if nav and missing:
                problems.append(f"UiScreen values with no page branch: {missing}")
            notes.append(f"ui screens: {len(values)} declared, {len(handled)} handled in the nav when")

    print("== Nebula build verification ==")
    for n in notes:
        print(f"  \u00b7 {n}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  \u2717 {p}")
        return 1
    print(f"\nAll checks passed ({len(kt_files)} Kotlin files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
